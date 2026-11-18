# Engine notes: what lasts how long

Facts about xNVSE, JIP LN and the game that these mods depend on, confirmed in the plugins' own
source code during the 2026-11-18 review. Several bugs came from assuming otherwise.

## Lifetimes across loading a save (within one game session)

| Thing | Survives loading a save? | Source |
|---|---|---|
| JIP aux variables without `*` (`"_name"`) | No: replaced by the save's own values | JIP `ProcessDataChangedFlags` clears `s_auxVariables[0]` only |
| JIP temporary aux variables (`"*_name"`) | **Yes**, until the game exits | `s_auxVariables[1]` is never cleared on load |
| xNVSE `SetEventHandler` handlers | **Yes**, until removed or the game exits | `ClearFlushOnLoadEventHandlers` flushes only `SetEventHandlerAlt` callbacks |
| xNVSE `CallWhilePerSeconds` / `CallAfterSeconds` | No: cleared on load and new game | `ClearDelayedCalls` in the load hook |
| JIP menu handlers (`SetOnMenuOpen/CloseEventHandler`) | Kept in a set, so re-adding is harmless | JIP |
| Base-form changes (`SetBaseItemValue`, `SetWeight`, other `Set...` on a base form) | **Yes**, until the game exits (not saved, but not undone by a load either) | |

Consequences, each a real bug that was found:
- Never read a base value back as the "original" after you might have changed it this session.
  Record it once (a temporary aux variable lasts the session) or compute from vanilla constants.
- A temporary "already registered" flag set by a tick goes stale when a *different* save loads,
  because its references are different. Have the `ln_` loader clear such flags (it runs on every
  load), and remove a handler before setting it again so it is never doubled.
- A reference that exists in a save but was spawned in an earlier session needs its handlers set
  again after a game restart.

## Script compilation
- A variable named like any game command or alias (`rW` is RevertWorld, `SSP` is SetSkyParam) stops
  the whole file compiling. `check_scripts.py` checks against the full list in
  `tools/fnv_commands.txt`, read from FalloutNV.exe by `tools/gen_fnv_commands.py`.
- Failures show only as "Failed to precompile" in `nvse.log`; the loaders name each failed file in
  the console and keep the rest of the mod running.

## Building and deploying
- `build.py` rewrites staged files in place, so a deployed (hardlinked) copy updates at once. New
  files need a Vortex deploy to reach the game, and removed files are taken out of the game by
  `build.py` itself.
