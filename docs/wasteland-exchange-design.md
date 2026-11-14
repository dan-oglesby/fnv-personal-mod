# Wasteland Exchange: design (draft, not built)

A stock market inside Wasteland Bank, opened from the bank card's menu. Draft of 2026-11-14.

**Goals**
- You can get rich, especially by calling the war right.
- Dividends, with a reinvestment (DRIP) option.
- Prices react to news. Most shocks fade, but some events change a company's value for good.
- Disasters are permanent: wipe out the Van Graffs and their stock is gone.

## Exchanges

| Exchange | Backer | Currency | Flavor |
|---|---|---|---|
| **New Vegas Exchange (NVX)** | Mr. House | caps | House's capital market for rebuilding Vegas: the Strip families, Vegas industry, RobCo |
| **Hub Exchange (HX)** | NCR | NCR dollars (shown with the caps equivalent) | The NCR's old trading city; the Fallout 1 caravan houses and NCR debt |

The Legion runs no market. Legion gains show up as market-wide shocks.

## Listings

Start prices are in caps (HX converts at the current NCR-dollar rate). Volatility is daily. Yield is
the annual dividend at the start price, paid weekly. "Get rich" upside means the best case if the
player's choices go its way.

| Ticker | Company | Exch | Sector | Start | Vol | Yield | Get-rich upside |
|---|---|---|---|---|---|---|---|
| GUN | Gun Runners | both | arms | 120 | 2% | 3% | wartime demand, NCR contracts, Van Graffs gone |
| CRIM | Crimson Caravan Company | HX | trade | 80 | 2% | 5% | NCR wins, roads secured, rivals gone |
| VGE | Van Graff Energy (Silver Rush) | NVX | arms | 60 | 4% | 0% | the Big Deal (*Birds of a Feather*); **delisted if the family is wiped out** |
| MEX | Mojave Express | NVX | logistics | 30 | 3% | 2% | a safe Primm, the courier's legend |
| TOPS | The Tops (Chairmen) | NVX | casino | 50 | 2% | 4% | Strip stability, *Talent Pool* |
| GOMR | Gomorrah (Omertas) | NVX | casino | 45 | 3% | 4% | *How Little We Know* (foiled vs helped) |
| ULUX | Ultra-Luxe (White Glove Society) | NVX | casino | 70 | 2% | 3% | *Beyond the Beef* scandal or cover-up |
| WRNG | Atomic Wrangler (Garrets) | NVX | casino | 15 | 4% | 2% | Freeside stability, the Kings |
| RBCO | RobCo Industries (House) | NVX | tech | 200 | 2.5% | 1% | Securitron upgrade, House winning (several times) |
| HAPY | Happy Trails Caravan Co. | HX | trade | 25 | 3% | 3% | collapses when Honest Hearts begins (its expedition is ambushed) |
| WTRM | Water Merchants (Hub) | HX | utilities | 90 | 1% | 6% | drifts; steady income |
| FGO | Far Go Traders (Hub) | HX | trade | 35 | 2.5% | 4% | drifts; moves with CRIM |
| BRMN | Brahmin Barons index | HX | agriculture | 100 | 1.5% | 4% | drifts; NCR fortunes |
| NCRB | NCR War Bonds | HX | government | 100 | 0.5% | 8% | pays par if the NCR holds the Dam; **defaults if the Legion wins** |

## Price model (per stock, once per game day)

```
price = start × level × shock × wobble
```

- **level**: the permanent part. It starts at 1 and changes only through permanent events (e.g.
  ×1.5 for RBCO when the Securitrons are upgraded). It is also nudged by a long-term trend: growth
  stocks like RBCO and GUN rise a little over time.
- **shock**: news jumps that fade. An event sets, say, −40%. Each day the shock moves toward 1
  with a set half-life (e.g. 7 days). One event can do both, e.g. a −40% shock plus a −10% change
  to level.
- **wobble**: the day-to-day randomness. It reverts toward 1, so prices don't wander off, and
  stocks in one sector move partly together (arms, trade, casinos, NCR).
- **Reload-proof randomness**: each day's random draw comes from a hash of (save seed, ticker,
  day). Reloading a save replays the same prices, so the market can't be save-scummed.
- **Days you skip** (sleep, wait, fast travel): the tick catches up day by day, like the bank's
  interest.

## Dividends and DRIP

- Paid weekly: yield × price ÷ 52, per share. Paid into the bank balance, or reinvested.
- DRIP toggles per holding. Shares are fractional, so reinvesting is exact.
- A delisted stock stops paying.

## News

- Every event prints a headline through the menu's news feed and a corner message, e.g.
  "MOJAVE MARKET WIRE: Silver Rush massacre — Van Graff Energy delisted".
- Large random moves get their own generated headline ("Water Merchants slide on reports of
  contaminated wells").
- The exchange menu keeps the last 10 headlines.

## Events (from the game's own quest stages)

Detected on the daily tick (or on load), each once. QUST IDs are FalloutNV.esm.

| Event | Detected by | Effect |
|---|---|---|
| Van Graffs wiped out | Jean-Baptiste and Gloria both dead (their refs), or *Heartache by the Number* (VCassCompanion 0x15DA16) past stage 40 with both dead | **VGE delisted** (holders recover 5%); CRIM +20% shock and ×1.10 level; GUN ×1.05 level |
| The Big Deal goes through | *Birds of a Feather* (VMS29a 0x124123) stage 100 | VGE +35% shock, ×1.15 level |
| Alice McLafferty killed | *Pressing Matters* (VMS51 0x14EF5F) or *You Can Depend on Me* (VMS05 0xEDB37) stage 110 | CRIM −35% shock, ×0.85 level |
| Crimson secures the Mojave route | *You Can Depend on Me* completed | CRIM +15% shock, ×1.05 level |
| Primm gets an NCR sheriff | *My Kind of Town* (0xDA115) stage 110 | MEX +20%, ×1.10 level; NCRB +2% |
| Primm gets Meyers or Primm Slim | stage 120 or 130 | MEX +10% |
| Primm left lawless | stage 100 (all candidates dead) | MEX −30% shock, ×0.90 level |
| Omerta plot foiled | *How Little We Know* (VMS21 0x110A63) stage 50 | GOMR −40% shock, ×0.90 level (scandal); TOPS and ULUX +5% |
| Omerta plot goes ahead | stage 55 | GOMR +10%, then a Strip-wide −15% shock when it plays out |
| Securitrons upgraded | *The House Always Wins II* (VMQHouse2 0x147886) stage 100 | RBCO +30% shock, ×1.5 level; all NVX +5% |
| Securitrons destroyed | stage 110 | RBCO −50% shock, ×0.5 level |
| Mr. House killed | House's ref dead | RBCO ×0.3 level; all NVX −25% shock |
| President Kimball saved / killed | *The House Always Wins VI* (VMQHouse6 0x14788A) stage 100 / 130; *Arizona Killer* (VMQ03b 0x131F09) stage 100 | NCRB, CRIM and BRMN ±10 to 20% |
| Nelson retaken | *Restoring Hope* (VMS30 0x1214AA) stage 170 | NCRB +5%, CRIM ×1.05 level |
| Khans leave or fall | *Oh My Papa* (VMS45 0x140C3A) stage 50 / 40 | trade +5% (roads safer) |
| Honest Hearts begins | Happy Trails expedition ambushed | HAPY −80%, ×0.2 level |
| Dam battle starts (NCR / House / Yes Man / Legion side) | final quest stage per path | NCRB par ×1.0 or default ×0.2; RBCO and NVX ×2 on House's path; a market-wide crash on the Legion's |

The game normally ends at the Dam, so the payoff comes from positioning before that battle, as each
side's quests advance.

### How "get rich" plays out

Buying RBCO early at 200, then the Securitron upgrade (×1.5 and a shock), Strip stability, and
House's path at the Dam (×2) adds up to roughly 5× to 6×. With DRIP on steady payers alongside, 5,000
caps can grow to tens of thousands. Betting the other way, holding NCRB when the Legion wins, loses
most of it.

## Trading

- Buy at ask and sell at bid, with a 1–2% spread plus a small commission. The player's own trades
  don't move prices.
- Fractional shares. Buy in caps amounts (100/500/1,000/All).
- Later, maybe: short selling, and insider trades flagged by quest knowledge (selling GOMR before the
  plot goes public).

## Implementation sketch

Plugin-free, like the rest of Wasteland Bank: JIP aux variables on the player and xNVSE functions.
- **Per ticker:** `_wx<T>L` level, `_wx<T>S` shock, `_wx<T>W` wobble, `_wx<T>H` shares,
  `_wx<T>C` cost basis, `_wx<T>D` DRIP, `_wx<T>X` delisted.
- **Global:** `_wxSeed`, `_wxDay`, event done-flags `_wxE<n>`, and the news ring.
- **Daily tick:** the existing `Tick.txt` calls `WastelandBank/Exchange/Day.txt` once per elapsed
  game day.
- **Events:** checked with `GetStage` / `GetQuestCompleted` / `GetDead` on BuildRef'd forms; one
  function per event.
- **UI:** an **Exchange** button on the bank card's main menu, with a board (paged), a stock page
  (buy, sell, DRIP, recent headlines) and a portfolio page (value, gains, dividends paid).

Prerequisite: Wasteland Bank itself hasn't been playtested yet, so test that first.

## Open questions

1. Both exchanges, or one board in caps?
2. Short selling: now, later, or never?
3. How generous: is about 5–6× on the best calls, ~10× in a once-per-game case, about right?
