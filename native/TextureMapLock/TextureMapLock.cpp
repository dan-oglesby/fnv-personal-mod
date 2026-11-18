// Texture Map Lock (2026-11-18): an xNVSE plugin for New Vegas's most common crash in this load
// order, FalloutNV.exe+0xA61A74 on the background task thread while a texture loads (10 of the 20
// crash logs on 2026-11-14..17).
//
// What the crash is (read from the running game, docs/engine-crash-research.md):
//   QueuedTexture::Run (0x43C150) -> 0x43C4C0 -> 0x43C4F0 -> 0xA61A60, a lookup in a global hash
//   map (pointer at 0x011F4468: 1001 buckets, key = a pointer, hash (key >> 4) % 1001, values held
//   by reference count). The crash is "cmp edx,[esi+4]" while walking a bucket's chain: a chain node
//   points at an entry that was just freed.
//   Every function that changes that map (0xA61B90, 0xA61C50, 0xA61CD0, 0xA61F30, 0xA61FB0,
//   0xA62030) first takes the engine's spin lock at 0x011F4480. The lookup on the texture thread
//   never does. So the main thread can remove an entry while the texture thread is walking past it.
//
// The fix: the one call at 0x43C4DB (call 0x43C4F0, the lookup) is pointed at a wrapper here that
// takes the same lock, does the same lookup, and releases it. The lock is the engine's own: the
// owning thread's ID at 0x011F4480 (taken with InterlockedCompareExchange) and a re-entry count at
// 0x011F4484 (1 when first taken; released by counting down and clearing the owner), exactly as
// the engine's 0x40FBF0 takes it and 0xA61CB9 releases it.
//
// It never waits forever: if the lock can't be had within kMaxWaitMs the lookup runs unlocked, as
// it always has, so the worst case is today's behaviour, never a freeze. Each such timeout is
// counted in TextureMapLock.log (the first few, then a total when the game closes).
//
// It patches only FalloutNV.exe 1.4.0.525 and only if every byte it relies on is exactly as
// expected (the call site, the lock's users, the lookup); otherwise it patches nothing and says why
// in TextureMapLock.log next to FalloutNV.exe. Not loaded in the GECK.

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

static const UInt32 kRuntime_1_4_0_525 = 0x040020D0;
static const DWORD kCallSite = 0x43C4DB;	// call 0x43C4F0 (the map lookup), inside 0x43C4C0
static const DWORD kLookup = 0x43C4F0;
static volatile LONG* const kLockOwner = (volatile LONG*)0x011F4480;
static volatile LONG* const kLockCount = (volatile LONG*)0x011F4484;
static const DWORD kMaxWaitMs = 50;

static volatile LONG g_timeouts = 0;
static char g_logPath[MAX_PATH];

static void Log(const char* text)
{
	FILE* f = NULL;
	if (fopen_s(&f, g_logPath, "a") == 0 && f) {
		fputs(text, f);
		fputs("\n", f);
		fclose(f);
	}
}

// The engine's lock, taken the engine's way, but giving up after kMaxWaitMs.
static bool Enter()
{
	LONG me = (LONG)GetCurrentThreadId();
	if (*kLockOwner == me) {			// re-entry by the thread that holds it
		*kLockCount = *kLockCount + 1;
		return true;
	}
	DWORD start = GetTickCount();
	for (unsigned spins = 0;; spins++) {
		if (InterlockedCompareExchange(kLockOwner, me, 0) == 0) {
			MemoryBarrier();
			*kLockCount = 1;
			return true;
		}
		if (GetTickCount() - start > kMaxWaitMs)
			return false;
		if (spins < 10000)
			YieldProcessor();
		else
			Sleep(0);
	}
}

static void Leave()
{
	LONG left = *kLockCount - 1;
	*kLockCount = left;
	if (left == 0)
		InterlockedExchange(kLockOwner, 0);
}

// Same calling convention as the lookup (thiscall: ecx = the map's buckets, two stack arguments,
// callee pops 8): __fastcall with an unused edx matches it exactly.
typedef void (__fastcall* LookupFn)(void* map, void* edx, void* key, void* out);

static void __fastcall LockedLookup(void* map, void* edx, void* key, void* out)
{
	bool locked = Enter();
	((LookupFn)kLookup)(map, edx, key, out);
	if (locked) {
		Leave();
	} else {
		LONG n = InterlockedIncrement(&g_timeouts);
		if (n <= 5) {
			char line[96];
			sprintf_s(line, "lock busy for over %u ms: lookup %ld ran unlocked, as before", kMaxWaitMs, n);
			Log(line);
		}
	}
}

static bool Matches(DWORD addr, const BYTE* bytes, int len)
{
	__try {
		return memcmp((const void*)addr, bytes, len) == 0;
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		return false;
	}
}

static bool Apply()
{
	// the call site: mov ecx,[0x11F4468] / call 0x43C4F0 / pop ebp / ret
	static const BYTE site[] = { 0x8B, 0x0D, 0x68, 0x44, 0x1F, 0x01, 0xE8, 0x10, 0x00, 0x00, 0x00, 0x5D, 0xC3 };
	// the lookup: push ebp / mov ebp,esp / sub esp,8 / mov [ebp-8],ecx
	static const BYTE lookup[] = { 0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x08, 0x89, 0x4D, 0xF8 };
	// a writer taking the lock: push 0 / mov ecx,0x11F4480 / call 0x40FBF0
	static const BYTE writer[] = { 0x6A, 0x00, 0xB9, 0x80, 0x44, 0x1F, 0x01, 0xE8 };
	// and releasing it: sub dword ptr [0x11F4484],1
	static const BYTE release[] = { 0x83, 0x2D, 0x84, 0x44, 0x1F, 0x01, 0x01 };
	// the engine's lock: push ebx / mov ebx,esp / push ecx
	static const BYTE enter[] = { 0x53, 0x8B, 0xDC, 0x51 };

	if (!Matches(kCallSite - 6, site, sizeof(site)))
		return Log("not patched: the call site at 0x43C4D5 is not as expected (another plugin, or another game version)"), false;
	if (!Matches(kLookup, lookup, sizeof(lookup)))
		return Log("not patched: the lookup at 0x43C4F0 is not as expected"), false;
	if (!Matches(0xA61C5C, writer, sizeof(writer)) || !Matches(0xA61CB9, release, sizeof(release)))
		return Log("not patched: the map's lock at 0x11F4480 is not used as expected"), false;
	if (!Matches(0x40FBF0, enter, sizeof(enter)))
		return Log("not patched: the engine's lock routine at 0x40FBF0 is not as expected"), false;

	BYTE* at = (BYTE*)kCallSite;
	DWORD old;
	if (!VirtualProtect(at, 5, PAGE_EXECUTE_READWRITE, &old))
		return Log("not patched: could not make the call site writable"), false;
	*(DWORD*)(at + 1) = (DWORD)LockedLookup - (kCallSite + 5);	// at[0] is already E8 (call)
	VirtualProtect(at, 5, old, &old);
	FlushInstructionCache(GetCurrentProcess(), at, 5);
	Log("patched: texture-thread lookups in the map at 0x11F4468 now take the engine's lock at 0x11F4480");
	return true;
}

extern "C" {

__declspec(dllexport) bool NVSEPlugin_Query(const NVSEInterface* nvse, PluginInfo* info)
{
	info->infoVersion = PluginInfo::kInfoVersion;
	info->name = "TextureMapLock";
	info->version = 1;
	return !nvse->isEditor && nvse->runtimeVersion == kRuntime_1_4_0_525;
}

__declspec(dllexport) bool NVSEPlugin_Load(const NVSEInterface* nvse)
{
	GetModuleFileNameA(NULL, g_logPath, MAX_PATH);
	char* slash = strrchr(g_logPath, '\\');
	strcpy_s(slash ? slash + 1 : g_logPath, MAX_PATH - (slash ? slash + 1 - g_logPath : 0), "TextureMapLock.log");
	DeleteFileA(g_logPath);
	Apply();
	return true;
}

}

BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID)
{
	if (reason == DLL_PROCESS_DETACH && g_timeouts) {
		char line[96];
		sprintf_s(line, "this session: %ld lookup(s) found the lock busy for over %u ms and ran unlocked", g_timeouts, kMaxWaitMs);
		Log(line);
	}
	return TRUE;
}
