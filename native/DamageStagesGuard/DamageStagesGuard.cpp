// Damage Stages Guard (2026-11-18): an xNVSE plugin that stops a crash in lStewieAl's Tweaks
// (nvse_stewie_tweaks.dll) seen three times in two days (2026-11-16 21:00, 2026-11-18 12:12 and
// 16:26), always on a weapon an NPC dropped (a Pool Cue, a Ripper, a 9mm Submachine Gun; runtime
// "FF" references) just as its model loaded.
//
// What happens (read from Stewie's DLL on disk; the crash logs give the rest):
//   WeaponDamageStagesFix::HandleDamageOnLoad (RVA 0x612D0) builds a temporary inventory entry for
//   the dropped weapon (the game's constructor at 0x4BC550), adds the weapon's own item data to the
//   entry's list of item-data records, and asks the game for the item's condition (0x4BCDB0, a
//   thiscall returning 0-100 as a float; Stewie scales it by 0.1 to pick the damage-stage model).
//   JIP LN's hook in that path walks every record in the list, and one record is not item data at
//   all: the crash is BaseExtraList::GetByType on a pointer such as 0x0E00CE69. The list's first
//   slot evidently isn't always cleared when the entry is made, so a stale value rides along.
//
// The fix: the one call to 0x4BCDB0 in HandleDamageOnLoad (the "mov eax, 0x4BCDB0" at RVA 0x61385)
// is pointed at a wrapper here. It checks each record in the entry's list is an ExtraDataList (its
// vtable, 0x10143E8, read under SEH); when one isn't, it returns 100 (undamaged) instead of letting
// the game walk the bad record, so the weapon simply shows its undamaged model. Otherwise it calls
// the game's function exactly as before. Skips are counted in DamageStagesGuard.log.
//
// It patches only the build it was read from (nvse_stewie_tweaks.dll with PE timestamp 0x6AD667F3)
// and only when every byte it relies on matches; otherwise it changes nothing and says so in
// DamageStagesGuard.log next to FalloutNV.exe. It patches after all plugins have loaded (xNVSE's
// PostPostLoad message), because Stewie's DLL loads after this one. Not loaded in the GECK.

#include <windows.h>
#include <stdio.h>

typedef unsigned int UInt32;
typedef UInt32 PluginHandle;

struct PluginInfo
{
	enum { kInfoVersion = 1 };
	UInt32 infoVersion;
	const char* name;
	UInt32 version;
};

struct NVSEInterface	// the leading fields, as xNVSE's PluginAPI.h lays them out
{
	UInt32 nvseVersion;
	UInt32 runtimeVersion;
	UInt32 editorVersion;
	UInt32 isEditor;
	void* RegisterCommand;
	void* SetOpcodeBase;
	void* (*QueryInterface)(UInt32 id);
	PluginHandle (*GetPluginHandle)(void);
};

struct NVSEMessagingInterface
{
	struct Message { const char* sender; UInt32 type; UInt32 dataLen; void* data; };
	typedef void (*EventCallback)(Message* msg);
	UInt32 version;
	bool (*RegisterListener)(PluginHandle listener, const char* sender, EventCallback handler);
	bool (*Dispatch)(PluginHandle sender, UInt32 messageType, void* data, UInt32 dataLen, const char* receiver);
};

static const UInt32 kRuntime_1_4_0_525 = 0x040020D0;
static const UInt32 kInterface_Messaging = 2;
static const UInt32 kMessage_PostPostLoad = 9;
static const DWORD kStewieTimestamp = 0x6AD667F3;
static const DWORD kSiteRva = 0x61383;			// push 1 / mov eax,0x4BCDB0 / lea ecx,[ebp-20h] / call eax
static const DWORD kFuncRva = 0x612D0;			// WeaponDamageStagesFix::HandleDamageOnLoad
static const DWORD kGameHealth = 0x4BCDB0;		// the item's condition, 0-100 (thiscall, one argument)
static const DWORD kVtblExtraDataList = 0x010143E8;

static char g_logPath[MAX_PATH];
static volatile LONG g_skipped = 0;
static PluginHandle g_handle = 0;

static void Log(const char* text)
{
	FILE* f = NULL;
	if (fopen_s(&f, g_logPath, "a") == 0 && f) {
		fputs(text, f);
		fputs("\n", f);
		fclose(f);
	}
}

struct ListNode { void* data; ListNode* next; };

// Same convention as the game's function (thiscall: ecx = the entry, one stack argument, callee
// pops 4, the float comes back in ST0): __fastcall with an unused edx matches it.
typedef float (__fastcall* HealthFn)(void* entry, void* edx, int arg);

static float __fastcall GuardedHealth(void* entry, void* edx, int arg)
{
	bool ok = true;
	__try {
		ListNode* node = entry ? *(ListNode**)entry : NULL;
		for (int i = 0; node && i < 64; i++) {
			void* xd = node->data;
			if (xd && *(DWORD*)xd != kVtblExtraDataList) {
				ok = false;
				break;
			}
			node = node->next;
		}
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		ok = false;
	}
	if (!ok) {
		LONG n = InterlockedIncrement(&g_skipped);
		if (n <= 20) {
			char line[160];
			sprintf_s(line, "skipped a damage-stage check (%ld): a bad item-data record on a dropped weapon; shown undamaged instead of crashing", n);
			Log(line);
		}
		return 100.0f;
	}
	return ((HealthFn)kGameHealth)(entry, edx, arg);
}

static bool Matches(const BYTE* at, const BYTE* bytes, int len)
{
	__try {
		return memcmp(at, bytes, len) == 0;
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return false;
	}
}

static void Apply()
{
	HMODULE mod = GetModuleHandleA("nvse_stewie_tweaks.dll");
	if (!mod) {
		Log("lStewieAl's Tweaks (nvse_stewie_tweaks.dll) is not loaded: nothing to guard");
		return;
	}
	BYTE* base = (BYTE*)mod;
	IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)(base + ((IMAGE_DOS_HEADER*)base)->e_lfanew);
	if (nt->FileHeader.TimeDateStamp != kStewieTimestamp) {
		char line[160];
		sprintf_s(line, "not patched: nvse_stewie_tweaks.dll is a different build (timestamp %08X, expected %08X)",
			nt->FileHeader.TimeDateStamp, kStewieTimestamp);
		Log(line);
		return;
	}
	static const BYTE site[] = { 0x6A, 0x01, 0xB8, 0xB0, 0xCD, 0x4B, 0x00, 0x8D, 0x4D, 0xE0, 0xFF, 0xD0 };
	static const BYTE func[] = { 0x55, 0x8B, 0xEC, 0x6A, 0xFF, 0x68 };
	if (!Matches(base + kSiteRva, site, sizeof(site)) || !Matches(base + kFuncRva, func, sizeof(func))) {
		Log("not patched: HandleDamageOnLoad is not as expected (another plugin changed it?)");
		return;
	}
	BYTE* imm = base + kSiteRva + 3;			// the 0x4BCDB0 of "mov eax, 0x4BCDB0"
	DWORD old;
	if (!VirtualProtect(imm, 4, PAGE_EXECUTE_READWRITE, &old)) {
		Log("not patched: could not make the call site writable");
		return;
	}
	*(DWORD*)imm = (DWORD)GuardedHealth;
	VirtualProtect(imm, 4, old, &old);
	FlushInstructionCache(GetCurrentProcess(), imm, 4);
	Log("patched: Stewie's WeaponDamageStagesFix now checks a dropped weapon's item-data records first");
}

static void OnMessage(NVSEMessagingInterface::Message* msg)
{
	if (msg && msg->type == kMessage_PostPostLoad)
		Apply();
}

extern "C" {

__declspec(dllexport) bool NVSEPlugin_Query(const NVSEInterface* nvse, PluginInfo* info)
{
	info->infoVersion = PluginInfo::kInfoVersion;
	info->name = "Damage Stages Guard";
	info->version = 1;
	return !nvse->isEditor && nvse->runtimeVersion == kRuntime_1_4_0_525;
}

__declspec(dllexport) bool NVSEPlugin_Load(const NVSEInterface* nvse)
{
	GetModuleFileNameA(NULL, g_logPath, MAX_PATH);
	char* slash = strrchr(g_logPath, '\\');
	strcpy_s(slash ? slash + 1 : g_logPath, MAX_PATH - (slash ? slash + 1 - g_logPath : 0), "DamageStagesGuard.log");
	DeleteFileA(g_logPath);
	g_handle = nvse->GetPluginHandle();
	NVSEMessagingInterface* msg = (NVSEMessagingInterface*)nvse->QueryInterface(kInterface_Messaging);
	if (!msg || !msg->RegisterListener(g_handle, "NVSE", OnMessage)) {
		Log("not patched: xNVSE's messaging interface is unavailable");
		return true;
	}
	return true;
}

}

BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID)
{
	if (reason == DLL_PROCESS_DETACH && g_skipped) {
		char line[128];
		sprintf_s(line, "this session: %ld damage-stage check(s) skipped instead of crashing", g_skipped);
		Log(line);
	}
	return TRUE;
}
