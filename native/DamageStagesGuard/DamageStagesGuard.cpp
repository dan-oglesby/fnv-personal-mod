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
//   In that path JIP LN's GetEntryDataModFlagsHook (patches_game.h) reads the weapon's first
//   item-data record, looks up its "dropped by" record (ExtraItemDropper, type 0x39), and then reads
//   the weapon-mod flags (0x8D) from the DROPPER's item data at dropper+0x44, without checking the
//   dropper still exists. The crash registers prove it: ecx = eax + 0x44 every time (0x00166E55 ->
//   0x00166E99 on 2026-11-18 16:42; 0x0015F954 -> 0x0015F998 at 16:26). The NPC who dropped the
//   weapon is gone (spawn mods such as IWS disable and delete their NPCs), and the weapon's record
//   still points at the freed memory.
//   (The first version of this guard, the same day, checked only the entry's own records, which
//   were fine, and the fourth crash went straight through it.)
//
// The fix: the one call to 0x4BCDB0 in HandleDamageOnLoad (the "mov eax, 0x4BCDB0" at RVA 0x61385)
// is pointed at a wrapper here. It repeats JIP's lookup and checks, under SEH, everything JIP will
// touch: the entry's records are ExtraDataLists (vtable 0x10143E8); the dropper, when there is one,
// is a reference or actor (by its vtable) whose own item data at +0x44 is an ExtraDataList with a
// walkable list. When anything fails it returns 100 (undamaged) instead, so the weapon shows its
// undamaged model rather than crashing the game. Otherwise it calls the game's function exactly as
// before. Skips are counted in DamageStagesGuard.log.
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
static const DWORD kVtblTESObjectREFR = 0x0102F55C;	// JIP LN class_vtbls.h
static const DWORD kVtblCharacter = 0x01086A6C;
static const DWORD kVtblCreature = 0x010870AC;
static const DWORD kVtblPlayerCharacter = 0x0108AA3C;
static const BYTE kXData_ItemDropper = 0x39;
static const BYTE kFormType_Weapon = 0x28;

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

// An item-data list (BaseExtraList: vtable, then the first BSExtraData at +4; each BSExtraData has its
// type at +4 and the next at +8) is sound when its vtable is ExtraDataList's and its chain can be
// walked. Returns the record of `type` (or NULL) through `found`. Called inside __try.
static bool ListSound(BYTE* list, BYTE type, BYTE** found)
{
	if (!list || *(DWORD*)list != kVtblExtraDataList)
		return false;
	BYTE* x = *(BYTE**)(list + 4);
	for (int i = 0; x && i < 256; i++) {
		BYTE t = x[4];					// reads the record: faults on a dead pointer
		if (found && t == type && !*found)
			*found = x;
		x = *(BYTE**)(x + 8);
	}
	return x == NULL;					// a chain that doesn't end within 256 records isn't sound
}

static bool IsRefVtbl(DWORD vt)
{
	return vt == kVtblTESObjectREFR || vt == kVtblCharacter || vt == kVtblCreature || vt == kVtblPlayerCharacter;
}

// Everything JIP LN's GetEntryDataModFlagsHook will touch for this entry, checked first.
static bool EntrySound(BYTE* entry)
{
	if (!entry)
		return true;
	ListNode* node = *(ListNode**)entry;
	for (int i = 0; node && i < 64; i++) {			// every record in the entry's list
		if (node->data && *(DWORD*)node->data != kVtblExtraDataList)
			return false;
		node = node->next;
	}
	BYTE* form = *(BYTE**)(entry + 8);
	if (!form || form[4] != kFormType_Weapon)
		return true;							// JIP's hook returns at once for anything but a weapon
	node = *(ListNode**)entry;
	if (!node || !node->data)
		return true;							// no item data: JIP's hook stops there too
	BYTE* dropperX = NULL;
	if (!ListSound((BYTE*)node->data, kXData_ItemDropper, &dropperX))
		return false;
	if (!dropperX)
		return true;
	BYTE* dropper = *(BYTE**)(dropperX + 0xC);
	if (!dropper)
		return true;
	if (!IsRefVtbl(*(DWORD*)dropper))			// the NPC who dropped it is gone (freed or reused)
		return false;
	return ListSound(dropper + 0x44, 0, NULL);	// and its item data, which JIP reads next
}

static float __fastcall GuardedHealth(void* entry, void* edx, int arg)
{
	bool ok = true;
	__try {
		ok = EntrySound((BYTE*)entry);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		ok = false;
	}
	if (!ok) {
		LONG n = InterlockedIncrement(&g_skipped);
		if (n <= 20) {
			char line[160];
			sprintf_s(line, "skipped a damage-stage check (%ld): a dropped weapon whose item data (or the NPC who dropped it) is gone; shown undamaged instead of crashing", n);
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
