"""Engine Watch: a live, out-of-process recorder for New Vegas sessions, and the report it writes.

    python tools/engine_watch.py live [--pid N]      record the running game (fnv_watch.ps1 starts it)
    python tools/engine_watch.py report <session>    (re)write report.md / report.json for a session
    python tools/engine_watch.py report --all        every session in SessionLogs, then the history
    python tools/engine_watch.py history             the cross-session table (history.md)

Why: the game's own logs have no timestamps, are overwritten at every launch, and a crash log only
describes the last instant. Watching from outside the game, this keeps what they can't:
  - every new line of nvse.log, falloutnv_error.log, ConsoleLog.txt and the plugin logs, stamped
    with the time it appeared (repeats grouped per second), in timeline.jsonl;
  - the process every 2 s: private memory, address space actually used and the largest free block
    left in it (the 32-bit game dies of fragmentation long before it runs out of bytes), handles,
    threads, CPU time, and whether Windows considers its window hung;
  - where the player is, read from the game's memory (read-only: PROCESS_VM_READ, no injection,
    nothing written): the current cell and position, so a crash has a place and a path to it;
  - how it ended: the process exit code (access violation, heap corruption, stack overrun, killed,
    normal) even when no crash logger fired, plus any crash log, classified by crash_report.py.
When the game exits it writes report.md and report.json into the session's folder (the same folder
fnv_watch.ps1 fills with copies of the logs) and adds a line to SessionLogs/history.md.

The report: how the session ended and the last two minutes before it; memory and fragmentation;
hangs; script errors grouped by script, split into ours (this repo's scripts) and others; mod
health (our loaders' "failed to compile ... is off" notices, and scripts in the repo that the game
never precompiled: an undeployed or stale build); nvse.log errors; and which plugins changed since
the session before. It works on old sessions too, with counts instead of times.

Nothing here changes the game, its files or its logs. Only the session folder is written.
"""
import argparse
import collections
import csv
import ctypes
import ctypes.wintypes as wt
import faulthandler
import datetime as dt
import json
import os
import re
import struct
import sys
import subprocess
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crash_report  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GAME = crash_report.GAME
SESSIONS = Path(os.path.expanduser("~")) / "Documents" / "My Games" / "FalloutNV" / "SessionLogs"
EXE = "FalloutNV.exe"
TAILED = ["nvse.log", "falloutnv_error.log", "ConsoleLog.txt", "CrashLogger.log", "ScanNullFix.log",
          "logs/jip_ln_nvse.log", "logs/JohnnyGuitarNVSE.log", "mcm.log"]
COUNTED = ["falloutnv_havok.log"]          # too chatty to keep line by line: counted per sample

EXIT_CODES = {
    0: "normal exit",
    1: "ended by another program (Task Manager / End task)",
    0xFFFFFFFF: "ended by another program (forced)",
    0xC0000005: "access violation (the classic crash)",
    0xC0000374: "heap corruption",
    0xC0000409: "stack buffer overrun / fail-fast",
    0xC00000FD: "stack overflow",
    0xC0000017: "out of memory",
    0xC0000094: "integer divide by zero",
    0xC000001D: "illegal instruction",
    0xC000013A: "closed with Ctrl+C",
    0x80000003: "breakpoint (an assert)",
    0xE06D7363: "unhandled C++ exception",
}

# ---------------------------------------------------------------- Windows, read-only --------------
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
SYNCHRONIZE, VM_READ, QUERY_INFO, QUERY_LIMITED = 0x00100000, 0x0010, 0x0400, 0x1000
k32.OpenProcess.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateMutexW.restype = wt.HANDLE
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.OpenThread.restype = wt.HANDLE
k32.GetCurrentProcess.restype = wt.HANDLE
k32.SetPriorityClass.argtypes = [wt.HANDLE, wt.DWORD]
ntdll = ctypes.WinDLL("ntdll")
THREAD_QUERY_INFO, THREAD_QUERY_LIMITED = 0x0040, 0x0800


class IOC(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]


class MODINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wt.DWORD), ("EntryPoint", ctypes.c_void_p)]


def cpu_mhz():
    """The processor's rated clock, to turn thread cycle counts into time (cycles are counted at it)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return float(winreg.QueryValueEx(k, "~MHz")[0])
    except OSError:
        return 3000.0


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", wt.LONG), ("tpDeltaPri", wt.LONG),
                ("dwFlags", wt.DWORD)]


def find_pid(name=EXE):
    arr = (wt.DWORD * 4096)()
    got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    for pid in arr[: got.value // 4]:
        h = k32.OpenProcess(QUERY_LIMITED, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(260)
        size = wt.DWORD(260)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        k32.CloseHandle(h)
        if ok and buf.value.lower().endswith("\\" + name.lower()):
            return pid
    return None


def filetime(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


class Proc:
    """A read-only handle on the game: memory counters, address space, threads, window, exit code."""

    def __init__(self, pid):
        self.pid = pid
        rights = SYNCHRONIZE | VM_READ | QUERY_LIMITED
        self.h = k32.OpenProcess(rights | QUERY_INFO, False, pid) or k32.OpenProcess(rights, False, pid)
        if not self.h:
            raise OSError("could not open process %d (error %d)" % (pid, ctypes.get_last_error()))
        c, e, kt, ut = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        k32.GetProcessTimes(self.h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
        self.started = dt.datetime(1601, 1, 1) + dt.timedelta(microseconds=filetime(c) // 10)
        self.started = self.started.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)

    def exited(self):
        return k32.WaitForSingleObject(self.h, 0) == 0

    def exit_code(self):
        code = wt.DWORD()
        k32.GetExitCodeProcess(self.h, ctypes.byref(code))
        return code.value

    def counters(self):
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        psapi.GetProcessMemoryInfo(self.h, ctypes.byref(pmc), pmc.cb)
        hc = wt.DWORD()
        k32.GetProcessHandleCount(self.h, ctypes.byref(hc))
        c, e, kt, ut = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        k32.GetProcessTimes(self.h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
        io = IOC()
        k32.GetProcessIoCounters(self.h, ctypes.byref(io))
        return {"private_mb": pmc.PrivateUsage >> 20, "ws_mb": pmc.WorkingSetSize >> 20,
                "handles": hc.value, "cpu_s": round((filetime(kt) + filetime(ut)) / 1e7, 2),
                "_faults": pmc.PageFaultCount, "_read": io.ReadBytes, "_reads": io.ReadOps, "_write": io.WriteBytes}

    def focused(self):
        """True while the game's window has the focus (an alt-tab gap is not a hitch)."""
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(u32.GetForegroundWindow(), ctypes.byref(pid))
        return pid.value == self.pid

    def modules(self):
        """[(base, end, name)] of the game's 32-bit modules, to name where its threads started."""
        arr = (ctypes.c_void_p * 1024)()
        need = wt.DWORD()
        if not psapi.EnumProcessModulesEx(self.h, arr, ctypes.sizeof(arr), ctypes.byref(need), 1):  # 32-bit list
            return []
        out = []
        for base in arr[: need.value // ctypes.sizeof(ctypes.c_void_p)]:
            mi = MODINFO()
            name = ctypes.create_unicode_buffer(260)
            if base and psapi.GetModuleInformation(self.h, ctypes.c_void_p(base), ctypes.byref(mi), ctypes.sizeof(mi)):
                psapi.GetModuleBaseNameW(self.h, ctypes.c_void_p(base), name, 260)
                out.append((base, base + mi.SizeOfImage, name.value.rsplit(".", 1)[0]))
        return out

    def address_space(self):
        """The 32-bit address space (below 4 GB): MB in use and the largest free block, in MB."""
        addr, used, largest, mbi = 0x10000, 0, 0, MBI()
        while addr < 0x100000000:
            if not k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            size = min(mbi.RegionSize, 0x100000000 - addr)
            if addr == 0x7FFF0000 and mbi.State == 0x2000 and size >= 1 << 30:
                break                                      # a 2 GB process: the rest is the system's
            if mbi.State == 0x10000:                       # MEM_FREE
                largest = max(largest, size)
            elif mbi.Type:                                 # image, mapped or private: the game's own
                used += size                               # (not the system's reserve above 2 GB)
            addr += mbi.RegionSize
        if not used:
            return {}
        return {"va_used_mb": used >> 20, "va_largest_free_mb": largest >> 20}

    def threads(self):
        snap = k32.CreateToolhelp32Snapshot(0x4, 0)
        if snap in (None, wt.HANDLE(-1).value):
            return None
        te, n = THREADENTRY32(), 0
        te.dwSize = ctypes.sizeof(te)
        ok = k32.Thread32First(snap, ctypes.byref(te))
        while ok:
            n += te.th32OwnerProcessID == self.pid
            ok = k32.Thread32Next(snap, ctypes.byref(te))
        k32.CloseHandle(snap)
        return n

    def thread_ids(self):
        snap = k32.CreateToolhelp32Snapshot(0x4, 0)
        if snap in (None, wt.HANDLE(-1).value):
            return []
        te, out = THREADENTRY32(), []
        te.dwSize = ctypes.sizeof(te)
        ok = k32.Thread32First(snap, ctypes.byref(te))
        while ok:
            if te.th32OwnerProcessID == self.pid:
                out.append(te.th32ThreadID)
            ok = k32.Thread32Next(snap, ctypes.byref(te))
        k32.CloseHandle(snap)
        return out

    def hung(self):
        """True when Windows marks the game's window "not responding" (no messages for 5 s)."""
        found = []
        proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def cb(hwnd, _):
            pid = wt.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.pid and u32.IsWindowVisible(hwnd):
                found.append(bool(u32.IsHungAppWindow(hwnd)))
            return True
        u32.EnumWindows(proto(cb), 0)
        return any(found) if found else None

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not addr or not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
            return None
        return buf.raw[: got.value] if got.value == size else None

    def u32(self, addr):
        b = self.read(addr, 4)
        return int.from_bytes(b, "little") if b else None


class ThreadWatch:
    """How busy each of the game's threads is (read-only: QueryThreadCycleTime). The main thread is
    the oldest; the others are named by where they started (module+offset, e.g. the texture loader
    FalloutNV+...). A hitch with the main thread at 100% is computation (scripts, AI, physics); one
    with it idle is waiting (disk, a lock, the GPU)."""

    def __init__(self, proc):
        self.proc, self.mhz = proc, cpu_mhz()
        self.th = {}                    # tid -> [handle, label, created, last cycles]
        self.mods, self.last_t = [], None

    def label(self, h):
        addr = ctypes.c_void_p()
        if ntdll.NtQueryInformationThread(h, 9, ctypes.byref(addr), ctypes.sizeof(addr), None) != 0 or not addr.value:
            return "?"
        a = addr.value
        for base, end, name in self.mods:
            if base <= a < end:
                return "%s+0x%X" % (name, a - base)
        return "0x%08X" % a

    def refresh(self):
        tids = set(self.proc.thread_ids())
        for tid in list(self.th):
            if tid not in tids:
                k32.CloseHandle(self.th.pop(tid)[0])
        new = [t for t in tids if t not in self.th]
        if new and not self.mods:
            self.mods = self.proc.modules()
        for tid in new:
            h = (k32.OpenThread(THREAD_QUERY_INFO | THREAD_QUERY_LIMITED, False, tid)
                 or k32.OpenThread(THREAD_QUERY_LIMITED, False, tid))
            if not h:
                continue
            c, e, kt, ut = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
            k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
            self.th[tid] = [h, self.label(h), filetime(c), None]

    def sample(self):
        """{"main_cpu": % of one core, "threads": "label 97%, ..."} since the last call."""
        now = time.perf_counter()
        busy = []
        for tid, rec in self.th.items():
            cyc = ctypes.c_ulonglong()
            if not k32.QueryThreadCycleTime(rec[0], ctypes.byref(cyc)):
                continue
            if rec[3] is not None and self.last_t is not None:
                busy.append((cyc.value - rec[3], tid, rec[1]))
            rec[3] = cyc.value
        span, self.last_t = (now - self.last_t) if self.last_t else None, now
        if not busy or not span:
            return {}
        main = min(self.th, key=lambda t: self.th[t][2])
        pct = lambda c: round(100 * c / (self.mhz * 1e6 * span))   # noqa: E731
        out = {"main_cpu": next((pct(c) for c, t, _ in busy if t == main), 0)}
        top = sorted(busy, reverse=True)[:3]
        out["threads"] = ", ".join("%s %d%%" % ("main" if t == main else lbl, pct(c)) for c, t, lbl in top if pct(c) >= 5)
        return out


# The game's own structures (FalloutNV.exe 1.4.0.525, which has no ASLR: these addresses are fixed;
# offsets as xNVSE and JIP LN use them). Every read is checked before it is believed: the player
# must be form 00000014 and a cell must carry the cell form type, or the probe reports nothing.
PLAYER_PTR = 0x011DEA3C          # PlayerCharacter* g_thePlayer
REFR_POS, REFR_CELL = 0x30, 0x40  # TESObjectREFR: position (3 floats), parentCell
FORM_TYPE, FORM_ID = 0x04, 0x0C   # TESForm: typeID (byte), refID
CELL_TYPE = 0x39                  # kFormType_TESObjectCELL
CELL_NAME = 0x1C                  # TESObjectCELL's TESFullName string: char*, u16 length


def probe(proc):
    player = proc.u32(PLAYER_PTR)
    if not player or proc.u32(player + FORM_ID) != 0x14:
        return {}
    out = {}
    pos = proc.read(player + REFR_POS, 12)
    if pos:
        out["pos"] = [round(v) for v in struct.unpack("<3f", pos)]
    cell = proc.u32(player + REFR_CELL)
    head = proc.read(cell, 0x24) if cell else None
    if head and head[FORM_TYPE] == CELL_TYPE:
        out["cell_id"] = "%08X" % int.from_bytes(head[FORM_ID:FORM_ID + 4], "little")
        sp, ln = int.from_bytes(head[CELL_NAME:CELL_NAME + 4], "little"), int.from_bytes(head[0x20:0x22], "little")
        name = proc.read(sp, ln) if sp and 0 < ln < 128 else None
        out["cell"] = name.decode("latin1") if name else ""
    return out


# ---------------------------------------------------------------- the live recorder ---------------
SCRIPT_RE = re.compile(r"[Ss]cript '([^']+)'")
LINE_RE = re.compile(r"line (\d+)")
NUM = re.compile(r"\b(0x)?[0-9A-Fa-f]{6,8}\b|-?\d+(\.\d+)?")


def signature(line):
    return NUM.sub("#", line.strip())[:160]


class Tail:
    """New lines of one log since we last looked. A file that shrank was started over (a new launch)."""

    def __init__(self, path, since):
        self.path, self.pos, self.rest, self.locked = path, 0, b"", None
        try:
            st = path.stat()
            if st.st_mtime < since:        # last written before this launch: only what comes next
                self.pos = st.st_size
        except OSError:
            pass

    def lines(self):
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self.pos:
            self.pos, self.rest = 0, b""
        if size == self.pos:
            return []
        try:
            with open(self.path, "rb") as f:
                f.seek(self.pos)
                data = f.read(min(size - self.pos, 4 << 20))
        except PermissionError:          # the game holds falloutnv_error.log open with no sharing:
            self.locked = size           # only its size can be seen until it exits
            return []
        self.locked = None
        self.pos += len(data)
        data = self.rest + data
        parts = data.split(b"\n")
        self.rest = parts.pop()
        return [p.rstrip(b"\r").decode("latin1") for p in parts if p.strip()]


def classify(src, line):
    """(kind, detail) for a log line: the timeline keeps everything, the report reads the kinds."""
    s = line.strip()
    if src == "nvse.log":
        m = re.search(r"Do(PreLoad|Load|Save|NewGame)\w*Hook:?\s*(.*)", s)
        if m:
            return {"PreLoad": "loading", "Load": "loaded", "Save": "saved", "NewGame": "new game"}[m.group(1)], m.group(2)
        if re.search(r"Failed to precompile|failed to compile|error|exception", s, re.I) and "RegisterCommand" not in s:
            return "nvse error", s
        return "nvse", s
    if src == "falloutnv_error.log":
        m = SCRIPT_RE.search(s)
        return ("script error", m.group(1)) if m else ("engine", s)
    if src == "ConsoleLog.txt":
        if re.search(r"failed to compile|is off\b|not installed", s, re.I):
            return "mod health", s
        if re.search(r"Error in script|NULL reference|statement failed", s):
            return "script error", s
        return "console", s
    if src in ("CrashLogger.log",) or src.startswith("Crash Logs"):
        return "crash", s
    return "log", s


def session_dir(started):
    return SESSIONS / started.strftime("%Y-%m-%d_%H%M%S")


PRESENTMON_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "fnv-tools" / "presentmon"

# The flight recorder's tiers (2026-11-18). Fine detail when something is likely to happen or just
# did; a light snapshot the rest of the time; raw data only around incidents.
ACTIVE_START_S = 600     # the first 10 minutes of a launch: fine detail
ACTIVE_BURST_S = 120     # and 2 minutes after a load, save, interior change, hang or hitch burst
RING_S = 180             # raw frames and samples kept in memory (the black box)
POST_S = 30              # an incident's raw record runs this long past its trigger
FLUSH_S = 60             # buffered output goes to disk once a minute (and on incidents and exit)
SAMPLE_S = {"active": 1.0, "passive": 10.0}
VA_S = {"active": 10.0, "passive": 60.0}
TAIL_S = {"active": 1.0, "passive": 5.0}
HITCH_MS = 50.0
BURST = (3, 10.0)        # 3 hitches within 10 s make a hitch burst
ERRLOG_FLOOD_KB = 20     # the error log growing this much within 10 s is an error flood
MAX_INCIDENTS = 30
HIST_STEP = 0.5          # frame-time histogram bins (ms), to 500 ms


def process_alive(pid):
    h = k32.OpenProcess(QUERY_LIMITED, False, pid)
    if not h:
        return False
    code = wt.DWORD()
    alive = bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
    k32.CloseHandle(h)
    return alive


def stop_trace_sessions(only=None, keep=None):
    """Stop Windows trace sessions this recorder started (named FNVEngineWatch...). Ending PresentMon
    forcibly leaves its session running with nobody reading it, which keeps the graphics event
    providers on for every frame of every program and starves new sessions (2026-11-18: three such
    orphans made later captures return nothing)."""
    try:
        q = subprocess.run(["logman", "query", "-ets"], capture_output=True, text=True, timeout=20,
                           creationflags=0x08000000).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    names = [l.split()[0] for l in q.splitlines() if l.strip().startswith("FNVEngineWatch")]
    stopped = []
    for n in names:
        if (only and n != only) or (keep and n == keep):
            continue
        # a sweep (no `only`) stops a session only when the game it records is gone: a session named
        # after a process that is still running belongs to a live recorder (2026-11-18: a test
        # recorder's sweep stopped the real game's session)
        if not only:
            tail = n.rsplit("_", 1)[-1]
            if tail.isdigit() and process_alive(int(tail)):
                continue
        try:
            subprocess.run(["logman", "stop", n, "-ets"], capture_output=True, timeout=20, creationflags=0x08000000)
            stopped.append(n)
        except (OSError, subprocess.SubprocessError):
            pass
    return stopped


class FrameFeed:
    """Intel PresentMon on a pipe (no CSV on disk): every frame of the game goes into a ring of the
    last RING_S seconds, a frame-time histogram, per-second stats and a list of hitches. PresentMon
    needs admin rights or "Performance Log Users" membership (from the next sign-in)."""

    def __init__(self, pid, note, out=None):
        import threading
        self.lock = threading.Lock()
        self.last_frame = time.time()            # wall time of the newest frame (for the watchdog)
        self.lost = 0                            # ETW events PresentMon reported lost
        self.ring = collections.deque()          # (epoch, ms, cpu busy, gpu busy)
        self.hist = collections.Counter()
        self.secs = {}                           # epoch second -> [n, sum, max, >25, >50]
        self.hitches = []                        # (epoch, ms)
        self.frames = 0
        self.offset = None
        self.ok = False
        exes = sorted(PRESENTMON_DIR.glob("PresentMon-*.exe"))
        if not exes:
            note("frames: PresentMon not found in %s, so no frame times this session" % PRESENTMON_DIR)
            return
        stale = stop_trace_sessions(keep="FNVEngineWatch_%d" % pid)   # leftovers from a recorder cut short
        if stale:
            note("frames: stopped leftover trace session(s) %s" % ", ".join(stale))
        self.session = "FNVEngineWatch_%d" % pid
        self.pm = subprocess.Popen(
            [str(exes[-1]), "--process_id", str(pid), "--output_stdout", "--no_console_stats", "--date_time",
             "--v2_metrics", "--terminate_on_proc_exit", "--session_name", "FNVEngineWatch_%d" % pid, "--stop_existing_session"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            creationflags=0x08000000 | 0x00004000)        # no window, below normal priority
        time.sleep(3)
        if self.pm.poll() is not None:
            why = (self.pm.stderr.read() or "").strip().splitlines()
            note("frames: PresentMon stopped at once (%s)" % (why[-1] if why else "exit %s" % self.pm.returncode))
            return
        self.ok = True
        threading.Thread(target=self.read, daemon=True).start()
        # PresentMon's warnings go to stderr. Nobody read it before 2026-11-18: its few-KB pipe filled
        # with "N ETW events were lost" lines and PresentMon blocked on the next one, so frames
        # stopped 45 s into a session. Now it is drained into presentmon.log.
        threading.Thread(target=self.drain, args=(out,), daemon=True).start()

    def drain(self, out):
        log = open(out / "presentmon.log", "a", encoding="utf-8") if out else None
        written = 0
        for line in self.pm.stderr:
            m = re.search(r"(\d+) ETW events were lost", line)
            if m:
                self.lost += int(m.group(1))
            if log and written < 200:            # the first 200 lines, then only the count
                log.write(dt.datetime.now().strftime("%H:%M:%S ") + line)
                log.flush()
                written += 1

    def read(self):
        cols = None
        for line in self.pm.stdout:
            parts = line.rstrip("\n").split(",")
            if cols is None:
                cols = {c.lstrip("﻿"): i for i, c in enumerate(parts)}
                continue
            try:
                stamp = parts[cols["CPUStartDateTime"]]
                ms = float(parts[cols["FrameTime"]])
                cpu = float(parts[cols["CPUBusy"]]) if parts[cols["CPUBusy"]] != "NA" else -1
                gpu = float(parts[cols["GPUBusy"]]) if parts[cols["GPUBusy"]] != "NA" else -1
                d, tm = stamp.split(" ")
                h, m, s = tm.split(":")
                t = dt.datetime.strptime(d, "%Y-%m-%d").timestamp() + int(h) * 3600 + int(m) * 60 + float(s)
            except (KeyError, ValueError, IndexError):
                continue
            if self.offset is None:              # PresentMon's clock isn't local time: align it once
                self.offset = round((time.time() - t) / 1800) * 1800
            t += self.offset
            self.last_frame = time.time()
            with self.lock:
                self.frames += 1
                self.ring.append((t, ms, cpu, gpu))
                while self.ring and self.ring[0][0] < t - RING_S:
                    self.ring.popleft()
                self.hist[min(int(ms / HIST_STEP), int(500 / HIST_STEP))] += 1
                b = self.secs.setdefault(int(t), [0, 0.0, 0.0, 0, 0])
                b[0] += 1
                b[1] += ms
                b[2] = max(b[2], ms)
                b[3] += ms > 25
                b[4] += ms > HITCH_MS
                if ms > HITCH_MS:
                    self.hitches.append((t, ms))

    def take_seconds(self, before):
        """Per-second stats for every whole second before `before`, removed from memory."""
        with self.lock:
            done = sorted(k for k in self.secs if k < int(before))
            return [(k, self.secs.pop(k)) for k in done]

    def raw(self, t0, t1):
        with self.lock:
            return [f for f in self.ring if t0 <= f[0] <= t1]

    def burst(self, now):
        with self.lock:
            recent = [h for h in self.hitches if h[0] >= now - BURST[1]]
        return len(recent) >= BURST[0]

    def stop(self, wait=15):
        if getattr(self, "pm", None) and self.pm.poll() is None:
            try:
                self.pm.wait(wait)               # it may end itself when the game does
            except subprocess.TimeoutExpired:
                self.pm.terminate()
        if getattr(self, "session", None):      # and its trace session always goes with it
            stop_trace_sessions(self.session)


def histogram_stats(hist):
    n = sum(hist.values())
    if not n:
        return {}
    out, acc = {}, 0
    for b in sorted(hist):
        acc += hist[b]
        for q, name in ((0.5, "median_ms"), (0.99, "p99_ms"), (0.999, "p999_ms")):
            if name not in out and acc >= q * n:
                out[name] = round((b + 0.5) * HIST_STEP, 1)
    return out


def live(pid=None, wait=True, summary_wait=120):
    if pid is None:
        while wait and find_pid() is None:
            time.sleep(5)
        pid = find_pid()
        if pid is None:
            sys.exit("the game is not running")
    # one recorder per game process (fnv_watch.ps1 starts one; a second, started by hand, leaves)
    mutex = k32.CreateMutexW(None, False, "Local\\FNVEngineWatch_%d" % pid)   # noqa: F841 (held)
    if ctypes.get_last_error() == 183:             # ERROR_ALREADY_EXISTS
        return
    import gzip
    proc = Proc(pid)
    out = session_dir(proc.started)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "recorder.log", "a", encoding="utf-8")
    faulthandler.enable(log)                   # even a hard crash of the recorder leaves a trace
    seen_errors = set()

    def note(text):
        key = text.strip().splitlines()[-1] if text.strip() else text
        if key not in seen_errors:             # each distinct error once
            seen_errors.add(key)
            log.write("%s %s\n" % (dt.datetime.now().strftime("%H:%M:%S"), text))
            log.flush()

    # Windows' background mode for the recorder: its CPU, disk and memory use always yield to the game
    if not k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00100000):        # PROCESS_MODE_BACKGROUND_BEGIN
        note("could not enter background mode (error %d); recording at normal priority" % ctypes.get_last_error())
    marker = out / "live.json"
    meta = {"pid": pid, "started": proc.started.isoformat(timespec="seconds"), "recorder": "engine_watch flight recorder"}
    feed = FrameFeed(pid, note, out)
    restarts = 0
    next_sweep = time.time() + 120
    meta["frames"] = "recording" if feed.ok else "unavailable (recorder.log)"
    marker.write_text(json.dumps(meta, indent=1))
    since = proc.started.timestamp() - 5
    tails = {n: Tail(GAME / n, since) for n in TAILED}
    counted = {n: Tail(GAME / n, since) for n in COUNTED}
    crash_dir = GAME / "Crash Logs"
    seen_crashes = {p.name for p in crash_dir.glob("*.log")} if crash_dir.exists() else set()
    cols = ["t", "mode", "fg", "private_mb", "ws_mb", "va_used_mb", "va_largest_free_mb", "handles", "threads",
            "cpu_s", "proc_cpu", "main_cpu", "busy_threads", "read_mb_s", "reads_s", "write_mb_s", "faults_s",
            "hung", "havok_lines", "errlog_kb", "cell", "cell_id", "x", "y", "z"]
    tw = ThreadWatch(proc)
    saves_dir = SESSIONS.parent / "Saves"
    last_save_mb = None
    month_log = SESSIONS / ("engine_watch_%s.jsonl" % dt.date.today().strftime("%Y-%m"))

    # buffered output, written once a minute
    buf = {"timeline": [], "samples": [], "seconds": [], "minutes": []}
    events = collections.deque()                # recent timeline events (for incidents)
    sample_ring = collections.deque()
    counts = collections.Counter()              # routine lines kept only as counts

    def flush():
        if buf["timeline"]:
            with open(out / "timeline.jsonl", "a", encoding="utf-8") as f:
                f.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in buf["timeline"])
        if buf["samples"]:
            new = not (out / "samples.csv").exists()
            with open(out / "samples.csv", "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, cols, extrasaction="ignore")
                if new:
                    w.writeheader()
                w.writerows(buf["samples"])
        if buf["seconds"]:
            with open(out / "seconds.jsonl", "a", encoding="utf-8") as f:
                f.writelines(json.dumps(s) + "\n" for s in buf["seconds"])
        if buf["minutes"]:
            with open(month_log, "a", encoding="utf-8") as f:
                f.writelines(json.dumps(m) + "\n" for m in buf["minutes"])
        for k in buf:
            buf[k] = []

    def emit(ev):
        buf["timeline"].append(ev)
        events.append((time.time(), ev))
        while events and events[0][0] < time.time() - RING_S - POST_S:
            events.popleft()

    # incidents: a cause, when it started, and when its raw record closes
    incident = None
    incidents_written = 0
    last_closed = {}                            # cause -> when its last incident was saved
    repeats = collections.Counter()             # triggers folded into an earlier incident

    def trigger(cause, now, always=False):
        nonlocal incident, active_until
        active_until = max(active_until, now + ACTIVE_BURST_S)
        if incidents_written >= MAX_INCIDENTS and not always:
            return
        # the same cause again while the last incident's raw minutes are still in the ring: counted, not
        # saved again (a long bad stretch would otherwise save the same minutes over and over)
        if incident is None and not always and cause not in ("hang", "crash log") and \
                now - last_closed.get(cause, -1e9) < RING_S:
            repeats[cause] += 1
            return
        if incident is None:
            incident = {"first": now, "close": now + POST_S, "causes": [cause]}
        else:                                    # one incident while triggers keep coming (to 5 min)
            incident["close"] = min(max(incident["close"], now + POST_S), incident["first"] + 300)
            if cause not in incident["causes"]:
                incident["causes"].append(cause)

    def write_incident(now):
        nonlocal incident, incidents_written
        for c in incident["causes"]:
            last_closed[c] = now
        t0 = incident["first"] - RING_S
        rec = {"from": dt.datetime.fromtimestamp(t0).strftime("%H:%M:%S"),
               "trigger": dt.datetime.fromtimestamp(incident["first"]).strftime("%H:%M:%S"),
               "to": dt.datetime.fromtimestamp(now).strftime("%H:%M:%S"), "causes": incident["causes"],
               "frames": [[round(f[0] - t0, 3), round(f[1], 2), round(f[2], 2), round(f[3], 2)] for f in feed.raw(t0, now)],
               "samples": [s for ts, s in sample_ring if ts >= t0],
               "events": [e for ts, e in events if ts >= t0]}
        with gzip.open(out / "incidents.jsonl.gz", "at", encoding="utf-8") as f:   # one gzip member each
            f.write(json.dumps(rec) + "\n")
        incidents_written += 1
        incident = None
        flush()

    t_start = time.time()
    active_until = t_start + ACTIVE_START_S
    mode = "active"
    last_cell, last_name, hung_since = None, None, None
    next_tail = next_sample = next_va = 0.0
    next_flush = t_start + FLUSH_S
    va, probing = {}, True
    errlog_hist = collections.deque()
    minute = {"n": 0}
    prev = None                                 # the last sample's counters, for per-second rates
    unfocused = set()                           # whole seconds the game didn't have the focus
    while not proc.exited():
        now = time.time()
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        try:
            if not proc.focused():
                unfocused.add(int(now))
        except Exception:
            pass
        new_mode = "active" if now < active_until else "passive"
        if new_mode != mode:
            mode = new_mode
            emit({"t": stamp, "src": "watch", "kind": "mode", "msg": mode, "n": 1})
        try:
            if now >= next_tail:
                next_tail = now + TAIL_S[mode]
                for name, t in tails.items():
                    groups = collections.OrderedDict()
                    for line in t.lines():
                        kind, _ = classify(name, line)
                        if kind == "nvse":                       # routine registration lines: a count
                            counts[name] += 1
                            continue
                        key = (kind, signature(line))
                        if key in groups:
                            groups[key]["n"] += 1
                        else:
                            groups[key] = {"t": stamp, "src": name, "kind": kind, "msg": line[:400], "n": 1}
                    for ev in groups.values():
                        emit(ev)
                        if ev["kind"] in ("loading", "loaded", "saved", "new game"):
                            active_until = max(active_until, now + ACTIVE_BURST_S)
                        if ev["kind"] == "saved":            # save bloat makes saves and loads slower
                            try:
                                newest = max(saves_dir.glob("*.fos"), key=lambda f: f.stat().st_mtime)
                                mb = newest.stat().st_size / 1048576
                                emit({"t": stamp, "src": "watch", "kind": "save size", "n": 1,
                                      "msg": "%s: %.1f MB%s" % (newest.stem[:60], mb, "" if last_save_mb is None
                                                                else " (%+.1f MB)" % (mb - last_save_mb))})
                                last_save_mb = mb
                            except (ValueError, OSError):
                                pass
                if crash_dir.exists():
                    for p in crash_dir.glob("*.log"):
                        if p.name not in seen_crashes:
                            seen_crashes.add(p.name)
                            emit({"t": stamp, "src": "Crash Logs", "kind": "crash", "msg": p.name, "n": 1})
                            trigger("crash log", now)
        except Exception:
            note(traceback.format_exc())
        try:
            # frames: per-second stats (per 10 s while passive), hitches, bursts
            if feed.ok:
                for sec, (n, total, worst, o25, o50) in feed.take_seconds(now - 3):   # frames arrive ~2 s late
                    if mode == "active" or not buf["seconds"] or sec - buf["seconds"][-1]["s"] >= 10:
                        buf["seconds"].append({"s": sec, "t": dt.datetime.fromtimestamp(sec).strftime("%H:%M:%S"),
                                               "n": n, "avg": round(total / n, 2), "max": round(worst, 1),
                                               "o25": o25, "o50": o50, "mode": mode})
                    else:                                    # passive: fold into the last 10 s row
                        r = buf["seconds"][-1]
                        r["avg"] = round((r["avg"] * r["n"] + total) / (r["n"] + n), 2)
                        r["n"] += n
                        r["max"] = max(r["max"], round(worst, 1))
                        r["o25"] += o25
                        r["o50"] += o50
                    if o50:
                        emit({"t": dt.datetime.fromtimestamp(sec).strftime("%H:%M:%S"), "src": "frames",
                              "kind": "hitch", "msg": "%d frame(s) over %d ms, worst %.0f ms" % (o50, HITCH_MS, worst), "n": o50})
                    minute["n"] += n
                    minute["sum"] = minute.get("sum", 0) + total
                    minute["max"] = max(minute.get("max", 0), worst)
                    minute["o50"] = minute.get("o50", 0) + o50
                focused_now = not ({int(now), int(now) - 1, int(now) - 2} & unfocused)
                if focused_now and feed.burst(now) and (incident is None or "hitch burst" not in incident["causes"]):
                    trigger("hitch burst", now)
            if now >= next_sample:
                next_sample = now + SAMPLE_S[mode]
                row = {"t": stamp, "mode": mode, "fg": int(int(now) not in unfocused), **proc.counters()}
                if now >= next_va:
                    next_va = now + VA_S[mode]
                    va = proc.address_space()
                    tw.refresh()
                    row["threads"] = len(tw.th)
                row.update(va)
                row.update({("busy_threads" if k == "threads" else k): v for k, v in tw.sample().items()})
                if prev:
                    span = max(1e-3, now - prev["now"])
                    row["read_mb_s"] = round((row["_read"] - prev["_read"]) / 1048576 / span, 1)
                    row["reads_s"] = round((row["_reads"] - prev["_reads"]) / span)
                    row["write_mb_s"] = round((row["_write"] - prev["_write"]) / 1048576 / span, 1)
                    row["faults_s"] = round((row["_faults"] - prev["_faults"]) / span)
                    row["proc_cpu"] = round(100 * (row["cpu_s"] - prev["cpu_s"]) / span)
                prev = {"now": now, **{k: row[k] for k in ("_read", "_reads", "_write", "_faults", "cpu_s")}}
                h = proc.hung()
                row["hung"] = int(bool(h))
                if h and hung_since is None:
                    hung_since = now
                    emit({"t": stamp, "src": "watch", "kind": "hang", "msg": "window stopped responding", "n": 1})
                    trigger("hang", now)
                elif not h and hung_since is not None:
                    emit({"t": stamp, "src": "watch", "kind": "hang end",
                          "msg": "responding again after %d s" % (now - hung_since), "n": 1})
                    hung_since = None
                row["havok_lines"] = sum(len(t.lines()) for t in counted.values())
                try:                     # the error log is locked while the game runs: its growth shows floods
                    kb = (GAME / "falloutnv_error.log").stat().st_size >> 10
                    row["errlog_kb"] = kb
                    errlog_hist.append((now, kb))
                    while errlog_hist and errlog_hist[0][0] < now - 10:
                        errlog_hist.popleft()
                    if kb - errlog_hist[0][1] >= ERRLOG_FLOOD_KB:
                        trigger("error flood", now)
                        errlog_hist.clear()
                except OSError:
                    pass
                if probing:
                    try:
                        p = probe(proc)
                    except Exception:              # never let a probe stop the recording
                        p, probing = {}, False
                    if p:
                        row.update({"cell": p.get("cell", ""), "cell_id": p.get("cell_id", "")})
                        if "pos" in p:
                            row["x"], row["y"], row["z"] = p["pos"]
                        if p.get("cell_id") and p.get("cell_id") != last_cell:
                            last_cell = p["cell_id"]
                            emit({"t": stamp, "src": "game", "kind": "cell",
                                  "msg": "%s [%s]" % (p.get("cell") or "exterior", p["cell_id"]), "n": 1})
                            if p.get("cell") and p.get("cell") != last_name:   # an interior: a load
                                active_until = max(active_until, now + ACTIVE_BURST_S)
                            last_name = p.get("cell")
                row = {k: v for k, v in row.items() if not k.startswith("_")}
                buf["samples"].append(row)
                sample_ring.append((now, row))
                while sample_ring and sample_ring[0][0] < now - RING_S - POST_S:
                    sample_ring.popleft()
                minute.update({k: row.get(k) for k in ("private_mb", "va_used_mb", "va_largest_free_mb", "cell", "cell_id")})
                minute["k"] = minute.get("k", 0) + 1
                minute["read"] = minute.get("read", 0) + (row.get("read_mb_s") or 0) * SAMPLE_S[mode]
                minute["main"] = max(minute.get("main", 0), row.get("main_cpu") or 0)
            if (minute["n"] or minute.get("k")) and int(now // 60) != minute.get("m", int(now // 60)):
                fps = 1000 * minute["n"] / minute["sum"] if minute.get("sum") else None
                buf["minutes"].append({"session": out.name, "t": dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),
                                       "fps": round(fps, 1) if fps else None, "worst_ms": round(minute.get("max", 0), 1),
                                       "hitches": minute.get("o50", 0), "private_mb": minute.get("private_mb"),
                                       "va_used_mb": minute.get("va_used_mb"), "va_free_mb": minute.get("va_largest_free_mb"),
                                       "read_mb": round(minute.get("read", 0)), "main_cpu_max": minute.get("main"),
                                       "cell": minute.get("cell") or minute.get("cell_id")})
                minute = {"n": 0}
            minute["m"] = int(now // 60)
            if incident and now >= incident["close"]:
                write_incident(now)
            # the frame feed's watchdog: the game has the focus but no frame came for 30 s
            if feed.ok and hung_since is None and now - feed.last_frame > 30 \
                    and not ({int(now) - k for k in range(30)} & unfocused) \
                    and restarts < 5:
                restarts += 1
                emit({"t": stamp, "src": "watch", "kind": "frames", "n": 1,
                      "msg": "no frames for 30 s with the game in focus: PresentMon restarted (%d)" % restarts})
                note("frames: stalled for 30 s; restarting PresentMon (%d, %d events lost so far)" % (restarts, feed.lost))
                lost = feed.lost
                feed.stop(wait=0)
                with feed.lock:
                    keep = (feed.ring, feed.hist, feed.secs, feed.hitches, feed.frames)
                feed = FrameFeed(pid, note, out)
                feed.ring, feed.hist, feed.secs, feed.hitches, feed.frames = keep
                feed.lost += lost
            # leftover trace sessions of earlier recorders starve PresentMon: sweep them
            if now >= next_sweep:
                next_sweep = now + 120
                swept = stop_trace_sessions(keep="FNVEngineWatch_%d" % pid)
                if swept:
                    note("frames: stopped leftover trace session(s) %s" % ", ".join(swept))
            if now >= next_flush:
                next_flush = now + FLUSH_S
                flush()
        except Exception:                      # log it and keep recording: one bad sample
            note(traceback.format_exc())       # must not cost the whole session
        time.sleep(0.5)
    exit_seen = time.time()
    code = proc.exit_code()
    feed.stop()
    ended = dt.datetime.now()
    trigger("exit", exit_seen, always=True)   # the black box: the last minutes before the exit
    time.sleep(8)                                 # the crash logger and the game finish writing
    stamp = ended.strftime("%H:%M:%S")
    for name, t in tails.items():              # what is left, including the error log the game kept
        groups = collections.OrderedDict()     # locked: no times for those lines, so grouped
        for line in t.lines():
            kind, _ = classify(name, line)
            if kind == "nvse":
                counts[name] += 1
                continue
            key = (kind, signature(line))
            if key in groups:
                groups[key]["n"] += 1
            else:
                groups[key] = {"t": stamp, "src": name, "kind": kind, "msg": line[:400], "n": 1, "untimed": True}
        for ev in groups.values():
            emit(ev)
    emit({"t": stamp, "src": "watch", "kind": "exit", "msg": "0x%08X %s" % (code, EXIT_CODES.get(code, "")), "n": 1})
    write_incident(time.time())
    flush()
    meta.update({"ended": ended.isoformat(timespec="seconds"), "exit_code": code, "incidents": incidents_written,
                 "repeat_triggers": dict(repeats), "frame_feed_restarts": restarts, "etw_events_lost": feed.lost,
                 "routine_lines": dict(counts), "frames_total": feed.frames,
                 "frame_stats": histogram_stats(feed.hist),
                 "frame_hist": {str(k): v for k, v in sorted(feed.hist.items())},
                 "unfocused_s": len(unfocused),
                 "hitch_times": [[dt.datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:12], round(ms, 1),
                                  int(int(t) not in unfocused)] for t, ms in feed.hitches]})
    marker.write_text(json.dumps(meta, indent=1))
    for _ in range(int(summary_wait // 5)):       # fnv_watch.ps1 copies the logs: wait for its summary
        s = out / "summary.txt"
        if s.exists() and s.stat().st_mtime >= exit_seen - 60:
            break
        time.sleep(5)
    report(out)
    history()


# ---------------------------------------------------------------- the report ----------------------
def read_text(session, name):
    for p in (session / name, session / name.replace("/", "_"), session / ("logs_" + Path(name).name)):
        if p.exists():
            return p.read_text(encoding="latin1", errors="replace")
    return ""


def our_scripts():
    """{prefix/file: path} for every user-defined function in this repo."""
    out = {}
    for p in (ROOT / "src").glob("*/nvse/user_defined_functions/*/*.txt"):
        out["%s/%s" % (p.parent.name, p.name)] = p
    return out


def plugins(session):
    return [l.strip().lstrip("*") for l in read_text(session, "plugins.txt").splitlines()
            if l.strip() and not l.startswith("#")]


def load_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(row, *keys):
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except ValueError:
                pass
    return None


def near_place(samples, hhmmss):
    """The cell from the sample nearest a time of day."""
    best, where = None, ""
    try:
        t = dt.datetime.strptime(hhmmss[:8], "%H:%M:%S")
    except ValueError:
        return ""
    for x in samples:
        if not (x.get("cell") or x.get("cell_id")) or not x.get("t"):
            continue
        d = abs((dt.datetime.strptime(x["t"], "%H:%M:%S") - t).total_seconds())
        if best is None or d < best:
            best, where = d, x.get("cell") or x.get("cell_id")
    return where if best is not None and best <= 10 else ""


def classify_incident(rec):
    """What most likely made an incident, from the raw minutes around its trigger (within 5 s):
    loading or saving (the engine's own pause), disk streaming (the game reading over 15 MB/s),
    the main thread at full load (scripts, AI, physics), an error flood, a hang."""
    try:
        trig = dt.datetime.strptime(rec["trigger"], "%H:%M:%S")
    except (KeyError, ValueError):
        return []

    def near(t, before=5, after=5):
        try:
            d = ((dt.datetime.strptime(t[:8], "%H:%M:%S") - trig).total_seconds() + 43200) % 86400 - 43200
        except ValueError:
            return False
        return -before <= d <= after

    kinds = {e.get("kind") for e in rec.get("events", []) if near(e.get("t", ""), 10, 5)}
    rows = [x for x in rec.get("samples", []) if near(x.get("t", ""))]
    reads = max((x.get("read_mb_s") or 0 for x in rows), default=0)
    main = max((x.get("main_cpu") or 0 for x in rows), default=0)
    out = []
    if kinds & {"loading", "loaded", "new game"}:
        out.append("loading")
    if "saved" in kinds:
        out.append("saving")
    if "cell" in kinds and not out:
        out.append("cell change")
    if reads >= 15:
        out.append("disk streaming (%.0f MB/s)" % reads)
    if main >= 90 and not out:
        out.append("main thread at full load (scripts, AI or physics)")
    for c in rec.get("causes", []):
        if c in ("error flood", "hang", "crash log") and c not in out:
            out.append(c)
    return out or ["unclear (see the raw minutes)"]


def played_min(meta, frames_total, median_ms):
    """Minutes the game ran with the focus (falls back to frames x median frame time)."""
    try:
        span = (dt.datetime.fromisoformat(meta["ended"]) - dt.datetime.fromisoformat(meta["started"])).total_seconds()
        return max(1e-9, (span - meta.get("unfocused_s", 0)) / 60)
    except (KeyError, ValueError):
        return max(1e-9, frames_total * (median_ms or 16.7) / 60000)


def recorded_frames(session, samples):
    """Frames as the flight recorder keeps them: the session's histogram and hitch list (live.json),
    and its incidents (incidents.jsonl.gz: the raw minutes around each burst, hang, flood or exit)."""
    import gzip
    f = session / "live.json"
    meta = json.loads(f.read_text()) if f.exists() else {}
    st = meta.get("frame_stats") or {}
    if not st:
        return {}
    hits = [h for h in meta.get("hitch_times", []) if len(h) < 3 or h[2]]
    stamps = [dt.datetime.strptime(h[0], "%H:%M:%S.%f") for h in hits]
    gaps = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:])]
    near = [g for g in gaps if 0.5 < g < 30 and abs(g - round(g)) < 0.04]
    total = meta.get("frames_total", 0)
    med = st.get("median_ms")
    incidents = []
    inc = session / "incidents.jsonl.gz"
    if inc.exists():
        with gzip.open(inc, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                worst = max((fr[1] for fr in rec.get("frames", [])), default=0)
                over = sum(fr[1] > HITCH_MS for fr in rec.get("frames", []))
                likely = classify_incident(rec)
                landmarks = [e["kind"] + " " + e["msg"][:60] for e in rec.get("events", [])
                             if e.get("kind") in ("loading", "loaded", "saved", "cell", "hang", "crash")][:4]
                incidents.append({"trigger": rec["trigger"], "from": rec["from"], "to": rec["to"],
                                  "causes": rec["causes"], "likely": likely, "worst_ms": round(worst, 1), "hitches": over,
                                  "where": near_place(samples, rec["trigger"]), "around": landmarks})
    return {"frames": total, "median_ms": med, "fps_median": round(1000 / med, 1) if med else None,
            "p99_ms": st.get("p99_ms"), "hitch_limit_ms": HITCH_MS, "hitches": len(hits),
            "hitches_per_min": round(len(hits) / played_min(meta, total, med), 2) if total else 0,
            "whole_second_share": round(len(near) / len(gaps), 2) if gaps else None,
            "worst": [{"t": h[0], "ms": h[1], "where": near_place(samples, h[0])} for h in sorted(hits, key=lambda h: -h[1])[:15]],
            "incidents": incidents}


def frames(session, samples):
    """Frame-time summary from PresentMon's frames.csv: typical and worst frames, hitches with when and
    where they happened, and whether they repeat once a second (the mark of a timed script)."""
    f = session / "frames.csv"
    if not f.exists():
        return recorded_frames(session, samples)
    times, ms = [], []
    with open(f, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            v = row.get("FrameTime") or row.get("MsBetweenPresents") or row.get("msBetweenPresents")
            t = row.get("CPUStartDateTime") or row.get("CPUStartTime") or row.get("TimeInSeconds")
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            ms.append(v)
            times.append(t)
    if len(ms) < 100:
        return {"frames": len(ms)}
    srt = sorted(ms)
    med = srt[len(srt) // 2]
    worst1 = srt[int(len(srt) * 0.99)]
    limit = max(50.0, 2.5 * med)
    def parse(t):                          # "2026-11-18 3:57:30.991534700": unpadded hour, nanoseconds
        try:
            d, tm = t.split(" ")
            h, m, sec = tm.split(":")
            whole, _, frac = sec.partition(".")
            return dt.datetime.strptime("%s %02d:%s:%s.%s" % (d, int(h), m, whole, (frac + "000000")[:6]), "%Y-%m-%d %H:%M:%S.%f")
        except (ValueError, AttributeError):
            return None
    first = next((parse(t) for t in times if t and parse(t)), None)
    try:                                   # PresentMon's clock isn't local time: align to the session start
        start = dt.datetime.strptime(session.name, "%Y-%m-%d_%H%M%S")
        shift = dt.timedelta(seconds=round((start - first).total_seconds() / 1800) * 1800) if first else dt.timedelta(0)
    except ValueError:
        shift = dt.timedelta(0)
    when = []
    for t, v in zip(times, ms):
        if v > limit:
            stamp = parse(t)
            stamp = stamp + shift if stamp else None
            when.append((stamp, v))
    # where: the sample (every 2 s) nearest each hitch
    place = {}
    for srow in samples:
        if srow.get("cell") or srow.get("cell_id"):
            place[srow["t"]] = srow.get("cell") or srow.get("cell_id")
    def where(stamp):
        if not stamp or not place:
            return ""
        key = min(place, key=lambda k: abs((dt.datetime.strptime(k, "%H:%M:%S") -
                                            stamp.replace(year=1900, month=1, day=1, microsecond=0)).total_seconds()))
        return place[key]
    # once a second? the share of gaps between hitches that are within 40 ms of a whole second
    stamps = sorted(s for s, _ in when if s)
    gaps = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:])]
    near = [g for g in gaps if 0.5 < g < 30 and abs(g - round(g)) < 0.04]
    periodic = round(len(near) / len(gaps), 2) if gaps else None
    top = sorted(when, key=lambda w: -w[1])[:15]
    return {"frames": len(ms), "median_ms": round(med, 1), "fps_median": round(1000 / med, 1) if med else None,
            "p99_ms": round(worst1, 1), "hitch_limit_ms": round(limit, 1), "hitches": len(when),
            "hitches_per_min": round(len(when) / max(1e-9, sum(ms) / 60000), 2),
            "whole_second_share": periodic,
            "worst": [{"t": s.strftime("%H:%M:%S.%f")[:12] if s else "?", "ms": round(v, 1), "where": where(s)} for s, v in top]}


def report(session):
    session = Path(session)
    meta = json.loads((session / "live.json").read_text()) if (session / "live.json").exists() else {}
    timeline = []
    if (session / "timeline.jsonl").exists():
        for l in (session / "timeline.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                timeline.append(json.loads(l))
            except ValueError:
                pass
    samples = load_csv(session / "samples.csv") or load_csv(session / "memory.csv")
    errlog, nvse, console = read_text(session, "falloutnv_error.log"), read_text(session, "nvse.log"), read_text(session, "ConsoleLog.txt")
    summary = read_text(session, "summary.txt")
    ours = our_scripts()
    our_names = {Path(k).stem for k in ours}
    r = {"session": session.name, "recorded_live": bool(timeline)}

    # how it ended
    # fnv_watch.ps1 copies crash logs from a minute before the launch: a crash log from before this
    # session started belongs to the session before
    files = [p for p in sorted(session.glob("Crash_Logs_CrashLogger.*.log"))
             if p.name[23:33].replace("-", "") + p.name[34:42].replace("-", "") >= session.name.replace("-", "").replace("_", "")]
    crashes = [crash_report.parse(p) for p in files]
    for c, p in zip(crashes, files):
        c["file"] = p.name
        c["while_closing"] = "LdrShutdownProcess" in p.read_text(encoding="latin1", errors="replace")
    code = meta.get("exit_code")
    if code is not None:
        ending = EXIT_CODES.get(code, "exit code 0x%08X" % code)
    elif "Exit: CRASH" in summary:
        ending = "crash"
    else:
        ending = "normal (no crash recorded)" if summary else "unknown"
    real = [c for c in crashes if not c["while_closing"]]
    if real:
        ending = "crash: %s at %s+%s" % (real[-1]["kind"], *real[-1]["top"])
    r["ending"], r["exit_code"], r["crashes"] = ending, code, crashes
    m = re.search(r"session (\S+ \S+) -> (\S+)\s+\((\d+) min\)", summary)
    r["minutes"] = int(m.group(3)) if m else None
    if meta.get("started") and meta.get("ended"):
        r["minutes"] = round((dt.datetime.fromisoformat(meta["ended"]) - dt.datetime.fromisoformat(meta["started"])).total_seconds() / 60)

    # memory
    mem = {}
    if samples:
        col = lambda *k: [v for v in (num(s, *k) for s in samples) if v is not None]   # noqa: E731
        priv, va, free = col("private_mb"), col("va_used_mb", "virtual_mb"), col("va_largest_free_mb")
        mem = {"peak_private_mb": max(priv) if priv else None, "peak_address_space_mb": max(va) if va else None,
               "smallest_largest_free_mb": min(free) if free else None,
               "last": {k: v for k, v in samples[-1].items() if v not in ("", None)}}
        timed = [(dt.datetime.strptime(x["t"], "%H:%M:%S"), num(x, "private_mb")) for x in samples
                 if x.get("t") and num(x, "private_mb") is not None]
        if len(timed) > 30:                     # after the first quarter of the session: warm-up
            (t0, p0), (t1, p1) = timed[len(timed) // 4], timed[-1]
            hours = ((t1 - t0).total_seconds() % 86400) / 3600
            if hours > 0.05:
                mem["private_growth_mb_per_hour"] = round((p1 - p0) / hours)
    r["memory"] = mem

    # script errors: from the timeline when recorded live (with times), else counted from the log
    errs = collections.OrderedDict()
    if timeline:
        for ev in timeline:
            if ev["kind"] == "script error" and ev["src"] == "falloutnv_error.log":
                name = SCRIPT_RE.search(ev["msg"]).group(1)
                t0 = None if ev.get("untimed") else ev["t"]
                e = errs.setdefault(name, {"count": 0, "first": t0, "last": t0, "example": ev["msg"], "lines": set()})
                e["count"] += ev.get("n", 1)
                if t0:
                    e["first"] = e["first"] or t0
                    e["last"] = t0
                e["lines"].update(LINE_RE.findall(ev["msg"]))
    else:
        for l in errlog.splitlines():
            mm = SCRIPT_RE.search(l)
            if mm:
                e = errs.setdefault(mm.group(1), {"count": 0, "example": l.strip(), "lines": set()})
                e["count"] += 1
                e["lines"].update(LINE_RE.findall(l))
    for name, e in errs.items():
        rt = re.match(r"nvseRuntimeScript\d+(\w+)$", name)
        cands = [k for k in ours if Path(k).stem == rt.group(1)] if rt else []
        e["ours"] = bool(cands)
        e["candidates"] = cands
        e["lines"] = sorted(e["lines"], key=int)[:12]
    r["script_errors"] = sorted(({"script": k, **v} for k, v in errs.items()), key=lambda e: -e["count"])

    # nvse.log and console errors
    nv = collections.Counter(re.sub(r"\b[0-9A-F]{8}\b", "#", l.strip()) for l in nvse.splitlines()
                             if re.search(r"Error in script|Failed to precompile|statement failed|exception", l, re.I))
    r["nvse_errors"] = [{"line": k, "count": v} for k, v in nv.most_common(12)]
    seen, health = set(), []
    for l in console.splitlines():
        if re.search(r"failed to compile|is off\b|not installed", l, re.I) and l.strip() not in seen:
            seen.add(l.strip())
            health.append(l.strip())
    r["mod_health"] = health

    # deploy drift: our scripts the game never precompiled, or precompiled but gone from the repo
    pre = set()
    for mm in re.finditer(r"user_defined_functions/([^\\/]+)[\\/]([^\s\\/]+\.txt)", nvse):
        pre.add("%s/%s" % (mm.group(1), mm.group(2)))
    prefixes = {k.split("/")[0] for k in ours}
    if pre:
        r["not_precompiled"] = sorted(k for k in ours if k not in pre)
        r["stale_in_game"] = sorted(k for k in pre if k.split("/")[0] in prefixes and k not in ours)
    else:
        r["not_precompiled"] = r["stale_in_game"] = []

    # the timeline's landmarks and last two minutes
    if timeline:
        keep = {"loading", "loaded", "saved", "new game", "cell", "hang", "hang end", "crash", "exit", "mod health", "nvse error"}
        r["landmarks"] = [ev for ev in timeline if ev["kind"] in keep][-60:]
        end = timeline[-1]["t"]
        endt = dt.datetime.strptime(end, "%H:%M:%S")
        r["last_two_minutes"] = [ev for ev in timeline if not ev.get("untimed") and
                                 (endt - dt.datetime.strptime(ev["t"], "%H:%M:%S")).total_seconds() % 86400 <= 120][-80:]
        r["hangs"] = [ev for ev in timeline if ev["kind"] in ("hang", "hang end")]
    r["frames"] = frames(session, samples)
    if timeline:
        loads_t, pending = [], None
        for ev in timeline:
            if ev["kind"] == "loading":
                pending = ev
            elif ev["kind"] == "loaded" and pending:
                d = (dt.datetime.strptime(ev["t"], "%H:%M:%S") - dt.datetime.strptime(pending["t"], "%H:%M:%S")).total_seconds() % 86400
                loads_t.append({"t": pending["t"], "seconds": int(d), "save": ev["msg"][-60:]})
                pending = None
        r["load_times"] = loads_t
        r["save_sizes"] = [{"t": ev["t"], "msg": ev["msg"]} for ev in timeline if ev["kind"] == "save size"]
    loads = len(re.findall(r"DoLoadGameHook", nvse))
    r["saves_loaded"] = loads

    # plugins changed since the session before
    earlier = sorted(p for p in SESSIONS.iterdir() if p.is_dir() and p.name < session.name and not p.name.startswith("_"))
    if earlier:
        a, b = plugins(earlier[-1]), plugins(session)
        if a and b:
            r["plugins_added"] = [p for p in b if p not in a]
            r["plugins_removed"] = [p for p in a if p not in b]
            r["compared_with"] = earlier[-1].name

    (session / "report.json").write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
    (session / "report.md").write_text(render(r), encoding="utf-8")
    return r


def render(r):
    L = ["# New Vegas session %s" % r["session"], ""]
    L.append("**Ended:** %s%s" % (r["ending"], "  (%s min)" % r["minutes"] if r.get("minutes") is not None else ""))
    L.append("")
    if not r["recorded_live"]:
        L += ["_Recorded before Engine Watch, or without it: counts only, no times or places._", ""]
    for c in r["crashes"]:
        L.append("- crash log `%s`: %s, %s+%s, thread %s, at %s%s%s" % (
            c["file"], c["kind"], c["top"][0], c["top"][1], c["thread"], c["where"],
            "; objects: " + c["classes"] if c["classes"] else "", " (while the game was closing: harmless)" if c["while_closing"] else ""))
        if c["overlays"]:
            L.append("  - overlays injected: " + ", ".join(c["overlays"]))
    m = r["memory"]
    if m:
        L += ["", "## Memory (32-bit: 4096 MB of address space)", ""]
        L.append("- peak address space used: %s MB; peak private: %s MB" % (m.get("peak_address_space_mb"), m.get("peak_private_mb")))
        if m.get("smallest_largest_free_mb") is not None:
            w = m["smallest_largest_free_mb"]
            L.append("- smallest \"largest free block\": %d MB%s" % (w, "  **low: large allocations (textures, cells) may fail**" if w < 256 else ""))
        if m.get("private_growth_mb_per_hour") is not None:
            L.append("- private memory trend after warm-up: %+d MB/hour" % m["private_growth_mb_per_hour"])
    if r.get("hangs"):
        L += ["", "## Hangs", ""] + ["- %s %s" % (e["t"], e["msg"]) for e in r["hangs"]]
    if r.get("last_two_minutes"):
        L += ["", "## The last two minutes", "", "```"]
        for e in r["last_two_minutes"]:
            L.append("%s %-14s %s%s" % (e["t"], e["kind"][:14], e["msg"][:150], "  (x%d)" % e["n"] if e.get("n", 1) > 1 else ""))
        L.append("```")
    ours = [e for e in r["script_errors"] if e["ours"]]
    other = [e for e in r["script_errors"] if not e["ours"]]
    if ours:
        L += ["", "## Script errors in our scripts", ""]
        for e in ours:
            L.append("- **%s** x%d%s: candidates %s" % (e["script"], e["count"],
                     " (%s to %s)" % (e["first"], e["last"]) if e.get("first") else "", ", ".join(e["candidates"])))
            L.append("  - `%s`%s" % (e["example"][:160], "  (script lines %s)" % ", ".join(e["lines"]) if e["lines"] else ""))
    if other:
        L += ["", "## Script errors in other mods or the base game", ""]
        for e in other[:12]:
            L.append("- %s x%d%s: `%s`" % (e["script"], e["count"], " (%s to %s)" % (e["first"], e["last"]) if e.get("first") else "",
                                           e["example"][:140]))
    if r["mod_health"] or r["not_precompiled"] or r["stale_in_game"]:
        L += ["", "## Mod health", ""]
        L += ["- " + h for h in r["mod_health"]]
        if r["not_precompiled"]:
            L.append("- in the repo but never precompiled by the game (not deployed yet, or it failed): " + ", ".join(r["not_precompiled"]))
        if r["stale_in_game"]:
            L.append("- precompiled by the game but no longer in the repo (a stale deploy): " + ", ".join(r["stale_in_game"]))
        L.append("- _(compared with the repo as it is now)_")
    if r["nvse_errors"]:
        L += ["", "## nvse.log errors", ""] + ["- x%d `%s`" % (e["count"], e["line"][:160]) for e in r["nvse_errors"]]
    if r.get("landmarks"):
        L += ["", "## Landmarks", "", "```"]
        L += ["%s %-10s %s" % (e["t"], e["kind"][:10], e["msg"][:150]) for e in r["landmarks"]]
        L.append("```")
    if r.get("plugins_added") or r.get("plugins_removed"):
        L += ["", "## Plugins changed since %s" % r["compared_with"], ""]
        L += ["- added: " + p for p in r["plugins_added"]] + ["- removed: " + p for p in r["plugins_removed"]]
    fr = r.get("frames") or {}
    if fr.get("median_ms"):
        L += ["", "## Frames (PresentMon)", ""]
        L.append("- %d frames; median %.1f ms (%.0f fps); 1%% of frames over %.1f ms" % (fr["frames"], fr["median_ms"], fr["fps_median"], fr["p99_ms"]))
        L.append("- hitches (over %.0f ms): %d, %.1f a minute" % (fr["hitch_limit_ms"], fr["hitches"], fr["hitches_per_min"]))
        if fr.get("whole_second_share") is not None:
            L.append("- share of gaps between hitches that are whole seconds: %.0f%%%s" % (
                100 * fr["whole_second_share"], "  **a once-a-second pattern: a timed script is the likely cause**" if fr["whole_second_share"] >= 0.4 else ""))
        if fr["worst"]:
            L += ["", "```"] + ["%s %7.1f ms  %s" % (w["t"], w["ms"], w["where"]) for w in fr["worst"]] + ["```"]
        if fr.get("incidents"):
            L += ["", "### Incidents (raw minutes kept in incidents.jsonl.gz)", ""]
            for i in fr["incidents"]:
                L.append("- %s (%s to %s): %s; likely: %s; worst frame %.0f ms, %d hitches%s%s" % (
                    i["trigger"], i["from"], i["to"], ", ".join(i["causes"]), ", ".join(i.get("likely") or ["?"]),
                    i["worst_ms"], i["hitches"],
                    "; at " + i["where"] if i["where"] else "", "; around: " + "; ".join(i["around"]) if i["around"] else ""))
    if r.get("load_times") or r.get("save_sizes"):
        L += ["", "## Loads and saves", ""]
        L += ["- loaded at %s in %d s: %s" % (x["t"], x["seconds"], x["save"]) for x in r.get("load_times", [])]
        L += ["- saved at %s: %s" % (x["t"], x["msg"]) for x in r.get("save_sizes", [])]
    L += ["", "Saves loaded: %d" % r["saves_loaded"], ""]
    return "\n".join(L)


def history():
    rows = []
    for d in sorted(p for p in SESSIONS.iterdir() if p.is_dir() and not p.name.startswith("_")):
        f = d / "report.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text(encoding="utf-8"))
        top = next((e for e in r["script_errors"] if e["ours"]), None)
        rows.append("| %s | %s | %s | %s | %s | %s |" % (
            d.name, r.get("minutes") or "", r["ending"][:60], (r["memory"] or {}).get("peak_address_space_mb", ""),
            (r["memory"] or {}).get("smallest_largest_free_mb", "") or "",
            "%s x%d" % (top["script"], top["count"]) if top else ""))
    text = ["# New Vegas sessions", "", "| session | min | ended | peak VA MB | min free block MB | top error in our scripts |",
            "|---|---|---|---|---|---|"] + rows[::-1]
    (SESSIONS / "history.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    return text


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lv = sub.add_parser("live")
    lv.add_argument("--pid", type=int)
    lv.add_argument("--out", help="session root (default: SessionLogs); for testing")
    lv.add_argument("--summary-wait", type=float, default=120)
    lv.add_argument("--test-tiers", action="store_true", help="seconds-long tiers, for testing the recorder")
    rp = sub.add_parser("report")
    rp.add_argument("session", nargs="?")
    rp.add_argument("--all", action="store_true")
    sub.add_parser("history")
    a = ap.parse_args()
    global SESSIONS
    if getattr(a, "out", None):
        SESSIONS = Path(a.out)
    if a.cmd == "live" and a.test_tiers:
        global ACTIVE_START_S, ACTIVE_BURST_S, RING_S, POST_S, FLUSH_S
        ACTIVE_START_S, ACTIVE_BURST_S, RING_S, POST_S, FLUSH_S = 8, 6, 15, 3, 5
    if a.cmd == "live":
        try:
            live(a.pid, summary_wait=a.summary_wait)
        except BaseException:                  # pythonw has no console: keep the reason somewhere
            SESSIONS.mkdir(parents=True, exist_ok=True)
            with open(SESSIONS / "_engine_watch_errors.log", "a", encoding="utf-8") as f:
                f.write("%s\n%s\n" % (dt.datetime.now().isoformat(timespec="seconds"), traceback.format_exc()))
            raise
    elif a.cmd == "report":
        dirs = sorted(p for p in SESSIONS.iterdir() if p.is_dir() and not p.name.startswith("_")) if a.all else [Path(a.session)]
        for d in dirs:
            r = report(d if d.is_absolute() or d.exists() else SESSIONS / d)
            print("%s  %-50s %s" % (r["session"], r["ending"][:50], ", ".join("%s x%d" % (e["script"], e["count"]) for e in r["script_errors"] if e["ours"])[:90]))
        history()
    else:
        print("\n".join(history()))


if __name__ == "__main__":
    main()
