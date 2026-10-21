"""Searches for the highest-damage rotation of a job over P12S phase 1 and prints it.

    python tools/rotation/solve.py --job blm [--gcd 2.32] [--until 449] [--slot R1] [--var para2=debuff]
                                   [--party AST,SCH,DRG,DNC] [--still] [--move 30-36] [--pot] [--carry] [--width 1000]
                                   [--compare]

Damage is in potency (Xenoglossy 890), multiplied by the raid buffs active when each hit lands. By default there are none:
it is the job's own potency, whatever party it plays in. The fight is P12S P1's fixed timeline (p12s.py): Athena can't
be hit during Palladion, and the player has to run for each mechanic as our strategy places them. --compare replays every
clear's logged rotation under the same buffs and downtime (their own movement, not ours).
"""
import argparse, collections, dataclasses, json, statistics as st, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import engine, p12s                              # noqa: E402
from engine import Move                          # noqa: E402
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
    party = {x.strip().upper() for x in a.party.split(",") if x.strip()}
    buffs = []
    if party:
        times = buff_times()
        for name, (job, m) in BUFFS.items():
            if job not in party: continue
            for i in range(len(BURSTS)):
                t = times.get((name, i))
                if t is not None: buffs.append((name, t, t + 20, m))
    f = p12s.fight(a.slot, p12s.parse_var(a.var), until=a.until, still=a.still,
                   buffs=sorted(buffs, key=lambda b: b[1]), pot=a.pot, carry=a.carry)
    extra = [tuple(float(x) for x in w.split("-")) for w in a.move.split(",") if w.strip()]
    if extra: f = dataclasses.replace(f, moves=f.moves + [Move(s, e, e - s, why="--move") for s, e in extra])
    f.buffs = [b for b in f.buffs if b[1] < f.until]
    return f


def show(s, job, fight):
    print(f"\n{'time':>7}  action")
    W = [m for m in fight.moves if m.need > 0]
    i = 0
    for t, name, note in s.history():
        if t >= fight.until: break
        while i < len(W) and W[i].lo <= t:
            print(f"{'':7}  -- {W[i].lo:.1f}-{W[i].hi:.1f}s: run {W[i].need:.1f} s  {W[i].why}"); i += 1
        print(f"{t:7.2f}  {name:<17} {note}")
    print(f"\npotency by {fight.until:.0f}s: {s.dmg:,.0f}  ({s.dmg / fight.until:,.1f} per second)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="blm", choices=sorted(JOBS))
    ap.add_argument("--gcd", type=float, default=2.32, help="GCD length without haste, from the player's spell speed")
    ap.add_argument("--until", type=float, default=None, help="end of the scored window, s (default: the clears' median kill)")
    ap.add_argument("--slot", default="R1", choices=["R1", "R2"], help="Paradeigma I: R1 baits the first lasers, R2 the second")
    ap.add_argument("--var", action="append", help="a mechanic's variant, e.g. para2=debuff, sc1=laser, para3=cross")
    ap.add_argument("--still", action="store_true", help="no forced movement (the ceiling standing still)")
    ap.add_argument("--party", default="", help="jobs whose raid buffs are in the party, e.g. AST,SCH,DRG,DNC (default none)")
    ap.add_argument("--move", default="", help="extra windows (s) in which nothing may be hard-cast, e.g. 30-36,42-44")
    ap.add_argument("--pot", action="store_true", help="allow one tincture")
    ap.add_argument("--carry", action="store_true", help="also value resources still held at the end")
    ap.add_argument("--width", type=int, default=1000, help="beam width: states kept per step, per heuristic setting")
    ap.add_argument("--compare", action="store_true", help="replay the clears' logged rotations under the same buffs")
    a = ap.parse_args()
    job, jobname = JOBS[a.job]
    job.SPEED = a.gcd / engine.BASE_GCD
    fight = fight_for(a)
    print("raid buffs: " + (", ".join(f"{n} {s:.1f}s" for n, s, _, _ in fight.buffs) or "none"))
    print("boss away: " + ", ".join(f"{s:.1f}-{e:.1f}s" for s, e in fight.untargetable))
    run = sum(m.need for m in fight.moves)
    print(f"forced running: {run:.0f} s in {sum(1 for m in fight.moves if m.need)} windows" +
          ("" if a.still else f" (slot {a.slot}" + "".join(f", {v}" for v in a.var or []) + ")"))
    t0 = time.time()
    best, setting, scores = engine.search(a.job, fight, width=a.width, speed=job.SPEED)
    print(f"searched in {time.time() - t0:.0f} s under {len(scores)} heuristic settings; best {setting[0]}/s, values x{setting[1]}, running x{setting[2]} "
          f"(spread {min(v for _, v in scores):,.0f}-{max(v for _, v in scores):,.0f})")
    show(best, job, fight)
    if a.compare:
        import calibrate, logs
        days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
        free = dataclasses.replace(fight, moves=[])
        print(f"\nclears' rotations replayed under the same buffs (0:00-{fight.until:.0f}s; own GCD speed and movement differ):")
        for p in logs.clears(jobname):
            if days[(p["code"], p["fight"])] < "2025-04-01" or p["end"] < fight.until: continue
            s = calibrate.replay_fight(p, free)
            print(f"  {days[(p['code'], p['fight'])]} {p['name']:<18} GCD {calibrate.gcd_of(p):.2f}  {s.dmg:9,.0f}  ({s.dmg / best.dmg:.1%} of the optimum)")


if __name__ == "__main__":
    main()
