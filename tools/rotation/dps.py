"""Turns the optimizer's potency into DPS for each of our players on a job, comparable with the scorecard's 0:00-2:00 rDPS.

    python tools/rotation/dps.py [--job blm|rpr|mnk|brd|drg|rdm|vpr|sam|pct|mch|nin|smn|dnc] [--clears] [--site [--gcds 2.30,2.40] | --ceilings-only [--reports CODE,...]] [--offline]
                                 [--no-polish] [--restarts]

Per player, from their clean pulls (alive through 2:00):
  damage per potency   their plain hits (no crit, no direct hit), external buffs divided out, over the model potency
  crit / direct hit    their average hit over their plain hit, action by action (weighted by hits): over all hits
                       for the replay check (the log's hits carry others' crit buffs), and over the hits under no
                       crit or direct-hit raid buff for the ceiling (rDPS credits those buffs to their givers), there
                       pooled with their other pulls up to their own first death or Damage Down (logs.ours_more, the
                       acts caches: about three times the hits; on the same pulls they agree within ~0.2% on average)
  DoT ticks            FFLogs reports ticks without crit or direct-hit flags and splits a target's combined tick
                       between players: their sum over FFLogs' own 100% ticks (tick_gain; for the ceiling, ticks
                       snapshotted under no crit or direct-hit raid buff); the model's tick potency is the tooltip's,
                       with the speed bonus at the player's speed (dot_tick)
  sure crits           hits that always crit (Monk's Bootshine in opo-opo form) count at their own average over the
                       model potency; those a buff makes sure (Dragoon's Life Surge) the model counts at their
                       expected worth, and they are left out of the crit / direct-hit gain
  GCD                  their unhasted GCD, from back-to-back casts
Check: each pull's logged casts, replayed through the model without buffs and converted, against the pull's logged
damage (buffs divided out) and against the scorecard's rDPS.
Ceiling: the best rotation without raid buffs at the player's GCD (the search's best, polished by polish.py unless
--no-polish), converted. FFLogs' rDPS credits a raid buff's gain to
the job that gave it, so for a job without raid buffs rDPS is its damage with others' buffs divided out, and the best
unbuffed rotation is the rDPS ceiling. A job with a raid buff (Reaper's Arcane Circle) also gets credit for what it
added to the others' damage: the ceiling here leaves that out, and the scorecard site adds each pull's own credit to
it. The rotation stays the one unbuffed optimum. 0:00-2:00 is played with our strategy's runs (p12s.py), at their worst:
the Paradeigma I slot of the job's role with the most running before Palladion (R1 / R2, or M1 / M2) and each mechanic's
variant with the most, so the rotation holds whichever the player is given.

--site writes each of our players' ceiling to .cache/ceilings.json (pooled over their nights, and per night from that
night's own pulls where it has NIGHT_PULLS or more: gear changes over the season; --ceilings-only writes just these,
and with --reports only what those reports touch: their players' nights in them and those players' pooled ceilings;
--job auto runs each job those reports have, one process each, as the scorecard's worker does after a build), and the optimized rotations behind them, one per GCD
(plus any --gcds), to .cache/rotations.json with the fight's timeline (mechanics, runs, out of reach), where the
scorecard's build_site.py picks both up. The site's rotations are a second search per GCD, over the whole phase (to
the clears' median kill, FULL), shown and scored up to where our groups' progress reaches, Palladion taking Athena away
(ROT_UNTIL, ~4:41). Not a search for that window: a rotation that has to go on holds resources one that ends there
spends, and as progress moves on the site shows more of the same rotation rather than a new one. Each also carries
its 0:00-2:00 ceiling. A rotation's expected DPS
is the median of our players' conversions on the job, each moved to its GCD (the speed points that takes come out of
their other substats), so GCDs compare with each other. For a job none of our players plays (Ninja), they convert at the
benchmark clears' players on it since the job's CONVERT_SINCE instead, at the GCDs those play, and the site says so.
"""
import argparse, collections, json, re, statistics as st, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import calibrate, engine, logs, p12s, polish    # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import JOBS                        # noqa: E402

SITE_FILE = HERE / ".cache" / "ceilings.json"
ROT_FILE = HERE / ".cache" / "rotations.json"
WINDOW = 120
# Spell / Skill Speed comes out of the same substat budget as critical hit, direct hit and determination. Level-90
# formulas (substat base 400, divisor 1900): a speed point takes 130/1900 per mille off the GCD (58.5 points per 0.01 s
# of a 2.5 s GCD) and adds as much to DoT ticks; a point of the others is worth 0.0068-0.0074% damage at our players'
# rates, and the cheapest (direct hit, determination: 0.0068%) is what a meld gives up. That is 0.40% damage per potency
# per 0.01 s of GCD; our Black Mages' conversions fall 0.38% per 0.01 s.
SPEED_PTS = 1900 * 1000 / (engine.BASE_GCD * 130)   # speed points per second of GCD
STAT_PT = 0.000068                                  # damage per point of the substat a speed point replaces
# raid buffs that raise crit or direct-hit rate (status ids as they appear on hits): Battle Voice, Battle Litany, Chain
# Stratagem, Devilment, the Wanderer's Minuet, Army's Paeon
CRIT_BUFFS = {"1000141", "1000786", "1001221", "1001825", "1002216", "1002218"}
# ...the others' (crit rate, direct-hit rate), for a job whose sure hits all come under them (SURE_BUFFED: sure_gain)
CRIT_RATES = {"1000141": (0, 0.20), "1000786": (0.10, 0), "1001221": (0.10, 0), "1002216": (0.02, 0), "1002218": (0, 0.03)}


PLAIN, DH, CRIT = 1.12, 1.37, 1.73     # flag_hits: a hit over its plain level is plain below 1.12, then direct hit, crit, both


def flag_hits(job, pulls):
    """Sets the crit / direct-hit flags offline logs lack (logs.ours_offline), player by player: each hit against its
    plain level. Hits of one action and bonusPercent at one model potency (own damage-ups divided out) form a group,
    whose plain level is the median of its hits within 13% of its lowest tenth; a group of fewer than 8 uses the
    player's level over all model hits, and an unlabelled one (no model potency) of fewer than 8 stays unflagged
    (hitType 0: neither plain nor crit). Sure crits (AUTO_CRIT) are crits whatever their level."""
    def level(v):
        v = sorted(v); lo = v[len(v) // 10] * 1.13
        return st.median(x for x in v if x <= lo)
    sure = getattr(job, "AUTO_CRIT", ())
    by = collections.defaultdict(list)
    for p in pulls: by[p["name"]].append(p)
    for ps in by.values():
        job.SPEED = player_speed(job, ps)
        groups, model = collections.defaultdict(list), {}
        for p in ps:
            for _, _, v, m, h in calibrate.model_hits(p, p["end"], lambda x: True, hit=True):
                if m: model[id(h)] = m
        for p in ps:
            for h in p["hits"]:
                if h["type"] != "damage" or h.get("tick"): continue
                m = model.get(id(h))
                groups[p["names"][str(h["abilityGameID"])], h.get("bonusPercent", 0), m].append((h["amount"] / h.get("multiplier", 1), h))
        whole = level([v / k[2] for k, g in groups.items() if k[2] for v, _ in g])
        for (name, _, m), g in groups.items():
            base = level([v for v, _ in g]) if len(g) >= 8 else whole * m if m else None
            for v, h in g:
                r = v / base if base else None
                h["hitType"] = 0 if r is None else 2 if r >= DH or name in sure else 1
                h["directHit"] = r is not None and (PLAIN <= r < DH or r >= CRIT)
    return pulls


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


def tick_gain(pulls, unbuffed=False):
    """The player's DoT ticks' crit and direct-hit gain: what they dealt over their plain (100%) value. The game sends
    one combined tick for every DoT on a target and FFLogs splits it between players by each one's simulated tick, so a
    single tick is no roll of the player's, but the split hands out the real total: their ticks' sum over the sum of
    FFLogs' own 100% ticks (T, `expectedAmount`, from the game's packet). Ticks the game sends as hits of their own
    (Slipstream's ground effect) carry crit and direct-hit flags: per DoT, their sum over as many plain ones.
    `unbuffed`: only ticks snapshotted under no crit or direct-hit raid buff. None without either (offline logs)."""
    num = den = 0.0
    real = collections.defaultdict(list)
    for p in pulls:
        for x in p["hits"]:
            if not x.get("tick") or x["type"] != "damage" or x.get("amount", 0) <= 0: continue
            if unbuffed and CRIT_BUFFS & set((x.get("buffs") or "").strip(".").split(".")): continue
            if x.get("expectedAmount"): num += x["amount"]; den += x["expectedAmount"]
            else: real[p["names"][str(x["abilityGameID"])]].append(x)
    for xs in real.values():
        if not any(x.get("hitType") == 2 or x.get("directHit") for x in xs): continue     # unflagged: offline
        plain = [x["amount"] / x.get("multiplier", 1) for x in xs if x.get("hitType") == 1 and not x.get("directHit")]
        if len(plain) < 5: continue
        num += sum(x["amount"] / x.get("multiplier", 1) for x in xs); den += len(xs) * st.mean(plain)
    return num / den if den else None


def crit_damage(pulls, skip=(), fallback=1.6):
    """The player's critical-hit damage: their crit-only hits over their plain hits, per action (5 or more of each) and
    weighted by crits, under no crit or direct-hit raid buff in 0:00-2:00; `fallback` without such an action."""
    cr, plain = collections.defaultdict(list), collections.defaultdict(list)
    for p in pulls:
        for x in p["hits"]:
            if x["type"] != "damage" or x.get("tick") or not 0 <= x["t"] < WINDOW or x.get("amount", 0) <= 0: continue
            if CRIT_BUFFS & set((x.get("buffs") or "").strip(".").split(".")): continue
            a, v = p["names"][str(x["abilityGameID"])], x["amount"] / x.get("multiplier", 1)
            if a in skip or x.get("directHit"): continue
            if x.get("hitType") == 2: cr[a].append(v)
            elif x.get("hitType") == 1: plain[a].append(v)
    use = [a for a in cr if len(cr[a]) >= 5 and len(plain[a]) >= 5]
    if not use: return fallback
    return sum(sum(cr[a]) for a in use) / sum(len(cr[a]) * st.mean(plain[a]) for a in use)


def sure_gain(job, pulls, k, unbuffed=False, more=()):
    """Hits that always crit: their average logged damage (others' buffs divided out) over k times the model potency.
    `unbuffed`: only hits under no crit or direct-hit raid buff (a crit buff raises a sure crit's damage instead) but
    the job's own (OWN_CRIT_BUFFS: Dancer's Starfall Dance always comes under their Devilment). A job whose sure hits
    nearly all come under others' buffs (SURE_BUFFED: Starfall Dance, cast in the burst, 100 of our 102 under Battle
    Litany or Chain Stratagem) keeps them all, each divided by what those buffs add to a sure critical direct hit,
    (1 + crit rate x (crit damage - 1)) x (1 + direct-hit rate x 0.25), at the player's crit damage (crit_damage, over
    `pulls` and `more`): without, most nights had none and the ceiling's Starfall fell back to the ordinary gain."""
    names = getattr(job, "AUTO_CRIT", ())
    if not names: return None
    own = set(getattr(job, "OWN_CRIT_BUFFS", ()))
    if unbuffed and getattr(job, "SURE_BUFFED", False):
        cd = crit_damage(list(pulls) + list(more), names, job.CRIT_DMG)
        def worth(x):
            f = 1.0
            for b in set((x.get("buffs") or "").strip(".").split(".")) - own:
                c, d = CRIT_RATES.get(b, (0, 0)); f *= (1 + c * (cd - 1)) * (1 + d * 0.25)
            return f
        v = [d / m / worth(h) for p in pulls for a, lab, d, m, h in calibrate.model_hits(p, WINDOW, lambda x: True, hit=True)
             if a in names and "sure crit" in lab and m]
        return st.mean(v) / k if v else None
    crit = CRIT_BUFFS - own
    keep = (lambda x: not crit & set((x.get("buffs") or "").strip(".").split("."))) if unbuffed else (lambda x: True)
    v = [d / m for p in pulls for a, lab, d, m in calibrate.model_hits(p, WINDOW, keep)
         if a in names and "sure crit" in lab and m]
    return st.mean(v) / k if v else None


def convert(s, k, e, et, ec=None, window=WINDOW):
    """DPS over the window from a simulated state: direct hits at the expected crit/direct-hit gain, ticks and sure
    crits at theirs."""
    dot, sure = getattr(s, "dotp", 0.0), getattr(s, "critp", 0.0)
    return k * (e * (s.dmg - dot - sure) + et * dot + (ec or e) * sure) / window


_ceiling, _fight = {}, {}
POLISH = True                                   # polish each search's best rotation (polish.py); --no-polish turns it off
RESTARTS = False                                # ...with its restarts (--restarts: ~0-1% more, minutes a search)
ROT_UNTIL = p12s.load()["untargetable"][0][0]   # the site's rotations: shown until Palladion takes Athena away (281.65 s)
FULL = p12s.load()["kill_median"]               # ...and searched over the whole phase (449 s)


def site_fight(job, until=WINDOW):
    """(slot, Fight) the ceilings (and the site's rotations, over the whole phase) are searched in, with our strategy's
    runs for the role's slot with the most running before Palladion, each mechanic's variant with the most (p12s's
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


def rot_key(gcd, crit=None, hasted=None):
    """The site's name for an optimized rotation: its GCD, the GCD under the job's buff haste where the GCD's tier holds
    two (calibrate.hasted_label: Samurai's 2.40 s is 2.08 or 2.09 s under Fuka), and its crit rate for a job whose
    resources come from crits."""
    return f"{gcd:.2f}" + (f"-h{hasted:.2f}" if hasted is not None else "") + (f"-c{round(100 * crit)}" if crit is not None else "")


def player_speed(job, ps):
    """A player's SPEED from their pulls: their GCD (calibrate.gcd_of, median) and, for a job with a buff haste, their
    GCD under it (hasted_gcd_of, lower median). Where the job model rounds as the game does (engine.recast) the speed
    factor itself counts, and calibrate.speed_for picks it; elsewhere it is the GCD / 2.5 as before."""
    gcds = [g for g in map(calibrate.gcd_of, ps) if g]
    hz = [g for g in map(calibrate.hasted_gcd_of, ps) if g]
    return calibrate.speed_for(job, st.median(gcds) if gcds else engine.BASE_GCD, st.median_low(hz) if hz else None)


def ceiling_key(job, gcd, crit=None, until=WINDOW, speed=None):
    """What a ceiling is cached by: the job, GCD, crit rate (for a job whose resources come from crits), window and speed
    factor (a player's, player_speed, where the job model rounds as the game does; else the GCD's)."""
    if speed is None or not calibrate._rounded(job): speed = calibrate.speed_for(job, round(gcd, 2))
    return job.__name__, round(gcd, 2), round(crit, 2) if crit is not None else None, until, round(speed, 3)


def ceilings(job, width, keys):
    """Search the ceilings (ceiling_key) not cached yet, all in one pool (engine.search_many: a run of several keeps
    every core busy), then polish each."""
    todo = [k for k in dict.fromkeys(keys) if k not in _ceiling]
    if not todo: return
    name, keep = job.__name__.split(".")[-1], job.SPEED
    params = lambda k: {"CRIT": k[2]} if k[2] is not None else None
    t0 = time.time()
    found = engine.search_many(name, [(site_fight(job, k[3])[1], k[4], params(k)) for k in todo], width=width)
    print(f"  searched {len(todo)} ceiling{'s' * (len(todo) > 1)} in {time.time() - t0:.0f} s", flush=True)
    for k, (s, setting, _) in zip(todo, found):
        if POLISH:
            job.SPEED, fight = k[4], site_fight(job, k[3])[1]
            before = job.final(s, fight)
            s, passes = polish.polish(name, fight, s, setting, k[4], params=params(k), log=lambda m: None, restarts=RESTARTS)
            print(f"  {rot_key(k[1], k[2], calibrate.hasted_label(job, k[4]))} until {k[3]:.0f}s: polished {before:,.0f} -> {job.final(s, fight):,.0f} "
                  f"in {passes} passes", flush=True)
        _ceiling[k] = s
    job.SPEED = keep


def ceiling(job, gcd, width, crit=None, until=WINDOW, speed=None):
    """The best unbuffed rotation over 0:00-until (2:00 for the ceilings) with our strategy's runs (site_fight) at this
    GCD, crit rate and speed factor (ceiling_key), searched with the job's own settings."""
    key = ceiling_key(job, gcd, crit, until, speed)
    ceilings(job, width, [key])
    return _ceiling[key]


def player_rows(job, pulls, width, more=()):
    """`more`: the players' other pulls (logs.ours_more, flagged), pooled into the ceiling's crit / direct-hit gain."""
    by, extra = collections.defaultdict(list), collections.defaultdict(list)
    for p in pulls: by[p["name"]].append(p)
    for p in more: extra[p["name"]].append(p)
    rows, keys = [], []
    for name, ps in sorted(by.items()):
        hits = [h for p in ps for h in calibrate.plain_hits(p, WINDOW + 5)]
        if len(hits) < 10: continue
        k = st.median(v / m for _, _, v, m in hits)
        crit, dh = rates(ps)
        skip, sure = getattr(job, "AUTO_CRIT", ()), no_sure(job)
        e, e0 = crit_gain(ps, skip=skip, sure=sure), crit_gain(ps + extra[name], unbuffed=True, skip=skip, sure=sure)
        et, et0 = tick_gain(ps) or e, tick_gain(ps, unbuffed=True) or e0        # offline logs: the hits' gain
        ec, ec0 = sure_gain(job, ps, k), sure_gain(job, ps, k, unbuffed=True, more=extra[name])
        own = natural_crit(ps, skip, sure) if hasattr(job, "CRIT") else None
        speed = player_speed(job, ps)
        gcd, job.SPEED = calibrate.gcd_at(job, speed), speed
        model, logged, sc = [], [], []
        for p in ps:
            s = calibrate.replay_fight(p, Fight(until=WINDOW))
            model.append(convert(s, k, e, et, ec))
            logged.append(logged_unbuffed(p, job=job) / WINDOW)
            if p.get("rdps"): sc.append(p["rdps"])
        keys.append(ceiling_key(job, gcd, own, speed=speed))
        rows.append(dict(name=name, pulls=len(ps), gcd=gcd, speed=speed, k=k, crit=crit, dh=dh, e=e, e0=e0, et=et, et0=et0, ec0=ec0, model=st.median(model),
                         logged=st.median(logged), rdps=st.median(sc) if sc else None, best=max(sc) if sc else None,
                         key=rot_key(round(gcd, 2), round(own, 2) if own is not None else None,
                                     calibrate.hasted_label(job, speed))))
    ceilings(job, width, keys)                           # every player's at once
    for r, key in zip(rows, keys): r["ceiling"] = convert(_ceiling[key], r["k"], r["e0"], r["et0"], r["ec0"])
    return rows


NIGHT_PULLS = 3   # a night's own ceiling needs this many clean pulls; with fewer the player's pooled one stands for it


def night_rows(job, pulls, width, more=()):
    """Per player and night (report code), the ceiling at that night's own conversion and GCD: gear changes over the
    season (a player 16% behind the clears one night and 5% the next), so one conversion pooled over all their nights
    fits none of them. Nights with fewer than NIGHT_PULLS clean pulls (or 10 plain hits) are left out."""
    by, extra = collections.defaultdict(list), collections.defaultdict(list)
    for p in pulls: by[p["name"], p["code"]].append(p)
    for p in more: extra[p["name"], p["code"]].append(p)
    rows, keys, keep = [], [], job.SPEED
    skip, sure = getattr(job, "AUTO_CRIT", ()), no_sure(job)
    for (name, code), ps in sorted(by.items()):
        hits = [h for p in ps for h in calibrate.plain_hits(p, WINDOW + 5)]
        if len(ps) < NIGHT_PULLS or len(hits) < 10: continue
        k = st.median(v / m for _, _, v, m in hits)
        e0 = crit_gain(ps + extra[name, code], unbuffed=True, skip=skip, sure=sure)
        et0, ec0 = tick_gain(ps, unbuffed=True) or e0, sure_gain(job, ps, k, unbuffed=True, more=extra[name, code])
        own = natural_crit(ps, skip, sure) if hasattr(job, "CRIT") else None
        speed = player_speed(job, ps)
        gcd = calibrate.gcd_at(job, speed)
        keys.append(ceiling_key(job, gcd, own, speed=speed))
        rows.append(dict(name=name, code=code, pulls=len(ps), gcd=gcd, k=k, e0=e0, et0=et0, ec0=ec0,
                         key=rot_key(round(gcd, 2), round(own, 2) if own is not None else None, calibrate.hasted_label(job, speed))))
    job.SPEED = keep
    ceilings(job, width, keys)
    for r, key in zip(rows, keys): r["ceiling"] = convert(_ceiling[key], r["k"], r["e0"], r["et0"], r["ec0"])
    return rows


CAST_NOTE = re.compile(r"(\d+(?:\.\d+)?)s cast")     # a hard cast in the history's note: "2.00s cast"
DASH_NOTE = re.compile(r"dash (\d+(?:\.\d+)?)s")        # running a dash saved (Red Mage): "dash 1.30s"


def placed_runs(hist, fight):
    """[(start, end)]: where a rotation does its runs. The search only checks that each move window has the seconds it
    needs outside cast bars (a cast's last SLIDE counts), so this places them: in the window's longest stretches outside
    cast bars first (instant GCDs, not slidecast slivers), as late as each stretch allows. A dash's saved running comes
    off its window's."""
    busy = sorted((t, t + float(m.group(1)) - engine.SLIDE) for t, _, note in hist if (m := CAST_NOTE.search(note or "")))
    dashed = [(t, float(m.group(1))) for t, _, note in hist if (m := DASH_NOTE.search(note or ""))]
    out = []
    for w in fight.moves:
        free, a = [], w.lo
        for b0, b1 in busy:
            if b1 <= w.lo or b0 >= w.hi: continue
            if b0 > a: free.append((a, b0))
            a = max(a, b1)
        if a < w.hi: free.append((a, w.hi))
        left = w.need - sum(x for t, x in dashed if w.lo <= t < w.hi)
        for a, b in sorted(free, key=lambda x: (x[1] - x[0], x[1]), reverse=True):
            if left <= 1e-9: break
            take = min(left, b - a)
            out.append((b - take, b)); left -= take
    return sorted(out)


def upto(job, s, fight, gcd, crit=None, until=ROT_UNTIL, speed=None):
    """A whole-phase rotation's state once its steps that start before `until` are done: its damage, DoT and sure-crit
    potency and waste are the window's. Exact at Palladion: Athena is away from then, so nothing cast before lands
    later and no DoT ticks on. Replayed at the GCD (and crit rate, speed factor) it was searched at."""
    h = s.history()
    keep = job.SPEED, getattr(job, "CRIT", None)
    job.SPEED = speed or calibrate.speed_for(job, gcd)
    if crit is not None: job.CRIT = crit
    try:
        steps, states = polish.split(job, fight, job.State.initial(fight), h)
    finally:
        job.SPEED = keep[0]
        if crit is not None: job.CRIT = keep[1]
    i = k = 0
    while k < len(steps) and h[i][0] < until: i += len(steps[k]); k += 1
    return states[k]


def site_rotation(job, s, until=ROT_UNTIL):
    """The site's rotation, a whole-phase one up to `until`: [time, action, "g" for a GCD / "o" for an oGCD, cast
    time, seconds run], waits left out. A GCD's running is what placed_runs puts between its start and the next GCD's."""
    hist = s.history()
    acts = [(t, n, note) for t, n, note in hist if t < until and not n.startswith("(")]
    runs, gs = placed_runs(hist, site_fight(job, FULL)[1]), [t for t, n, _ in acts if n in job.GCDS]
    out = []
    for t, n, note in acts:
        m, run = CAST_NOTE.search(note or ""), 0.0
        if n in job.GCDS:
            nxt = next((g for g in gs if g > t), until)
            run = sum(engine._overlap(a, b, t, nxt) for a, b in runs)
        out.append([t, n, "g" if n in job.GCDS else "o", float(m.group(1)) if m else 0.0, round(run, 1)])
    return out


def _spec(g):
    """A --gcds entry as (GCD, hasted GCD or None, crit rate or None)."""
    return (g, None, None) if isinstance(g, (int, float)) else (g[0], g[1] if len(g) > 1 else None, g[2] if len(g) > 2 else None)


def _parse_gcds(arg):
    """--gcds / --bis-gcds: GCD[/hasted][-cNN] entries, comma-separated (NN: the crit rate in %, for a job whose
    resources come from crits: Monk's best-in-slot set at its own rate, not the job's default)."""
    out = []
    for g in (arg.split(",") if arg else ()):
        g, _, c = g.partition("-c")
        v = [float(x) for x in g.split("/")]
        out.append((v[0], v[1] if len(v) > 1 else None, int(c) / 100 if c else None))
    return out


def rotations(job, rows, width, extra=(), ours=None, bis=()):
    """The site's optimized rotations for a job, {fight: timeline, rotations: {key: ...}}: at every GCD (and crit rate)
    searched for our players' ceilings, plus the extra GCDs (at the job's default crit rate), the best whole-phase
    rotation up to ROT_UNTIL, with its expected DPS there at the median of our players' conversions and their range, the
    same over the whole phase (FULL: `dps_full`), and the 0:00-2:00 ceiling's at the median. Each player is moved to the rotation's GCD first (SPEED_PTS, STAT_PT): a faster GCD costs
    them damage per potency, so GCDs compare at what a player would have there. `ours`: the players counted as playing
    at each GCD, when `rows` (the conversions) are someone else's (the clears', for a job none of ours plays). `bis`:
    more GCDs, searched as the extra ones, that are there for the gear model's best-in-slot sets (tools/gear): their
    rotations are marked `bis_gcd`, so a later run can drop them once no set is at that GCD (scratch/gear/rerun_all.py)."""
    more = []
    for g in [*extra, *bis]:   # a GCD, or (GCD, hasted GCD) where the tier holds two (Samurai's 2.48 s: 2.15 or 2.16 s under Fuka)
        g, h, c = _spec(g)     # (and the crit rate, where the job's resources come from crits: the job's default without)
        crit = getattr(job, "CRIT", None) if c is None or not hasattr(job, "CRIT") else c
        more.append(ceiling_key(job, g, crit, speed=calibrate.speed_for(job, round(g, 2), h) if h else None))
    short = [k for k in _ceiling if k[0] == job.__name__ and k[3] == WINDOW] + more
    ceilings(job, width, short + [ceiling_key(job, k[1], k[2], FULL, k[4]) for k in short])    # all in one go
    def conv(s, r, gcd, w=ROT_UNTIL):
        """The rotation in a player's DPS, the player moved to its GCD: the speed points that takes come out of their
        other substats (or go back into them). DoT ticks follow the speed through the rotation itself, searched at its
        GCD (the models' dot_tick)."""
        pts = SPEED_PTS * (r["gcd"] - gcd)
        return convert(s, r["k"] * (1 - STAT_PT * pts), r["e0"], r["et0"], r["ec0"], w)
    out = {}
    for (jn, gcd, crit, until, speed), s2 in sorted(_ceiling.items(), key=lambda x: (x[0][1], x[0][4], x[0][2] or 0)):
        if jn != job.__name__ or until != WINDOW: continue
        whole = ceiling(job, gcd, width, crit, FULL, speed)
        s = upto(job, whole, site_fight(job, FULL)[1], gcd, crit, speed=speed)
        hl = calibrate.hasted_label(job, speed)
        key, each = rot_key(gcd, crit, hl), [conv(s, r, gcd) for r in rows]
        each_full = [conv(whole, r, gcd, FULL) for r in rows]           # the whole phase, to the clears' median kill
        rot = site_rotation(job, whole)
        out[key] = dict(gcd=gcd, **({"hasted": hl} if hl is not None else {}), crit=crit, window=ROT_UNTIL, potency=round(s.dmg), dps=round(st.median(each)), dps_lo=round(min(each)),
                        ceiling_2min=round(st.median(conv(s2, r, gcd, WINDOW) for r in rows)),
                        dps_hi=round(max(each)), window_full=FULL, dps_full=round(st.median(each_full)),
                        dps_full_lo=round(min(each_full)), dps_full_hi=round(max(each_full)), players=sum(r["key"] == key for r in (rows if ours is None else ours)),
                        conv_players=len(rows),
                        waste={w: round(n, 1) for w, n in zip(job.WASTE, s.waste) if n}, rotation=rot)
        at = lambda gs: any(abs(gcd - g) < 0.005 and (h is None or hl is None or abs(hl - h) < 0.005)
                            and (c is None or crit is None or abs(crit - c) < 0.005) for g, h, c in map(_spec, gs))
        if at(bis) and not at(extra): out[key]["bis_gcd"] = True     # an extra asked for on its own stays
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
    ap.add_argument("--job", default="blm", choices=sorted(JOBS) + ["auto"], help="auto: with --reports, every job those reports have")
    ap.add_argument("--clears", action="store_true", help="also the benchmark clears' players (tincture hits are kept)")
    ap.add_argument("--width", type=int, default=None, help="search width (default: the job's SWEEP_WIDTH)")
    ap.add_argument("--site", action="store_true", help=f"save our players' ceilings and the optimized rotations for the scorecard site "
                    f"({SITE_FILE.name}, {ROT_FILE.name})")
    ap.add_argument("--gcds", help="with --site: also optimize at these GCDs (comma-separated), for the site's rotation pages; "
                    "GCD/hasted (2.48/2.15) picks the hasted GCD under Fuka, Swiftscaled or Ley Lines where the tier holds two; "
                    "-cNN the crit rate in %% (2.43-c28) for a job whose resources come from crits (Monk)")
    ap.add_argument("--bis-gcds", help="with --site: as --gcds, for the gear model's best-in-slot sets: marked so a later run "
                    "can drop them once no set is at that GCD (scratch/gear/rerun_all.py)")
    ap.add_argument("--offline", action="store_true", help="our players' logs from the scorecard's acts caches, not FFLogs "
                    "(logs.ours_offline, flag_hits): for when FFLogs is down; 'logged' then misses the hits left out")
    ap.add_argument("--ceilings-only", action="store_true", help="save our players' ceilings (pooled and per night) for the "
                    "scorecard site without searching the site's rotations again (those stay as they are)")
    ap.add_argument("--reports", help="with --ceilings-only: only these reports (comma-separated codes): the nights of their players "
                    "on the job, and those players' pooled ceilings; everyone else's stay as saved")
    ap.add_argument("--no-polish", action="store_true", help="skip the local search on each search's best rotation (polish.py)")
    ap.add_argument("--restarts", action="store_true", help="polish with restarts (the rest of the fight searched afresh from "
                    "points along the rotation): ~0-1%% more, 2-15 minutes a whole-phase search")
    a = ap.parse_args()
    codes = set(a.reports.split(",")) if a.reports else None
    if codes and not a.ceilings_only: ap.error("--reports goes with --ceilings-only")
    if a.job == "auto":   # each job of the reports in a process of its own, as a run per job always was
        if not codes: ap.error("--job auto needs --reports")
        site, key = json.loads(logs.SITE.read_text())["reports"], {name: k for k, (_, name) in JOBS.items()}
        for k in sorted({key[p["job"]] for c in codes if c in site for p in site[c]["players"] if p["job"] in key}):
            print(f"=== {k}", flush=True)
            subprocess.run([sys.executable, __file__, "--job", k, "--ceilings-only", "--reports", a.reports] + ["--offline"] * a.offline, check=True)
        return
    global POLISH, RESTARTS
    POLISH, RESTARTS = not a.no_polish, a.restarts
    job, jobname = JOBS[a.job]
    calibrate.use(a.job)
    names = None
    if codes:   # only the players on the job in these reports (all their pulls, for their pooled ceiling)
        site = json.loads(logs.SITE.read_text())["reports"]
        names = {p["name"] for c in codes if c in site for p in site[c]["players"] if p["job"] == jobname}
        if not names: print(f"no {jobname} in {', '.join(sorted(codes))}"); return
    own = getattr(job, "own_factor", lambda p, h: 1.0)
    pulls = flag_hits(job, [p for p in logs.ours_offline(jobname, own) if names is None or p["name"] in names]) if a.offline else logs.ours(jobname, names)
    more = flag_hits(job, logs.ours_more(jobname, own, names=names))   # for the crit / DH gain
    rows = player_rows(job, pulls, a.width, more)
    show(rows, f"Our players on {jobname}, clean pulls, 0:00-2:00 (DPS)")
    print("  gain / unbuf: average hit over plain hit, all hits / hits under no crit or direct-hit raid buff;\n"
          "  rDPS/best: scorecard median / best of the clean pulls; replay: their casts through the model, at gain;\n"
          "  logged: their damage with others' buffs divided out; ceiling: best unbuffed rotation at their GCD, at unbuf\n"
          "  (a raid buff's credit for the others' damage, which rDPS includes, is not in it: the scorecard site adds it).")
    if a.site or a.ceilings_only:   # each player's pooled ceiling, and one per night (night_rows) the site prefers
        nights = night_rows(job, [p for p in pulls if not codes or p["code"] in codes], a.width,
                            [p for p in more if not codes or p["code"] in codes])
        for r in nights: print(f"  {r['name']:20} {r['code']}  {r['pulls']:3} pulls  {r['gcd']:.2f}  dmg/pot {r['k']:6.2f}  ceiling {r['ceiling']:8,.0f}")
        saved = json.loads(SITE_FILE.read_text()) if SITE_FILE.exists() else {}
        night = lambda n: dict(ceiling=round(n["ceiling"]), gcd=n["gcd"], pulls=n["pulls"], rotation_key=n["key"])
        new = {r["name"]: dict(ceiling=round(r["ceiling"]), gcd=r["gcd"], pulls=r["pulls"], rotation_key=r["key"],
                               nights={n["code"]: night(n) for n in nights if n["name"] == r["name"]}) for r in rows}
        if codes:   # merged in: these players' other nights stay, and so does everyone else
            cur = saved.get(jobname, {})
            for name, x in new.items():
                x["nights"] = {**{c: v for c, v in cur.get(name, {}).get("nights", {}).items() if c not in codes}, **x["nights"]}
                cur[name] = x
            new = cur
        saved[jobname] = new
        SITE_FILE.parent.mkdir(exist_ok=True)
        SITE_FILE.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
        print(f"\nsaved {len(rows)} ceilings ({len(nights)} nights) to {SITE_FILE}")
    if a.site:
        conv = rows
        if not rows:     # none of our players on the job: the rotations convert at the benchmark clears' players instead
            since = getattr(job, "CONVERT_SINCE", job.LOGS_SINCE)
            days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
            conv = player_rows(job, [p for p in logs.clears(jobname) if days[(p["code"], p["fight"])] >= since], a.width)
            show(conv, f"None of our players on {jobname}: the site converts at the benchmark clears' since {since} (DPS)")
        mine = rotations(job, conv, a.width, _parse_gcds(a.gcds), ours=rows, bis=_parse_gcds(a.bis_gcds))
        if conv is not rows:                              # the site says whose conversion it is
            mine.update(converted_from="clears", converted_since=since)
        if a.offline: mine["offline"] = True              # the site says its DPS comes from the acts caches
        # read only now: the searches take long, and another job's run may have saved its rotations meanwhile
        rots = json.loads(ROT_FILE.read_text()) if ROT_FILE.exists() else {}
        rots[jobname] = mine
        ROT_FILE.write_text(json.dumps(rots, indent=1, ensure_ascii=False))
        print(f"saved {len(rots[jobname]['rotations'])} rotations to {ROT_FILE}")
    if a.clears:
        days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
        cl = [p for p in logs.clears(jobname) if days[(p["code"], p["fight"])] >= job.LOGS_SINCE]
        show(player_rows(job, cl, a.width), f"Benchmark clears' {jobname}s, 0:00-2:00 (DPS)")


if __name__ == "__main__":
    main()
