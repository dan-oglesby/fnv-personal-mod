"""Offline twin of Wasteland Exchange's maths, used as a test (run by build.py).

    python tools/exchange_sim.py

Mirrors ExRng.txt / ExNorm.txt / ExDay.txt / ExHit.txt step for step, then checks:
  - the random draws are uniform and independent (a linear hash once tied them together),
  - prices without news stay in a sensible band,
  - the best RobCo path (House's side: Securitron upgrade, Boomers, RACKET, Brotherhood, the Dam)
    lands near the agreed 5-6x, after trading costs.
Exits 1 if a check fails.
"""
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_exchange as g  # noqa: E402

M = 16777213


def md(x):
    q = int(x / M)
    x = x - q * M
    return x + M if x < 0 else x


def rng(seed, a, b, day):                       # ExRng.txt
    h = md(seed)
    for v in (a, b, day):
        h = md(h + v * 7919 + 1)
        h = md(h * h + 12345)
        h = md(h * 48271)
    h = md(h * h + 54321)
    h = md(h * 48271)
    return max(h, 1) / M


def norm(seed, a, b, day):                      # ExNorm.txt
    return (sum(rng(seed, a, b * 4 + k, day) for k in range(4)) - 2) * 1.7320508


def step(state, i, day, seed):                  # ExDay.txt, one ticker
    tk, name, ex, p0, vol, yld, sec, tr = g.TICKERS[i]
    L, S, W = state
    W = W * 0.95 + vol * (0.5 * norm(seed, 100 + sec, 0, day) + 0.866 * norm(seed, i, 1, day))
    S *= 0.9057
    L += tr
    return [L, S, W]


def price(i, state):
    return g.TICKERS[i][3] * math.exp(sum(state))


def hit(state, pct, mult):                      # ExHit.txt
    state[0] += math.log(mult)
    state[1] += math.log(max(1 + pct, 0.05))


def main():
    fails = []
    seed = 424242
    xs = [rng(seed, t, b, d) for t in range(14) for b in range(4) for d in range(150)]
    mean, sd = statistics.mean(xs), statistics.pstdev(xs)
    if abs(mean - 0.5) > 0.02 or abs(sd - 0.2887) > 0.02:
        fails.append("uniform draws off: mean %.3f sd %.3f" % (mean, sd))
    a = [rng(seed, 5, 4, d) for d in range(1500)]
    for label, b in (("adjacent b", [rng(seed, 5, 5, d) for d in range(1500)]),
                     ("other ticker", [rng(seed, 6, 4, d) for d in range(1500)]),
                     ("next day", a[1:] + a[:1])):
        c = statistics.correlation(a, b)
        if abs(c) > 0.08:
            fails.append("draws correlated (%s): %.3f" % (label, c))
    print("random draws: mean %.3f, sd %.3f (ideal 0.5, 0.289)" % (mean, sd))

    for i, t in enumerate(g.TICKERS):
        s = [0.0, 0.0, 0.0]
        lo = hi = t[3]
        for d in range(1, 121):
            s = step(s, i, d, seed)
            p = price(i, s)
            lo, hi = min(lo, p), max(hi, p)
        if not (0.5 * t[3] < lo and hi < 2.5 * t[3]):
            fails.append("%s wandered too far without news: %.1f-%.1f" % (t[0], lo, hi))
        print("%-5s 120 days, no news: %6.1f -> %6.1f (range %.1f-%.1f)" % (t[0], t[3], p, lo, hi))

    # best RobCo path: the House events as generated (E10, E13, E14, E15, E27)
    rb = g.T["RBCO"]
    house = {e[0]: e for e in g.EVENTS if e[0] in (10, 13, 14, 15, 27)}
    when = {20: 10, 30: 13, 40: 14, 50: 15, 70: 27}
    s = [0.0, 0.0, 0.0]
    buy = price(rb, s) * 1.015
    for d in range(1, 71):
        s = step(s, rb, d, seed)
        if d in when:
            for tk, pct, mult in house[when[d]][3]:
                if tk == "RBCO":
                    hit(s, pct, mult)
    sell = price(rb, s) * 0.985
    x = sell / buy
    print("RobCo, House's whole path, sold after the Dam news: %.2fx" % x)
    if not 4.5 <= x <= 6.5:
        fails.append("RobCo best path %.2fx, outside the agreed 5-6x" % x)

    for f in fails:
        print("SIM FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
