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
import datetime as dt
import json
import os
import re
import struct
import sys
import time
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
SAMPLE_S, VA_EVERY, TAIL_S = 2.0, 5, 1.0   # samples every 2 s, address-space walk every 5th

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
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]


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
        return {"private_mb": pmc.PrivateUsage >> 20, "ws_mb": pmc.WorkingSetSize >> 20,
                "handles": hc.value, "cpu_s": round((filetime(kt) + filetime(ut)) / 1e7, 1)}

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
        self.path, self.pos, self.rest = path, 0, b""
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
        with open(self.path, "rb") as f:
            f.seek(self.pos)
            data = f.read(min(size - self.pos, 4 << 20))
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


def live(pid=None, wait=True, summary_wait=120):
    if pid is None:
        while wait and find_pid() is None:
            time.sleep(5)
        pid = find_pid()
        if pid is None:
            sys.exit("the game is not running")
    proc = Proc(pid)
    out = session_dir(proc.started)
    out.mkdir(parents=True, exist_ok=True)
    marker = out / "live.json"
    meta = {"pid": pid, "started": proc.started.isoformat(timespec="seconds"), "recorder": "engine_watch live"}
    marker.write_text(json.dumps(meta, indent=1))
    since = proc.started.timestamp() - 5
    tails = {n: Tail(GAME / n, since) for n in TAILED}
    counted = {n: Tail(GAME / n, since) for n in COUNTED}
    crash_dir, seen_crashes = GAME / "Crash Logs", set()
    if crash_dir.exists():
        seen_crashes = {p.name for p in crash_dir.glob("*.log")}
    timeline = open(out / "timeline.jsonl", "a", encoding="utf-8")
    samples = open(out / "samples.csv", "a", newline="", encoding="utf-8")
    cols = ["t", "private_mb", "ws_mb", "va_used_mb", "va_largest_free_mb", "handles", "threads", "cpu_s",
            "hung", "havok_lines", "cell", "cell_id", "x", "y", "z"]
    writer = csv.DictWriter(samples, cols, extrasaction="ignore")
    if samples.tell() == 0:
        writer.writeheader()

    def emit(ev):
        timeline.write(json.dumps(ev, ensure_ascii=False) + "\n")

    last_cell, hung_since, n, next_sample, va = None, None, 0, 0.0, {}
    probing = True
    while not proc.exited():
        now = time.time()
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        for name, t in tails.items():
            groups = collections.OrderedDict()
            for line in t.lines():
                kind, detail = classify(name, line)
                key = (kind, signature(line))
                if key in groups:
                    groups[key]["n"] += 1
                else:
                    groups[key] = {"t": stamp, "src": name, "kind": kind, "msg": line[:400], "n": 1}
            for ev in groups.values():
                emit(ev)
        if crash_dir.exists():
            for p in crash_dir.glob("*.log"):
                if p.name not in seen_crashes:
                    seen_crashes.add(p.name)
                    emit({"t": stamp, "src": "Crash Logs", "kind": "crash", "msg": p.name, "n": 1})
        if now >= next_sample:
            next_sample = now + SAMPLE_S
            row = {"t": stamp, **proc.counters()}
            if n % VA_EVERY == 0:
                va = proc.address_space()
                row["threads"] = proc.threads()
            row.update(va)
            h = proc.hung()
            row["hung"] = int(bool(h))
            if h and hung_since is None:
                hung_since = now
                emit({"t": stamp, "src": "watch", "kind": "hang", "msg": "window stopped responding", "n": 1})
            elif not h and hung_since is not None:
                emit({"t": stamp, "src": "watch", "kind": "hang end",
                      "msg": "responding again after %d s" % (now - hung_since), "n": 1})
                hung_since = None
            row["havok_lines"] = sum(len(t.lines()) for t in counted.values())
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
            writer.writerow(row)
            n += 1
            if n % 15 == 0:
                timeline.flush()
                samples.flush()
        time.sleep(TAIL_S)
    code = proc.exit_code()
    ended = dt.datetime.now()
    time.sleep(8)                                 # the crash logger and the game finish writing
    stamp = ended.strftime("%H:%M:%S")
    for name, t in tails.items():
        for line in t.lines():
            kind, _ = classify(name, line)
            emit({"t": stamp, "src": name, "kind": kind, "msg": line[:400], "n": 1})
    emit({"t": stamp, "src": "watch", "kind": "exit", "msg": "0x%08X %s" % (code, EXIT_CODES.get(code, "")), "n": 1})
    timeline.close()
    samples.close()
    meta.update({"ended": ended.isoformat(timespec="seconds"), "exit_code": code})
    marker.write_text(json.dumps(meta, indent=1))
    for _ in range(int(summary_wait // 5)):       # fnv_watch.ps1 copies the logs: wait for its summary
        s = out / "summary.txt"
        if s.exists() and s.stat().st_mtime >= ended.timestamp() - 2:
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
        if len(priv) > 60:
            step = SAMPLE_S if (session / "samples.csv").exists() else 10      # fnv_watch.ps1 samples every 10 s
            q = len(priv) // 4                                                   # after the first quarter: warm-up
            mem["private_growth_mb_per_hour"] = round((priv[-1] - priv[q]) / ((len(priv) - q) * step / 3600))
    r["memory"] = mem

    # script errors: from the timeline when recorded live (with times), else counted from the log
    errs = collections.OrderedDict()
    if timeline:
        for ev in timeline:
            if ev["kind"] == "script error" and ev["src"] == "falloutnv_error.log":
                name = SCRIPT_RE.search(ev["msg"]).group(1)
                e = errs.setdefault(name, {"count": 0, "first": ev["t"], "last": ev["t"], "example": ev["msg"], "lines": set()})
                e["count"] += ev.get("n", 1)
                e["last"] = ev["t"]
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
        r["last_two_minutes"] = [ev for ev in timeline
                                 if (endt - dt.datetime.strptime(ev["t"], "%H:%M:%S")).total_seconds() % 86400 <= 120][-80:]
        r["hangs"] = [ev for ev in timeline if ev["kind"] in ("hang", "hang end")]
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
    rp = sub.add_parser("report")
    rp.add_argument("session", nargs="?")
    rp.add_argument("--all", action="store_true")
    sub.add_parser("history")
    a = ap.parse_args()
    global SESSIONS
    if getattr(a, "out", None):
        SESSIONS = Path(a.out)
    if a.cmd == "live":
        live(a.pid, summary_wait=a.summary_wait)
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
