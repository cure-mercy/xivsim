"""Turns the optimizer's potency into DPS for each of our players on a job, comparable with the scorecard's 0:00-2:00 rDPS.

    python tools/rotation/dps.py [--job blm|rpr] [--clears] [--site]

Per player, from their clean pulls (alive through 2:00):
  damage per potency   their plain hits (no crit, no direct hit), external buffs divided out, over the model potency
  crit / direct hit    their average hit over their plain hit, action by action (weighted by hits): over all hits
                       for the replay check (the log's hits carry others' crit buffs), and over the hits under no
                       crit or direct-hit raid buff for the ceiling (rDPS credits those buffs to their givers)
  DoT ticks            FFLogs reports ticks without crit or direct-hit flags; they count at the player's average tick
  GCD                  their unhasted GCD, from back-to-back casts
Check: each pull's logged casts, replayed through the model without buffs and converted, against the pull's logged
damage (buffs divided out) and against the scorecard's rDPS.
Ceiling: the best rotation without raid buffs at the player's GCD, converted. FFLogs' rDPS credits a raid buff's gain to
the job that gave it, so for a job without raid buffs rDPS is its damage with others' buffs divided out, and the best
unbuffed rotation is the rDPS ceiling. A job with a raid buff (Reaper's Arcane Circle) also gets credit for what it
added to the others' damage: the ceiling here leaves that out, and the scorecard site adds each pull's own credit to
it. The rotation stays the one unbuffed optimum. 0:00-2:00 is taken standing still (no forced movement).

--site writes each of our players' ceiling to .cache/ceilings.json, where the scorecard's build_site.py picks it up.
"""
import argparse, collections, json, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import calibrate, engine, logs                  # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import blm, rpr                        # noqa: E402

JOBS = {"blm": (blm, "BlackMage"), "rpr": (rpr, "Reaper")}
SITE_FILE = HERE / ".cache" / "ceilings.json"
WINDOW = 120
# raid buffs that raise crit or direct-hit rate (status ids as they appear on hits): Battle Voice, Battle Litany, Chain
# Stratagem, Devilment, the Wanderer's Minuet, Army's Paeon
CRIT_BUFFS = {"1000141", "1000786", "1001221", "1001825", "1002216", "1002218"}


def rates(pulls):
    """(crit rate, direct-hit rate) over the player's direct hits."""
    hits = [x for p in pulls for x in p["hits"] if x["type"] == "damage" and not x.get("tick") and x.get("amount", 0) > 0]
    return sum(x.get("hitType") == 2 for x in hits) / len(hits), sum(bool(x.get("directHit")) for x in hits) / len(hits)


def crit_gain(pulls, unbuffed=False):
    """The player's average direct hit over their average plain hit (no crit, no direct hit), per action and weighted
    by hits, in 0:00-2:00. `unbuffed`: only hits under no crit or direct-hit raid buff. (A formula from the crit rate
    overshoots by up to 3% when others' crit buffs raise the rate but not the crit damage.)"""
    allh, plain = collections.defaultdict(list), collections.defaultdict(list)
    for p in pulls:
        n = p["names"]
        for x in p["hits"]:
            if x["type"] != "damage" or x.get("tick") or not 0 <= x["t"] < WINDOW or x.get("amount", 0) <= 0: continue
            if unbuffed and CRIT_BUFFS & set((x.get("buffs") or "").strip(".").split(".")): continue
            a, v = n[str(x["abilityGameID"])], x["amount"] / x.get("multiplier", 1)
            allh[a].append(v)
            if x.get("hitType") == 1 and not x.get("directHit"): plain[a].append(v)
    use = [a for a in allh if len(plain[a]) >= 5]
    return sum(sum(allh[a]) for a in use) / sum(len(allh[a]) * st.mean(plain[a]) for a in use)


def logged_unbuffed(p, until=WINDOW, job=None):
    """The pull's logged damage in 0:00-until with external buffs divided out (tincture hits are kept). FFLogs'
    multiplier also holds the player's own damage-ups (Reaper's Death's Design): the job's own_factor puts them back."""
    own = getattr(job, "own_factor", lambda p, x: 1.0)
    return sum(x["amount"] / x.get("multiplier", 1) * own(p, x) for x in p["hits"] if x["type"] == "damage" and 0 <= x["t"] < until)


def tick_gain(pulls):
    """The player's average DoT tick over their median tick: ticks carry whatever crits they roll, unflagged."""
    v = [x["amount"] / x.get("multiplier", 1) for p in pulls for x in p["hits"] if x.get("tick") and x["type"] == "damage"]
    return st.mean(v) / st.median(v) if v else 1.0


def convert(s, k, e, et):
    """DPS over the window from a simulated state: direct hits at the expected crit/direct-hit gain, ticks at theirs."""
    dot = getattr(s, "dotp", 0.0)
    return k * (e * (s.dmg - dot) + et * dot) / WINDOW


_ceiling = {}


def ceiling(job, gcd, width):
    """The best unbuffed rotation over 0:00-2:00 at this GCD (cached per GCD), searched with the job's own settings."""
    key = (job.__name__, round(gcd, 2))
    if key not in _ceiling:
        job.SPEED = key[1] / engine.BASE_GCD
        _ceiling[key] = engine.search(job.__name__.split(".")[-1], Fight(until=WINDOW), width=width, speed=job.SPEED)[0]
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
        e, e0, et = crit_gain(ps), crit_gain(ps, unbuffed=True), tick_gain(ps)
        gcd = st.median(g for g in (calibrate.gcd_of(p) for p in ps) if g)
        job.SPEED = gcd / engine.BASE_GCD
        model, logged, sc = [], [], []
        for p in ps:
            s = calibrate.replay_fight(p, Fight(until=WINDOW))
            model.append(convert(s, k, e, et))
            logged.append(logged_unbuffed(p, job=job) / WINDOW)
            if p.get("rdps"): sc.append(p["rdps"])
        top = convert(ceiling(job, gcd, width), k, e0, et)
        rows.append(dict(name=name, pulls=len(ps), gcd=gcd, k=k, crit=crit, dh=dh, e=e, e0=e0, model=st.median(model),
                         logged=st.median(logged), rdps=st.median(sc) if sc else None, best=max(sc) if sc else None, ceiling=top))
    return rows


def show(rows, title):
    print(f"\n{title}")
    print(f"  {'player':<20} {'pulls':>5} {'GCD':>5} {'dmg/pot':>8} {'crit':>5} {'DH':>5} {'gain':>5} {'unbuf':>5}  {'rDPS':>7} {'best':>7}  "
          f"{'replay':>7} {'logged':>7}  {'ceiling':>7} {'median of':>9} {'best of':>8}")
    for r in rows:
        f = lambda v: f"{v:7,.0f}" if v else "      -"
        print(f"  {r['name']:<20} {r['pulls']:>5} {r['gcd']:5.2f} {r['k']:8.2f} {r['crit']:5.1%} {r['dh']:5.1%} {r['e']:5.3f} {r['e0']:5.3f}  {f(r['rdps'])} {f(r['best'])}  "
              f"{f(r['model'])} {f(r['logged'])}  {f(r['ceiling'])} " +
              (f"{r['rdps'] / r['ceiling']:9.1%} {r['best'] / r['ceiling']:8.1%}" if r["rdps"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="blm", choices=sorted(JOBS))
    ap.add_argument("--clears", action="store_true", help="also the benchmark clears' players (tincture hits are kept)")
    ap.add_argument("--width", type=int, default=None, help="beam width (default: the job's)")
    ap.add_argument("--site", action="store_true", help=f"save our players' ceilings for the scorecard site ({SITE_FILE.name})")
    a = ap.parse_args()
    job, jobname = JOBS[a.job]
    calibrate.use(a.job)
    rows = player_rows(job, logs.ours(jobname), a.width)
    show(rows, f"Our players on {jobname}, clean pulls, 0:00-2:00 (DPS)")
    print("  gain / unbuf: average hit over plain hit, all hits / hits under no crit or direct-hit raid buff;\n"
          "  rDPS/best: scorecard median / best of the clean pulls; replay: their casts through the model, at gain;\n"
          "  logged: their damage with others' buffs divided out; ceiling: best unbuffed rotation at their GCD, at unbuf\n"
          "  (a raid buff's credit for the others' damage, which rDPS includes, is not in it: the scorecard site adds it).")
    if a.site:
        saved = json.loads(SITE_FILE.read_text()) if SITE_FILE.exists() else {}
        saved[jobname] = {r["name"]: dict(ceiling=round(r["ceiling"]), gcd=r["gcd"], pulls=r["pulls"]) for r in rows}
        SITE_FILE.parent.mkdir(exist_ok=True)
        SITE_FILE.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
        print(f"\nsaved {len(rows)} ceilings to {SITE_FILE}")
    if a.clears:
        days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
        cl = [p for p in logs.clears(jobname) if days[(p["code"], p["fight"])] >= job.LOGS_SINCE]
        show(player_rows(job, cl, a.width), f"Benchmark clears' {jobname}s, 0:00-2:00 (DPS)")


if __name__ == "__main__":
    main()
