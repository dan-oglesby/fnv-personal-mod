# Fallout: New Vegas personal mods

Small personal mods for New Vegas, built on top of the stability base (Gopher's Stable New Vegas
collection in Vortex: xNVSE, JIP LN NVSE and friends). Quality of life, not cheats.

The stability setup these are built on (mod list with Nexus links, settings, things to avoid) is in
[STABILITY.md](STABILITY.md).

Each folder in `src/` mirrors the game's `Data` folder. `python build.py` zips each one into
`dist/` and stages a copy in Vortex's New Vegas staging folder (`%APPDATA%\Vortex\falloutnv\mods\<Mod Name>`),
so it shows up in Vortex's Mods list ready to enable and deploy (`--no-stage` for zips only).
Staged files are rewritten in place, so a mod Vortex has already deployed picks up a rebuild.

## Menu items instead of hotkeys

Wasteland Bank and Auto Smoke open their menus from an item, the way the original Bank Card did:
an apparel item with no body slot and no weight. Equip it from the Pip-Boy's Apparel tab; it takes
itself off again and the menu opens when you close the Pip-Boy. Each item is in a tiny plugin of
its own (`WastelandBank.esp`, `AutoSmoke.esp`; only master FalloutNV.esm) written by
`make_plugins.py`, which `build.py` runs. The plugins carry no scripts. The mods' xNVSE scripts
watch for the item being equipped (`OnActorEquip`), and give it to you on load if you don't have
it. The old hotkeys (K and L) are still in the `ln_` files, commented out.

| Mod | What it does | Needs | Status |
|---|---|---|---|
| Wasteland Bank | A rewrite of Bank Card (BankCard.esp, Nexus 39741, 2011) without its bugs. Equip the **Wasteland Bank Card** from the Pip-Boy's Apparel tab and the bank opens when you close the Pip-Boy, as with the original. Money has weight (about 4.7 lb per 1,000 caps), so cash moves only through a **courier squad** you call from the card: they arrive in 1 to 2 game hours, are essential, and handle deposits, withdrawals, conversion and loans for a 2 percent fee, plus a **vault** for storing anything at 1 cap a pound each way, casino chips exchanged at a cap each, and **selling for you** (all junk, or whatever you put in their consignment box: half the market value, less their 10 percent, paid into your balance a day later). Each squad carries 2,500 caps of your balance for withdrawals (order a larger sum a day ahead); exchange trades go through them; and they invest the NCR dollars you hand them in NCR War Bonds, or cash your bonds out as NCR notes delivered a day later. **Credit:** a score from repaying loans on time sets your grade (A to F), how much you can borrow (up to 25,000) and the weekly rate; loans are due in 30 days, overdue ones cost credit and let the bank take your balance, and two weeks late **debt collectors** come to take what you owe (pockets, vault caps, then your vault's best things at half value) or fight you for it. **Caravan ventures:** back a caravan run with a big stake and walk it to its destination yourself (it may be ambushed) for a high, certain return, or let it take its chances on the road. **Pay by bank card** at any merchant: your balance counts as spendable caps while you barter (carried caps go first; 1 percent on what comes from the bank). Couriers run up to you and run off again, and have no dialogue: activate one for their services. Goods go through the game's **Mojave Express dropboxes** instead (bank card, at any dropbox): the vault, ammo and supplies (top the weapon in hand up to 300, sell all or the excess over 500, buy up to 500; each visit tops up your ammo and aid from the vault; loose ammo reboxed for 5 percent), selling, and the catalogue. Menus show only what your wealth stage has opened. The **catalogue** takes orders for supplies and ammo, collected at any dropbox a day later (plan and later phases: `docs/wasteland-bank-couriers.md`). Deposit and withdraw caps with daily interest, take one loan at a time with weekly interest, convert NCR, Legion and pre-war money to caps, and optional auto-deposit (keeps a set amount on hand) and auto-convert. Includes the **Wasteland Exchange**: stocks on a New Vegas and an NCR (Hub) exchange, with dividends, reinvestment, short selling and prices that react to your quests. | xNVSE 6.2.8+, JIP LN 56.95+. Enable `WastelandBank.esp` | Built 2026-11-11, untested in play. Don't run it alongside BankCard.esp |
| After the Dam | Play goes on after the ending. When the end slides finish, instead of fading to the credits and quitting, the game puts things back (saving, your controls, the companions who were with you) and you wake on the road by Boulder City, at the developers' own unused post-game start. The world doesn't otherwise change. Pairs with Wasteland Bank's Dam papers. Don't use it with another post-ending mod. | xNVSE, JIP LN. Scripts only, no plugin | Built 2026-11-17, untested in play |
| Mojave Heat | The Wasteland has a temperature: time of day (coolest about 6 AM, hottest about 3 PM), region (the Strip, Goodsprings, the Colorado River, Jacobstown, Black Mountain, the DLC areas), weather (cloud, rain, storms, fallout) and interiors (caves, sewers, vaults hold steady and cool). In Hardcore, heat over 85F makes you thirsty faster, about double at the 104F Mojave peak; running and combat add to it, rain eases it, powered power armor cools you. Waits, sleep and fast travel are charged for the hours they skip. Shows on Needs Meters. Console settings: `_mhOn`, `_mhStr` (strength), `_mhUnit` (1 = Celsius), `_mhComfort`, `_mhSeason` (1 = follow the month), `_mhPA`. | xNVSE, JIP LN. Scripts only, no plugin | Built 2026-11-17, untested in play |
| Monocyte Limb Regen | With the Monocyte Breeder implant (New Vegas Medical Clinic), crippled limbs heal on their own at the implant's own health rate, 0.1 a second, so a fully crippled limb heals in about 17 minutes of play. | xNVSE 6.2.8+, JIP LN 56.95+ | Built 2026-11-11, untested in play |
| Auto Smoke (in Wasteland Tweaks) | An add-on for Light Up and Smoke Those Cigarettes (edisleado, Nexus 49677). Lights your next cigarette for you, as if you'd used it from the Pip-Boy: keep one lit, light up 1 to 20 minutes after the last one goes out, or only when you have nicotine withdrawal. Opens a pack or carton when you run out of loose ones. Drops butts and empty packs and cartons where you stand. Settings: equip the **Cigarette Case (Auto Smoke)** from the Pip-Boy's Apparel tab. | Light Up and Smoke Those Cigarettes, xNVSE 6.2.8+, JIP LN 56.95+. Enable `AutoSmoke.esp` | Built 2026-11-11, untested in play |
| Scan Null Fix | Fixes a crash in xNVSE itself: scripts that scan the objects around you (`GetFirstRef`/`GetNextRef`, used by Auto Loot Enhanced, Increased Wasteland Spawns, Alternative Start and others) crash on an object whose base item is gone, such as an item just picked up. Skips those objects instead. | xNVSE **6.4.9** exactly (does nothing on any other version, and says so in `ScanNullFix.log`) | Built and tested offline against the real xNVSE DLL 2026-11-13 |
| Fission Power | Power armor runs on fission batteries. Walking drains the one in the suit; when it's spent it's ejected at your feet as a Depleted Fission Battery and the next goes in. Out of batteries, the suit is dead weight (Agility -2, no Strength bonus, like NCR Salvaged Power Armor, and 25% slower: the dead servos drag) until you find one. PWR meter via Needs Meters; Smart Loot keeps a few batteries. With no fission batteries left, it runs on **energy weapon ammo**: each cell worth its vanilla value against a battery (an energy cell about 267 steps), least energy-dense first, two magazines of your weapon's loaded ammo kept back; by default each cell runs on its own, with a click and a count of cells left when it's spent (or refuel a fifth of a battery at a time); drained cells go back into your pack. Smart Loot keeps energy ammo as fuel while you own power armor, up to 200 of each kind, even with no energy weapon. The suit also mulches the food you carry into **Nutrient Paste** whenever its reservoir has room (richer food makes more, at a little battery) and feeds you a serving in Hardcore as hunger nears its first stage; at a campfire, closing the recipe menu offers to turn all your food into paste for no power. It holds **water** too (the water you carry, clean first, irradiated water filtered at more power) and gives you a Purified Water as Hardcore thirst nears its first stage. The worn suit weighs its processor (5 lb) plus what its reservoirs hold. | xNVSE 6.4+, JIP LN. Enable `FissionPower.esp` | Built 2026-11-15, untested in play |
| Perk Bank | Finish the level-up menu without taking a perk and save the perk for later. Done stays clickable on the perk page, so you're never stuck when every perk you qualify for is taken. Banked perks come back at your next perk level: after you take that level's perk, the menu opens again once per banked perk. No plugin. | xNVSE, JIP LN | Built 2026-11-15, untested in play |
| Wasteland Market | A living Mojave economy. Prices move by category with your trading (buy and they rise, sell and they fall, up to 50% either way), drift back about halfway in a week, and scarce goods (energy cells, fission batteries, medicine, pre-war goods) keep part of any rise. Traders you deal with bring in stock of whatever is selling well above normal. Now and then a scavenger's haul floods a category or a shortage drives it up. Equip the **Mojave Market Pamphlet** to see what's moving and why. | xNVSE, JIP LN. Enable `WastelandMarket.esp` | Built 2026-11-15, untested in play |
| Wasteland Tweaks | Small adjustments in one place: lasting shells (spent casings stay an hour and up to 1,500 at once, with the two numbers set separately, instead of Permanent Weapon Shells), a VATS rescue (a watchdog ends a VATS camera stuck for 15 s, and the End key ends it any time), a console log (everything the console shows, including other mods' messages, written to ConsoleLog.txt each launch), a Stewie Tweaks override that turns off `bWeaponDamageStagesFix` (a dropped-weapon crash path through JIP), power armor footsteps (the vanilla sound pointed at a missing folder: silent steps and a flood of log errors), a cheat terminal storage link (with the FNV Cheat Terminal installed, its personal storage boxes count as your inventory and work as a feed: ammo and food over a working amount (four magazines for the weapon in hand, one for each other weapon's ammo, one of each food and drink) go into storage and come back out as you use them, a fission battery comes out when you wear power armor with none, Smart Loot's auto-consume and Auto Smoke draw from them when you carry nothing suitable), and Auto Smoke (below). Its only plugin is `AutoSmoke.esp`, for the Cigarette Case. | xNVSE, JIP LN, JohnnyGuitar NVSE (VATS rescue); Light Up and Smoke Those Cigarettes for Auto Smoke | Built 2026-11-15, untested in play. Disable Permanent Weapon Shells, and remove the old separate Auto Smoke mod in Vortex |
| Needs Meters | Thirst, hunger, sleep (Hardcore), radiation and power armor charge (with Fission Power) as small segmented meters on the HUD, in the vanilla HUD style. Replaces Primary Needs HUD without replacing the game's HUD file. No plugin. Since 2026-11-17 the needs show as their actual numbers (H2O 240 = 240 dehydration points, as the Pip-Boy counts), with a game clock above them and, with Mojave Heat, the temperature (warning colour while heat adds thirst). `_nmNum` 0 bars, 1 numbers (default), 2 both; `_nmClock` 0 off, 1 12-hour, 2 24-hour; `_nmTemp` 0 hides the temperature. | xNVSE 6.2.8+, JIP LN 56.95+, UI Organizer | Built 2026-11-14, untested in play. Disable Primary Needs HUD |
| Target Readout | A Terminator-style readout beside the reticle while your crosshair is on an NPC or creature within range (3,000 units, about 43 m): its **name**, **level** and **condition** (or DECEASED), **faction** (the most specific of 41 vanilla factions, so Crimson Caravan before NCR and Fiends before Raiders; a creature's class when it has none), **status** towards you (HOSTILE, ENGAGED, NEUTRAL, FRIENDLY, ALLY) and **weapon** with its class ("HUNTING RIFLE / RIFLE"). Updates four times a second, lingers about a second after the crosshair leaves, and hides in menus, VATS and the kill camera. Red by default, or the HUD colour. No plugin. | xNVSE 6.2.8+, JIP LN 56.95+, UI Organizer; JohnnyGuitar NVSE optional (HOSTILE as the compass shows it). Enable `TargetReadout.esp` for the passive scan | Built 2026-11-17, untested in play |
| Smart Loot | Auto-loot that takes what is useful to you now: ammo for the weapons you carry (up to a cap), weapons with more Pip-Boy DPS than your best, spares for repairs, weapon mods that fit, a few of each aid item, keys, notes, anything weightless with value, and anything else worth enough caps a pound. From loose items, corpses and unowned containers (unlocked with your skill when that's no crime). Never steals. Also eats, drinks and patches you up (replaces Hardcore Helper). Settings: equip the **Scavenger's Duffel (Smart Loot)**. | xNVSE 6.4+, JIP LN, JohnnyGuitar NVSE, ITR NVSE (auto-consume). Enable `SmartLoot.esp` | Built 2026-11-14, untested in play. Disable Auto Loot Enhanced / Ultimate and Hardcore Helper |
| Survival Start Kit | Gives Lonesome Road's Roughin' It! Bedroll Kit (sleep anywhere outdoors) at the start of a new game, or on the next load of an existing save, once, the same way the DLC does. No plugin. | Lonesome Road, xNVSE 6.1+, JIP LN 56.95+ | Built 2026-11-11, untested in play |

## How the Survival Start Kit works

New Vegas has no command to start a run with an item, and a plugin's start-up script must be
compiled by the GECK. Instead this uses JIP LN NVSE's script runner: text files in
`Data\nvse\plugins\scripts\` run on game events. `ln_` files run on a new game and on every load.
They run in the console environment, so editor IDs don't resolve; forms are built from
`LonesomeRoad.esm`'s load-order index (`BuildRef`).

The kit (ALCH `0x00CD51` in LonesomeRoad.esm) has its own scripts. Using it from the Pip-Boy opens
the sleep menu. It works outdoors only, and not in the Lucky 38, the Fort or the Big MT greenhouses.
Its OnAdd shows its intro message and sets `NVDLC04GenericPerkQUEST.bFirstPickedUp`
(`0x00A603`), which this mod checks so the kit is given only once.

Check it worked: the intro message box appears in Doc Mitchell's house on a new game, and the
console (`~`) shows "Survival Start Kit: gave the Roughin' It! Bedroll Kit".

## How Monocyte Limb Regen works

The vanilla implant's effect script (`ImplantRegenScript`) restores Health by
`ScriptEffectElapsedSeconds / 10` each frame, which is 0.1 a second. This mod's `ln_` script
registers an xNVSE `CallWhilePerSeconds` that, once a second, restores each of the six limb
conditions by 0.1, but only while the player has `ImplantRegenPerk` (FalloutNV.esm `0x14CCE1`).
Flags 4 + 16 keep it out of menus and pauses, like the implant's own effect.

It is registered again on every load and new game, and xNVSE clears all repeating calls on
those same events (`ClearDelayedCalls` in its load and new-game hooks), so it never stacks.

Check it worked: with the implant, cripple a limb (`player.DamageAV LeftMobilityCondition 100`
in the console) and watch it come back in the Pip-Boy's status page.

## How Wasteland Bank works

The 2011 Bank Card's bugs and their fixes:
- **Loan interest every few seconds instead of weekly.** It stored the day as a whole number and
  compared it with the fractional day. Here every day count is whole (`Floor GameDaysPassed`), and
  interest is 0.5% per 7 whole game days.
- **Auto-convert and auto-consolidate never ran.** Its seconds timer was a whole number and stayed
  at 0. Here they run on a 10-second tick.
- **Cash figure up to a few seconds old.** Depositing just after spending could credit caps you no
  longer had. Here every button counts your caps at the moment you click it.
- **Auto-deposit took every cap you carried.** Here it keeps a chosen amount on hand
  (100/200/500/1000, default 200).

Currency converts at each item's own value in the game, read with `GetValue`, so a mod that
reprices money is followed. Caravan money (the `CMNY` twins) converts at its matching item's value.
Deposit interest stays as in the original: 0.5% a game day plus Barter/50000, compounding. The
rates are at the top of `Tick.txt` and `Loan.txt`.

Layout: `nvse/plugins/scripts/ln_wasteland_bank.txt` gives you the bank card if you have none,
registers the card's equip handler (`OnEquip.txt`, which calls `UseCard.txt`) and a 10-second bookkeeping tick on every load. Each menu and its buttons is a user-defined
function in `nvse/user_defined_functions/WastelandBank/`, compiled by xNVSE at startup and called
with `CompileScript`. Balances are JIP auxiliary variables on the player (`_wb...`), saved in
JIP's co-save. Console: `call (CompileScript "WastelandBank/Open.txt")`.

## How Auto Smoke works

Auto Smoke has been part of Wasteland Tweaks since 2026-11-15. Its plugin is still `AutoSmoke.esp`,
so the Cigarette Case and your settings carry over. Light Up and Smoke puts butts, empty packs and
empty cartons in your inventory. Auto Smoke drops them where you stand every 5 s, whether you lit
up by hand or not. They're worth nothing, so Smart Loot leaves them. Turn it off with
`player.AuxVarSetFlt "_asNoLitter" 1`.

**Nicotine alertness (Hardcore, on by default, toggle in the case's menu).** A smoke that's just
been lit, by hand or automatically, lowers sleep deprivation by 20 (cigarette), 25 (cigarillo) or
35 (cigar). The stages are at 200/400/600/800/1000, so that's about a tenth of a stage. Each smoke
in the last 6 game hours halves the next one's effect, so chain-smoking can't replace sleep.
- **Bedtime:** a smoke within 1 game hour of sleeping takes away Well Rested. A JIP handler flags
  it when the Sleep/Wait menu opens, and Well Rested is removed when you wake.
- **Withdrawal:** while you have Nicotine Withdrawal, sleep deprivation builds 25% faster. This is
  measured from its own rise, so it follows the game's real rate.
- **"When tired" mode:** a new auto-smoke setting that lights up at Tired (200+), but only while
  another smoke would still give at least half its effect.
- **Safety:** all sleep-deprivation access goes through `NicSleep.txt`. It is optional in the load
  check, so if it ever fails to compile only this feature turns off. After each smoke the console
  shows the actual change.


Light Up and Smoke Those Cigarettes makes smokes aid items: using one from the Pip-Boy runs its
script, which wears a lit cigarette (cigarillo, cigar) in the mouth slot, applies the tobacco
effects and addiction chance, and turns it into a butt about 2 minutes later. Auto Smoke uses the
item the same way (`EquipItem` on the aid item), so all of that still applies; it only decides when.

Every 5 seconds of play (not in menus or while paused) it checks whether you are smoking, by
looking for a worn lit smoke the same way the mod does. If not, it counts the time since the last
one went out and, after the chosen break, lights the next: ordinary cigarettes first, then
cigarillos, then cigars. Lucky cigarettes are left for you. With no loose smokes it opens a
pack, or else a carton, and lights one from it on the next check. It never lights up while
something else is worn in the mouth slot (lighting up would take it off).

The "only when craving" setting lights up when you have Nicotine Withdrawal (its Agility effect,
`AddictRedAGTobacco`, FalloutNV.esm `0x0FAB0F`). Default: on, 5 minutes between smokes, open
packs on. Settings are per character, in JIP aux variables (`_as...`). It does nothing if the
smoking mod isn't loaded.

Check it worked: with some cigarettes, equip the Cigarette Case, close the Pip-Boy, set "keep one lit", close, and wait a few
seconds. You should hear the lighter.

## How Perk Bank works

On the level-up menu's perk page, the Continue/Done button is clickable only while the menu's
`_CurrPoints` equals its `_MaxPoints`, which means "perks chosen = perks offered" (vanilla
`levelup_menu.xml`). Clicking it finishes the menu with no other check. The decompiled click handler
(0x00785AA0, case 7) just moves to the next page, and past the last page the menu closes. You get
stuck when every perk the game lists is greyed out, because then nothing can be picked. Perk Bank
watches the menu every frame and holds `_MaxPoints` equal to `_CurrPoints`, so Done always works.

- **Done without a perk:** the perk is banked (`_pbBank`, saved with the game), with a message.
- **Spending:** the game only offers perks on a perk level, and only one per menu
  (`LevelUpMenu_Create`, 0x00784C80, fills the list only when your level divides by
  `iLevelsPerPerk`). So when you take a perk with some banked, the level-up menu opens again (JIP
  `ShowLevelUpMenuEx 0`), once per banked perk. Close one of those without picking and the bank stays
  as it was. If nothing is offered, the bank waits.
- **Check the bank:** in the console, `print player.AuxVarGetFlt "_pbBank"` shows how many are banked.

## How Wasteland Market works

**Categories.** On every load, each loaded item (ammo, aid, weapons, armor, misc; JIP
`GetLoadedTypeArray`) is sorted into a category, and its original value is noted. Worthless, quest
and unplayable items and currency are left out.

| # | Category | How an item gets there | Market depth (caps of net trade per 10%) |
|---|---|---|---|
| 0 | Ammo | any other ammo | 600 |
| 1 | Energy cells | ammo named energy cell, microfusion, electron charge or flamer fuel | 400, scarce |
| 2 | Fission batteries | the Fission Battery | 300, scarce |
| 3 | Medicine | aid flagged as medicine | 400, scarce |
| 4 | Food and drink | other aid | 300 |
| 5 | Chems | addictive aid | 400 |
| 6 | Weapons | weapons | 1500 |
| 7 | Armor | armor | 1500 |
| 8 | Pre-war goods | anything named "pre-war" | 500, scarce |
| 9 | Scrap and junk | other misc items | 400 |

**Prices.** Each category has a multiplier, 1 = normal, and every item's value is set to its
original value times that multiplier (JIP `SetBaseItemValue`). Buying and selling prices change
everywhere at once, and so does Smart Loot's "worth taking" rule.

- **Your trading:** what you carry when a barter opens and closes (menu 1053) gives your net
  purchase per category, in caps at original value. Buying pushes the price up and selling pushes it
  down, by 10% per "depth" of caps. The limit is 50% either way.
- **Scarce goods keep a premium:** a quarter of any rise also raises the level a scarce category
  settles back to (at most +25%), and that extra fades only very slowly.
- **Settling:** every game day, prices drift 10% of the way back, so about halfway in a week.
- **Supply follows price:** each merchant you've traded with is remembered, up to 30. While a category
  sells at least 10% above its settling level, each of them has a daily chance equal to the premium
  (+40% gives a 40% chance) to bring in stock: a random item of that category in their stock
  container. Each delivery eases the price 2%. So buying fission batteries gets more of your traders
  carrying them.
- **Market events:** an 8% daily chance, which can be switched off in the pamphlet. A scavenger's big
  haul floods a random category (down 20-40%), or a shortage drives it up (20-40%).

**The pamphlet.** The Mojave Market Pamphlet, in Apparel, lists every category at least 3% off normal
(up or down, by how much, and why: your buying, your selling, a haul, a shortage, or traders bringing
stock), the latest news, and how many traders you deal with.

## How Needs Meters works

Needs Meters replaces Primary Needs HUD. It shows thirst, hunger, sleep and radiation as four small
meters on the right of the HUD, above the ammo counter, drawn in the HUD colour like the vanilla HP
and AP bars:

- **H2O, FOD and SLP drain** as you get thirsty, hungry and tired, and are shown only in Hardcore
  mode. Each meter has five segments, one per Hardcore stage (200 points each).
- **RAD fills** as radiation builds, and is shown only while you have any.
- A meter switches to the HUD's alternate colour (the one the vanilla radiation meter uses) once its
  penalties start: need 400+, or rads 200+. It blinks at the critical stage (800+).

**How it gets onto the HUD:** Primary Needs HUD replaced the game's whole `hud_main_menu.xml`.
Needs Meters adds one file instead: UI Organizer reads `uio/public/NeedsMeters.txt` and injects
`menus/prefabs/NeedsMeters/NeedsMeters.xml` into the HUD. That XML is generated by
`tools/gen_needs_meters.py`, which `build.py` runs. A script updates the values once a second. There
is no plugin, so it needs no load-order slot. It needs xNVSE, JIP LN NVSE and UI Organizer.

**Settings (console):**
- `player.AuxVarSetFlt "_nmOff" 1` hides the meters, and 0 shows them again.
- `player.AuxVarSetFlt "_nmX" -40` moves them 40 left, and `"_nmY" 30` moves them 30 down.
- `player.AuxVarSetFlt "_nmGap" 16` sets the space between rows. The default is 10. Rows are spaced by
  the label's real height plus this gap, and the bars are centred on the labels.

Settings are saved with the game.

**Check it worked:** in Hardcore, the three meters show on the HUD and shorten as time passes, and
RAD appears after drinking irradiated water. If nothing shows, the console says whether the HUD file
was injected.

## How Target Readout works

Point the crosshair at an NPC or creature within range and a five-line readout appears above and to
the right of the reticle, its last line just above the reticle's level, so it stays clear of the
game's own prompt (the name and "E) Talk") under the reticle:

```
NAME: BENNY
LEVEL 12   CONDITION 85%
FACTION: THE CHAIRMEN
STATUS: NEUTRAL
WEAPON: MARIA / PISTOL
```

- **Faction** is the first of 41 vanilla factions the actor is in, checked most specific first
  (`TargetReadout/Faction.txt` lists them with their form IDs). Groups whose members are also in a
  wider faction come first: Crimson Caravan before NCR, Fiends before Raiders, Jacobstown before
  generic Nightkin. Armor, dialogue and utility factions are left out, because they would mislabel
  people. With no match an NPC reads UNAFFILIATED and a creature reads its class (ANIMAL, MUTATED
  INSECT, ROBOT and so on, from JIP's `GetCreatureType`). DLC factions are not covered.
- **Status**, in this order: TERMINATED (dead), ALLY (your companion), ENGAGED (fighting you),
  HOSTILE, ALLY or FRIENDLY (faction relation), NEUTRAL. HOSTILE is the compass's own test (red on
  the compass, from JohnnyGuitar NVSE's `IsCompassHostile`, which counts aggression, reputation and
  disguises). Without JohnnyGuitar NVSE it is the game's `GetShouldAttack` ("would attack you on
  sight"), or a faction that counts you an enemy. The faction relation alone would miss most
  hostiles: in FalloutNV.esm Raiders, Fiends, Vipers, Scorpions and the Powder Gangers have no
  reaction to the player's faction, and NCR and the Legion are neutral to it whatever your
  reputation. The combat, relation and compass checks each sit in an optional file
  (`TargetReadout/Rel.txt`, `TargetReadout/Hostile.txt`): if one fails to compile, the console says
  so and only that part of the STATUS line is lost.
- **Weapon** is the equipped weapon and its class from xNVSE's `GetWeaponType`, or UNARMED.
- Tumbleweeds are left out: the game makes them creatures ("Wind Brahmin"), in the Nightkin and Super
  Mutant factions among others.

**How it gets onto the HUD:** the same way as Needs Meters. UI Organizer reads
`uio/public/TargetReadout.txt` and injects `menus/prefabs/TargetReadout/TargetReadout.xml` into the
HUD. That XML is hand-written. A script runs four times a second and writes the readout text to it.
When the crosshair leaves, the readout stays for half a second, fades over the next half second, and
then hides. It hides at once when VATS opens and during the kill camera. The crosshair reference
comes from JIP's `GetCrosshairRefEx`, which reaches past activation distance. If that function can't
be used, the readout falls back to xNVSE's `GetCrosshairRef`, and the console says that targets are
read only within reach.

**Only in VATS (default):** the readout shows while you're targeting in VATS, beside the target VATS
has lit up (JIP's `GetEnemyHealthTarget`; placed with JohnnyGuitar NVSE's `WorldToScreen`, else by the
reticle), and follows as you switch targets, so it isn't always lighting up the HUD. A sixth line gives
the body armor and its DT. `"_trAimZ" 120` moves the point it sits beside higher up the target. `"_trVats" 0` shows it
whenever the crosshair is on someone, as before.

**Passive scan:** every 6 seconds while your weapon is out, the people and creatures around you in
sight flash a soft outline for 2 seconds, in the STATUS line's colours: enemies red, neutrals amber,
friends and allies green. The outlines are softened copies of the Spotter perk's outline, so they
shimmer gently and fade on their own. Needs `TargetReadout.esp` enabled. `"_trScan" 0` switches it
off; `_trScanT` (seconds between scans), `_trScanD` (how long they last), `_trScanR` (range, 4000),
`_trScanW` (0 also with the weapon away) and `_trScanLOS` (0 also through walls) tune it.

**Typing it out:** each new target's readout types itself out in the game's terminal font, line by line
behind a block cursor, with the terminal's character clicks, in well under a second. The same target
updates in place without retyping; look away and back and it types again.

**Settings (console):**
- `player.AuxVarSetFlt "_trOn" 0` switches the readout off, and 1 switches it on again.
- `player.AuxVarSetFlt "_trRange" 5000` reads actors up to 5000 units away. The default is 3000.
- `player.AuxVarSetFlt "_trRed" 0` shows the text in the HUD colour. 1 is red, the default, and 2 is
  the HUD's alternate colour.
- `player.AuxVarSetFlt "_trX" -40` moves it 40 left, and `"_trY" 30` moves it 30 down.
- `"_trType" 0` shows each readout at once; `"_trStep" 5` types faster (letters per frame, default 3);
  `"_trSound" 0` silences the clicks.

Settings are saved with the game.

**Check it worked:** aim at anyone in Goodsprings and the readout appears. If nothing shows, the
console says whether the HUD file was injected or a script failed to compile. If the text shows white
instead of red, set `_trRed` to 0 or 2 (the red uses plain RGB tile traits, untested in this repo).
Stand next to an NPC, close enough to talk, and check that the readout doesn't cover the game's
prompt (or the sneak indicator while crouched); move it with `_trX` / `_trY` if it does. Check STATUS
at a raider camp before they see you (HOSTILE) and, on a save where the NCR is vilified, at an NCR
patrol (HOSTILE).

## How Fission Power works

Once a second, while you wear power armor, it measures how far you have moved and turns that into
steps (52.5 game units, 0.75 m, per step). One fission battery powers a suit for 10,000 steps, about
7.5 km. That is roughly half an hour of nonstop running. Just having the suit online also draws
power, more slowly: by default 1 step's worth per second of play, so a battery lasts about 2.8 hours
standing still. Time skipped by waiting or sleeping doesn't count, since the check only runs during
play.

**Fast travel drains it too.** By default, a jump within one outdoor worldspace counts as fast travel and
uses power for the straight-line distance times 1.25, since roads wind. A long trip can use several
batteries: they're all ejected where you arrive, and one message says how many. Doors and interiors
don't count. Turn it off with `player.AuxVarSetFlt "_fpFT" 0`. Doors, fast
travel and other jumps (a change of cell, or of worldspace outside, or more than 1,000 units in one
second) don't count. Only armor the game flags as power armor needs power. NCR Salvaged Power Armor
has had its servos stripped, and the game doesn't flag it, so it runs on nothing.

- **A battery runs out:** the spent one is ejected and dropped at your feet as a Depleted Fission
  Battery (worth nothing, so Smart Loot leaves it), with the battle rifle's crisp clip-spring
  sound (This Machine's reload sound, part 3). A fresh one
  from your inventory goes in, and a message says how many spares are left.
- **No batteries left:** the suit is dead weight. Like NCR Salvaged Power Armor, the stripped-servo
  suit, you get Agility -2, and the suit's own Strength bonus is cancelled (read from its
  enchantment). On top of that, the dead servos drag against every move, so you are **25% slower**.
  Vanilla salvaged armor has no speed penalty, but its servos are gone rather than seized. Speed is
  the SpeedMult actor value. The game caches movement speed, so JIP's `SetSpeedMult` refreshes it
  and the change applies at once. All of it comes back as soon as you load a battery or take the
  suit off.
- **Low power:** a warning at 10% when you have no spares.
- **On the HUD:** Needs Meters shows a **PWR** meter (five segments, alternate colour at 20%, blinking
  at 10%) and your spare count, only while you wear power armor.
- **Smart Loot:** while you own power armor, it keeps up to 4 fission batteries (6 lb each), within
  its carry-weight reserve.

The charge belongs to you, not to each suit, so swapping suits keeps it. Your first suit comes with
a full battery.

**Settings (console):**
- `player.AuxVarSetFlt "_fpLife" 20000` sets the steps per battery.
- `player.AuxVarSetFlt "_fpPen" 0` turns off the dead-suit penalty.
- `player.AuxVarSetFlt "_fpSlow" 40` sets how much slower a dead suit makes you, in percent.
- `player.AuxVarSetFlt "_fpIdle" 2` sets the standby draw, in steps per second worn (0 = none).
- `player.AuxVarSetFlt "_fpSnd" 1` sets the eject sound to part 1, 2 or 3 of the battle rifle's
  reload (default 3). To hear them in the console: `playsound 174696`, `174697`, `174698`.
- `player.AuxVarSetFlt "_slBatt" 6` sets the batteries Smart Loot keeps.

Take power armor off before uninstalling, or a dead-suit penalty that is active at the time stays.

## How Smart Loot works

A light check every 0.25 s also runs a pass early when there's a reason. If you've moved about
1.4 m since the last pass, it runs one at most once a second. If your crosshair is on a container,
corpse or item within reach, it runs one straight away. So things are looted as they come into
reach. Standing still adds nothing.

Every 1.5 seconds of play (never in menus, and by default not in combat), Smart Loot scans
everything within reach once. It sorts what it finds into loose items and containers or corpses, and
only then picks things up, at most 10 stacks per check. Picking up in the middle of a scan is what
crashed Auto Loot Enhanced. Loose items are activated for you, as if you had pressed E, so their
scripts run and the game adds them as usual. Items from containers and corpses move whole
(JIP's `RemoveItemTarget`), keeping their condition and mods. Each pickup plays the item's own
pickup sound, unless that sound is already playing.

**What it takes**, in order:

| Rule | Default | Choices |
|---|---|---|
| Every currency (caps, NCR dollars, Legion coins, pre-war money, caravan money, casino chips, Sierra Madre chips) and NCR dogtags, quest flag or not | always | |
| Keys and notes | always | |
| No weight but some value (caps, money, stimpaks, magazines) | always | |
| Ammo that a weapon you carry can fire (including its special ammo) | up to 300 per calibre | 100, 200, 300, 500, no cap |
| Weapons with more DPS than your best of the same skill (or your best overall, if you carry none of that skill). DPS is the Pip-Boy's own figure for you, from JohnnyGuitar's `GetCalculatedWeaponDPS`. | 10% better | off, any better, 10%, 25% |
| ...except ones whose Strength requirement you don't meet | left | take or leave |
| Spares of your equipped weapon, for repairs | when it is under 60% condition | off, 40%, 60%, 80% |
| Weapon mods that fit a weapon you carry | if you don't have one | |
| Food, drink and other aid with weight | up to 5 of each | off, 3, 5, 10, 20 |
| Anything else | worth at least 10 caps a pound | off, 5, 10, 20, 50 |
| Quest items | left | take or leave |

**Carry weight:** weighted items never use your last 25 lb of carry weight (0, 10, 25 or 50).

**Containers and corpses:** corpses are always fair game. A container or loose item is taken from
only if neither it nor its cell has an owner, or if every owner is your **enemy**. An enemy is a
faction the game counts as hostile to you (`GetPCEnemyOfFaction`, the test the Lucky 38 scripts use),
or a person in such a faction. Robbing the Legion once it wants you dead costs no karma: an enemy's
loose item is made yours just before it is picked up, and items from containers arrive with the old
owner cleared, so nothing is marked stolen. This can be switched off ("Enemies' things" on page 2).
It never empties your own containers at home. A
locked container is unlocked if your Lockpick skill is at least the lock's level, or with its key.
It gives the same XP as Auto Loot Ultimate (20, plus 10 per lock level). Optionally it also uses up
a bobby pin. "Requires key" locks need the key.

**Searched containers stay slightly open.** Once Smart Loot has gone through a container, it
plays the container's own "Open" animation (JIP `PlayAnimSequence`) and freezes it part-way 0.3 s
later (`SetAnimSequenceFrequency "Open" 0`), so you can see what's been searched. All the common
vanilla containers (footlockers, ammo boxes, lockers, gun cabinets, trunks, first aid kits,
toolboxes, safes) have that animation. Plain metal boxes don't, so they can't show it. Searched
containers are remembered with the save and open again when you come back. Turn it off with
`player.AuxVarSetFlt "_slAjar" 0`.

**Other settings:** reach (150, 200, 300 or 450 units), messages (off, upgrades and unlocks, or every
pickup), pickup sounds, and looting in combat.

**Auto-consume** (settings page 3; replaces Hardcore Helper). Items are used through ITR NVSE's
`UseAidItem`, which is the game's own "use from the Pip-Boy" path. Each one plays its own eating or
drinking sound, counts toward addiction and gets your perks. Hardcore Helper applied the effect and
deleted the item instead, and only knew about 60 items by name. Smart Loot reads each item's own
effects, so modded food works too.

| Need | When | Uses |
|---|---|---|
| Stimpak | at 25% health or less, **even in combat**, one at a time | the cheapest healer (stimpak before super stimpak) |
| Everything below | **never during combat**, checked every 6 s | |
| Crippled limb | any limb crippled | the cheapest limb restorer (doctor's bag) |
| Radiation | 50 points before radiation sickness | RadAway |
| Taking radiation | while you are being irradiated | Rad-X |
| Thirst, hunger (Hardcore) | 50 points before the first penalty stage | water and food |
| Sleep items (off by default) | 50 points before the first penalty stage | coffee, Nuka-Cola... |

The thresholds are read from the game's own stage records (Water1, hunger1, sleep1, Rad1), so a mod
that moves them is followed.

**Which food or drink:** the **heaviest for what it gives** goes first. If another item gives the
same thirst for less weight carried, the heavier one is used. Weightless items go last, and among
equals the cheaper goes first. Aid (stimpaks, doctor's bags, RadAway, Rad-X) uses the cheapest that
works. It never uses quest items. It also avoids addictive items (chems, alcohol), and only uses
irradiated food or dirty water when nothing clean is left.

**Choices:** the 50-point margin (0, 25, 50 or 100), the stimpak level (never, 15, 25 or 40%), each
need on or off, and the food rule (never irradiated or addictive / irradiated only if nothing clean
/ anything).

**How it decides what you want:** every few seconds, or as soon as what you carry changes, it reads
your inventory and builds its lists. These are the ammo types your weapons fire, the mods that fit
them, your best DPS for each weapon skill, and your equipped weapon if it needs repair. The lists are
empty form lists in `SmartLoot.esp`, filled at run time.

**Check it worked:** after enabling, a Scavenger's Duffel appears in Apparel. Walk over some ammo
for a gun you carry and it is picked up with its usual sound. Ammo for guns you don't carry stays
where it is.

## How Scan Null Fix works

Three New Vegas crashes on 2026-11-12/13 were all at `nvse_1_4.dll`+0x36C03. Cobb Crash Logger's
stack was `RefMatcherFormType::Accept` < `GetCellRefEntry` < `CellScan` < `GetNextRef`, with the
base-form pointer null. In xNVSE 6.4.9 (`Commands_MiscRef.cpp`), the matchers behind every
reference scan read `refr->baseForm->typeID` without checking `baseForm`, and a scan tests every
reference in the cell. Auto Loot Enhanced picks items up in the middle of its scans, which can
leave such a reference behind; its weapon scan (type 40) is the next full pass and crashes.

`native/ScanNullFix/ScanNullFix.cpp` is a small xNVSE plugin. At load it replaces the base-form
read in `RefMatcherFormType`, `RefMatcherActor` and `RefMatcherItem` (`Accept`) with a jump to a
stub that does the same read, checks for null, and takes the function's own "no match" exit. It
checks the DLL's timestamp, the exact original bytes and each exit before changing anything, and
patches nothing otherwise. The result is written to `ScanNullFix.log` next to `FalloutNV.exe`.

Build: `python native/build_native.py` (Visual Studio Build Tools 2022, x86, static CRT). The DLL
is committed, so `build.py` needs no compiler. Test: `native/ScanNullFix/test_harness.cpp` maps the
real `nvse_1_4.dll` without running it, calls the three real functions with fake objects, and
checks that a reference with no base form crashes before the fix and is skipped after, with
normal references matching as before. When xNVSE updates, re-check the three functions
(`dumpbin /disasm` around `?Accept@RefMatcher...`) and update the offsets, bytes and timestamp,
or drop the fix if xNVSE has added the check.

## Session watcher (`tools/fnv_watch.ps1`)

A small PowerShell script for chasing crashes. It waits for `FalloutNV.exe`, records its memory
every 10 s, and when the game exits saves that session's logs (xNVSE, error, Havok, crash logger,
DXVK, Scan Null Fix, plugins.txt) into `Documents\My Games\FalloutNV\SessionLogs\<start time>\`
with a `summary.txt`: duration, whether it crashed, peak memory against the 32-bit 4 GB ceiling,
and the last save/load events. It keeps the newest 30 sessions. To run it at sign-in, put a
shortcut in the Startup folder:
`powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File tools\fnv_watch.ps1`.
`-TestStart "<date time>"` summarizes an earlier session's logs and exits.

## License

MIT (see `LICENSE`). Wasteland Bank is a fresh rewrite inspired by Bank Card (Nexus 39741) and
contains none of its files. Auto Smoke uses, but doesn't include, Light Up and Smoke Those
Cigarettes (Nexus 49677).

## Wasteland Exchange (inside Wasteland Bank)

From the bank card's menu, **Wasteland Exchange (stocks)**. Full design and rationale:
[docs/wasteland-exchange-design.md](docs/wasteland-exchange-design.md).

- **Two exchanges.** The New Vegas Exchange (Mr. House's, in caps): Gun Runners, Van Graff Energy,
  Mojave Express, The Tops, Gomorrah, Ultra-Luxe, Atomic Wrangler, RobCo Industries. The Hub
  Exchange (NCR, in NCR dollars at the game's own rate): Gun Runners, Crimson Caravan, Happy Trails,
  Water Merchants, Far Go Traders, Brahmin Barons, NCR War Bonds. Trades settle in caps through
  the bank balance.
- **Prices.** Each stock's price is its start price × e^(level + shock + wobble). The wobble moves
  every game day, mean-reverts, and is half shared within a sector. News shocks fade with a 7-day
  half-life. The level is permanent and changes only through big events. The randomness is seeded
  per character, so reloading replays the same market.
- **News.** 30 events, keyed to real quest stages and deaths (e.g. *My Kind of Town*'s sheriff,
  *How Little We Know*, *The House Always Wins*, Alice McLafferty, the Van Graffs, each faction's
  march on the Dam). Each posts a Mojave Market Wire headline. Wiping out the Van Graffs **delists**
  Van Graff Energy. When the exchange is added to an existing save, past events are priced in
  quietly.
- **Getting rich.** Calling the war right pays: RobCo bought early and held through House's whole
  path is about 5×. Holding NCR bonds when the Legion takes the Dam is not a good time.
- **Dividends** are paid weekly. Reinvestment can be switched on per stock (fractional shares).
- **Short selling.** Your equity must cover half of all short positions to open one. A weekly
  margin check covers everything if equity drops below 30%. Shorts pay the dividend plus a 0.2%
  weekly borrowing fee. A delisting settles shorts at 5% of the price.
- **Costs.** Buying pays price + 1.5%; selling gets price − 1.5%.
- **Auto-invest** (Exchange settings). Once per game day, the bank balance above a **reserve**
  (0–25,000 caps, default 1,000) is invested in 100-cap steps, up to 10,000 caps a day. Each step
  buys the eligible stock you hold least of by value, so the money spreads evenly. **Index** uses
  every listed stock; **my stocks** only tops up stocks you already own. It skips delisted stocks
  and anything you're short, costs the same as buying by hand, and has an **Invest now** button.
  It pairs with the bank's auto-deposit: caps carried above your keep amount go to the bank, then
  into stocks.
- **Reinvest all dividends** (Exchange settings): an account-wide switch. When it's on, every
  holding reinvests; when it's off, each stock's own setting applies.
- **Currencies float with faction power.** The NCR dollar and the Legion denarius are priced by
  the same engine, as a multiplier on their vanilla values. Kimball's fate, Nelson, Forlorn Hope,
  the Boomers, Caesar, Lanius, General Oliver and each faction's march on the Dam all move them.
  Merchants see the new values: every load and every 10 s, the NCR notes and Legion coins are
  revalued to vanilla × multiplier, rounded to whole caps, so a $5 note is 1–3 caps. The bank's
  currency converter and the Hub Exchange use the exact rate. In simulation the NCR's path lifts
  the dollar from 0.40 to about 0.54 caps, and the Legion's sinks it to about 0.20 while the
  denarius goes from 4 to about 6. The rates show on the exchange menu.

Built from `tools/gen_exchange.py` (listings and events as a table, generating `ExData.txt` and
`ExEvents1-3.txt`). `tools/exchange_sim.py` is a Python twin of the price maths, run by
`build.py`: it checks the random draws are uniform and independent, that prices without news stay
in range, and that the best path lands at 5–6×.

