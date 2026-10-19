"""Searches for the highest-damage rotation of a job over the first two minutes of P12S P1 and prints it.

    python tools/rotation/solve.py --job blm [--gcd 2.32] [--until 120] [--party AST,SCH,DRG,DNC]
                                   [--move 30-36,42-44] [--pot] [--carry] [--width 2000] [--compare]

Damage is in potency (Xenoglossy 880), multiplied by the raid buffs active when each hit lands. Raid buffs land at the
median times seen in the benchmark clears. --compare replays every clear's logged rotation under the same buffs.
"""
import argparse, collections, json, statistics as st, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import engine                                    # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import blm                             # noqa: E402

JOBS = {"blm": (blm, "BlackMage")}
CRIT, CRIT_DMG, DH = 0.25, 1.60, 0.36            # typical rates at this gear level, for the value of crit and direct hit buffs
BUFFS = {   # name: (job, multiplier)
    "Divination": ("AST", 1.06), "Technical Finish": ("DNC", 1.05), "Brotherhood": ("MNK", 1.05), "Embolden": ("RDM", 1.05),
    "Searing Light": ("SMN", 1.05), "Arcane Circle": ("RPR", 1.03), "Dokumori": ("NIN", 1.05), "Starry Muse": ("PCT", 1.05),
    "Radiant Finale": ("BRD", 1.06),
    "Chain Stratagem": ("SCH", 1 + 0.10 * (CRIT_DMG - 1) / (1 + CRIT * (CRIT_DMG - 1))),
    "Battle Litany": ("DRG", 1 + 0.10 * (CRIT_DMG - 1) / (1 + CRIT * (CRIT_DMG - 1))),
    "Battle Voice": ("BRD", 1 + 0.20 * 0.25 / (1 + DH * 0.25)),
}
BURSTS = [(-10, 40), (100, 160), (220, 300), (350, 430)]


def buff_times():
    """Median landing time of each raid buff per burst in the benchmark clears."""
    import acts
    bench = json.loads((HERE.parent / "scorecard" / "benchmark.json").read_text())
    per = collections.defaultdict(list)
    for k in bench["kills"]:
        p = json.loads((HERE.parent / "scorecard" / ".cache" / "benchmark" / f"acts_{k['code']}_{k['fight']}.json").read_text())
        for t, n, _, _ in acts.buff_uses(p):
            i = next((i for i, (a, b) in enumerate(BURSTS) if a <= t < b), None)
            if i is not None: per[(n, i)].append(t)
    return {k: st.median(v) for k, v in per.items() if len(v) >= 3}


def fight_for(a):
    times = buff_times()
    party = {x.strip().upper() for x in a.party.split(",") if x.strip()}
    buffs = []
    for name, (job, m) in BUFFS.items():
        if job not in party: continue
        for i in range(len(BURSTS)):
            t = times.get((name, i))
            if t is not None and t < a.until: buffs.append((name, t, t + 20, m))
    moves = [tuple(float(x) for x in w.split("-")) for w in a.move.split(",") if w.strip()]
    return Fight(until=a.until, buffs=sorted(buffs, key=lambda b: b[1]), moves=moves, pot=a.pot, carry=a.carry)


def show(s, job, fight):
    print(f"\n{'time':>7}  action")
    for t, name, note in s.history():
        if t < fight.until: print(f"{t:7.2f}  {name:<14} {note}")
    print(f"\npotency by {fight.until:.0f}s: {s.dmg:,.0f}  ({s.dmg / fight.until:,.1f} per second)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="blm", choices=sorted(JOBS))
    ap.add_argument("--gcd", type=float, default=2.32, help="GCD length without haste, from the player's spell speed")
    ap.add_argument("--until", type=float, default=120)
    ap.add_argument("--party", default="AST,SCH,DRG,DNC", help="jobs whose raid buffs are in the party")
    ap.add_argument("--move", default="", help="windows (s) in which nothing may be hard-cast, e.g. 30-36,42-44")
    ap.add_argument("--pot", action="store_true", help="allow one tincture")
    ap.add_argument("--carry", action="store_true", help="also value resources still held at the end")
    ap.add_argument("--width", type=int, default=2000, help="beam width: states kept per step")
    ap.add_argument("--compare", action="store_true", help="replay the clears' logged rotations under the same buffs")
    a = ap.parse_args()
    job, jobname = JOBS[a.job]
    job.SPEED = a.gcd / engine.BASE_GCD
    fight = fight_for(a)
    print("raid buffs: " + (", ".join(f"{n} {s:.1f}s" for n, s, _, _ in fight.buffs) or "none"))
    if fight.moves: print("movement: " + ", ".join(f"{s:.0f}-{e:.0f}s" for s, e in fight.moves))
    t0 = time.time()
    best = engine.beam(job, fight, width=a.width, log=lambda m: print(m, file=sys.stderr))
    print(f"searched in {time.time() - t0:.0f} s")
    show(best, job, fight)
    if a.compare:
        import calibrate, logs
        days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
        print(f"\nclears' rotations replayed under the same buffs (0:00-{a.until:.0f}s; own GCD speed differs):")
        for p in logs.clears(jobname):
            if days[(p["code"], p["fight"])] < "2025-04-01": continue
            s = calibrate.replay_fight(p, fight)
            print(f"  {days[(p['code'], p['fight'])]} {p['name']:<18} GCD {calibrate.gcd_of(p):.2f}  {s.dmg:9,.0f}  ({s.dmg / best.dmg:.1%} of the optimum)")


if __name__ == "__main__":
    main()
