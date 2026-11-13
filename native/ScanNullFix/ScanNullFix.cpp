// Scan Null Fix (Dan, 2026-11-13): an xNVSE plugin that stops reference scans (GetFirstRef /
// GetNextRef, GetNumRefs and the array versions) crashing on a reference with no base form.
//
// The crash: xNVSE 6.4.9's RefMatcherFormType::Accept, RefMatcherActor::Accept and
// RefMatcherItem::Accept (Commands_MiscRef.cpp) read refr->baseForm->typeID without checking
// baseForm. Scans test every reference in the cell, so one reference whose base is gone, such as
// a dropped item just picked up by script, crashes the next scan. Seen three times in a row
// (2026-11-12/13): nvse_1_4.dll+0x36C03, from Auto Loot Enhanced's weapon scan.
//
// The fix: at load, each of the three spots gets a jump to a stub here that does the same load,
// checks the base form, and takes the function's own "no match" exit when it is null. Nothing else
// changes. It patches only the exact build it was written against (xNVSE 6.4.9, PE timestamp
// 0x6AAB0300) and only if every patched byte and every exit is exactly as expected; otherwise it
// patches nothing and says so in ScanNullFix.log next to FalloutNV.exe. Not loaded in the GECK.

#include <windows.h>
#include <stdio.h>

typedef unsigned int UInt32;

struct PluginInfo
{
	enum { kInfoVersion = 1 };
	UInt32 infoVersion;
	const char* name;
	UInt32 version;
};

struct NVSEInterface	// only the leading fields are used
{
	UInt32 nvseVersion;
	UInt32 runtimeVersion;
	UInt32 editorVersion;
	UInt32 isEditor;
};

static const DWORD kExpectedTimestamp = 0x6AAB0300;	// nvse_1_4.dll from xNVSE 6.4.9

// Where each stub returns to: the "no match" exit and the instruction after the patched bytes.
static DWORD g_false0, g_back0, g_false1, g_back1, g_false2, g_back2;

// RefMatcherFormType::Accept: was  mov ecx,[edx+20h] / movzx eax,byte ptr [ecx+4]
__declspec(naked) static void Stub0()
{
	__asm {
		mov ecx, dword ptr [edx + 20h]
		test ecx, ecx
		jnz ok0
		jmp dword ptr [g_false0]
	ok0:
		movzx eax, byte ptr [ecx + 4]
		jmp dword ptr [g_back0]
	}
}

// RefMatcherActor::Accept: was  mov eax,[eax] / mov cl,byte ptr [eax+4]   (eax = &refr->baseForm)
__declspec(naked) static void Stub1()
{
	__asm {
		mov eax, dword ptr [eax]
		test eax, eax
		jnz ok1
		jmp dword ptr [g_false1]
	ok1:
		mov cl, byte ptr [eax + 4]
		jmp dword ptr [g_back1]
	}
}

// RefMatcherItem::Accept: was  mov edx,[ecx+20h] / movzx eax,byte ptr [edx+4]
__declspec(naked) static void Stub2()
{
	__asm {
		mov edx, dword ptr [ecx + 20h]
		test edx, edx
		jnz ok2
		jmp dword ptr [g_false2]
	ok2:
		movzx eax, byte ptr [edx + 4]
		jmp dword ptr [g_back2]
	}
}

struct Site
{
	const char* name;
	DWORD rva;				// patched bytes
	BYTE orig[7];
	int len;
	DWORD falseRva;			// the function's "return false": pop edi / xor al,al / pop esi
	void (*stub)();
	DWORD* falseOut;
	DWORD* backOut;
};

static Site s_sites[] = {
	{ "RefMatcherFormType::Accept", 0x36C00, { 0x8B, 0x4A, 0x20, 0x0F, 0xB6, 0x41, 0x04 }, 7, 0x36CF2, Stub0, &g_false0, &g_back0 },
	{ "RefMatcherActor::Accept",    0x36D22, { 0x8B, 0x00, 0x8A, 0x48, 0x04 },             5, 0x36E17, Stub1, &g_false1, &g_back1 },
	{ "RefMatcherItem::Accept",     0x36E5F, { 0x8B, 0x51, 0x20, 0x0F, 0xB6, 0x42, 0x04 }, 7, 0x36F92, Stub2, &g_false2, &g_back2 },
};
static const BYTE kFalseExit[] = { 0x5F, 0x32, 0xC0, 0x5E };

static FILE* OpenLog()
{
	char path[MAX_PATH];
	DWORD n = GetModuleFileNameA(NULL, path, MAX_PATH);
	while (n && path[n - 1] != '\\') n--;
	path[n] = 0;
	strcat_s(path, "ScanNullFix.log");
	FILE* f = NULL;
	fopen_s(&f, path, "w");
	return f;
}

static void Log(FILE* f, const char* fmt, ...)
{
	if (!f) return;
	va_list args;
	va_start(args, fmt);
	vfprintf(f, fmt, args);
	va_end(args);
	fputc('\n', f);
	fflush(f);
}

static bool ApplyPatches(FILE* log)
{
	HMODULE mod = GetModuleHandleA("nvse_1_4.dll");
	if (!mod) { Log(log, "nvse_1_4.dll is not loaded: nothing patched."); return false; }
	BYTE* base = (BYTE*)mod;

	IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)base;
	IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)(base + dos->e_lfanew);
	DWORD stamp = nt->FileHeader.TimeDateStamp;
	if (stamp != kExpectedTimestamp)
	{
		Log(log, "nvse_1_4.dll timestamp %08X is not xNVSE 6.4.9 (%08X): nothing patched. "
			"This fix needs updating for this xNVSE version (or the new version may already fix it).", stamp, kExpectedTimestamp);
		return false;
	}

	// Check everything before changing anything.
	for (const Site& s : s_sites)
	{
		if (memcmp(base + s.rva, s.orig, s.len) != 0 || memcmp(base + s.falseRva, kFalseExit, sizeof(kFalseExit)) != 0)
		{
			Log(log, "%s: bytes are not as expected (another patch?): nothing patched.", s.name);
			return false;
		}
	}

	for (Site& s : s_sites)
	{
		BYTE* at = base + s.rva;
		*s.falseOut = (DWORD)(base + s.falseRva);
		*s.backOut = (DWORD)(at + s.len);
		DWORD old;
		VirtualProtect(at, s.len, PAGE_EXECUTE_READWRITE, &old);
		at[0] = 0xE9;	// jmp rel32 to the stub
		*(DWORD*)(at + 1) = (DWORD)s.stub - (DWORD)(at + 5);
		for (int i = 5; i < s.len; i++) at[i] = 0x90;	// nop the rest
		VirtualProtect(at, s.len, old, &old);
		FlushInstructionCache(GetCurrentProcess(), at, s.len);
		Log(log, "patched %s at nvse_1_4.dll+%05X", s.name, s.rva);
	}
	Log(log, "Scan Null Fix active: reference scans now skip references with no base form.");
	return true;
}

extern "C" {

__declspec(dllexport) bool NVSEPlugin_Query(const NVSEInterface* nvse, PluginInfo* info)
{
	info->infoVersion = PluginInfo::kInfoVersion;
	info->name = "Scan Null Fix";
	info->version = 1;
	return !nvse->isEditor;
}

__declspec(dllexport) bool NVSEPlugin_Load(const NVSEInterface* nvse)
{
	if (nvse->isEditor)
		return false;
	FILE* log = OpenLog();
	ApplyPatches(log);
	if (log) fclose(log);
	return true;
}

}
