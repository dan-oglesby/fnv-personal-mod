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
- Status: built; needs in-game testing. Success looks like no 0xA61A74 crashes over several sessions; the Engine Watch history makes that easy to see.
