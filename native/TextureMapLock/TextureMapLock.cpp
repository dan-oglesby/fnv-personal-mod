// Texture Map Lock (2026-11-18): an xNVSE plugin for New Vegas's most common crash in this load
// order, FalloutNV.exe+0xA61A74 on the background task thread while a texture loads (10 of the 20
// crash logs on 2026-11-14..17, and two more on 2026-11-18 with version 1 in place).
//
// What the crash is (read from the running game, docs/engine-crash-research.md):
//   QueuedTexture::Run (0x43C150) -> 0x43C4C0 -> 0x43C4F0 -> 0xA61A60, a lookup in the texture
//   cache: a hash table whose pointer is at 0x011F4468 (1001 buckets, hash (key >> 4) % 1001). A
//   bucket holds a chain of entries {record*, next}; a record is {texture, key, ...}. The crash is
//   "cmp edx,[esi+4]" at 0xA61A74: reading the key of a record that has been freed.
//
// Version 1 took the engine's lock (0x011F4480) around that lookup, on the theory that the main
// thread was removing an entry while the texture thread walked past it. The crash came back twice
// with the lock held and no timeouts, so that wasn't it. Others had found this crash before us:
//   - NVAC (New Vegas Anti Crash, 2014-16) caught the access violation at 00A61A74 and carried on;
//   - Psycho Engine Fixes' analysis (github.com/acidpointer/psycho, analysis/heap_analysis.md,
//     "Texture Cache Hash Table"): the cache never removes single entries. They outlive the
//     textures they point to, and the game only empties the cache on worldspace changes. A freed
//     record left in a chain is what the lookup trips over.
//
// Version 2 keeps the lock and adds NVAC's guard, plus a repair:
//   - the lookup runs under structured exception handling. An access violation inside the lookup
//     (0xA61A60-0xA61AC7, and nowhere else) is caught instead of crashing the game;
//   - then, still holding the lock that every writer of the cache takes, the faulting bucket's
//     chain is walked with guarded reads and any entry whose record can't be read is unlinked, so
//     nothing else trips over it (the insert that follows a miss walks the same chain). The
//     unlinked entry is left allocated (8 bytes) rather than freed;
//   - the lookup is retried once. If it still can't run, it reports "not cached" and the task
//     loads the texture from disk, the normal path for a texture that isn't cached.
// Each catch is written to TextureMapLock.log (the first ten, then a total when the game closes).
// A record freed and then reused for something else can't be detected this way. It doesn't
// fault, and only a perfectly matching key would make the lookup return it.
//
// The lock: the owning thread's ID at 0x011F4480 (taken with InterlockedCompareExchange) and a
// re-entry count at 0x011F4484, as the engine's 0x40FBF0 takes it and 0xA61CB9 releases it. It is
// never waited on for more than kMaxWaitMs; past that the lookup runs unlocked (and nothing is
// repaired), as the game always did.
//
// It patches only FalloutNV.exe 1.4.0.525 and only if every byte it relies on is as expected (the
// call site, the lock's users, the lookup and the chain walk it guards). Otherwise it patches
// nothing, or leaves out the guard, and says why in TextureMapLock.log next to FalloutNV.exe.
// Not loaded in the GECK.

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
static const DWORD kCallSite = 0x43C4DB;	// call 0x43C4F0 (the cache lookup), inside 0x43C4C0
#ifndef TML_LOOKUP					// a test outside the game places its stand-in elsewhere
#define TML_LOOKUP 0x43C4F0
#endif
static const DWORD kLookup = TML_LOOKUP;	// thiscall(buckets; key, NiPointer& out): hashes, calls 0xA61A60
static const DWORD kWalkBegin = 0xA61A60;	// the bucket walk (103 bytes); the only place a fault is caught
static const DWORD kWalkEnd = 0xA61AC8;
static const UInt32 kBuckets = 1001;
static volatile LONG* const kLockOwner = (volatile LONG*)0x011F4480;
static volatile LONG* const kLockCount = (volatile LONG*)0x011F4484;
static const DWORD kMaxWaitMs = 50;

static volatile LONG g_timeouts = 0;
static volatile LONG g_caught = 0;
static volatile LONG g_unlinked = 0;
static bool g_guard = false;
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

// Same calling convention as the lookup (thiscall: ecx = the cache's buckets, two stack arguments,
// callee pops 8): __fastcall with an unused edx matches it exactly.
typedef void (__fastcall* LookupFn)(void* buckets, void* edx, void* key, void* out);

static bool ReadDword(const DWORD* p, DWORD* value)
{
	__try {
		*value = *(volatile const DWORD*)p;
		return true;
	} __except (GetExceptionCode() == EXCEPTION_ACCESS_VIOLATION ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) {
		return false;
	}
}

// Catch an access violation only inside the bucket walk; anything else crashes as it would have.
static int WalkFilter(EXCEPTION_POINTERS* ep, DWORD* where)
{
	if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION)
		return EXCEPTION_CONTINUE_SEARCH;
	DWORD at = (DWORD)ep->ExceptionRecord->ExceptionAddress;
	if (at < kWalkBegin || at >= kWalkEnd)
		return EXCEPTION_CONTINUE_SEARCH;
	*where = at;
	return EXCEPTION_EXECUTE_HANDLER;
}

static bool TryLookup(void* buckets, void* edx, void* key, void* out, DWORD* where)
{
	__try {
		((LookupFn)kLookup)(buckets, edx, key, out);
		return true;
	} __except (WalkFilter(GetExceptionInformation(), where)) {
		return false;
	}
}

// Unlink every entry of key's bucket whose record can't be read. Call only with the lock held.
static LONG RepairBucket(DWORD* buckets, DWORD key)
{
	DWORD* link = buckets + (key >> 4) % kBuckets;
	LONG removed = 0;
	for (int guard = 0; guard < 100000; guard++) {
		DWORD entry, record, next, k;
		if (!ReadDword(link, &entry) || !entry)
			break;
		if (!ReadDword((DWORD*)entry, &record) || !ReadDword((DWORD*)entry + 1, &next)) {
			*link = 0;					// the entry itself is gone: the chain ends here
			removed++;
			break;
		}
		if (!record || !ReadDword((DWORD*)record + 1, &k)) {
			*link = next;				// its record is gone: skip the entry
			removed++;
			continue;
		}
		link = (DWORD*)entry + 1;
	}
	return removed;
}

static void __fastcall LockedLookup(void* buckets, void* edx, void* key, void* out)
{
	bool locked = Enter();
	if (!g_guard) {
		((LookupFn)kLookup)(buckets, edx, key, out);
	} else {
		DWORD where = 0;
		if (!TryLookup(buckets, edx, key, out, &where)) {
			LONG removed = 0;
			if (locked)
				removed = RepairBucket((DWORD*)buckets, (DWORD)key);
			DWORD again = 0;
			bool retried = locked && removed && TryLookup(buckets, edx, key, out, &again);
			InterlockedExchangeAdd(&g_unlinked, removed);
			LONG n = InterlockedIncrement(&g_caught);
			if (n <= 10) {
				char line[200];
				sprintf_s(line, "caught a freed texture-cache record at 0x%08X (key 0x%08X, bucket %u): %ld entr%s unlinked, %s",
					where, (DWORD)key, (UInt32)(((DWORD)key >> 4) % kBuckets), removed, removed == 1 ? "y" : "ies",
					retried ? "lookup retried" : (locked ? "texture loads from disk" : "lock not held, nothing repaired"));
				Log(line);
			}
		}
	}
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
	// the bucket walk the guard relies on: mov ecx,[ecx+eax*4] (the chain's head), then
	// mov esi,[ecx] / cmp edx,[esi+4] (the record and its key), then mov ecx,[ecx+4] (next)
	static const BYTE head[] = { 0x8B, 0x0C, 0x81 };
	static const BYTE compare[] = { 0x8B, 0x31, 0x3B, 0x56, 0x04 };
	static const BYTE next[] = { 0x8B, 0x49, 0x04 };

	if (!Matches(kCallSite - 6, site, sizeof(site)))
		return Log("not patched: the call site at 0x43C4D5 is not as expected (another plugin, or another game version)"), false;
	if (!Matches(kLookup, lookup, sizeof(lookup)))
		return Log("not patched: the lookup at 0x43C4F0 is not as expected"), false;
	if (!Matches(0xA61C5C, writer, sizeof(writer)) || !Matches(0xA61CB9, release, sizeof(release)))
		return Log("not patched: the map's lock at 0x11F4480 is not used as expected"), false;
	if (!Matches(0x40FBF0, enter, sizeof(enter)))
		return Log("not patched: the engine's lock routine at 0x40FBF0 is not as expected"), false;
	g_guard = Matches(0xA61A64, head, sizeof(head)) && Matches(0xA61A72, compare, sizeof(compare))
		&& Matches(0xA61A79, next, sizeof(next));

	BYTE* at = (BYTE*)kCallSite;
	DWORD old;
	if (!VirtualProtect(at, 5, PAGE_EXECUTE_READWRITE, &old))
		return Log("not patched: could not make the call site writable"), false;
	*(DWORD*)(at + 1) = (DWORD)LockedLookup - (kCallSite + 5);	// at[0] is already E8 (call)
	VirtualProtect(at, 5, old, &old);
	FlushInstructionCache(GetCurrentProcess(), at, 5);
	Log("patched: texture-thread lookups in the map at 0x11F4468 now take the engine's lock at 0x11F4480");
	Log(g_guard ? "guard on: a freed record met in the lookup is caught, unlinked under the lock, and the texture loads from disk"
		: "guard off: the bucket walk at 0xA61A60 is not as expected, so faults there are not caught");
	return true;
}

extern "C" {

__declspec(dllexport) bool NVSEPlugin_Query(const NVSEInterface* nvse, PluginInfo* info)
{
	info->infoVersion = PluginInfo::kInfoVersion;
	info->name = "TextureMapLock";
	info->version = 2;
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
	if (reason == DLL_PROCESS_DETACH && (g_timeouts || g_caught)) {
		char line[160];
		sprintf_s(line, "this session: %ld freed record(s) caught, %ld entr(ies) unlinked; %ld lookup(s) found the lock busy for over %u ms",
			g_caught, g_unlinked, g_timeouts, kMaxWaitMs);
		Log(line);
	}
	return TRUE;
}
