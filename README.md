# Fallout: New Vegas personal mods

Dan's own small mods for New Vegas, built on top of the stability base (Gopher's Stable New Vegas
collection in Vortex: xNVSE, JIP LN NVSE and friends). Quality of life, not cheats.

Each folder in `src/` mirrors the game's `Data` folder. `python build.py` zips each one into
`dist/`. Install a zip by dragging it onto Vortex's Mods page, then enable and deploy it.

| Mod | What it does | Needs | Status |
|---|---|---|---|
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
