"""P12S phase 1 (Athena, Savage) for the optimizer: the boss's timeline, when Athena can't be hit, and where a Black Mage
has to run under our groups' strategy.

    python tools/rotation/p12s.py --build          # timeline and the clears' movement from FFLogs -> p12s_p1.json
    python tools/rotation/p12s.py [--slot R2] [--var para2=debuff ...]     # list the move windows

The timeline is fixed: every boss cast lands within ~0.2 s of its median from pull to pull, and the only time Athena
can't be hit is Palladion. Times are medians over six benchmark clears.

Runs come from our raidplan (Syncademy P12S P1, raidplan.io/plan/qa834veq2fssd2yc) and the trainer's geometry for it
(mechanics/paradeigma-*.js: 40-yalm floor, 12 px a yalm), in yalms at 6 a second, measured from Athena's centre: that
is where Black Mages stand in the clears between mechanics (median 0.4-1 yalm away). Each run has to be done between a
cue (plus REACT) and the moment its mechanic snapshots. Where the run depends on a random assignment, the mechanic has
variants; the default is the one with the most running, since the rotation is planned before the assignment shows.

Stretches our plan does not cover take their running from the benchmark clears' Black Mages instead: the median path
they ran in that window (from their position at every cast). From Palladion to the end that is the only source for now
and is marked provisional; our groups' strategy there may still change.

A melee (slots M1 / M2) runs the DPS assignments too, measured the same way (they wait at the hitbox edge, as often
nearer to the next spot as farther), except Paradeigma I, where the melee's spot on the bait line is next to the tank.
Every spot of our plan is within a melee's reach of Athena (REACH_MELEE from her centre), so the plan costs a melee
only the hard casts its runs block, and positionals: while the plan fixes their spot (`pinned`) only True North gets
one. Elsewhere the runs are the clears' Reapers' paths, and where those Reapers went longer than a GCD without a melee
action, the melee is away (out of reach) for that long somewhere in the window.

A ranged player stands within a melee's reach too, except at a few far spots of our plan (FAR: the wall end of
Paradeigma I's bait line, the Heavensflame corner of Superchain I). A ranged job with melee actions (Red Mage's melee
combo) is out of reach around those snapshots (`far`).
"""
import argparse, collections, datetime, json, math, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
from engine import RUN, REACH, Fight, Move          # noqa: E402

DATA = HERE / "p12s_p1.json"
CACHE = HERE / ".cache"
REACT = 1.0                 # seconds from a cue to the first step
CLEARS_SINCE = "2025-04-01" # Black Mage clears on the 7.2 kit, as in calibrate.py
# melee: the clears' Reapers use melee actions up to 14 y from Athena's centre (99th percentile 13.5 y; 2 of 2,427
# beyond 14 y), so her hitbox is ~11 y and reach 3 y more
REACH_MELEE = 14.0
AWAY_GCD = 2.5              # a gap between melee actions longer than a GCD is time out of reach
MIN_AWAY = 1.0              # seconds: less than this is noise

# --- our strategy ---------------------------------------------------------------------------------------------------
# (from, to, yalms, what): `from` / `to` are timeline events, "Ability#n" for its n-th cast landing, "Ability#n.begin"
# for its cast bar starting, with an optional offset in seconds.
# Paradeigma I (raidplan slides 2-5): the light party that baits stands in a line down the adds' half, tank by Athena,
# ranged by the wall (18.3 y out); the other stacks on the hitbox edge on the far half (7.9 y out), on the side the
# cleave leaves safe (2.5 y off the middle). LP1 baits the first wave, then the two light parties swap through the
# middle while the second and third cleaves go off. The adds show 4.2 s after Paradeigma.
PARA1_CUE = ("Paradeigma#0", 4.2 + REACT)
PLAN = {
    "Paradeigma I": {
        "R1": [(PARA1_CUE, "White Flame#0", 18.3, "out to the wall end of the bait line on the adds' half"),
               ("White Flame#0", "Trinity of Souls#2", 28.0,
                "swap through the middle to the hitbox edge on the far half, on the safe side of cleaves 2 and 3 "
                "(26.2 y straight, one side switch on the way)")],
        "R2": [(PARA1_CUE, "White Flame#0", 8.3, "to the stack on the hitbox edge, far half"),
               ("White Flame#0", "White Flame#1", 26.5, "swap through the middle to the wall end of the bait line")],
        # melee: second on the bait line, after the tank (slide 3: 6.6 y out); M1 is in LP1, M2 in LP2
        "M1": [(PARA1_CUE, "White Flame#0", 6.6, "to the melee spot of the bait line on the adds' half, next to the tank"),
               ("White Flame#0", "Trinity of Souls#2", 16.3,
                "swap through the middle to the hitbox edge on the far half, on the safe side of cleaves 2 and 3 "
                "(14.5 y straight, one side switch on the way)")],
        "M2": [(PARA1_CUE, "White Flame#0", 8.3, "to the stack on the hitbox edge, far half"),
               ("White Flame#0", "White Flame#1", 14.8, "swap through the middle to the melee spot of the bait line")],
    },
    # Paradeigma II (slides 6-11): DPS either catch a tether and stretch it straight across through Athena's hitbox
    # (13 y out), then step into the tower an opposite-colour Soul drops (~7 y, slide 10); or carry a Soul to their
    # quadrant spot (anticlockwise from A, 14 y out) and step out of its tower (~5 y). Then everyone dodges Ray of Light
    # into a safe column (columns 10 y wide: up to ~6 y).
    "Paradeigma II": {
        "tether": [(("Searing Radiance#0.begin", REACT), "Searing Radiance#0", 13.3, "stretch the tether straight across"),
                   ("Searing Radiance#0", "Astral Advance#0", 7.0, "into the tower dropped for you"),
                   ("Astral Advance#0", "Ray of Light#0", 6.0, "into a safe column")],
        "debuff": [(("Searing Radiance#0.begin", REACT), "Polarized Glow#0", 14.3, "Soul to your quadrant spot"),
                   ("Polarized Glow#0", "Astral Advance#0", 5.0, "out of your tower"),
                   ("Astral Advance#0", "Ray of Light#0", 6.0, "into a safe column")],
    },
    # Superchain Theory I (slides 12-22): the spheres sit 12 y out on the intercardinals. First corner (point-blank or
    # doughnut, with clock spots or pairs), then the doughnut of the second set with the light/dark split left and
    # right of the boss, then across to the final sphere (point-blank and doughnut one after the other), then the
    # spread role runs to a corner away from the cardinals while the laser role places and takes towers on them.
    # The first set goes off with Emission/Radiation, 6.1 s before Polarized Ray; the final sphere 2.25 s and 0.3 s
    # before the second Polarized Glow (all three steady in our pulls).
    "Superchain I": {
        "spread": [(("Superchain Theory I#0", REACT), ("Polarized Ray#0", -6.1), 12.0, "first corner's safe spot"),
                   (("Polarized Ray#0", -6.1), "Astral Impact#0", 15.0, "into the second doughnut, your side of the boss"),
                   ("Astral Impact#0", ("Polarized Glow#1", -2.25), 15.0, "across to the final sphere"),
                   (("Polarized Glow#1", -2.25), ("Polarized Glow#1", -0.3), 7.0, "in or out for its second shape"),
                   (("Polarized Glow#1", -0.3), "Theos's Holy#0", 12.0, "spread to a corner, away from the towers")],
        "laser": [(("Superchain Theory I#0", REACT), ("Polarized Ray#0", -6.1), 12.0, "first corner's safe spot"),
                  (("Polarized Ray#0", -6.1), "Astral Impact#0", 15.0, "into the second doughnut, your side of the boss"),
                  ("Astral Impact#0", ("Polarized Glow#1", -2.25), 15.0, "across to the final sphere"),
                  (("Polarized Glow#1", -2.25), ("Polarized Glow#1", -0.3), 7.0, "in or out for its second shape"),
                  (("Polarized Glow#1", -0.3), "Astral Advance#1", 12.0, "place your tower, then take one on a cardinal")],
    },
    # Paradeigma III (slides 23-28, drill mechanics/paradeigma-3.js): DPS stretch their tether on a middle platform
    # before the floor falls, straight (level with the add, 10.4 y out) or crossed (outer edge, 13.1 y out); dodge the
    # + and X; then the straight tethers take the centre-of-arena tower (~7.6 y), the crossed ones the tower in the
    # middle of their segment (~4 y).
    "Paradeigma III": {
        "straight": [(("Searing Radiance#1.begin", REACT), "Unnatural Enchainment#0", 10.4, "stretch on a middle platform"),
                     ("Searing Radiance#1", "Theos's Cross#0", 4.0, "clear of the + and X"),
                     ("Theos's Cross#0", "Astral Advance#2", 7.6, "into the centre tower")],
        "cross": [(("Searing Radiance#1.begin", REACT), "Unnatural Enchainment#0", 13.1, "cross on a middle platform"),
                  ("Searing Radiance#1", "Theos's Cross#0", 4.0, "clear of the + and X"),
                  ("Theos's Cross#0", "Astral Advance#2", 4.0, "into your segment's tower")],
    },
}
DEFAULT_VAR = {"Paradeigma II": "tether", "Superchain I": "spread", "Paradeigma III": "straight"}   # the most running
# Spots of our plan beyond a melee action's reach (REACH_MELEE from Athena's centre), where a ranged job with melee
# actions (Red Mage) can't use them around the run's snapshot: (mechanic, variant, run index) -> yalms from her centre.
# Paradeigma I: the wall end of the bait line (18.3 y); Superchain I: the ranged Heavensflame spot, back into the corner
# behind the last cluster (mechanics/superchain-1.js: 110 px beyond the cluster, 12 y out, and 44 px aside: ~21.5 y).
# Every other spot of the plan is within reach.
FAR = {("Paradeigma I", "R1", 0): 18.3, ("Paradeigma I", "R2", 1): 18.3, ("Superchain I", "spread", 4): 21.5}
# Stretches of our plan's ranged runs a dash can cover (engine.Move.dash), (mechanic, variant, run index) -> [(kind,
# yalms of the run before it, yalms from Athena's centre where it starts or ends)]. "in": straight toward Athena from
# that far out; a gap closer lands at her hitbox edge (ATHENA_EDGE: Red Mages' Corps-a-corps from 11-19 y out all land
# at 10.5 y in our pulls). "out": straight away from her, from beside her, to that far out (a backstep). Only runs that
# go straight to or from her: Superchain I's paths depend on the spheres' layout, and Paradeigma III's floor falls.
ATHENA_EDGE = 10.5
DASH = {("Paradeigma I", "R1", 0): [("out", 0.0, 18.3)],        # Athena -> the wall end of the bait line
        ("Paradeigma I", "R1", 1): [("in", 0.0, 18.3)],         # the wall end -> through the middle -> far half
        ("Paradeigma I", "R2", 0): [("out", 0.0, 8.3)],         # Athena -> the stack on the far half
        ("Paradeigma I", "R2", 1): [("out", 7.9, 18.3)],        # far half -> the middle -> the wall end
        ("Paradeigma II", "tether", 0): [("out", 0.0, 13.3)],   # stretch the tether straight across
        ("Paradeigma II", "debuff", 0): [("out", 0.0, 14.3)]}   # the Soul out to your quadrant spot
# the major mechanics as the site's timeline marks them: when their boss cast's bar starts
MECHANICS = [("Paradeigma#0.begin", "Paradeigma I"), ("Paradeigma#1.begin", "Paradeigma II"), ("Glaukopis#0.begin", "Glaukopis"),
             ("Superchain Theory I#0.begin", "Superchain I"), ("Peridialogos#0.begin", "Dialogos"),
             ("Paradeigma#2.begin", "Paradeigma III"), ("Ultima Blade#0", "Ultima Blade"), ("Palladion#0.begin", "Palladion"),
             ("Theos's Ultima#0.begin", "Theos's Ultima"), ("Superchain Theory IIA#0.begin", "Superchain IIA"),
             ("Superchain Theory IIB#0.begin", "Superchain IIB")]
SHORT = {"para1": "Paradeigma I", "para2": "Paradeigma II", "sc1": "Superchain I", "para3": "Paradeigma III"}

# --- what the clears ran where our plan has nothing (yet) ------------------------------------------------------------
# (from, to, mechanic, provisional). Each is clipped to the time between the plan's windows around it.
CLEARS = [
    ("Paradeigma#0", ("Paradeigma#0", 4.2 + REACT), "before Paradeigma I", False),
    ("Trinity of Souls#2", "Paradeigma#1", "after Paradeigma I", False),
    ("Paradeigma#1", ("Searing Radiance#0.begin", REACT), "Paradeigma II, before the tethers", False),
    ("Ray of Light#0", "Superchain Theory I#0", "Glaukopis", False),
    ("Theos's Holy#0", "Trinity of Souls#3", "Trinity of Souls, first cleave", False),
    ("Trinity of Souls#3", "Trinity of Souls#4", "Trinity of Souls, second cleave", False),
    ("Trinity of Souls#4", "Trinity of Souls#5", "Trinity of Souls, third cleave", False),
    ("Trinity of Souls#5", "Dialogos#0", "Peridialogos / Apodialogos and Dialogos", False),
    ("Dialogos#0", ("Searing Radiance#1.begin", REACT), "On the Soul, Paradeigma III before the tethers", False),
    ("Astral Advance#2", "Glaukopis#2", "after Paradeigma III, Glaukopis", False),
    ("Glaukopis#2", "Ultima Blade#1", "Ultima Blade", False),
    ("Ultima Blade#1", "Palladion#0.begin", "before Palladion", False),
    ("Palladion#9", "Theos's Ultima#0", "Theos's Ultima", True),
    ("Theos's Ultima#0", "Superchain Theory IIA#0", "before Superchain Theory IIA", True),
    ("Superchain Theory IIA#0", "Trinity of Souls#6", "Superchain IIA, first cleave", True),
    ("Trinity of Souls#6", "Trinity of Souls#7", "Superchain IIA, second cleave", True),
    ("Trinity of Souls#7", "Trinity of Souls#8", "Superchain IIA, third cleave", True),
    ("Trinity of Souls#8", "Dialogos#1", "Superchain IIA, last sphere and Dialogos", True),
    ("Dialogos#1", "Superchain Theory IIB#0", "On the Soul", True),
    ("Superchain Theory IIB#0", "Parthenos#0", "Superchain IIB, Paradeigma", True),
    ("Parthenos#0", "Ray of Light#1", "Superchain IIB, Ray of Light", True),
    ("Ray of Light#1", "Sample#1", "Superchain IIB, Unnatural Enchainment", True),
    ("Sample#1", "On the Soul#6", "Superchain IIB, the end", True),
]
MIN_RUN = 1.5               # yalms: less than this in a window is shuffling, not a forced run


# --- building the data -----------------------------------------------------------------------------------------------

def _enemy_events(k):
    """Enemy casts and targetability changes of one clear, cached."""
    import fflogs
    cf = CACHE / f"enemy_{k['code']}_{k['fight']}.json"
    if cf.exists(): return json.loads(cf.read_text())
    q = '''query($c:String!,$f:[Int]!){reportData{report(code:$c){fights(fightIDs:$f){id startTime endTime}
      masterData{abilities{gameID name}}}}}'''
    m = fflogs.gql(q, {"c": k["code"], "f": [k["fight"]]})["reportData"]["report"]
    f = m["fights"][0]
    names = {a["gameID"]: a["name"] for a in m["masterData"]["abilities"]}
    rel = lambda e: round((e["timestamp"] - f["startTime"]) / 1000, 3)
    casts = [(rel(e), e["type"], names.get(e["abilityGameID"], str(e["abilityGameID"])))
             for e in fflogs.events(k["code"], [f], "Casts", hostility="Enemies") if e["type"] in ("begincast", "cast")]
    target = [(rel(e), e.get("targetable")) for e in
              fflogs.events(k["code"], [f], "All", hostility="Enemies", filter='type = "targetabilityupdate"')]
    out = dict(casts=casts, target=target)
    CACHE.mkdir(exist_ok=True)
    cf.write_text(json.dumps(out))
    return out


def _occurrences(casts):
    """{"Ability#n" / "Ability#n.begin": time}: one entry per occurrence (several adds casting together count once)."""
    seen, last, out = collections.Counter(), {}, {}
    for t, typ, name in sorted(casts):
        key = (name, typ)
        if key in last and t - last[key] < 1.0: continue
        last[key] = t
        out[f"{name}#{seen[key]}" + (".begin" if typ == "begincast" else "")] = t
        seen[key] += 1
    return out


def _trace(p):
    """The player's position at each of their casts (begin and end): [(t, x, y)] in yalms from the arena centre."""
    pts = []
    for x in p["casts"]:
        r = x.get("sourceResources")
        if r and "x" in r: pts.append((x["t"], (r["x"] - 10000) / 100, (r["y"] - 10000) / 100))
    return sorted(pts)


def _path(pts, lo, hi):
    """Yalms run in [lo, hi], moving at an even pace between the samples."""
    d = 0.0
    for (t0, x0, y0), (t1, x1, y1) in zip(pts, pts[1:]):
        if t1 <= lo or t0 >= hi or t1 <= t0: continue
        d += math.dist((x0, y0), (x1, y1)) * (min(t1, hi) - max(t0, lo)) / (t1 - t0)
    return d


def build(n=6):
    import logs
    bench = json.loads(logs.BENCH.read_text())
    kills = sorted((k for k in bench["kills"] if not k["echo"]), key=lambda k: -k["dur"])[:n]
    occ = collections.defaultdict(list)
    downs = []
    for k in kills:
        e = _enemy_events(k)
        for key, t in _occurrences(e["casts"]).items(): occ[key].append(t)
        off = [t for t, v in e["target"] if v == 0]; on = [t for t, v in e["target"] if v == 1]
        downs.append(list(zip(off, on)))
    events = {key: [round(st.median(v), 2), round(st.pstdev(v), 2), len(v)] for key, v in occ.items() if len(v) >= n // 2 + 1}
    untargetable = [[round(st.median(w[i][0] for w in downs), 2), round(st.median(w[i][1] for w in downs), 2)]
                    for i in range(min(map(len, downs)))]
    data = dict(built=datetime.date.today().isoformat(), kills=[f"{k['code']}#{k['fight']}" for k in kills],
                events=events, untargetable=untargetable, kill_median=bench["pools"]["clears"]["kill_median_s"],
                enrage=bench["hp_checkpoints"]["enrage_s"])
    # the clears' Black Mages: what they ran in every window, ours and the gaps
    days = {(k["code"], k["fight"]): k["day"] for k in bench["kills"]}
    traces = [(_trace(p), p["end"]) for p in logs.clears("BlackMage") if days[(p["code"], p["fight"])] >= CLEARS_SINCE]
    ev = lambda ref: _at(events, ref)
    windows = {_wkey(a, b) for a, b, *_ in CLEARS}
    windows |= {_wkey(a, b) for v in PLAN.values() for runs in v.values() for a, b, *_ in runs}
    path = {}
    for w in sorted(windows):
        a, b = json.loads(w)
        lo, hi = ev(a), ev(b)
        v = [_path(pts, lo, hi) for pts, end in traces if end >= hi]
        if len(v) >= 3: path[w] = [round(st.median(v), 1), len(v)]
    data["clears_path"] = path
    data["melee"] = _melee(events, windows)
    DATA.write_text(json.dumps(data, indent=1) + "\n")
    return data


MELEE_ACTIONS = {"Slice", "Waxing Slice", "Infernal Slice", "Shadow of Death", "Soul Slice", "Gibbet", "Gallows",
                 "Void Reaping", "Cross Reaping", "Blood Stalk", "Unveiled Gibbet", "Unveiled Gallows", "Lemure's Slice"}


def _melee(events, windows):
    """The clears' Reapers in every window: the median path they ran, and the median of their longest gap between
    melee actions (each pull once: some clears are in two reports)."""
    import logs
    seen, L = set(), []
    for p in logs.clears("Reaper"):
        if (p["name"], round(p["end"])) not in seen: seen.add((p["name"], round(p["end"]))); L.append(p)
    ev = lambda ref: _at(events, tuple(ref) if isinstance(ref, list) else ref)
    path, gap = {}, {}
    for w in sorted(windows):
        a, b = json.loads(w)
        lo, hi = ev(a), ev(b)
        ps = [p for p in L if p["end"] >= hi]
        if len(ps) < 3: continue
        path[w] = [round(st.median(_path(_trace(p), lo, hi) for p in ps), 1), len(ps)]
        g = []
        for p in ps:
            n = p["names"]
            ts = [lo] + sorted(x["t"] for x in p["casts"] if x["type"] == "cast" and lo < x["t"] < hi
                               and n[str(x["abilityGameID"])] in MELEE_ACTIONS) + [hi]
            g.append(max(y - x for x, y in zip(ts, ts[1:])))
        gap[w] = [round(st.median(g), 1), len(ps)]
    return dict(path=path, away=gap)


# --- using it --------------------------------------------------------------------------------------------------------

def _wkey(a, b):
    return json.dumps([a, b])


def _at(events, ref):
    name, off = (ref, 0.0) if isinstance(ref, str) else ref
    if name not in events: raise KeyError(f"timeline event {name!r} not in {DATA.name}; rebuild with --build")
    return events[name][0] + off


def load():
    return json.loads(DATA.read_text())


def melee(slot):
    return slot.startswith("M")


def windows(slot="R1", var=None, data=None):
    """[(lo, hi, yalms, mechanic, what, source)] for the slot and variants, sorted, the clears' gaps clipped between
    the plan's windows (a melee slot takes the clears' Reapers' paths)."""
    data = data or load()
    paths = data["melee"]["path"] if melee(slot) else data["clears_path"]
    who = "Reapers" if melee(slot) else "Black Mages"
    ev = lambda ref: _at(data["events"], tuple(ref) if isinstance(ref, list) else ref)
    pick = dict(DEFAULT_VAR, **{"Paradeigma I": slot}, **(var or {}))
    out = []
    for mech, variants in PLAN.items():
        if pick[mech] not in variants: raise ValueError(f"{mech}: no variant {pick[mech]!r} (have {', '.join(variants)})")
        for a, b, y, what in variants[pick[mech]]:
            out.append((ev(a), ev(b), y, mech, what, f"plan, {pick[mech]}"))
    plan = sorted(out)
    for a, b, mech, prov in CLEARS:
        lo, hi = ev(a), ev(b)
        lo = max([lo] + [w[1] for w in plan if w[1] <= hi and w[0] < lo + 1e-9])
        hi = min([hi] + [w[0] for w in plan if w[0] >= lo])
        got = paths.get(_wkey(a, b))
        if hi - lo < 0.5 or not got or got[0] < MIN_RUN: continue
        out.append((lo, hi, got[0], mech, f"as the clears' {who} ran (median of {got[1]})",
                    "clears, provisional" if prov else "clears"))
    return sorted(out)


def mechanics(data=None):
    """[(t, name)]: when each major mechanic starts."""
    data = data or load()
    return [(_at(data["events"], ref), name) for ref, name in MECHANICS if ref in data["events"]]


def worst_slot(melee_job=False, until=None, data=None):
    """Of the two Paradeigma I slots of the job's role (R1 / R2, or M1 / M2), the one with the most running before
    `until`: a rotation planned for it holds whichever the player is given (the variants default to the most already)."""
    data = data or load()
    run = lambda slot: sum(min(y / RUN, hi - lo) for lo, hi, y, *_ in windows(slot, None, data) if until is None or lo < until)
    return max(("M1", "M2") if melee_job else ("R1", "R2"), key=run)


def plan_spans(slot="R1", var=None, data=None):
    """[(lo, hi, mechanic)]: from the first cue to the last snapshot of each mechanic of our plan."""
    out = collections.defaultdict(list)
    for lo, hi, _, mech, _, src in windows(slot, var, data):
        if src.startswith("plan"): out[mech] += [lo, hi]
    return sorted((min(v), max(v), m) for m, v in out.items())


def away(slot="R1", var=None, data=None):
    """A melee's stretches out of reach: [(lo, hi, seconds, mechanic, source)]. Our plan has none (every spot is in
    reach); elsewhere, the clears' Reapers' longest gap between melee actions beyond a GCD, inside the stretch between
    the plan's mechanics and outside Palladion."""
    if not melee(slot): return []
    data = data or load()
    ev = lambda ref: _at(data["events"], tuple(ref) if isinstance(ref, list) else ref)
    spans = plan_spans(slot, var, data)
    out = []
    for a, b, mech, prov in CLEARS:
        got = data["melee"]["away"].get(_wkey(a, b))
        if not got or got[0] - AWAY_GCD < MIN_AWAY: continue
        lo, hi = ev(a), ev(b)
        lo = max([lo] + [x[1] for x in spans if x[1] <= hi and x[0] < lo + 1e-9])
        hi = min([hi] + [x[0] for x in spans if x[0] >= lo])
        for d0, d1 in data["untargetable"]:
            if d0 <= lo < d1: lo = d1
            if d0 < hi <= d1: hi = d0
        need = min(got[0] - AWAY_GCD, hi - lo)
        if need >= MIN_AWAY: out.append((lo, hi, round(need, 1), mech, "clears, provisional" if prov else "clears"))
    return sorted(out)


def far(slot="R1", var=None, data=None):
    """A ranged player's stretches out of melee reach at our plan's far spots (FAR): [(lo, hi, seconds, mechanic,
    source)], each around the run's snapshot, for the time it takes to step out past REACH_MELEE and back (they run in
    as late and leave as early as the mechanic allows)."""
    if melee(slot): return []
    data = data or load()
    ev = lambda ref: _at(data["events"], tuple(ref) if isinstance(ref, list) else ref)
    pick = dict(DEFAULT_VAR, **{"Paradeigma I": slot}, **(var or {}))
    out = []
    for (mech, v, i), d in FAR.items():
        if pick[mech] != v: continue
        x = (d - REACH_MELEE) / RUN
        t = ev(PLAN[mech][v][i][1])
        out.append((round(t - x, 2), round(t + x, 2), round(2 * x, 2), mech, f"plan, {v}: {d:.1f} y out"))
    return sorted(out)


def out_of_reach(slot="R1", var=None, data=None, far_spots=False):
    """A melee slot's stretches out of reach (away); for a ranged slot, the plan's far spots if the job has melee
    actions (far_spots), else none."""
    return away(slot, var, data) if melee(slot) else far(slot, var, data) if far_spots else []


def dashes(mech, src, what):
    """A plan run's dash segments for engine.Move.dash (DASH): (kind, yalms before it, its length)."""
    if not src.startswith("plan, "): return ()
    v = src[len("plan, "):]
    i = next((k for k, run in enumerate(PLAN[mech].get(v, ())) if run[3] == what), None)
    return tuple((kind, before, r - ATHENA_EDGE if kind == "in" else r) for kind, before, r in DASH.get((mech, v, i), ()))


def moves(slot="R1", var=None, data=None):
    """The windows as engine Moves; a run that can't fit its window is clipped to standing still through it."""
    out = []
    for lo, hi, y, mech, what, src in windows(slot, var, data):
        need = min(y / RUN, hi - lo)
        out.append(Move(lo, hi, need, relocate=y > REACH, why=f"{mech}: {what} ({y:.0f} y; {src})",
                        dash=dashes(mech, src, what)))
    return out


def fight(slot="R1", var=None, until=None, still=False, far_spots=False, **kw):
    """The fight for a slot and variants. far_spots: a ranged job with melee actions is out of reach at the plan's far
    spots (far)."""
    data = load()
    gone = [] if still else [Move(lo, hi, need, why=f"{mech}: out of reach " +
                                  (f"as the clears' Reapers were ({src})" if melee(slot) else f"at the far spot ({src})"))
                             for lo, hi, need, mech, src in out_of_reach(slot, var, data, far_spots)]
    pinned = [] if still or not melee(slot) else [(lo, hi) for lo, hi, _ in plan_spans(slot, var, data)]
    return Fight(until=until or data["kill_median"], moves=[] if still else moves(slot, var, data),
                 untargetable=[tuple(w) for w in data["untargetable"]], away=gone, pinned=pinned, **kw)


def parse_var(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[SHORT.get(k, k)] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", action="store_true", help="fetch the clears' timeline and movement, write " + DATA.name)
    ap.add_argument("--slot", default="R1", choices=["R1", "R2", "M1", "M2"])
    ap.add_argument("--var", action="append", help="mechanic=variant, e.g. para2=debuff (para1/para2/sc1/para3)")
    a = ap.parse_args()
    data = build() if a.build else load()
    if a.build: print(f"wrote {DATA.name}: {len(data['events'])} events from {len(data['kills'])} clears")
    print(f"untargetable: " + ", ".join(f"{x:.1f}-{y:.1f}s" for x, y in data["untargetable"]) +
          f"; median kill {data['kill_median']} s, enrage {data['enrage']} s")
    total = 0.0
    print(f"\n{'window':>15} {'run':>6} {'needs':>6}  mechanic")
    for lo, hi, y, mech, what, src in windows(a.slot, parse_var(a.var), data):
        total += y
        print(f"{lo:6.1f}-{hi:6.1f}s {y:5.1f}y {y / RUN:5.1f}s  {mech}: {what} [{src}]")
    print(f"\n{total:.0f} yalms in all, {total / RUN:.0f} s of running")
    if melee(a.slot):
        print("\nout of reach (melee):")
        for lo, hi, need, mech, src in away(a.slot, parse_var(a.var), data):
            print(f"{lo:6.1f}-{hi:6.1f}s {need:5.1f}s  {mech} [{src}]")
        print("spot fixed by our plan (positionals need True North): " +
              ", ".join(f"{lo:.1f}-{hi:.1f}s {m}" for lo, hi, m in plan_spans(a.slot, parse_var(a.var), data)))
    else:
        print("\nout of melee reach at the plan's far spots (a ranged job with melee actions, e.g. Red Mage):")
        for lo, hi, need, mech, src in far(a.slot, parse_var(a.var), data):
            print(f"{lo:6.1f}-{hi:6.1f}s {need:5.1f}s  {mech} [{src}]")
    print("\nour plan against the clears' Black Mages (median yalms run in the same window):")
    for mech, variants in PLAN.items():
        for v, runs in variants.items():
            ours = sum(y for *_, y, _ in runs)
            theirs = [data["clears_path"].get(_wkey(x, y)) for x, y, *_ in runs]
            if all(theirs): print(f"  {mech:<15} {v:<9} ours {ours:5.1f}  clears {sum(t[0] for t in theirs):5.1f}")


if __name__ == "__main__":
    main()
