# Performance: stutter from our own scripts (2026-11-18)

## What was wrong

**Every timer fired in the same frame.**
- Every mod's loader runs in the same frame when a save loads.
- A repeating timer registered there fires one interval later.
- xNVSE resets a timer's clock to "now" each time it fires (Hooks_Gameplay.cpp,
  HandleCallWhilePerSecondsScripts), so timers with the same interval stay in step at a steady
  frame rate.

The result was that every once-a-second script of every mod ran in one frame, every second, for
the whole session. `tools/timer_slots.py` measured it: **up to 16 of our scripts in one frame,
11 of them heavy**, every 10 seconds when the slow timers lined up, and 14–15 in the other
seconds. That is a regular hitch.

## What changed

1. **Slots.** Each timer now starts at its own offset within the second:
   - `CallAfterSeconds <offset> rStart 1 rTick rTrue <interval> <flags>`, where `rStart` is the
     mod's `<Prefix>/Start.txt`, which calls CallWhilePerSeconds;
   - `timer_slots.py --assign` places the heaviest and most frequent timers first, each where it
     collides least;
   - heavy once-a-second timers are 75 ms apart (4–5 frames at 60 fps), and the slow heavy ones sit
     in the otherwise empty half of the second.

   Now **no 25 ms slot holds more than two timers, and never two heavy ones**. Every load starts
   the pattern over. Frozen timers (menus, pause) keep their phase.
2. **The rule is enforced.** `check_scripts.py` runs `timer_slots.check()` on every build. Each of
   these fails it:
   - a `CallWhilePerSeconds`, `CallWhile` or `CallForSeconds` outside a Start.txt that isn't
     marked `; slot: exempt (why)`;
   - two heavy timers sharing a slot;
   - more than two timers in a slot.

   A new timer gets its slot from `python tools/timer_slots.py --suggest <interval> heavy|light`.
3. **Weights.**
   - A timer is heavy when its script, or the scripts it calls, scans inventories or the
     references around the player, or has several loops.
   - A script that is cheap until something is active says so: `; slot weight: light (why)`. The
     bank's squad, collector and caravan ticks return at once while nothing is out, and Smart
     Loot's 0.25 s check only looks at your position and crosshair.
4. **Smart Loot.** A timed loot pass is skipped when the quick check started one less than half a
   second before. While you walk, the two used to run full scans of the area back to back.
5. **Monocyte Limb Regen.** Its once-a-second timer was an inline function. It is now
   MonocyteRegen/Tick.txt, so it can be slotted.

Exempt, with reasons written beside them:
- Target Readout's typewriter runs every frame but returns at once unless a readout is typing.
- Perk Bank's watcher runs every frame, only while the perk menu is open.

## Measuring it

Engine Watch records every frame with Intel PresentMon. That needs membership in "Performance Log
Users", which takes effect at the next sign-in. Each session's report.md then shows:
- the median and 1%-low frame times;
- hitches (over 50 ms or 2.5× the median) per minute;
- the worst hitches with their time and cell;
- the share of gaps between hitches that are whole seconds. A high share is the mark of a timed
  script. A test with synthetic once-a-second hitches gave 100%; random hitches gave 4%.

The plan is one session before these changes (the current deploy) and one after, compared.

## Still to look at
- The error floods: the Fission Power suit script's errors (about 5,000 in a long session, each a
  disk write from the main thread) and VFSVaporizationVolumeSCRIPT's failed StartCombat (6,350).
- The display settings: 1176×664 with 4× anti-aliasing, and DXVK with an empty dxvk.conf.
