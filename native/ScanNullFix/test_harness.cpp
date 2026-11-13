// Offline test for ScanNullFix: maps the real nvse_1_4.dll without running it (no DllMain, no
// imports), loads ScanNullFix.dll, and calls the three real Accept functions with fake objects.
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef bool(__thiscall* AcceptFn)(void* self, void* refr);
struct NVSEInterface { unsigned nvseVersion, runtimeVersion, editorVersion, isEditor; };
typedef bool (*LoadFn)(const NVSEInterface*);

static BYTE g_form[0x40];          // fake base form: typeID at +4, refID at +0xC
static BYTE g_refrOK[0x80];        // fake reference: flags at +8, baseForm at +0x20
static BYTE g_refrNull[0x80];      // same with baseForm = null

static int Call(AcceptFn f, void* self, void* refr, const char* label)
{
	__try { bool r = f(self, refr); printf("  %-46s -> %s\n", label, r ? "match" : "no match"); return r ? 1 : 0; }
	__except (EXCEPTION_EXECUTE_HANDLER) { printf("  %-46s -> CRASH (exception %08X)\n", label, GetExceptionCode()); return -1; }
}

int main(int argc, char** argv)
{
	HMODULE nvse = LoadLibraryExA(argv[1], NULL, DONT_RESOLVE_DLL_REFERENCES);
	if (!nvse) { printf("could not map %s (%lu)\n", argv[1], GetLastError()); return 2; }
	BYTE* base = (BYTE*)nvse;
	AcceptFn formType = (AcceptFn)(base + 0x36BD0), actor = (AcceptFn)(base + 0x36D00), item = (AcceptFn)(base + 0x36E30);

	// matchers: all-zero = no distance ref, include taken false, no base-form filter
	BYTE mFormType[0x20] = {}; *(unsigned*)(mFormType + 0x14) = 40;	// scan for WEAP (40), as Auto Loot does
	BYTE mActor[0x20] = {};
	BYTE mItem[0x20] = {};

	g_form[4] = 40; *(unsigned*)(g_form + 0xC) = 0x1234;	// a weapon
	*(void**)(g_refrOK + 0x20) = g_form;
	*(void**)(g_refrNull + 0x20) = NULL;

	int fails = 0;
	printf("BEFORE the fix:\n");
	fails += Call(formType, mFormType, g_refrOK, "FormType(40): weapon ref") != 1;
	fails += Call(item, mItem, g_refrOK, "Item: weapon ref") != 1;
	fails += Call(actor, mActor, g_refrOK, "Actor: weapon ref") != 0;
	int before = Call(formType, mFormType, g_refrNull, "FormType(40): ref with no base form");
	Call(actor, mActor, g_refrNull, "Actor: ref with no base form");
	Call(item, mItem, g_refrNull, "Item: ref with no base form");

	HMODULE fix = LoadLibraryA(argv[2]);
	if (!fix) { printf("could not load %s (%lu)\n", argv[2], GetLastError()); return 2; }
	NVSEInterface iface = { 0x06040090, 0x040020D0, 0, 0 };
	((LoadFn)GetProcAddress(fix, "NVSEPlugin_Load"))(&iface);

	printf("AFTER the fix:\n");
	fails += Call(formType, mFormType, g_refrOK, "FormType(40): weapon ref") != 1;
	fails += Call(item, mItem, g_refrOK, "Item: weapon ref") != 1;
	fails += Call(actor, mActor, g_refrOK, "Actor: weapon ref") != 0;
	g_form[4] = 0x2A;	// NPC
	fails += Call(actor, mActor, g_refrOK, "Actor: NPC ref") != 1;
	fails += Call(formType, mFormType, g_refrOK, "FormType(40): NPC ref") != 0;
	*(unsigned*)(g_form + 0xC) = 7;	// the player's base form
	fails += Call(actor, mActor, g_refrOK, "Actor: player ref (excluded)") != 0;
	fails += Call(formType, mFormType, g_refrNull, "FormType(40): ref with no base form") != 0;
	fails += Call(actor, mActor, g_refrNull, "Actor: ref with no base form") != 0;
	fails += Call(item, mItem, g_refrNull, "Item: ref with no base form") != 0;

	printf(before == -1 ? "original crash reproduced before the fix\n" : "WARNING: original did not crash\n");
	printf(fails ? "%d CHECK(S) FAILED\n" : "all checks passed\n", fails);
	return fails ? 1 : 0;
}
