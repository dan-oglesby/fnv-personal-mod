# Bank ideas: designs to agree before building (2026-11-17)

## The Vegas book: a betting market (to build next, once the bet list is agreed)

A bookmaker's board of things you can bet on, with Vegas odds, most of which you can influence: in
effect a challenge system that pays. Reached through the courier squad (they carry the book) or at
the Strip casinos.

**How a bet works.** Each bet has a deadline, a stake you choose (100 / 1,000 / 10,000 caps, from
your balance) and odds that pay stake x odds on a win. Odds are set from how hard the thing is for
you right now (your level, skills, gear, how far away it is) and drift with news. The book keeps a
house edge (about 10 percent), and its fee counts as bank revenue. Several bets can run at once;
new ones come up each game day.

**What you can bet on.** The game keeps counters the scripts can read (the Pip-Boy's statistics:
creatures and people killed, locks picked, computers hacked, quests completed, places discovered,
stimpaks used, speech successes, casino winnings and so on; to be confirmed in game), plus quest
stages, deaths of named characters, your karma and reputations, money and time. So, for example:
- *Bounties on yourself:* kill 10 creatures in a day; clear a named camp (its boss dead) within 3
  days; no stimpaks for a day; take no damage for an hour.
- *Feats:* pick 5 locks this week; hack 3 terminals; pass 5 speech checks; discover 3 new places.
- *Journeys:* reach a place (the Strip, the Fort, Jacobstown) within N days; walk from Goodsprings
  to Vegas without fast travel.
- *The tables:* finish a day up at the casinos; win at Caravan.
- *The war (no influence, or some):* Kimball survives his visit; who holds the Dam; Benny's fate;
  a faction's reputation with you by a date.
- *Against yourself:* lay odds that you *won't* do something (for example, take no chems for a
  week), paid if you hold out.

**Influence.** Most bets are about what you do, so you can win them by playing for them; the odds
account for that (an easy feat for your build pays little).

**Decided:** start with bounties, including generated bounties on specific characters, a small
quest each ("kill the Viper leader at the camp by the Sloan quarry by day N"): the script picks a
target (a named or leader-type enemy and where it is), marks it, and pays on its death before the
deadline. The book lives at the casino cashier windows; the couriers take bets remotely.

## Caravan ventures (to explore further)

Fund a caravan run as a silent partner. Mechanics to settle:
- **Who:** Crimson Caravan (Hub-listed, NCR-aligned), Happy Trails, the Van Graffs' gun runs, a
  freelance Freeside crew (riskier, better cut).
- **The run:** you pick a route (Vegas to the Hub, Vegas to Arizona, the Long 15), put up caps;
  the run takes days to weeks; returns 10 to 60 percent, set by route danger.
- **Danger follows the world:** routes through Legion land worse while the Legion is strong; the
  Long 15 worse with the Khans hostile; random events (raided, lost a brahmin, sold out early) in
  the weekly letter.
- **Your hand in it:** clearing the threats on a route (a known raider camp) before it leaves cuts
  the danger and raises your share; escorting a run yourself (meeting it at a waypoint) pays a bonus.
- **Ties:** returns move the caravan companies' stocks; a lost caravan hurts Crimson Caravan's price.
**Decided:** physical caravans and large investments. You get an optional quest (and a quest
item) to escort your caravan to its destination: walk it there and it pays a high return for
certain; don't, and it travels on its own at the route's ordinary odds.

**Built (2026-11-17), first version:** Investments > Caravan ventures, from the Investor stage, one
venture at a time, stakes of 2,000 to 20,000 caps. Five routes (Crimson Caravan Company to Mojave
Outpost and to Primm, Freeside's East Gate to Novac, Novac to Nipton, Goodsprings to Primm), each
with a danger that moves with the war. The run sets out 6 hours after you back it; be at its start
within a day and a real caravan (caravaneer, two guards, a pack brahmin) walks the road with you,
with a chance of an ambush halfway: walk it in for 60 percent plus 60 x danger. Lose it, or don't
come, and it travels alone at the route's odds (1 - 0.7 x danger to succeed, paying 15 percent plus
50 x danger; a loss salvages 30 percent). A Caravan Manifest marks a run on the road.

**Representatives (2026-11-17, second version):** ventures are arranged in person, not through the
bank card or the couriers. A Caravan Agent stands by the Crimson Caravan Company (the five routes,
in caps, from the Investor stage) and a Publicanus by Cottonwood Cove: the Legion's caravans,
Cottonwood Cove to Nipton and to Searchlight Airport, in denarii from the denarius account (stakes
500 to 5,000), from the Financier stage, for those the Legion accepts, until its treasury defaults.
A Legion caravan is a veteran, an explorer, a recruit and a pack brahmin; NCR troopers ambush it,
and its danger rises with the NCR dollar. They replace the publicani contracts (contracts already
bought run out as before). Both representatives are placed by script the first time you come near
and talking to one opens their menu. The Caravan Agent can't die; the Publicanus can (he keeps the
Legion's factions, so he fights with the Cove), and once he's dead the Legion's caravans are over.

## The fence: Gomorrah's books (to explore further)

The couriers won't touch stolen goods; the Omertas will.
- **Fencing:** a stolen item can be sold through a Gomorrah contact (in Gomorrah, or a dead drop in
  Freeside) for a steep cut (40 to 60 percent), and its stolen mark comes off ("laundered").
- **Heat:** fencing a lot raises your heat with the NCR and the Strip's law: higher heat means
  worse cuts, and at the top a bank audit (the couriers' fees rise, or an account freeze).
- **Laundering caps:** money from crimes (kingpin operations, robberies) can be washed through
  Gomorrah's tables into clean balance, for a cut.
- **A stake in the books:** at the Kingpin stage, buy into Gomorrah's books (a share of the fence's
  take), which ties into operations; the Omertas' story (their plot against the Strip) can wipe it.
**Decided:** only once the Omertas trust you.

## Built 2026-11-17 (evening)

- **Courier delivery:** away from a dropbox, the Mojave Express menu offers the catalogue for
  courier delivery. A squad (called if none is coming) carries the order out and hands it over when
  they reach you: the goods' value plus a 25 percent commission (setting `_wbDelivCut`), no
  shipping.
- **The Mojave Market Report:** the first squad you meet each week hands you that week's edition of
  the Wasteland Market pamphlet, dated: the war (the Dam, the NCR dollar and the denarius and their
  moves since your last report, the treasury's default, the week's wire headlines), then the
  markets. A week without a meeting has no edition. The pamphlet keeps the last four.
- **Caravans and the market:** each route carries a market category. A run that comes in sells at
  the going price (the gain scales with it) and floods the category; a lost run makes it scarce
  (5 to 15 percent, by stake).
- **Hired guards:** from the Caravan Agent. Up to three Crimson Caravan guards follow and fight for
  you: 200 caps to sign one on, 40 caps a day each from the bank. One unpaid day and they warn you,
  two and they walk off. They can die. Talk to one for wait here / follow me / dismiss. Companions
  like Boone keep their own motives; wages are only for hired guards.

## Repairs by mail: thinking it through

The worry: the base game prices a repair from the item's value and the condition restored, so a
valuable weapon in bad shape costs more than an early bank balance holds. Ways to make it fit:

1. **Pay as you go (layaway by condition):** leave the item at a dropbox; each payment buys a
   step of condition (say 10 percent). Collect it at any point with what's been paid for, or leave
   it until it's whole. No lump sum, no lock-in.
2. **Parts credit:** spares you hand in (Smart Loot already keeps spares of your weapon) or repair
   kits and scrap pay for part of the work, so the bill depends on what you bring, not only on the
   item's value. Uniques have no spares, so they still cost the most.
3. **Repair on credit:** the bank fronts the repair as a loan (interest by credit grade; unpaid,
   the debt collectors come). Ties into what's built.
4. **Labour pricing:** charge for the work (condition restored x a rate by weapon type), not the
   item's value. Cheapest to build, but breaks parity with the game's merchants.

Leaning: 1 with 2, and 3 as a way to pay. Open questions: the price basis (the game's value-based
cost or labour), how long an item is away (a day per step?), whether a partly repaired item can be
collected, and interest on unpaid layaway. Technically: condition can be read and set on an item
held in a container through xNVSE inventory references, keeping its weapon mods; needs a test.

## Kept for later (not building now)

- **Insurance** (on Mojave Express shipments and courier cash, with robbery events): parked.
- **Real estate:** better as its own mod, with properties that each have buying opportunities and
  running costs (in the spirit of Fable), and overlap with the bank through mortgages.
- **Commodity futures:** too abstract from play; dropped.
