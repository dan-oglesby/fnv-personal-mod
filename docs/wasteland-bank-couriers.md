# Wasteland Bank: courier squads, the vault and government debt (plan, 2026-11-16)

**The idea underneath:** the currency you hold is an implicit bet on how the war ends. Caps ride
on House or an independent Vegas, NCR dollars on the NCR, denarii on the Legion, and the news that
moves the war moves the rates.

Money gets weight, so a fortune can't sit in your pocket, and the bank stops being a teleporter:
every movement of physical cash or goods goes through a **courier squad** you call with the bank
card. The squad is the bank's only counter. There are no fixed tellers or brokers anywhere.

## Phase 1: weight, the squad, cash and the vault

- **Weight** (set on every load, since base-item changes aren't saved): bottle cap 0.0047 lb
  (1,000 caps about 4.7 lb), NCR notes 0.0022 lb, denarius 0.0085 lb (mangled too), aureus 0.018 lb.
- **Calling:** the card's main menu calls a squad. It arrives 1 to 2 game hours later (not in combat
  or VATS; it waits), three couriers spawned a short way behind you. They're essential (knocked
  down, never killed), have no faction and aren't aggressive, and they stay near where they arrived.
  They leave once you've gone about 60 m away, after 3 game hours, or when you send them off.
- **While they're here** (within about 15 m) the card offers their services; walking up to them
  the first time opens it on its own:
  - deposit and withdraw caps, and convert NCR, Legion and pre-war money, for a **2% fee** on what
    they move (charged to your balance);
  - **the vault:** a container screen onto your own storage at the bank. Whatever you put in or take
    out is carried by the squad, at **1 cap per pound each way**;
  - loans are paid out and repaid in cash, so through the squad too.
  Auto-deposit and auto-convert happen when a squad arrives, not on their own.
- **Cash on hand** (to build: phase 1's withdraw has no limit yet): the account manager sees that
  every squad carries a float of 2,500 caps, drawn from your balance (less if your balance is
  less). That's the most you can withdraw from a squad called the ordinary way; a larger sum is
  ordered when calling and delivered by a squad at least 24 hours later, like cash-out orders
  (Dan was fine either way; this keeps one rule). Deposits have no limit.
- **Selling through the squad** (built with phase 1): "sell all junk" in one go, or hand-pick
  anything in a consignment box. They sell to merchants at half the current market value (Wasteland
  Market's prices), keep 10 percent, and the rest reaches your balance a day later. The sales move
  Wasteland Market's prices like any selling. Quest items, money and casino chips aren't sold.
- **Casino chips** convert to caps at 1 each, with the usual fee.
- With no squad: balances, settings, prices and your portfolio can still be read.
- Fees come out of your balance; if it's short, from the caps you carry; whatever is left is added
  to your loan.

## Phase 2: the exchange and NCR war bonds through the squad

- Trading on the Wasteland Exchange only while a squad is here (prices can be read any time).
- Hand the squad NCR dollars and they're invested in NCR War Bonds (ticker NCRB).
- **Cash-out orders:** order a sale of your bonds (or other holdings) any time you have them; the
  money is delivered in that currency (NCR notes for war bonds) by the next squad you call at least
  24 hours after the order.
- **Wasteland Bank stock (WBNK)** on the New Vegas exchange, small enough to buy a controlling
  stake (over half the shares). With control, the bank's settings gain the fee levels: the cash
  fee, the vault rate per pound and the loan rate. Decided behavior:
  - it trades like a safe, dividend-paying bank today: low volatility (about 20 percent a year)
    and a steady dividend yield of about 3 to 4 percent at the start, with the price following how
    the bank is doing (its fee revenue, including the fees you pay);
  - **dividend reinvestment:** your dividends always buy shares from other shareholders, so your
    stake grows by itself, slowly;
  - **as you own more, the float thins:** volatility and the price rise with your share of the
    company, while the dividend per share stays about the same (so its yield falls);
  - the stake's size and cost (open): a controlling stake as a mid-game goal, around 20,000 to
    30,000 caps at the start.

- **Currency accounts:** keep your balance in caps, NCR dollars or denarii (the squad converts
  between them at the usual fee), so holding a currency is a choice and a bet. **Each pays its own
  interest** (decided): the riskier the currency, the more it pays, so backing a faction earns
  something while it holds up. Proposed: caps the base rate, NCR dollars 1.5 times it, denarii 2.5
  times, each nudged up when its side takes bad news (risk premium) and down on good.
- **A Vegas index fund:** one ticker on the New Vegas exchange that holds every listed stock across
  the exchanges (index-style investing in a single purchase). Stocks only; equal weights unless
  decided otherwise.
- **A sovereign debt fund** (decided: a second fund rather than mixing debt into the index): NCR
  War Bonds and Legion treasury debt in one ticker, a bet on governments paying their debts,
  whoever wins. Legion debt joins it once phase 3 exists.
- **Currency effects of your investing:** net buying of NCR assets (war bonds, Hub-listed stocks)
  supports the NCR dollar a little, selling weakens it, and the same for Legion debt and the
  denarius. Small, building up over time and fading, so the rates still follow the faction story.

- **Managed account: a trader betting for you, the high roller.** Hand part of your balance (through
  the squad) to the bank's trader, who trades it on the real exchange prices:
  - a separate portfolio, rebalanced every few days by rules that chase news and momentum: piling
    into tickers on good news, shorting the ones on bad, betting on currencies with the war, with
    some randomness so no two runs match;
  - risk dial: Steady (index-like, no leverage), Bold, or High roller (the default: concentrated
    bets on margin up to 2x, which can double the account or wipe most of it out);
  - the trader is only a correspondent, not a character (decided): a weekly report as a message
    from "your account manager" ("up 14 percent: long Gomorrah on the Benny news, short NCR War
    Bonds before the Dam");
  - fees of 2 percent a month plus 20 percent of new profits (above the account's previous high), the
    bank's revenue like the courier fees;
  - a stop: at 25 percent of what you put in, the trader closes everything and hands back what's
    left; you can never owe more than you put in;
  - withdrawals as cash-out orders, delivered by a squad at least 24 hours later.

- **Wasteland Bank notes** (built): the bank's own paper money, 10 and 100 caps at face, worth face
  times the bank's share price against its start, so they strengthen with the bank. Free to take
  from or turn in to the couriers; merchants take them at their worth.
- **Customer tiers** (built): High roller to start, Trader once the bank has earned 2,500 caps
  from you, Mogul from 15,000. Each tier lowers the fees (by a quarter, then half), raises the
  float (2,500 / 5,000 / 10,000), speeds the couriers, raises interest (1 / 1.1 / 1.25 times) and
  cuts the managed account's monthly fee (2 / 1.5 / 1 percent). The managed account's riskiest
  setting is called All in, so High roller names only the tier.
- **The NCR's tax** (built): if the NCR wins the Dam and play goes on (a post-ending mod), 5 percent
  of each month's investment profits.
- Built as planned: currency accounts, the market-cap-weighted Vegas Total Market Fund (VIDX),
  the sovereign debt fund (SOVD), WBNK with fee control, currency effects of investing, and the
  managed account with faction and company exclusions. The bank's stock and the two funds trade on
  their own board, "Funds and the bank".

## Phase 3: the Legion treasury (built with phase 2b)

Lending to Caesar instead of an equity market (the Legion has none; Rome ran on state loans and
*publicani*, private contractors who supplied the army or collected a province's tribute).

- **Treasury loans:** lend denarii for a fixed term (30 days), with a weekly coupon in denarii and
  the principal back at the end. Fixed in denarii, so their worth in caps follows the denarius.
- **Publicani contracts:** a few offered at a time, each sold once: grain for the Fort, Arizona
  tribute, the caravan roads. Payouts follow the frontier news (a march on the Dam pays a bonus; the
  Khans breaking with Caesar hurts the roads); only losing the Dam voids them.
- Needs Legion reputation of at least Accepted (a floor that stays). Vilified: they repudiate what
  they owe you.
- No secondary market; leaving a loan early costs a heavy penalty. Paid in denarii and aurei.
- **Default only over the Dam** (decided: nothing else touches the treasury's risk, not Lanius or
  Caesar's death): if the Legion loses the battle for the Dam, 75% is lost at once, and what's left shrinks to nothing over 30 days. When the last payout is collected, the
  Legion's business ends with a short goodbye: their paymaster has fled down the river.
- Denarii handed to a squad go into treasury loans, and cash-out orders work as in phase 2.

## Phase 4 (to research): faction presence follows faction fortunes

NCR and Legion patrols, vanilla and from spawn mods such as Increased Wasteland Spawns, become
rarer the worse each government is doing (their currency and news state), and caps gain against
both as House or an independent Vegas does well (the House and Yes Man paths already move the
rates; this would make it consistent). First step: find how those patrols are spawned (leveled
lists and their chance of none, encounter markers) and whether that can be scaled at run time.

## Phase 5 (planned): an international market

Cap-denominated emerging-market companies from beyond the Mojave, quoted on a much longer lag and
far more volatile; companies list, grow, fail and vanish over time. The Vegas Total Market Fund
holds them too, by market cap, making it a total international fund. A long list of
interchangeable company names and places (in the spirit of Klamath traders) is to be drawn from
the Old World Blues mod for Hearts of Iron IV installed on Dan's machine: anything taken from that
mod stays local, generated into an untracked file and never committed to this public repository.

## Phase 6 (planned): wealth unlocks, and the kingpin

- Options grow with your total wealth: a bank balance, then the exchange, the managed account, and
  at the top your own hedge fund. At that scale individual stocks give way to sector portfolios.
- Government debt follows your main-quest allegiance.
- Around a million caps (House's league), your management team can move markets underhandedly:
  random events you can steer, flagged by which faction to hurt (bear raids, a run on a currency,
  shorting caps while crashing it). Getting caught carries fines and reputation damage.
- House intervenes against your team when its moves cut against his interest; your team's chance
  of beating him grows with the size of your account.
