"""Disassemble New Vegas engine code from the running game, read-only, for crash research.

    python tools/live_disasm.py 0x43C150 0x43C550     # a range
    python tools/live_disasm.py --func 0xA61A74        # the whole function containing an address
    python tools/live_disasm.py --func 0xA61A74 --mark 0xA61A74

FalloutNV.exe's code is encrypted on disk (Steam's DRM wrapper) and only decrypted in memory while
the game runs, so this reads it from the running process: PROCESS_VM_READ and
PROCESS_QUERY_LIMITED_INFORMATION only (no write, no debug, no injection). The bytes are
disassembled in memory with capstone (pip install capstone) and printed. Nothing is written to
disk: no decrypted copy of the game is ever made. Start the game (the main menu is enough) first.

--func walks back from the address to the function's start (the int3 or nop padding the compiler
puts between functions, then the first instruction after it) and forward to its end (a ret
followed by padding).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import sys

import capstone

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


def find_pid(name="FalloutNV.exe"):
    arr = (wt.DWORD * 4096)()
    got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    for pid in arr[: got.value // 4]:
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(260)
        size = wt.DWORD(260)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        k32.CloseHandle(h)
        if ok and buf.value.lower().endswith("\\" + name.lower()):
            return pid
    return None


class Game:
    def __init__(self):
        pid = find_pid()
        if pid is None:
            sys.exit("FalloutNV.exe is not running: start the game (the main menu is enough)")
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not self.h:
            sys.exit("could not open the game read-only (error %d)" % ctypes.get_last_error())

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
            sys.exit("could not read %08X (error %d)" % (addr, ctypes.get_last_error()))
        return buf.raw[: got.value]


def func_bounds(game, addr):
    back = game.read(addr - 0x2000, 0x2000)
    i = len(back) - 1
    while i > 0 and not (back[i] in (0xCC, 0x90) and back[i - 1] in (0xCC, 0x90)):
        i -= 1
    while i < len(back) and back[i] in (0xCC, 0x90):
        i += 1
    start = addr - 0x2000 + i
    fwd = game.read(addr, 0x2000)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    end = addr + len(fwd)
    for ins in md.disasm(fwd, addr):
        if ins.mnemonic.startswith("ret"):
            nxt = ins.address + ins.size - addr
            if nxt + 1 < len(fwd) and fwd[nxt] in (0xCC, 0x90) and fwd[nxt + 1] in (0xCC, 0x90):
                end = ins.address + ins.size
                break
    return start, end


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?")
    ap.add_argument("end", nargs="?")
    ap.add_argument("--func")
    ap.add_argument("--mark", action="append", default=[])
    a = ap.parse_args()
    game = Game()
    if a.func:
        start, end = func_bounds(game, int(a.func, 16))
    else:
        start, end = int(a.start, 16), int(a.end, 16)
    marks = {int(m, 16) for m in a.mark}
    code = game.read(start, end - start)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    print("; %08X-%08X (%d bytes), read live from FalloutNV.exe" % (start, end, end - start))
    for ins in md.disasm(code, start):
        flag = "  <==" if ins.address in marks else ""
        print("%08X  %-8s %s%s" % (ins.address, ins.mnemonic, ins.op_str, flag))


if __name__ == "__main__":
    main()
