"""Tunes a job's heuristic settings (engine.search's portfolio) instead of guessing them.

    python tools/rotation/tune.py --job sam [--rounds 3] [--per 12] [--keep 4] [--seed 1]
    python tools/rotation/tune.py --job sam --candidate "[(185, 0.85, 0.0), (250, 0.8, 0.0)]"

A setting is (rate, scale, move weight): the rank's potency per second of time, a scale on the job's resource VALUEs,
and the weight on uncovered running (only for a job whose rank has a move_debt, the Black Mage). Each round
searches `per` settings in parallel in the site's fight (dps.py: the whole phase, no buffs, in the role's slot with the
most running before Palladion: R1 or M2), each a full search at
the job's SWEEP_WIDTH: the first round the job's current HEURISTICS and random settings (rate 0.75-1.35 times the
job's RATE, scale 0.3-2 on a log scale), later rounds settings around the best so far. The search is chaotic in its
settings (a nearby setting can find a quite different rotation), so the result is a portfolio: the best `keep`.

Tuned on one fight, a portfolio can fit that fight's noise (and it is the best of many tries against the few of the
current HEURISTICS), so both are then searched in the role's other slot (R2 or M1) and compared there. Prints both
and a HEURISTICS line to paste into the job's module. --candidate skips the tuning and compares a given portfolio with
the current one in both fights.
"""
import argparse, ast, math, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import dps, engine, p12s, solve                # noqa: E402

OTHER = {"R1": "R2", "R2": "R1", "M1": "M2", "M2": "M1"}


def rounded(rate, scale, mw):
    return (int(round(rate / 5) * 5), round(round(scale / 0.05) * 0.05, 2), mw)


def random_setting(job, rng, weights):
    return rounded(job.RATE * rng.uniform(0.75, 1.35), math.exp(rng.uniform(math.log(0.3), math.log(2.0))), rng.choice(weights))


def near(setting, rng, weights):
    rate, scale, mw = setting
    if rng.random() < 0.3: mw = rng.choice(weights)
    return rounded(rate * math.exp(rng.gauss(0, 0.08)), min(3.0, max(0.1, scale * math.exp(rng.gauss(0, 0.2)))), mw)


def portfolio(jobname, fight, settings, speed):
    """{setting: score} of a search under each setting."""
    _, _, scores = engine.search(jobname, fight, speed=speed, settings=list(settings), procs=len(settings))
    return dict(scores)


def compare(jobname, job, fight, title, current, tuned):
    """Search both portfolios in a fight and print their bests."""
    both = portfolio(jobname, fight, list(dict.fromkeys(current + tuned)), job.SPEED)
    c, t = max(both[x] for x in current), max(both[x] for x in tuned)
    print(f"\n{title}: current portfolio {c:,.1f}, tuned {t:,.1f} ({t / c - 1:+.2%})", flush=True)
    for x in sorted(both, key=lambda x: -both[x]):
        print(f"  {x}: {both[x]:,.1f}" + ("  current" if x in current else "") + ("  tuned" if x in tuned else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="blm", choices=sorted(solve.JOBS))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--per", type=int, default=12, help="settings searched per round, in parallel")
    ap.add_argument("--keep", type=int, default=4, help="settings in the tuned portfolio")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--candidate", help="a portfolio to compare with the current one, as a Python list, instead of tuning")
    ap.add_argument("--no-check", action="store_true", help="skip the comparison in the role's other slot")
    a = ap.parse_args()
    job = solve.JOBS[a.job][0]
    rng = random.Random(a.seed)
    moves = hasattr(job, "move_debt")              # every job has a MOVE_WEIGHT; only a rank with move_debt uses it
    weights = [0.0, 0.5, 1.0, 2.0] if moves else [0.0]
    current = list(dict.fromkeys((r, v, m if moves else 0.0) for r, v, m in getattr(job, "HEURISTICS", engine.HEURISTICS)))
    slot, fight = dps.site_fight(job, dps.FULL)
    other = p12s.fight(OTHER[slot], far_spots=getattr(job, "FAR", False))
    if a.candidate:
        tuned = [tuple(x) for x in ast.literal_eval(a.candidate)]
        compare(a.job, job, fight, f"{slot}, whole phase ({fight.until:.0f} s)", current, tuned)
        compare(a.job, job, other, f"{OTHER[slot]}, whole phase", current, tuned)
        return
    seen, t0 = {}, time.time()
    for r in range(a.rounds):
        if r == 0: batch = list(dict.fromkeys(current))
        else: batch = []
        top = sorted(seen, key=lambda x: -seen[x])[:3]
        tries = 0
        while len(batch) < a.per and tries < 1000:
            tries += 1
            x = random_setting(job, rng, weights) if r == 0 or not top else near(rng.choice(top), rng, weights)
            if x not in seen and x not in batch: batch.append(x)
        seen.update(portfolio(a.job, fight, batch, job.SPEED))
        best = max(seen, key=seen.get)
        print(f"round {r + 1}: {len(batch)} settings, best so far {best} = {seen[best]:,.1f} ({time.time() - t0:.0f} s)", flush=True)
    ranked = sorted(seen, key=lambda x: -seen[x])
    tuned = ranked[:a.keep]
    base = max(seen[x] for x in current)
    print(f"\n{slot}, whole phase ({fight.until:.0f} s), {len(seen)} settings searched:")
    for x in ranked[:max(a.keep, 8)]:
        print(f"  {x}: {seen[x]:,.1f}" + ("  (current)" if x in current else ""))
    print(f"  current portfolio's best {base:,.1f}; tuned {seen[tuned[0]]:,.1f} ({seen[tuned[0]] / base - 1:+.2%})")
    if not a.no_check: compare(a.job, job, other, f"{OTHER[slot]}, whole phase (the check)", current, tuned)
    print(f"\nHEURISTICS = {tuned}")


if __name__ == "__main__":
    main()
