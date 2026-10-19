"""Turns the optimizer's potency into DPS for each of our players on a job, comparable with the scorecard's 0:00-2:00 rDPS.

    python tools/rotation/dps.py [--job blm] [--clears]

Per player, from their clean pulls (alive through 2:00):
  damage per potency   their plain hits (no crit, no direct hit), external buffs divided out, over the model potency
  crit / direct hit    the share of their hits that crit / direct-hit; crit damage = 1.35 + crit rate (same stat)
  DoT ticks            FFLogs reports ticks without crit or direct-hit flags; they count at the player's average tick
  GCD                  their unhasted GCD, from back-to-back casts
Check: each pull's logged casts, replayed through the model without buffs and converted, against the pull's logged
damage (buffs divided out) and against the scorecard's rDPS.
Ceiling: the best rotation without raid buffs at the player's GCD, converted. FFLogs' rDPS credits a raid buff's gain to
the job that gave it, so for a job without raid buffs rDPS is its damage with others' buffs divided out, and the best
unbuffed rotation is the rDPS ceiling. Paradeigma I is taken standing still (no forced movement).
"""
import argparse, collections, json, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import calibrate, engine, logs                  # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import blm                             # noqa: E402

JOBS = {"blm": (blm, "BlackMage")}
WINDOW = 120
DH_BONUS = 0.25


def rates(pulls):
    """(crit rate, direct-hit rate) over the player's direct hits."""
    hits = [x for p in pulls for x in p["hits"] if x["type"] == "damage" and not x.get("tick") and x.get("amount", 0) > 0]
    return sum(x.get("hitType") == 2 for x in hits) / len(hits), sum(bool(x.get("directHit")) for x in hits) / len(hits)


def expected(crit, dh):
    return (1 + crit * (0.35 + crit)) * (1 + DH_BONUS * dh)


def logged_unbuffed(p, until=WINDOW):
    """The pull's logged damage in 0:00-until with external buffs divided out (tincture hits are kept)."""
    return sum(x["amount"] / x.get("multiplier", 1) for x in p["hits"] if x["type"] == "damage" and 0 <= x["t"] < until)


def tick_gain(pulls):
    """The player's average DoT tick over their median tick: ticks carry whatever crits they roll, unflagged."""
    v = [x["amount"] / x.get("multiplier", 1) for p in pulls for x in p["hits"] if x.get("tick") and x["type"] == "damage"]
    return st.mean(v) / st.median(v) if v else 1.0


def convert(s, k, e, et):
    """DPS over the window from a simulated state: direct hits at the expected crit/direct-hit gain, ticks at theirs."""
    return k * (e * (s.dmg - s.dotp) + et * s.dotp) / WINDOW


_ceiling = {}


def ceiling(job, gcd, width):
    """The best unbuffed rotation over 0:00-2:00 at this GCD (cached per GCD)."""
    key = round(gcd, 2)
    if key not in _ceiling:
        job.SPEED = key / engine.BASE_GCD
        _ceiling[key] = engine.beam(job, Fight(until=WINDOW), width=width)
    return _ceiling[key]


def player_rows(job, pulls, width):
    by = collections.defaultdict(list)
    for p in pulls: by[p["name"]].append(p)
    rows = []
    for name, ps in sorted(by.items()):
        hits = [h for p in ps for h in calibrate.plain_hits(p, WINDOW + 5)]
        if len(hits) < 10: continue
        k = st.median(v / m for _, _, v, m in hits)
        crit, dh = rates(ps)
        e, et = expected(crit, dh), tick_gain(ps)
        gcd = st.median(g for g in (calibrate.gcd_of(p) for p in ps) if g)
        job.SPEED = gcd / engine.BASE_GCD
        model, logged, sc = [], [], []
        for p in ps:
            s = calibrate.replay_fight(p, Fight(until=WINDOW))
            model.append(convert(s, k, e, et))
            logged.append(logged_unbuffed(p) / WINDOW)
            if p.get("rdps"): sc.append(p["rdps"])
        top = convert(ceiling(job, gcd, width), k, e, et)
        rows.append(dict(name=name, pulls=len(ps), gcd=gcd, k=k, crit=crit, dh=dh, e=e, model=st.median(model),
                         logged=st.median(logged), rdps=st.median(sc) if sc else None, best=max(sc) if sc else None, ceiling=top))
    return rows


def show(rows, title):
    print(f"\n{title}")
    print(f"  {'player':<20} {'pulls':>5} {'GCD':>5} {'dmg/pot':>8} {'crit':>5} {'DH':>5}  {'rDPS':>7} {'best':>7}  "
          f"{'replay':>7} {'logged':>7}  {'ceiling':>7} {'median of':>9} {'best of':>8}")
    for r in rows:
        f = lambda v: f"{v:7,.0f}" if v else "      -"
        print(f"  {r['name']:<20} {r['pulls']:>5} {r['gcd']:5.2f} {r['k']:8.2f} {r['crit']:5.1%} {r['dh']:5.1%}  {f(r['rdps'])} {f(r['best'])}  "
              f"{f(r['model'])} {f(r['logged'])}  {f(r['ceiling'])} " +
              (f"{r['rdps'] / r['ceiling']:9.1%} {r['best'] / r['ceiling']:8.1%}" if r["rdps"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="blm", choices=sorted(JOBS))
    ap.add_argument("--clears", action="store_true", help="also the benchmark clears' players (tincture hits are kept)")
    ap.add_argument("--width", type=int, default=1500)
    a = ap.parse_args()
    job, jobname = JOBS[a.job]
    show(player_rows(job, logs.ours(jobname), a.width), f"Our players on {jobname}, clean pulls, 0:00-2:00 (DPS)")
    print("  rDPS/best: scorecard median / best of the clean pulls; replay: their casts through the model, converted;\n"
          "  logged: their damage with others' buffs divided out; ceiling: best unbuffed rotation at their GCD, converted.")
    if a.clears:
        days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
        cl = [p for p in logs.clears(jobname) if days[(p["code"], p["fight"])] >= "2025-04-01"]
        show(player_rows(job, cl, a.width), f"Benchmark clears' {jobname}s, 0:00-2:00 (DPS)")


if __name__ == "__main__":
    main()
