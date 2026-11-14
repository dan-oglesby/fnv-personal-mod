# Fallout: New Vegas personal mods

Dan's own small mods for New Vegas, built on top of the stability base (Gopher's Stable New Vegas
collection in Vortex: xNVSE, JIP LN NVSE and friends). Quality of life, not cheats.

The stability setup these are built on (mod list with Nexus links, settings, things to avoid) is in
[STABILITY.md](STABILITY.md).

Each folder in `src/` mirrors the game's `Data` folder. `python build.py` zips each one into
`dist/` and stages a copy in Vortex's New Vegas staging folder (`%APPDATA%\Vortex\falloutnv\mods\<Mod Name>`),
so it shows up in Vortex's Mods list ready to enable and deploy (`--no-stage` for zips only).
Staged files are rewritten in place, so a mod Vortex has already deployed picks up a rebuild.

## Menu items instead of hotkeys

Wasteland Bank and Auto Smoke open their menus from an item, the way the original Bank Card did:
an apparel item with no body slot and no weight. Equip it from the Pip-Boy's Apparel tab; it takes
itself off again and the menu opens when you close the Pip-Boy. Each item is in a tiny plugin of
its own (`WastelandBank.esp`, `AutoSmoke.esp`; only master FalloutNV.esm) written by
`make_plugins.py`, which `build.py` runs. The plugins carry no scripts. The mods' xNVSE scripts
watch for the item being equipped (`OnActorEquip`), and give it to you on load if you don't have
it. The old hotkeys (K and L) are still in the `ln_` files, commented out.

| Mod | What it does | Needs | Status |
|---|---|---|---|
| Wasteland Bank | A rewrite of Bank Card (BankCard.esp, Nexus 39741, 2011) without its bugs. Equip the **Wasteland Bank Card** from the Pip-Boy's Apparel tab and the bank opens when you close the Pip-Boy, as with the original: deposit and withdraw caps with daily interest, take one loan at a time with weekly interest, convert NCR, Legion and pre-war money to caps, and optional auto-deposit (keeps a set amount on hand) and auto-convert. | xNVSE 6.2.8+, JIP LN 56.95+. Enable `WastelandBank.esp` | Built 2026-11-11, untested in play. Don't run it alongside BankCard.esp |
| Monocyte Limb Regen | With the Monocyte Breeder implant (New Vegas Medical Clinic), crippled limbs heal on their own at the implant's own health rate, 0.1 a second, so a fully crippled limb heals in about 17 minutes of play. | xNVSE 6.2.8+, JIP LN 56.95+ | Built 2026-11-11, untested in play |
| Auto Smoke | An add-on for Light Up and Smoke Those Cigarettes (edisleado, Nexus 49677). Lights your next cigarette for you, as if you'd used it from the Pip-Boy: keep one lit, light up 1 to 20 minutes after the last one goes out, or only when you have nicotine withdrawal. Opens a pack or carton when you run out of loose ones. Settings: equip the **Cigarette Case (Auto Smoke)** from the Pip-Boy's Apparel tab. | Light Up and Smoke Those Cigarettes, xNVSE 6.2.8+, JIP LN 56.95+. Enable `AutoSmoke.esp` | Built 2026-11-11, untested in play |
| Scan Null Fix | Fixes a crash in xNVSE itself: scripts that scan the objects around you (`GetFirstRef`/`GetNextRef`, used by Auto Loot Enhanced, Increased Wasteland Spawns, Alternative Start and others) crash on an object whose base item is gone, such as an item just picked up. Skips those objects instead. | xNVSE **6.4.9** exactly (does nothing on any other version, and says so in `ScanNullFix.log`) | Built and tested offline against the real xNVSE DLL 2026-11-13 |
| Survival Start Kit | Gives Lonesome Road's Roughin' It! Bedroll Kit (sleep anywhere outdoors) at the start of a new game, or on the next load of an existing save, once, the same way the DLC does. No plugin. | Lonesome Road, xNVSE 6.1+, JIP LN 56.95+ | Built 2026-11-11, untested in play |

## How the Survival Start Kit works

New Vegas has no command to start a run with an item, and a plugin's start-up script must be
compiled by the GECK. Instead this uses JIP LN NVSE's script runner: text files in
`Data\nvse\plugins\scripts\` run on game events. `ln_` files run on a new game and on every load.
They run in the console environment, so editor IDs don't resolve; forms are built from
`LonesomeRoad.esm`'s load-order index (`BuildRef`).

The kit (ALCH `0x00CD51` in LonesomeRoad.esm) has its own scripts. Using it from the Pip-Boy opens
the sleep menu. It works outdoors only, and not in the Lucky 38, the Fort or the Big MT greenhouses.
Its OnAdd shows its intro message and sets `NVDLC04GenericPerkQUEST.bFirstPickedUp`
(`0x00A603`), which this mod checks so the kit is given only once.

Check it worked: the intro message box appears in Doc Mitchell's house on a new game, and the
console (`~`) shows "Survival Start Kit: gave the Roughin' It! Bedroll Kit".

## How Monocyte Limb Regen works

The vanilla implant's effect script (`ImplantRegenScript`) restores Health by
`ScriptEffectElapsedSeconds / 10` each frame, which is 0.1 a second. This mod's `ln_` script
registers an xNVSE `CallWhilePerSeconds` that, once a second, restores each of the six limb
conditions by 0.1, but only while the player has `ImplantRegenPerk` (FalloutNV.esm `0x14CCE1`).
Flags 4 + 16 keep it out of menus and pauses, like the implant's own effect.

It is registered again on every load and new game, and xNVSE clears all repeating calls on
those same events (`ClearDelayedCalls` in its load and new-game hooks), so it never stacks.

Check it worked: with the implant, cripple a limb (`player.DamageAV LeftMobilityCondition 100`
in the console) and watch it come back in the Pip-Boy's status page.

## How Wasteland Bank works

The 2011 Bank Card's bugs and their fixes:
- **Loan interest every few seconds instead of weekly.** It stored the day as a whole number and
  compared it with the fractional day. Here every day count is whole (`Floor GameDaysPassed`), and
  interest is 0.5% per 7 whole game days.
- **Auto-convert and auto-consolidate never ran.** Its seconds timer was a whole number and stayed
  at 0. Here they run on a 10-second tick.
- **Cash figure up to a few seconds old.** Depositing just after spending could credit caps you no
  longer had. Here every button counts your caps at the moment you click it.
- **Auto-deposit took every cap you carried.** Here it keeps a chosen amount on hand
  (100/200/500/1000, default 200).

Currency converts at each item's own value in the game, read with `GetValue`, so a mod that
reprices money is followed. Caravan money (the `CMNY` twins) converts at its matching item's value.
Deposit interest stays as in the original: 0.5% a game day plus Barter/50000, compounding. The
rates are at the top of `Tick.txt` and `Loan.txt`.

Layout: `nvse/plugins/scripts/ln_wasteland_bank.txt` gives you the bank card if you have none,
registers the card's equip handler (`OnEquip.txt`, which calls `UseCard.txt`) and a 10-second bookkeeping tick on every load. Each menu and its buttons is a user-defined
function in `nvse/user_defined_functions/WastelandBank/`, compiled by xNVSE at startup and called
with `CompileScript`. Balances are JIP auxiliary variables on the player (`_wb...`), saved in
JIP's co-save. Console: `call (CompileScript "WastelandBank/Open.txt")`.

## How Auto Smoke works

Light Up and Smoke Those Cigarettes makes smokes aid items: using one from the Pip-Boy runs its
script, which wears a lit cigarette (cigarillo, cigar) in the mouth slot, applies the tobacco
effects and addiction chance, and turns it into a butt about 2 minutes later. Auto Smoke uses the
item the same way (`EquipItem` on the aid item), so all of that still applies; it only decides when.

Every 5 seconds of play (not in menus or while paused) it checks whether you are smoking, by
looking for a worn lit smoke the same way the mod does. If not, it counts the time since the last
one went out and, after the chosen break, lights the next: ordinary cigarettes first, then
cigarillos, then cigars. Lucky cigarettes are left for you. With no loose smokes it opens a
pack, or else a carton, and lights one from it on the next check. It never lights up while
something else is worn in the mouth slot (lighting up would take it off).

The "only when craving" setting lights up when you have Nicotine Withdrawal (its Agility effect,
`AddictRedAGTobacco`, FalloutNV.esm `0x0FAB0F`). Default: on, 5 minutes between smokes, open
packs on. Settings are per character, in JIP aux variables (`_as...`). It does nothing if the
smoking mod isn't loaded.

Check it worked: with some cigarettes, equip the Cigarette Case, close the Pip-Boy, set "keep one lit", close, and wait a few
seconds. You should hear the lighter.

## How Scan Null Fix works

Three New Vegas crashes on 2026-11-12/13 were all at `nvse_1_4.dll`+0x36C03. Cobb Crash Logger's
stack was `RefMatcherFormType::Accept` < `GetCellRefEntry` < `CellScan` < `GetNextRef`, with the
base-form pointer null. In xNVSE 6.4.9 (`Commands_MiscRef.cpp`), the matchers behind every
reference scan read `refr->baseForm->typeID` without checking `baseForm`, and a scan tests every
reference in the cell. Auto Loot Enhanced picks items up in the middle of its scans, which can
leave such a reference behind; its weapon scan (type 40) is the next full pass and crashes.

`native/ScanNullFix/ScanNullFix.cpp` is a small xNVSE plugin. At load it replaces the base-form
read in `RefMatcherFormType`, `RefMatcherActor` and `RefMatcherItem` (`Accept`) with a jump to a
stub that does the same read, checks for null, and takes the function's own "no match" exit. It
checks the DLL's timestamp, the exact original bytes and each exit before changing anything, and
patches nothing otherwise. The result is written to `ScanNullFix.log` next to `FalloutNV.exe`.

Build: `python native/build_native.py` (Visual Studio Build Tools 2022, x86, static CRT). The DLL
is committed, so `build.py` needs no compiler. Test: `native/ScanNullFix/test_harness.cpp` maps the
real `nvse_1_4.dll` without running it, calls the three real functions with fake objects, and
checks that a reference with no base form crashes before the fix and is skipped after, with
normal references matching as before. When xNVSE updates, re-check the three functions
(`dumpbin /disasm` around `?Accept@RefMatcher...`) and update the offsets, bytes and timestamp,
or drop the fix if xNVSE has added the check.

## Session watcher (`tools/fnv_watch.ps1`)

A small PowerShell script for chasing crashes. It waits for `FalloutNV.exe`, records its memory
every 10 s, and when the game exits saves that session's logs (xNVSE, error, Havok, crash logger,
DXVK, Scan Null Fix, plugins.txt) into `Documents\My Games\FalloutNV\SessionLogs\<start time>\`
with a `summary.txt`: duration, whether it crashed, peak memory against the 32-bit 4 GB ceiling,
and the last save/load events. It keeps the newest 30 sessions. To run it at sign-in, put a
shortcut in the Startup folder:
`powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File tools\fnv_watch.ps1`.
`-TestStart "<date time>"` summarizes an earlier session's logs and exits.

## License

MIT (see `LICENSE`). Wasteland Bank is a fresh rewrite inspired by Bank Card (Nexus 39741) and
contains none of its files. Auto Smoke uses, but doesn't include, Light Up and Smoke Those
Cigarettes (Nexus 49677).

