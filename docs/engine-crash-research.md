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
