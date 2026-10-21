"""Turns the optimizer's potency into DPS for each of our players on a job, comparable with the scorecard's 0:00-2:00 rDPS.

    python tools/rotation/dps.py [--job blm|rpr|mnk|brd|drg|rdm|vpr] [--clears] [--site [--gcds 2.30,2.40]]

Per player, from their clean pulls (alive through 2:00):
  damage per potency   their plain hits (no crit, no direct hit), external buffs divided out, over the model potency
  crit / direct hit    their average hit over their plain hit, action by action (weighted by hits): over all hits
                       for the replay check (the log's hits carry others' crit buffs), and over the hits under no
                       crit or direct-hit raid buff for the ceiling (rDPS credits those buffs to their givers)
  DoT ticks            FFLogs reports ticks without crit or direct-hit flags; they count at the player's average tick
  sure crits           hits that always crit (Monk's Bootshine in opo-opo form) count at their own average over the
                       model potency; those a buff makes sure (Dragoon's Life Surge) the model counts at their
                       expected worth, and they are left out of the crit / direct-hit gain
  GCD                  their unhasted GCD, from back-to-back casts
Check: each pull's logged casts, replayed through the model without buffs and converted, against the pull's logged
damage (buffs divided out) and against the scorecard's rDPS.
Ceiling: the best rotation without raid buffs at the player's GCD, converted. FFLogs' rDPS credits a raid buff's gain to
the job that gave it, so for a job without raid buffs rDPS is its damage with others' buffs divided out, and the best
unbuffed rotation is the rDPS ceiling. A job with a raid buff (Reaper's Arcane Circle) also gets credit for what it
added to the others' damage: the ceiling here leaves that out, and the scorecard site adds each pull's own credit to
it. The rotation stays the one unbuffed optimum. 0:00-2:00 is played with our strategy's runs (p12s.py), at their worst:
the Paradeigma I slot of the job's role with the most running before Palladion (R1 / R2, or M1 / M2) and each mechanic's
variant with the most, so the rotation holds whichever the player is given.

--site writes each of our players' ceiling to .cache/ceilings.json, and the optimized rotations behind them, one per GCD
(plus any --gcds), to .cache/rotations.json with the fight's timeline (mechanics, runs, out of reach), where the
scorecard's build_site.py picks both up. The site's rotations run on from the pull until Palladion takes Athena away
(ROT_UNTIL, ~4:41): a second search per GCD, since the engine scores a whole window and a rotation that goes on holds
resources a 0:00-2:00 one spends. Each also carries its 0:00-2:00 ceiling. A rotation's expected DPS
is the median of our players' conversions on the job, each moved to its GCD (the speed points that takes come out of
their other substats), so GCDs compare with each other.
"""
import argparse, collections, json, re, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import calibrate, engine, logs, p12s            # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import blm, brd, drg, mnk, rdm, rpr, vpr    # noqa: E402

JOBS = {"blm": (blm, "BlackMage"), "rpr": (rpr, "Reaper"), "mnk": (mnk, "Monk"), "brd": (brd, "Bard"),
        "drg": (drg, "Dragoon"), "rdm": (rdm, "RedMage"), "vpr": (vpr, "Viper")}
SITE_FILE = HERE / ".cache" / "ceilings.json"
ROT_FILE = HERE / ".cache" / "rotations.json"
WINDOW = 120
# Spell / Skill Speed comes out of the same substat budget as critical hit, direct hit and determination. Level-90
# formulas (substat base 400, divisor 1900): a speed point takes 130/1900 per mille off the GCD (58.5 points per 0.01 s
# of a 2.5 s GCD) and adds as much to DoT ticks; a point of the others is worth 0.068-0.074% damage at our players'
# rates, and the cheapest (direct hit, determination: 0.068%) is what a meld gives up. That is 0.40% damage per potency
# per 0.01 s of GCD; our Black Mages' conversions fall 0.38% per 0.01 s.
SPEED_PTS = 1900 * 1000 / (engine.BASE_GCD * 130)   # speed points per second of GCD
STAT_PT = 0.000068                                  # damage per point of the substat a speed point replaces
DOT_PT = 130 / 1900 / 1000                          # DoT damage per speed point
# raid buffs that raise crit or direct-hit rate (status ids as they appear on hits): Battle Voice, Battle Litany, Chain
# Stratagem, Devilment, the Wanderer's Minuet, Army's Paeon
CRIT_BUFFS = {"1000141", "1000786", "1001221", "1001825", "1002216", "1002218"}


def rates(pulls):
    """(crit rate, direct-hit rate) over the player's direct hits."""
    hits = [x for p in pulls for x in p["hits"] if x["type"] == "damage" and not x.get("tick") and x.get("amount", 0) > 0]
    return sum(x.get("hitType") == 2 for x in hits) / len(hits), sum(bool(x.get("directHit")) for x in hits) / len(hits)


def no_sure(job):
    """p -> {(time, ability id)} of the hits in pull p that a buff made sure crits (the job's sure_crits: Dragoon's Life Surge),
    left out with the AUTO_CRIT actions when measuring a player's own crit rate and gain."""
    return getattr(job, "sure_crits", lambda p: ())


def natural_crit(pulls, skip=(), sure=lambda p: ()):
    """The player's own critical-hit rate: hits under no crit raid buff, without the actions that always crit."""
    hits = [x for p in pulls for gone in [set(sure(p))] for x in p["hits"] if x["type"] == "damage" and not x.get("tick")
            and x.get("amount", 0) > 0 and p["names"][str(x["abilityGameID"])] not in skip
            and not CRIT_BUFFS & set((x.get("buffs") or "").strip(".").split(".")) and (x["t"], x["abilityGameID"]) not in gone]
    return sum(x.get("hitType") == 2 for x in hits) / len(hits)


def crit_gain(pulls, unbuffed=False, skip=(), sure=lambda p: ()):
    """The player's average direct hit over their average plain hit (no crit, no direct hit), per action and weighted
    by hits, in 0:00-2:00. `unbuffed`: only hits under no crit or direct-hit raid buff. (A formula from the crit rate
    overshoots by up to 3% when others' crit buffs raise the rate but not the crit damage.)"""
    allh, plain = collections.defaultdict(list), collections.defaultdict(list)
    for p in pulls:
        n, gone = p["names"], set(sure(p))
        for x in p["hits"]:
            if x["type"] != "damage" or x.get("tick") or not 0 <= x["t"] < WINDOW or x.get("amount", 0) <= 0: continue
            if unbuffed and CRIT_BUFFS & set((x.get("buffs") or "").strip(".").split(".")): continue
            a, v = n[str(x["abilityGameID"])], x["amount"] / x.get("multiplier", 1)
            if a in skip or (x["t"], x["abilityGameID"]) in gone: continue
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


def sure_gain(job, pulls, k, unbuffed=False):
    """Hits that always crit: their average logged damage (others' buffs divided out) over k times the model potency.
    `unbuffed`: only hits under no crit or direct-hit raid buff (a crit buff raises a sure crit's damage instead)."""
    names = getattr(job, "AUTO_CRIT", ())
    if not names: return None
    keep = (lambda x: not CRIT_BUFFS & set((x.get("buffs") or "").strip(".").split("."))) if unbuffed else (lambda x: True)
    v = [d / m for p in pulls for a, lab, d, m in calibrate.model_hits(p, WINDOW, keep)
         if a in names and "sure crit" in lab and m]
    return st.mean(v) / k if v else None


def convert(s, k, e, et, ec=None, window=WINDOW):
    """DPS over the window from a simulated state: direct hits at the expected crit/direct-hit gain, ticks and sure
    crits at theirs."""
    dot, sure = getattr(s, "dotp", 0.0), getattr(s, "critp", 0.0)
    return k * (e * (s.dmg - dot - sure) + et * dot + (ec or e) * sure) / window


_ceiling, _fight = {}, {}
ROT_UNTIL = p12s.load()["untargetable"][0][0]   # the site's rotations: until Palladion takes Athena away (281.65 s)


def site_fight(job, until=WINDOW):
    """(slot, Fight) the ceilings (and the site's rotations, until ROT_UNTIL) are searched in, with our strategy's runs
    for the role's slot with the most running before Palladion, each mechanic's variant with the most (p12s's
    default)."""
    if (job.__name__, until) not in _fight:
        slot = p12s.worst_slot(getattr(job, "MELEE", False), ROT_UNTIL)
        _fight[job.__name__, until] = (slot, p12s.fight(slot, until=until, far_spots=getattr(job, "FAR", False)))
    return _fight[job.__name__, until]


def timeline(job, until=ROT_UNTIL):
    """The site's timeline of the fight its rotations are searched in: major mechanics' starts, the runs (lo, hi,
    seconds needed, yalms, mechanic, what, source), a melee's stretches out of reach and spots fixed by the plan, boss
    away."""
    slot, f = site_fight(job, until)
    data, r = p12s.load(), lambda v: round(v, 1)
    return dict(slot=slot, window=until,
                mechanics=[[r(t), n] for t, n in p12s.mechanics(data) if t < until],
                runs=[[r(lo), r(hi), r(min(y / p12s.RUN, hi - lo)), r(y), mech, what, src]
                      for lo, hi, y, mech, what, src in p12s.windows(slot, None, data) if lo < until],
                away=[[r(lo), r(hi), need, mech, src] for lo, hi, need, mech, src in
                      p12s.out_of_reach(slot, None, data, getattr(job, "FAR", False)) if lo < until],
                pinned=[[r(lo), r(hi), mech] for lo, hi, mech in p12s.plan_spans(slot, None, data) if lo < until] if f.pinned else [],
                untargetable=[[r(a), r(b)] for a, b in f.untargetable if a < until])


def rot_key(gcd, crit=None):
    """The site's name for an optimized rotation: its GCD, and its crit rate for a job whose resources come from crits."""
    return f"{gcd:.2f}" + (f"-c{round(100 * crit)}" if crit is not None else "")


def ceiling(job, gcd, width, crit=None, until=WINDOW):
    """The best unbuffed rotation over 0:00-until (2:00 for the ceilings) with our strategy's runs (site_fight) at this
    GCD (and crit rate, for a job whose resources come from crits; cached per all three), searched with the job's own
    settings."""
    key = (job.__name__, round(gcd, 2), round(crit, 2) if crit is not None else None, until)
    if key not in _ceiling:
        job.SPEED = key[1] / engine.BASE_GCD
        _ceiling[key] = engine.search(job.__name__.split(".")[-1], site_fight(job, until)[1], width=width, speed=job.SPEED,
                                      params={"CRIT": key[2]} if key[2] is not None else None)[0]
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
        skip, sure = getattr(job, "AUTO_CRIT", ()), no_sure(job)
        e, e0, et = crit_gain(ps, skip=skip, sure=sure), crit_gain(ps, unbuffed=True, skip=skip, sure=sure), tick_gain(ps)
        ec, ec0 = sure_gain(job, ps, k), sure_gain(job, ps, k, unbuffed=True)
        own = natural_crit(ps, skip, sure) if hasattr(job, "CRIT") else None
        gcd = st.median(g for g in (calibrate.gcd_of(p) for p in ps) if g)
        job.SPEED = gcd / engine.BASE_GCD
        model, logged, sc = [], [], []
        for p in ps:
            s = calibrate.replay_fight(p, Fight(until=WINDOW))
            model.append(convert(s, k, e, et, ec))
            logged.append(logged_unbuffed(p, job=job) / WINDOW)
            if p.get("rdps"): sc.append(p["rdps"])
        opt = ceiling(job, gcd, width, own)
        top = convert(opt, k, e0, et, ec0)
        rows.append(dict(name=name, pulls=len(ps), gcd=gcd, k=k, crit=crit, dh=dh, e=e, e0=e0, et=et, ec0=ec0, model=st.median(model),
                         logged=st.median(logged), rdps=st.median(sc) if sc else None, best=max(sc) if sc else None, ceiling=top,
                         key=rot_key(round(gcd, 2), round(own, 2) if own is not None else None)))
    return rows


CAST_NOTE = re.compile(r"(\d+(?:\.\d+)?)s cast")     # a hard cast in the history's note: "2.00s cast"


def placed_runs(hist, fight):
    """[(start, end)]: where a rotation does its runs. The search only checks that each move window has the seconds it
    needs outside cast bars (a cast's last SLIDE counts), so this places them: in the window's longest stretches outside
    cast bars first (instant GCDs, not slidecast slivers), as late as each stretch allows."""
    busy = sorted((t, t + float(m.group(1)) - engine.SLIDE) for t, _, note in hist if (m := CAST_NOTE.search(note or "")))
    out = []
    for w in fight.moves:
        free, a = [], w.lo
        for b0, b1 in busy:
            if b1 <= w.lo or b0 >= w.hi: continue
            if b0 > a: free.append((a, b0))
            a = max(a, b1)
        if a < w.hi: free.append((a, w.hi))
        left = w.need
        for a, b in sorted(free, key=lambda x: (x[1] - x[0], x[1]), reverse=True):
            if left <= 1e-9: break
            take = min(left, b - a)
            out.append((b - take, b)); left -= take
    return sorted(out)


def site_rotation(job, s, until=ROT_UNTIL):
    """The site's rotation: [time, action, "g" for a GCD / "o" for an oGCD, cast time, seconds run], waits left out. A
    GCD's running is what placed_runs puts between its start and the next GCD's."""
    hist = s.history()
    acts = [(t, n, note) for t, n, note in hist if t < until and not n.startswith("(")]
    runs, gs = placed_runs(hist, site_fight(job, until)[1]), [t for t, n, _ in acts if n in job.GCDS]
    out = []
    for t, n, note in acts:
        m, run = CAST_NOTE.search(note or ""), 0.0
        if n in job.GCDS:
            nxt = next((g for g in gs if g > t), until)
            run = sum(engine._overlap(a, b, t, nxt) for a, b in runs)
        out.append([t, n, "g" if n in job.GCDS else "o", float(m.group(1)) if m else 0.0, round(run, 1)])
    return out


def rotations(job, rows, width, extra=()):
    """The site's optimized rotations for a job, {fight: timeline, rotations: {key: ...}}: at every GCD (and crit rate)
    searched for our players' ceilings, plus the extra GCDs (at the job's default crit rate), the best rotation until
    ROT_UNTIL, with its expected DPS at the median of our players' conversions and their range, and the 0:00-2:00
    ceiling's at the median. Each player is moved to the rotation's GCD first (SPEED_PTS, STAT_PT): a faster GCD costs
    them damage per potency, so GCDs compare at what a player would have there."""
    for g in extra: ceiling(job, g, width, getattr(job, "CRIT", None))
    def conv(s, r, gcd, w=ROT_UNTIL):
        """The rotation in a player's DPS, the player moved to its GCD: the speed points that takes come out of their
        other substats (or go back into them), and DoT ticks follow the speed."""
        pts = SPEED_PTS * (r["gcd"] - gcd)
        return convert(s, r["k"] * (1 - STAT_PT * pts), r["e0"], r["et"] * (1 + DOT_PT * pts), r["ec0"], w)
    out = {}
    for (jn, gcd, crit, until), s2 in sorted(_ceiling.items(), key=lambda x: (x[0][1], x[0][2] or 0)):
        if jn != job.__name__ or until != WINDOW: continue
        s = ceiling(job, gcd, width, crit, ROT_UNTIL)
        key, each = rot_key(gcd, crit), [conv(s, r, gcd) for r in rows]
        rot = site_rotation(job, s)
        out[key] = dict(gcd=gcd, crit=crit, window=ROT_UNTIL, potency=round(s.dmg), dps=round(st.median(each)), dps_lo=round(min(each)),
                        ceiling_2min=round(st.median(conv(s2, r, gcd, WINDOW) for r in rows)),
                        dps_hi=round(max(each)), players=sum(r["key"] == key for r in rows), conv_players=len(rows),
                        waste={w: n for w, n in zip(job.WASTE, s.waste) if n}, rotation=rot)
    return dict(fight=timeline(job), rotations=out, speed_cost=round(100 * STAT_PT * SPEED_PTS * 0.01, 2))


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
    ap.add_argument("--site", action="store_true", help=f"save our players' ceilings and the optimized rotations for the scorecard site "
                    f"({SITE_FILE.name}, {ROT_FILE.name})")
    ap.add_argument("--gcds", help="with --site: also optimize at these GCDs (comma-separated), for the site's rotation pages")
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
        saved[jobname] = {r["name"]: dict(ceiling=round(r["ceiling"]), gcd=r["gcd"], pulls=r["pulls"], rotation_key=r["key"])
                          for r in rows}
        SITE_FILE.parent.mkdir(exist_ok=True)
        SITE_FILE.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
        rots = json.loads(ROT_FILE.read_text()) if ROT_FILE.exists() else {}
        rots[jobname] = rotations(job, rows, a.width, [float(g) for g in a.gcds.split(",")] if a.gcds else ())
        ROT_FILE.write_text(json.dumps(rots, indent=1, ensure_ascii=False))
        print(f"\nsaved {len(rows)} ceilings to {SITE_FILE} and {len(rots[jobname]['rotations'])} rotations to {ROT_FILE}")
    if a.clears:
        days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
        cl = [p for p in logs.clears(jobname) if days[(p["code"], p["fight"])] >= job.LOGS_SINCE]
        show(player_rows(job, cl, a.width), f"Benchmark clears' {jobname}s, 0:00-2:00 (DPS)")


if __name__ == "__main__":
    main()
