# Feasibility: four systems (2026-11-17)

Research only, nothing built yet. Each section: what the engine and the installed script
extenders allow, a recommended design, and the risks. Command availability was checked against
this setup's xNVSE, JIP LN, JohnnyGuitar and ShowOff registrations (nvse.log).

## 1. A shoulder-mounted 5.56 gun (apparel)

**Engine limits.** An actor holds one weapon. There is no command here that spawns a projectile
from a point (JIP and JohnnyGuitar can edit projectiles, and JIP has a fire-weapon *event*, but
nothing creates one). The vanilla `FireWeapon` command makes a creature or NPC fire a weapon it
doesn't hold; whether it works on the player has to be tested in game.

**Options, best first.**
1. *Player fires it:* the apparel item (a shoulder mount) and a hotkey or "fire with your gun"
   setting; each shot calls `player.FireWeapon` with a 5.56 weapon form of our own (damage and
   spread like a light machine gun), takes a 5.56 round from your inventory and a slice of a
   fission battery (Fission Power). Cheap and clean if `FireWeapon` works on the player.
2. *A drone:* an invisible, unaggressive helper actor holding the 5.56 weapon, kept at your
   shoulder every frame and pointed at your target with JIP `ForceCombatTarget`. Works with what's
   installed, but the helper can lag or snag on scenery, and it needs a "no model" actor.
3. Either way the visible mount needs a model (a NIF attached to a shoulder bone): an asset to
   make or borrow from a mod whose author allows it.

**Weight and power** are easy: the apparel's weight, ammo used per shot, and a battery drain per
shot through Fission Power, scaled against the suit's draw.

**Recommendation:** a 10-minute in-game test of `player.FireWeapon` first. If it works, option
1 is a small build plus the model question.

## 2. VATS auto-queue

**Engine limits.** Nothing exposes the VATS shot queue or the per-part hit chances. The only lever
is simulating the buttons VATS already understands (xNVSE `TapControl`), timed with
`CallAfterSeconds`, while the VATS menu is open. JohnnyGuitar gives the weapon's damage per shot
(via its DPS) and the target's health is readable.

**Design.** On VATS opening (menu open event) the game already targets the nearest enemy: count
the shots to kill it (its health divided by your weapon's damage, rounded up, plus one more when
your skill or the distance makes misses likely) and tap "queue a shot" that many times, a few
frames apart, stopping when action points run out. Pressing A on another enemy does the same for
that one. B is VATS's own cancel and still clears everything.

**Risks.** Simulated presses inside menus are timing-sensitive, and VATS is where the game has
frozen before (the Mysterious Stranger hang); the VATS rescue in Wasteland Tweaks stays as the
safety net. Hit chance is estimated, not read. Needs in-game tuning.

**Recommendation:** feasible as an option in Wasteland Tweaks, off by default, built and then
tuned with you in game.

## 3. Power armor nutrient paste and water

**Engine limits.** Fine: new aid items can be made in a plugin (copied from vanilla food with
new effects), the recipe menu can be read and changed (JIP recipe commands), and Smart Loot's
auto-consume already uses whatever food and water you carry.

**Design.**
- *Nutrient Paste:* a new aid item, weightless per point of hunger compared with real food.
- *At a campfire:* when the recipe menu opens at a campfire, a prompt offers "turn all food
  into paste": every food item (not drinks, not chems) becomes paste by the hunger it restores.
- *The suit's dispenser:* while you wear power armor (Fission Power), paste and purified water
  go into the suit's reservoirs instead of your pockets, the suit counts a dispenser's weight,
  and Hardcore auto-consume draws from the reservoirs first. The dispenser runs off the battery.

**Recommendation:** buildable as a Fission Power addition; a medium build.

## 4. Hand-loaded magazines

**Design.** Rounds the game counts as "in your inventory" become the rounds in three magazines
per kind of ammo; the rest live in a pouch (a hidden container, its weight added back so carry
weight stays honest). Out of combat, a loader moves one round a second from the pouch into the
magazines, starting with the kind in your weapon, until each kind has three full magazines. In
combat you can fire and reload through those three magazines and nothing more; after that you
hand-load. Smart Loot pickups and the bank's top-ups go into the pouch.

**Engine limits.** No hard blocker: it's ammo counts moved by script on a timer, plus a menu to
see the pouch. The pouch's weight needs a token item whose weight tracks it.

**Risks.** It changes every gun's feel and touches Smart Loot, the bank and Fission Power, so it
wants its own setting and careful testing.

**Recommendation:** feasible; a large build. Do it after the smaller ones above.
