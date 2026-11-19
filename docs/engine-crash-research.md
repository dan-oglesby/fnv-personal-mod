# Engine crash research: New Vegas's texture-streaming crash

Notes toward fixing the most common crash in this load order. Everything here was established
from the game's own unencrypted data, the open-source plugins' headers (JIP LN NVSE, xNVSE) and
Crash Logger output, without decrypting or modifying the game.

## The crash
In one load order, 10 of 20 crashes (2026-11-14 to 2026-11-17) were the same:

- faulting address `FalloutNV.exe+0xA61A74`, return address `0x43C4E0`, then `0x43C1BB`;
- on the background loader (`BSTaskManagerThread`) and sometimes the main thread;
- with `QueuedTexture`, `IOManager` and often an NPC's generated body texture
  (`textures\characters\bodymods\<plugin>\<npc id>modbody*.dds`) or landscape textures on the stack.

`tools/crash_report.py` groups crash logs this way.

## What the code is
- FalloutNV.exe 1.4.0.525 (Steam) has no ASLR (image base `0x400000`), so addresses are stable. Its
  `.text` section is encrypted on disk (Steam's DRM wrapper, `.bind` section; entropy 8.0), so the
  code can't be disassembled from the file. `.rdata` is plain, and vtables can be read from it.
- `QueuedTexture` (JIP `GameTasks.h`: a `QueuedFileEntry` task holding `niTexture` at `+0x30`, the
  file name at `+0x28` and BSA data at `+0x2C`) has its vtable at `0x1016788`. Read from `.rdata`:

  | slot | function | address |
  |---|---|---|
  | 0 | Destroy | `0x43BE30` |
  | 1 | Run | `0x43C150` |
  | 2 | Unk_02 | `0x43C550` |
  | 8 | DoRequestHandles | `0x43C050` |
  | 9 | DoOnChildrenFinished | `0x43BDE0` |
  | 10 | DoOnTaskFinished | `0xC3C930` |

- So the crash path is: task manager thread (`0xC3FC94`) → `QueuedTexture::Run` (`0x43C150`, return
  `0x43C1BB` inside it) → a helper between `0x43C150` and `0x43C550` (return `0x43C4E0`) → Gamebryo
  core at `0xA61A74` (near JIP's NiTArray methods `0xA65300` / `0xA66150`).

## Hypothesis
A use-after-free race: the main thread releases a texture (an NPC unloading, a cell detaching)
while a queued `QueuedTexture` task still points at it, and the loader thread then runs the task
on freed memory. It fits the two threads it happens on, the heavy-NPC places it happens in
(the Strip, Freeside, McCarran) and the generated body textures, which are per-NPC.

## Ideas, in order of safety
1. **Diagnose first**: an NVSE plugin that swaps `QueuedTexture`'s vtable `Run` slot (in `.rdata`,
   so no code bytes need to be known) for a wrapper that records the task's texture pointer,
   reference count and name, and re-raises any exception unchanged. Behaviour is identical, and the
   next crash says exactly which object was gone.
2. **Hold a reference**: if the texture's reference count is what drops to zero, have the wrapper
   (or the task's creation) hold a reference for the task's lifetime, so the texture can't be freed
   while a load is pending.
3. **Cancel instead of crash**: if a task's texture is already invalid when it runs, finish the task
   without loading. That needs the task's completion protocol, which needs the decrypted code.

Status: research; nothing here is shipped yet.

## 2026-11-18: the texture crash, read from the running game (tools/live_disasm.py)

**Where it crashes.** 0xA61A60 is a hash-map lookup that returns a reference-counted pointer:
- signature: `thiscall(map buckets; bucket index, key, NiPointer& out)`;
- it walks the chosen bucket's chain, where a node is {entry*, next} and an entry is {value, key};
- 0xA61A74 is `cmp edx,[esi+4]`, comparing the key of a chain node's entry.

**The path to it.** QueuedTexture::Run (0x43C150) → 0x43C4C0 → 0x43C4F0 → 0xA61A60.
- 0x43C4C0 sets out = NULL, then calls the lookup on the map whose pointer is at **0x011F4468**.
- 0x43C4F0 hashes the key as `(key >> 4) % 1001` (0x43C530).
- So the map has 1,001 buckets keyed by a pointer.

**The bug: one unguarded reader.** Fifteen instructions use 0x011F4468:
- Every function that changes the map (0xA61B90, A61C50, A61CD0, A61F30, A61FB0, A62030) first takes the engine's spin lock at **0x011F4480** (via 0x40FBF0, ecx = 0x11F4480).
- The task thread's lookup (0x43C4C0) takes no lock.
- So the main thread can free an entry while the task thread is walking past it. That is the use-after-free, and it is in the map's entries, not the texture object.

**The engine's lock (0x40FBF0):**
- [lock] = owner thread ID, taken with `InterlockedCompareExchange(lock, tid, 0)`;
- spins with Sleep(0), then Sleep(1) after 10,000 tries;
- [lock+4] = re-entry count, set to 1 on first entry;
- release (0xA61CB9): decrement the count; at 0, clear the owner.

**The fix: native/TextureMapLock (the Texture Map Lock mod).**
- It points the call at 0x43C4DB to a wrapper that takes the same lock around the lookup.
- It gives up after 50 ms and runs the lookup unlocked, as before, so the worst case is today's behaviour, never a deadlock.
- It patches only if all 50 bytes it relies on match. They were checked against the running game with the full plugin set, so no other plugin patches that site.
- It logs to TextureMapLock.log.
- Status (version 1): built and deployed 2026-11-18. Success looks like no 0xA61A74 crashes over several sessions; the Engine Watch history makes that easy to see.

## 2026-11-18 evening: the lock wasn't enough; others had found this crash

Two more 0xA61A74 crashes came at 19:07 (Freeside East Gate, 29 minutes in) and 19:18 (Wilderness,
11 minutes in), both through Texture Map Lock's wrapper (TextureMapLock+0x1108 on the stack). The
log showed no lock timeouts, so the lookup crashed while holding the lock.
- **Registers:** the stack held the bucket index the lookup computed, 0xFE for key 0x182D59CC and
  0x274 for 0x182D329C. Both match `(key >> 4) % 1001`. esi was the record being compared,
  0x0D2AA790 and 0x0D3BFA40, and neither was readable. So a chain entry still pointed at a record
  that had been freed. There was no race with a writer.
- **Known before us:**
  - NVAC (New Vegas Anti Crash, 2014-16, now considered obsolete) caught the access violation at
    00A61A74 and carried on.
  - Psycho Engine Fixes (github.com/acidpointer/psycho; `analysis/heap_analysis.md`, chapter "Texture
    Cache Hash Table", and `analysis/ghidra/output/crash/crash_00A61A74_bstask.txt`) worked out the
    structure. The texture cache never removes single entries, they outlive the textures they point
    to, and the game empties the cache only on worldspace changes. Their fix keeps a "dead set" of
    destroyed textures.
  - Their disassembly also confirms what the guard below relies on. 0x43C4F0 passes its `this` (the
    bucket array) to 0xA61A60 (`mov ecx,[ebp-8]` at 0x43C514). An entry is {record, next}, and the
    walk compares the key at record+4.
- **NVTF ruled out:** its `iReplaceTextureCreationLocks` (mode 1 here) only wraps the Direct3D
  texture critical sections at 0xE6DC4C, 0xE90B46 and 0xE90C91 (source:
  carxt/New-Vegas-Tick-Fix, `nvtf/internal/ThreadingTweaks.cpp`). It doesn't touch the cache's
  lock.

**Texture Map Lock version 2** keeps the lock and adds NVAC's guard, plus a repair:
- An access violation inside the walk (0xA61A60-0xA61AC7 only) is caught.
- Still holding the lock that every writer takes, it unlinks the faulting bucket's entries whose
  record can't be read, using guarded reads. The insert that follows a miss walks the same chain.
- It retries once. Failing that, it reports "not cached" and the texture loads from disk.
- Each catch is logged to TextureMapLock.log.
- No plugin in this setup installs a first-chance (vectored) exception handler. So the guard sees
  the fault before anything else, and Crash Logger, which uses the unhandled-exception filter, only
  ever sees real crashes.
- Not covered: a freed record whose memory has already been reused doesn't fault. The worldspace
  reset (0xA615C0) writes to every record, so a stale one is a hazard there too.
- A stand-alone test of the fault path couldn't run: Bitdefender removed the test program, which
  writes code to fixed addresses and faults on purpose. The guard will show itself in the game's
  log.
