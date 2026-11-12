# Fallout: New Vegas personal mods

Dan's own small mods for New Vegas, built on top of the stability base (Gopher's Stable New Vegas
collection in Vortex: xNVSE, JIP LN NVSE and friends). Quality of life, not cheats.

Each folder in `src/` mirrors the game's `Data` folder. `python build.py` zips each one into
`dist/`. Install a zip by dragging it onto Vortex's Mods page, then enable and deploy it.

| Mod | What it does | Needs | Status |
|---|---|---|---|
| Wasteland Bank | A rewrite of Bank Card (BankCard.esp, Nexus 39741, 2011) without its bugs or a plugin. Press **K** to open: deposit and withdraw caps with daily interest, take one loan at a time with weekly interest, convert NCR, Legion and pre-war money to caps, and optional auto-deposit (keeps a set amount on hand) and auto-convert. | xNVSE 6.2.8+, JIP LN 56.95+ | Built 2026-11-11, untested in play. Don't run it alongside BankCard.esp |
| Monocyte Limb Regen | With the Monocyte Breeder implant (New Vegas Medical Clinic), crippled limbs heal on their own at the implant's own health rate, 0.1 a second, so a fully crippled limb heals in about 17 minutes of play. | xNVSE 6.2.8+, JIP LN 56.95+ | Built 2026-11-11, untested in play |
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

Layout: `nvse/plugins/scripts/ln_wasteland_bank.txt` registers the hotkey (K, DirectInput 37)
and a 10-second bookkeeping tick on every load. Each menu and its buttons is a user-defined
function in `nvse/user_defined_functions/WastelandBank/`, compiled by xNVSE at startup and called
with `CompileScript`. Balances are JIP auxiliary variables on the player (`_wb...`), saved in
JIP's co-save. Console: `call (CompileScript "WastelandBank/Open.txt")`.
