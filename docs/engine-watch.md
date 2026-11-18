# Engine Watch: recording engine failures during live play

New Vegas leaves poor evidence. Its logs have no timestamps and are overwritten at every launch. A
crash log describes one instant. A freeze or a silent exit leaves nothing at all. Engine Watch
records a session from outside the game and turns it into a report.

## Layers

| Layer | What it adds | Risk | State |
|---|---|---|---|
| 1. Out-of-process recorder (`tools/engine_watch.py live`) | timestamps for every log line, memory and address space, hangs, the player's cell and position, the exit code | none: it reads only, and the game cannot see it | built (2026-11-18) |
| 2. Session report (`engine_watch.py report`) | how the session ended, the last two minutes, script errors split ours/others, mod health, deploy drift, plugin changes, cross-session history | none: it reads files | built |
| 3. In-game breadcrumbs (script) | menus opened, combat start, actors spawned, our own tick scripts' heartbeats, written to the console log the recorder already tails | low: a script; a failure is logged like any other | designed |
| 4. Native breadcrumbs (NVSE plugin) | a ring buffer in a memory-mapped file that survives the crash; a vectored handler for first-chance exceptions; a QueuedTexture run counter | medium: native code in the game; must be version-gated like ScanNullFix | designed |

## Layer 1: the recorder

`fnv_watch.ps1` already runs from the Startup folder and copies the logs when the game exits. It
now also starts `engine_watch.py live --pid <game>` (with pythonw, hidden) as soon as it sees
FalloutNV.exe. The recorder writes into the same session folder,
`Documents\My Games\FalloutNV\SessionLogs\<start>\`:

- **`timeline.jsonl`**: each new line of nvse.log, falloutnv_error.log, ConsoleLog.txt, the crash
  logger, ScanNullFix and the JIP/JohnnyGuitar logs. Each line is stamped with the second it
  appeared and gets a kind: loaded, saved, script error, mod health, nvse error, crash. Identical
  lines within one second are grouped with a count, so an error storm stays small. New crash-log
  files, cell changes, hangs and the exit are events here too. The havok log is too chatty to keep
  line by line, so it is only counted.
- **`samples.csv`**, every 2 seconds:
  - private memory and working set;
  - address space in use and the **largest free block** (walked with VirtualQueryEx every 10 s).
    The 32-bit game fails a large allocation when the free block is too small, even with hundreds
    of MB free in total, so the largest free block is the number that predicts out-of-memory;
  - handles, threads and CPU time;
  - whether Windows marks the window hung;
  - the player's cell (name and form ID) and position.
- **`live.json`**: the process ID, the start and end, and the **exit code**. It catches a crash
  the crash logger missed: 0xC0000005 access violation, 0xC0000374 heap corruption, 0xC0000409
  fail-fast, a forced kill, or 0 for a normal exit.

### Reading the game's memory

The recorder opens the process with `PROCESS_VM_READ | PROCESS_QUERY_*` only. It never injects
anything, never writes, and never debugs. FalloutNV.exe 1.4.0.525 has no ASLR, so these
addresses are fixed:

- `g_thePlayer` is at 0x011DEA3C.
- TESObjectREFR keeps its position at +0x30 and its parentCell at +0x40.
- TESForm keeps its typeID at +0x04 and its refID at +0x0C.
- The cell's full-name string is at +0x1C.

Every read is validated before it is believed: the player must be form 00000014, and the cell must
carry form type 0x39. If a read fails, it records nothing; it never invents a value. If anything
in the probe throws, probing switches off for the rest of the session and the recording carries on.

## Layer 2: the report

`report.md` and `report.json` are written into the session folder when the game exits.
`report --all` rebuilds every old session from the copied logs; those have counts but no times.
`SessionLogs/history.md` keeps one row per session. The report covers:

- **Ending:** the exit code's meaning, or the crash logger's verdict. Each crash log is classified
  by `crash_report.py`: texture streaming, the memory heap, and so on. A crash during shutdown is
  marked harmless. A crash log older than the session belongs to the session before and is not
  counted.
- **The last two minutes** of the timeline before the exit.
- **Memory:** the peak address space, the smallest "largest free block", and the private-memory
  trend after warm-up (a leak shows as steady MB/hour).
- **Script errors grouped by script.** Runtime-compiled scripts (`nvseRuntimeScript<N><File>`) are
  matched to this repo's user-defined functions by file name, so our errors are separated from
  other mods' and the base game's. Line numbers are shown when the engine gives them.
- **Mod health:**
  - our loaders' "failed to compile ... is off" notices;
  - scripts in the repo that the game never precompiled (not deployed, or failed);
  - scripts the game precompiled that the repo no longer has (a stale deploy).
- **nvse.log errors** and **plugins added or removed** since the session before.

## First findings (the 30 sessions on disk, 2026-11-14 to 17)

- **`FissionPower/Suit.txt` (nvseRuntimeScript29Suit): 5,102 errors in a 133-minute session**,
  217 and 399 in the two sessions before. The error is "Unable to find function definition for
  command -27904". In the same session Camp.txt errored with command 29285, which is 0x7265,
  ASCII "er", and a Tick script with command 26. None of these is a registered opcode. The engine
  is reading the compiled bytes at the wrong offset: the middle of a string, or a parameter.
  - This looks like a jump or statement length that lands mid-statement. Many other scripts with
    the same shapes (loops inside plain `if` blocks) run cleanly, so the shape alone isn't the cause.
  - When it happens the run stops, so everything after that point in the script is skipped every
    second.
  - The next step is a read-only bytecode dump of the live script: `tools/live_script.py`, still
    to be written, the counterpart of `live_disasm.py`.
- The Target Readout's "failed to compile" notices were a mixed deploy. In that session the game
  had the old Hide.txt and lacked Armor/Proj/Type/VatsPick. The current deploy matches the repo
  file for file.
- Other mods' storms:
  - `VFSVaporizationVolumeSCRIPT` failing StartCombat, 6,350 times in one session;
  - `NQlvlSCRIPT` with a missing local variable, 386 times;
  - UPNVSEP's `UPNVSEPEvOnProcessLevelChange` calling SetPersistent on a null actor.

## Layer 3: in-game breadcrumbs (designed)

A small UDF set registers event handlers and `print`s one tagged line per event to the console log
(`[EW] menu open 1035`, `[EW] combat start <ref>`, `[EW] cell <id>`). The recorder already tails
that log and stamps each line with its time. It costs a print per event, and none per frame.
Heartbeats from our own per-second scripts would show which of them stopped running before a
freeze.

## Layer 4: native breadcrumbs (designed)

An NVSE plugin, version-gated to 1.4.0.525 like ScanNullFix:

- **Ring buffer:** a 64 KB ring of fixed-size records in a named file mapping
  (`Local\FNVEngineWatch`). The recorder opens it read-only, so the last few thousand events
  survive a crash without any disk write on the game's side.
- **Vectored exception handler:** it records first-chance access violations (address, module,
  thread) and passes them on untouched. A handled access violation that comes before a crash is
  often the first sign of it.
- **Texture-crash probe:** a QueuedTexture vtable wrapper (Run at 0x43C150, Destroy at 0x43BE30)
  writes "task start/end/destroy" records. It would show whether the 0xA61A74 crash is a destroy
  racing a run, the use-after-free hypothesis in `engine-crash-research.md`.
- **Testing:** the offline harness is blocked by the antivirus, so this needs an in-game test, and
  it is optional: layers 1 to 3 stand on their own.
