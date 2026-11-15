# Stable New Vegas setup

The stability base these mods are built and tested on, so it can be rebuilt on a new computer. It
lists what is installed, the settings changed from defaults and why, and things to avoid. Last
updated 2026-11-14. Nexus links are `nexusmods.com/newvegas/mods/<id>`.

## Order on a new computer

1. Install Fallout: New Vegas (Steam) and run it once from the launcher, so it writes its INIs and
   registry key.
2. Install Vortex and the **Gopher's Stable New Vegas** collection: find it under
   [New Vegas collections](https://next.nexusmods.com/newvegas/collections). That covers the
   first table below.
3. Add the extras from the second table.
4. Apply the settings changes and run the Vanilla BSAs Patcher once.
5. Add your other mods, then this repo's mods (`python build.py` stages them in Vortex).

## 1. Gopher's Stable New Vegas (Vortex collection)

| Mod | Link | What it does |
|---|---|---|
| New Vegas Script Extender (xNVSE) | [67883](https://www.nexusmods.com/newvegas/mods/67883) ([GitHub](https://github.com/xNVSE/NVSE/releases)) | Script extender everything else needs |
| 4GB Patcher | [62552](https://www.nexusmods.com/newvegas/mods/62552) | Lets the 32-bit game use 4 GB of address space; also launches xNVSE |
| JIP LN NVSE Plugin (+ JIP LN Settings INI) | [58277](https://www.nexusmods.com/newvegas/mods/58277) | Script functions and engine fixes |
| JohnnyGuitar NVSE | [66927](https://www.nexusmods.com/newvegas/mods/66927) | Script functions and fixes |
| ShowOff xNVSE (+ ShowOff INI) | [72541](https://www.nexusmods.com/newvegas/mods/72541) | Script functions, engine tweaks and fixes |
| lStewieAl's Tweaks (+ Stewie Tweaks INI) | [66347](https://www.nexusmods.com/newvegas/mods/66347) | Hundreds of engine fixes and options |
| NVTF - New Vegas Tick Fix (+ Gopher's INI) | [66537](https://www.nexusmods.com/newvegas/mods/66537) | Stutter and frame-pacing fixes, threading tweaks (see settings) |
| Engine Optimizations | [80993](https://www.nexusmods.com/newvegas/mods/80993) | Engine performance fixes |
| ActorCause Save Bloat Fix | [80666](https://www.nexusmods.com/newvegas/mods/80666) | Stops saves growing without limit |
| Cell Offset Generator - NVSE | [92182](https://www.nexusmods.com/newvegas/mods/92182) | Faster, lighter cell loading |
| FNV Mod Limit Fix (MLF) | [68714](https://www.nexusmods.com/newvegas/mods/68714) | Raises the open-file limit, faster loads |
| Fast Weapon Lag Fix | [71973](https://www.nexusmods.com/newvegas/mods/71973) | Fixes weapon-switch lag |
| VATS Lag Fix | [84823](https://www.nexusmods.com/newvegas/mods/84823) | Fixes VATS lag |
| Viewmodel Shake Fix - NVSE | [84443](https://www.nexusmods.com/newvegas/mods/84443) | Fixes first-person shake |
| Collision Meshes FNV | [59149](https://www.nexusmods.com/newvegas/mods/59149) | Fixed collision meshes |
| Ultimate Edition ESM Fixes Remastered | [92289](https://www.nexusmods.com/newvegas/mods/92289) | Optimized and fixed vanilla and DLC ESMs |
| Yukichigai Unofficial Patch (YUP) | [51664](https://www.nexusmods.com/newvegas/mods/51664) | Thousands of vanilla bug fixes |
| Unofficial Patch NVSE Plus | [71239](https://www.nexusmods.com/newvegas/mods/71239) | Fixes YUP leaves for xNVSE |
| UIO - User Interface Organizer | [57174](https://www.nexusmods.com/newvegas/mods/57174) | Keeps UI mods from conflicting |
| OneTweak | [79211](https://www.nexusmods.com/newvegas/mods/79211) | Borderless window and focus fixes |
| Faster Start Menu | [67811](https://www.nexusmods.com/newvegas/mods/67811) | Quicker main menu |

## 2. Added on top

| Mod / tool | Link | Why |
|---|---|---|
| Yvile's Crash Logger | [82540](https://www.nexusmods.com/newvegas/mods/82540) | Detailed crash logs. Replaces Cobb Crash Logger (72317); don't run both |
| ITR NVSE | [96922](https://www.nexusmods.com/newvegas/mods/96922) | More engine bug fixes (recommended by the Viva New Vegas guide) |
| Vanilla BSAs Patcher | [98738](https://www.nexusmods.com/newvegas/mods/98738) | A tool, not a mod: run `Vanilla BSAs Patcher.exe` once, defaults (keep decompression on for an SSD), Patch. Faster loading, fixes vanilla audio. Re-run after Steam "verify files" |
| DXVK (32-bit `d3d9.dll`) | [GitHub releases](https://github.com/doitsujin/dxvk/releases) (the guides also link Nexus [79299](https://www.nexusmods.com/newvegas/mods/79299)) | Copy `x32\d3d9.dll` from the release into the game folder (next to `FalloutNV.exe`). Keeps texture memory out of the 32-bit address space, which helps long-session out-of-memory crashes. Remove by deleting `d3d9.dll`  Briefly disabled on 2026-11-14 to test a loader crash; the crash recurred without it, so it was re-enabled. |
| Scan Null Fix | this repo (`src/Scan Null Fix`) | Fixes an xNVSE 6.4.9 crash when scripts scan nearby objects (auto-loot mods); does nothing on other xNVSE versions (see `ScanNullFix.log`) |
| Session watcher | this repo (`tools/fnv_watch.ps1`) | Saves each session's logs and memory use to `Documents\My Games\FalloutNV\SessionLogs`, for diagnosing crashes |

## Settings changed

- **NVTF.ini**: `iReplaceTextureCreationLocks = 0` (Gopher's INI ships 2). Lowered to 1 on 2026-11-14
  after a background-loader crash, then to 0 the same day after two more crashes at the same
  instruction in the game's background loader (a queued model, then a queued texture during fast
  travel). 0 keeps the game's own locking.
- **NVTF.ini**: `iReplaceGeometryPrecacheLocks = 0` (Gopher's INI ships 1, "makes geometry loading
  multithreaded"). Changed 2026-11-14 after a crash while the main thread finished a background model
  load.
- **NVTF.ini**: `bTweakMiscCriticalSections = 0` (Gopher's INI ships 1). Changed 2026-11-14 after a
  fifth crash at the same loader instruction (FalloutNV 0xA61A74), which came after both lock tweaks
  above were already 0 and with or without DXVK. Turning it off only costs a little loading speed.
- **ITR NVSE**: `Data\config\itr-nvse.ini` with only `[Tweaks] bSmallDebrisCap=0`; all other ITR
  settings stay at defaults, including every crash fix. SmallDebrisCap (new in ITR 2.3.0) retains,
  culls and releases shell-casing debris, and both casing crashes on 2026-11-14 involved those objects.
- **Permanent Weapon Shells**: use **Light** (`iDebrisMaxCount` 1250, casings last 10 min), not Very
  Heavy (10000 for a day).
- **dxvk.conf** (game folder): defaults. NVTF's `bUseFlipModel = 0` and
  `bUseDefaultPoolForTextures = 1` work as they are with DXVK.
- **NVIDIA "DXGI interop"** for DXVK (NVIDIA Profile Inspector): *not* set. It's optional on
  desktops and costs about 150–170 MB of the game's memory.
- `bUseThreadedAI=0` in Fallout.ini (the default; keep it off).

## Avoid

- A heap replacer (NVHR): current guides don't use one, and it's reported to conflict with DXVK.
- NVAC: outdated.
- Two crash loggers at once.
- Late in a long session, reloading a save in-game (e.g. after dying): quitting and relaunching is
  far less crash-prone.
- Heavy "permanent" debris mods at their highest settings (e.g. Permanent Weapon Shells "Very
  Heavy"): they cost memory and save size.

## Sources

- [Viva New Vegas: utilities](https://vivanewvegas.moddinglinked.com/utilities.html)
- [Fallout: New Vegas performance guide (NVTF, DXVK)](https://performance.moddinglinked.com/falloutnv.html)
- [New Vegas Rebuilt: mod management](https://newvegasrebuilt.github.io/mod-management)

## Script event handlers (for mods in this repo)

xNVSE queues game events fired on background threads (NPCs equipping gear while cells load) onto
an unlocked list that the main thread clears every frame. An **unfiltered** `OnActorEquip`
handler sends every NPC equip there. On 2026-11-14 that race corrupted memory and crashed the
game's loaders four times (FalloutNV 0xA61A74, in queued model, texture and file loads).
Handlers for high-traffic events must be filtered, e.g.
`SetEventHandler "OnActorEquip" fn "second"::item`; `check_scripts.py` enforces this. Other
installed mods with unfiltered handlers: UPNVSE, Live Dismemberment and Immersive Hit Reactions
(`OnHit`, mostly main-thread).

