"""The analysis behind the scorecard website: fetches an FFLogs report and works out, per raid group and player,
the mistakes and wipes (with classifier.py, against the party strategy in briefs.html), damage against other
groups' clears (benchmark.json), the damage lost to deaths, and damage per phase of the fight.

build_site.py is the command that uses it. Needs .fflogs_v2 at the repository root (see fflogs.py).
"""
import collections, datetime, json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fflogs, gamedata
from classifier import CONF_ORDER, Pull, classify, infer_light_parties

HERE = Path(__file__).resolve().parent
P1, SAVAGE, DD = 91, 101, 1002911
WINDOW = 120                     # seconds of damage measured from the pull, on pulls clean that long
# a tincture's share of the damage done under it (Medicated: +10.57% for DPS and healers, +10.42% for tanks), taken out
# of rDPS: neither the clears' (build_benchmark.py) nor the rotation ceiling has one
POT = {"tank": 0.1042 / 1.1042, "dps": 0.1057 / 1.1057}
POT_RATE_S = 38                  # the damage rate a tincture multiplies: the player's over 0:00-0:38, as for the clears
CACHED_ONLY = False              # build_site --cached: don't fetch parts a cached report lacks
ROLES = ["Tank", "Healer", "Melee", "Ranged", "Caster"]
ROLE = gamedata.ROLE
# grade thresholds: mistakes per pull, share of pulls whose wipe the player caused, damage vs clears, uptime points
# vs clearers of the role. With eight players and one wipe a pull, a fair share of the wipes is 12.5%.
G_MIST, G_WIPE, G_DMG, G_UP = (0.30, 0.60), (0.10, 0.20), (-0.05, -0.12), (-0.5, -1.5)
# Mistakes per pull and wipes count each culprit's share of a mistake (the classifier's `shares`: 1 for their own, 1/n
# for one of n players it cannot tell apart, a share of a shortfall spread over the party). Confidence, how sure the
# reading of the log is, is shown but not discounted: on a held-out sample (2026-10-28, scratch/accuracy/) high, medium
# and low verdicts were right about as often (92%, 88%, 94%), so a discount by it had no footing (the user's call).
CASCADE_GAP = 15                 # deaths closer together than this (seconds) belong to the same collapse
SIMULTANEOUS_S = 0.6             # deaths this close to the one that lost the pull lost it with it (one mechanic's step:
                                 # in the hand-checked pulls up to 0.53 s apart; its next step comes 0.8 s or more later)
RAIDWIDE = {"Electrify", "Unmitigated Explosion"}   # kill everyone left alive: two such deaths are already a mass death,
RAIDWIDE_S = 5                   # when they come this soon after the collapse began (later, the pull was already lost)
UNCLEAR = {"p2.tower.unclear", "sc1.tower.wrong_tilt_unclear"}   # rules that blame without knowing why it failed (lone_start)
LONE_S = 1.5                     # a death with no other this close leads the collapse alone (see lone_start)
MISTAKE_AFTER_WIPE = 2           # mistakes are counted up to this long after the one that decided the wipe
# the fight's phases, each from the start of one major mechanic to the next (the HP checkpoints' boundaries)
WINDOWS = [("Opener & Paradeigma I", 0.0, 55.4), ("Paradeigma II", 55.4, 112.4), ("Superchain I & Dialogos", 112.4, 193.9),
           ("Paradeigma III & Ultima Blade", 193.9, 284.0), ("Palladion & Theos's Ultima", 284.0, 349.0),
           ("Superchain IIA", 349.0, 399.1), ("Superchain IIB", 399.1, 458.0)]
# after a raise: share of damage lost for the debuff's 100 s, measured on these logs (Damage Down costs nothing measurable)
# damage a player loses under these, measured from each player's own hits of the same skill during and around them
# (FFLogs does not list Damage Down among a hit's buffs, so a regression on the buff list read it as no loss):
# Damage Down x0.62 over 1,264 windows (an in-game combat log agrees), Weakness after a raise x0.78 over 479;
# Brink of Death had too few samples (x0.36 over 3) and is taken as half damage
RAISE_PENALTY, RAISE_S = {"Weakness": 0.22, "Brink of Death": 0.50}, 100
DD_PENALTY = 0.38
# what each classifier rule (its tag, classifier.fault) is called in the summaries: a label, or (group, kind) for tower
# and tether failures, named with their mechanic (MECHS) or the group ("Tower: ...")
TOWER, TETHER = "Tower", "Tether"
LABELS = {
    # any mechanic
    "jump": "Left the arena", "early_pull": "Early pull", "broken_gear": "Broken gear (low max HP)", "fell_off": "Fell off the arena",
    "raidwide": "Healing / mitigation (everyone)", "tank_autos": "Tank death to auto-attacks", "unexplained": "Other",
    "avoid.Trinity of Souls": "Trinity of Souls: on the cleaved side", "avoid.Ray of Light": "Ray of Light column",
    "avoid.Superchain Burst": "Green orb (Superchain)", "avoid.Superchain Coil": "Donut (Superchain)", "avoid.Clear Cut": "Clear Cut cone",
    "avoid.Unnatural Enchainment": "Destroyed tile", "avoid.Sample": "Destroyed tile", "avoid.Palladian Ray": "Palladion puddle",
    "palladion.dash": "Palladion dash line",
    # Paradeigma I
    "p1.wf.not_in_line_up": "Missed White Flame bait", "p1.wf.too_close": "Too close to a White Flame add",
    "p1.wf.off_spot": "Off their White Flame line-up spot", "p1.wf.line": "White Flame line", "p1.wf.baiter_dead": "White Flame line",
    "p1.wf.undecided": "White Flame bait undecided (both blamed)", "p1.auto": "Auto-attack through wave 2's vulnerability",
    # Paradeigma II
    "p2.tether.not_stretched": (TETHER, "tether not stretched far enough"), "p2.tether.stood_in": (TETHER, "stood in another player's tether laser"),
    "p2.tether.holder_off": (TETHER, "tether held off its line (laser through another)"), "p2.tether.undecided": (TETHER, "tether laser undecided (both blamed)"),
    "p2.tether.dead_holder": "Tether laser", "p2.soul_and_tether": "Paradeigma II: a Soul and a tether on one player (party short)",
    "p2.soul.wrong_quadrant": (TOWER, "Soul tower in the wrong quadrant"), "p2.soul_aoe": "Soul AoE",
    "p2.tower.wrong_quadrant": (TOWER, "Soul tower in the wrong quadrant"), "p2.tower.soul_dead": (TOWER, "Soul died before dropping their tower"),
    "p2.tower.wrong_player": (TOWER, "wrong player in a tower"), "p2.tower.unsoaked": (TOWER, "tower not soaked"), "p2.tower.unclear": (TOWER, "tower not soaked"),
    "p2.tower.undecided": (TOWER, "tower unsoaked, undecided (both blamed)"), "p2.tower.out_of_reach": (TOWER, "tower dropped out of its soaker's reach"),
    # Glaukopis
    "glauk.swap": "Glaukopis tank swap", "glauk.line": "Stood in the Glaukopis line", "glauk.tanks_dead": "Glaukopis with the tanks dead",
    # Superchain I
    "sc1.purple": "Purple pair", "sc1.orange": "Orange cone overlap", "sc1.orange.undecided": "Orange cone undecided (all blamed)",
    "sc1.laser.group": "Superchain laser group", "sc1.laser.short": "Superchain laser group", "sc1.laser.both": "Both Superchain lasers on one player",
    "sc1.laser.undecided": "Superchain laser undecided (both blamed)", "sc1.laser.short_dead": "Superchain laser a sharer short (sharer dead)",
    "sc1.laser.short_undecided": "Superchain laser a sharer short, undecided",
    "sc1.flame.spread": "Heavensflame spread", "sc1.flame.walked_in": "Walked into a Heavensflame", "sc1.flame.undecided": "Heavensflame undecided (both blamed)",
    "sc1.flame.bright_aoe": "Heavensflame in a bright Soul's AoE", "sc1.bright_aoe": "Bright Soul's AoE", "sc1.bright_together": "Bright Souls' towers dropped together",
    "sc1.bright_together.undecided": "Bright Souls' towers dropped together, undecided (both blamed)",
    "sc1.glow.early": (TOWER, "stepped into the tower too early"), "sc1.glow.dropped_on": (TOWER, "bright tower dropped on its soaker"),
    "sc1.tower.soul_dead": (TOWER, "Soul died before dropping their tower"), "sc1.tower.wrong_side": (TOWER, "tower dropped on the wrong side"),
    "sc1.tower.wrong_player": (TOWER, "wrong player in a tower"), "sc1.tower.substitute": (TOWER, "tower held by a substitute, who died to it"),
    "sc1.tower.unsoaked": (TOWER, "tower not soaked"), "sc1.tower.undecided": (TOWER, "tower unsoaked, undecided (both blamed)"),
    "sc1.tower.out_of_reach": (TOWER, "tower dropped out of its soaker's reach"), "sc1.tower.dropped_on": (TOWER, "bright tower dropped on its soaker"),
    "sc1.tower.wrong_tilt": (TOWER, "tower soaked with the wrong Tilt"), "sc1.tower.wrong_tilt_unclear": (TOWER, "tower soaked with the wrong Tilt"),
    # Dialogos
    "dlg.tank_share": "Tank share (Apo / Peridialogos)", "dlg.stack": "Dialogos stack",
    # Paradeigma III
    "p3.support_tower.empty": (TOWER, "support tower left empty (Electrify)"), "p3.support_tower.dps": (TOWER, "DPS in a support tower"),
    "p3.tether.not_stretched": (TETHER, "tether not stretched far enough"), "p3.tether.stood_in": (TETHER, "stood in another player's tether laser"),
    "p3.tether.holder_off": (TETHER, "tether laser through another DPS (holder off their seat)"), "p3.tether.clipped": (TETHER, "tether laser clipped a soaking support"),
    "p3.tether.dead_holder": (TETHER, "a dead DPS's tether laser hit another"), "p3.tether.undecided": (TETHER, "tether laser undecided (both blamed)"), "p3.cross": "+ / X placement", "p3.bright_aoe": "Bright Soul's AoE",
    "p3.wf.missed": "Missed White Flame bait", "p3.wf.line": "White Flame line", "p3.wf.baiter_dead": "White Flame line", "p3.wf.own": "White Flame line",
    "p3.tower.soul_dead": (TOWER, "Soul died before dropping their tower"), "p3.tower.wrong_player": (TOWER, "wrong player in a tower"),
    "p3.tower.unsoaked": (TOWER, "tower not soaked"), "p3.tower.misplaced": (TOWER, "bright tower placed wrong"),
    "p3.tower.out_of_reach": (TOWER, "tower dropped out of its soaker's reach"), "p3.tower.undecided": (TOWER, "tower unsoaked, undecided (both blamed)"),
    "p3.cross.off_spot": "+ / X dropped off its spot",
}
MECHS = {"Paradeigma II", "Superchain I", "Paradeigma III"}


def cause_label(tag, mech=""):
    """Summary label for a classifier entry's rule (its tag); tether and tower failures are named with their mechanic.
    An unknown tag is an error: every rule needs a label here."""
    lab = LABELS[tag]
    if isinstance(lab, str): return lab
    group, kind = lab
    return f"{mech}: {kind}" if mech in MECHS else f"{group}: {kind}"


# ---------- fetching ----------
def fetch_hp(data, bench):
    """Party damage up to each checkpoint's start, for every pull that lasted that long."""
    cps = bench["hp_checkpoints"]["mechanics"]
    jobs = [(f, i) for f in data["fights"] for i, c in enumerate(cps) if (f["endTime"] - f["startTime"]) / 1000 >= c["start_s"]]
    tabs = fflogs.tables(data["code"], [(f["startTime"], f["startTime"] + int(cps[i]["start_s"] * 1000)) for f, i in jobs])
    data["hp"] = collections.defaultdict(dict)
    for (f, i), t in zip(jobs, tabs): data["hp"][str(f["id"])][cps[i]["mechanic"]] = sum(y["total"] for y in t["entries"])


def fetch_windows(data):
    """Each player's damage in every phase window a pull lasted through."""
    jobs = [(f, w) for f in data["fights"] for w in WINDOWS if (f["endTime"] - f["startTime"]) / 1000 >= w[2]]
    tabs = fflogs.tables(data["code"], [(f["startTime"] + int(a * 1000), f["startTime"] + int(b * 1000)) for f, (_, a, b) in jobs])
    data["wtables"] = collections.defaultdict(dict)
    for (f, (name, a, b)), t in zip(jobs, tabs):
        span = b - a
        data["wtables"][str(f["id"])][name] = [dict(name=y["name"], job=y["type"], total=y["total"], rdps=y["totalRDPS"] / span,
                                                   ndps=y["totalNDPS"] / span, active=y["activeTime"] / (10 * span))
                                              for y in t["entries"] if y["type"] in ROLE]


OPENER_S = 20                   # seconds of opener damage compared with the clears


def fetch_opener(data):
    """Each player's damage over the first OPENER_S seconds of every pull that lasted longer."""
    fights = [f for f in data["fights"] if (f["endTime"] - f["startTime"]) / 1000 > OPENER_S + 2]
    tabs = fflogs.tables(data["code"], [(f["startTime"], f["startTime"] + OPENER_S * 1000) for f in fights])
    data["otables"] = {str(f["id"]): [dict(name=y["name"], job=y["type"], ndps=y["totalNDPS"] / OPENER_S) for y in t["entries"] if y["type"] in ROLE]
                       for f, t in zip(fights, tabs)}


def fetch_tables(data, fights):
    """Each player's 0:00-2:00 damage in the pulls clean that long: rDPS, nDPS, active time, and the rDPS their raid
    buffs gave the others (FFLogs' totalRDPSGiven: a Reaper's Arcane Circle on the party)."""
    tabs = fflogs.tables(data["code"], [(f["startTime"], f["startTime"] + WINDOW * 1000) for f in fights])
    data["tables"] = {str(f["id"]): [dict(name=y["name"], job=y["type"], total=y["total"], rdps=y["totalRDPS"] / WINDOW,
                                         ndps=y["totalNDPS"] / WINDOW, active=y["activeTime"] / (10 * WINDOW),
                                         given=y.get("totalRDPSGiven", 0) / WINDOW)
                                    for y in t["entries"] if y["type"] in ROLE] for f, t in zip(fights, tabs)}
    data["tables_given"] = True


def ceilings():
    """Our players' rotation ceilings (unbuffed DPS over 0:00-2:00), {job: {name: {ceiling, gcd, pulls, rotation_key}}},
    as tools/rotation/dps.py --site saved them; empty when it hasn't been run."""
    f = HERE.parent / "rotation" / ".cache" / "ceilings.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def rotations():
    """The optimized rotations behind the ceilings, {job: {fight, rotations: {key: {gcd, crit, potency, dps, ...,
    rotation}}, icons: {action: data URI}, job_icon, role}}, one per GCD, as tools/rotation/dps.py --site saved them;
    empty when it hasn't been run."""
    f = HERE.parent / "rotation" / ".cache" / "rotations.json"
    out = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    g = HERE.parent / "gear" / ".cache" / "bis_site.json"     # tools/gear/ceiling.py: the best-in-slot ceilings
    bis = json.loads(g.read_text(encoding="utf-8")) if g.exists() else {}
    import gamedata
    for job, v in out.items():   # each job's action icons, for the compact rotation, its job icon and role
        v["icons"] = gamedata.icons(job, {r[1] for x in v["rotations"].values() for r in x["rotation"]})
        v["job_icon"] = gamedata.job_icon(job)
        v["role"] = ROLE.get(job, "Melee")
        if job in bis: v["bis"] = bis[job]
    return out


def gear():
    """The best-in-slot sets for the Gear pages and the rotations' job pages, {jobs: {job: sheet}, icons: {item id: data
    URI}} (tools/gear/sheets.py, from bis.py --combined's sets); empty when there are none."""
    sys.path.insert(0, str(HERE.parent / "gear"))
    import sheets
    js = sheets.sheets({a: n for n, a in gamedata.ABBR.items()})
    if not js: return {}
    for name, s in js.items(): s["role"] = ROLE.get(name, "Melee")
    return dict(jobs=js, icons=gamedata.item_icons(sheets.ids(js)))


def fetch_echo(data):
    """Ids of the pulls played with The Echo (+20% damage, HP and healing): their damage is not comparable."""
    fs = data["fights"]
    t = fflogs.tables(data["code"], [(fs[0]["startTime"], fs[-1]["endTime"])], "Buffs")[0]
    bands = [(b["startTime"], b["endTime"]) for a in t.get("auras", []) if "echo" in a["name"].lower() for b in a.get("bands", [])]
    data["echo_pulls"] = [f["id"] for f in fs if any(s < f["endTime"] and e > f["startTime"] for s, e in bands)]


def fetch_servers(data):
    """Each player's home world and the report's region, to look up their FFLogs character id (build_site.py roster)."""
    r = fflogs.gql('query($c:String!){reportData{report(code:$c){region{slug} masterData{actors(type:"Player"){name server}}}}}',
                   {"c": data["code"]})["reportData"]["report"]
    data["region"] = (r.get("region") or {}).get("slug")
    data["servers"] = {a["name"]: a["server"] for a in r["masterData"]["actors"] if a.get("server")}


def fetch_pots(data):
    """Tinctures (Medicated) running during 0:00-2:00 of the clean pulls, with the player's damage over 0:00-0:38 of that
    pull: {fight id: {name: [seconds under it, damage 0:00-0:38]}} (see pot_gain)."""
    fs = [f for f in data["fights"] if str(f["id"]) in data["tables"]]
    out = {}
    if fs:   # one Buffs table over the report, from 30 s before the first pull (a pre-pull tincture lasts into it)
        t = fflogs.tables(data["code"], [(fs[0]["startTime"] - 30000, fs[-1]["endTime"])], "Buffs", extra=",abilityID:1000049")[0]
        bands = collections.defaultdict(list)
        for a in t.get("auras", []): bands[a["name"]] += [(b["startTime"], b["endTime"]) for b in a.get("bands", [])]
        for f in fs:
            s, e = f["startTime"], f["startTime"] + WINDOW * 1000
            for name, bs in bands.items():
                under = sum(max(0, min(b1, e) - max(b0, s)) for b0, b1 in bs) / 1000
                if under > 0: out.setdefault(str(f["id"]), {})[name] = [under, 0]
        need = [f for f in fs if str(f["id"]) in out]
        for f, t38 in zip(need, fflogs.tables(data["code"], [(f["startTime"], f["startTime"] + POT_RATE_S * 1000) for f in need])):
            for y in t38["entries"]:
                if y["name"] in out[str(f["id"])]: out[str(f["id"])][y["name"]][1] = y["total"]
    data["pots"] = out


WF_WINDOW = (35, 47)   # seconds into the pull: Paradeigma I's two White Flame waves
WF_EVENTS = '''f%d:events(fightIDs:[%d],startTime:%d,endTime:%d,dataType:All,hostilityType:%s,includeResources:true,limit:10000){data}'''


def wf_compact(f, events, abilities):
    """One pull's White Flame lasers and every position the log has around them, for the classifier (Pull.wf):
    {lasers: [[t, laser instance, add x, add y]], adds: [[t, add instance, x, y]], pos: [[t, player id, x, y]]}, times in
    seconds from the pull. Each add fires at its two nearest players at the laser cast, ~0.7 s before the hits; the
    damage events hold only the hit players' positions, at the hit. The adds' own White Flame cast, ~0.9 s before the
    lasers, has where they are; half the waves' lasers still log Athena's spot."""
    players, seen, lasers, adds, pos = set(f["friendlyPlayers"]), set(), [], [], []
    xy = lambda r: (round((r["x"] - 10000) / 100, 2), round((r["y"] - 10000) / 100, 2)) if r and "x" in r else None
    for e in events:
        k = json.dumps(e, sort_keys=True)   # the Enemies and Friendlies queries both return events between the sides
        if k in seen: continue
        seen.add(k)
        t = round((e["timestamp"] - f["startTime"]) / 1000, 3)
        if e["type"] == "cast" and abilities.get(str(e.get("abilityGameID"))) == "White Flame" and (p := xy(e.get("sourceResources"))):
            # the adds' own White Flame cast targets themselves; the lasers do not
            (adds if e.get("targetID") == e.get("sourceID") else lasers).append([t, e.get("sourceInstance"), *p])
        for side in ("source", "target"):
            if e.get(f"{side}ID") in players and (p := xy(e.get(f"{side}Resources"))): pos.append([t, e[f"{side}ID"], *p])
    return dict(lasers=sorted(lasers), adds=sorted(adds), pos=sorted(pos))


def fetch_wf(data):
    """Positions around Paradeigma I's White Flame for every pull that lasts into it (wf_compact)."""
    fights, out = [f for f in data["fights"] if f["endTime"] - f["startTime"] > WF_WINDOW[0] * 1000], {}
    for i in range(0, len(fights), 8):
        part, evs = fights[i:i + 8], collections.defaultdict(list)
        for h in ("Enemies", "Friendlies"):
            q = "query($c:String!){reportData{report(code:$c){" + " ".join(WF_EVENTS % (f["id"], f["id"], f["startTime"] + WF_WINDOW[0] * 1000,
                min(f["endTime"], f["startTime"] + WF_WINDOW[1] * 1000), h) for f in part) + "}}}"
            r = fflogs.gql(q, {"c": data["code"]})["reportData"]["report"]
            for f in part: evs[f["id"]] += r[f"f{f['id']}"]["data"]
        for f in part: out[str(f["id"])] = wf_compact(f, evs[f["id"]], data["abilities"])
    data["wf"] = out


P3_WINDOW = (205, 215.5)   # seconds into the pull: Paradeigma III's add tethers, up to the DPS lasers


def p3_compact(f, events):
    """One pull's Paradeigma III tethers, for the classifier (Pull.p3): {tethers: [[t, add instance, player id]]}, times
    in seconds from the pull. Each add's last tether before its laser names the laser's holder; the calculated hits
    cannot when a laser goes through two DPS or its holder died as it fired."""
    players, seen, out = set(f["friendlyPlayers"]), set(), []
    for e in events:
        k = json.dumps(e, sort_keys=True)
        if e["type"] != "tether" or k in seen or e.get("targetID") not in players: continue
        seen.add(k)
        out.append([round((e["timestamp"] - f["startTime"]) / 1000, 3), e.get("sourceInstance"), e["targetID"]])
    return dict(tethers=sorted(out))


def fetch_p3(data):
    """The add tethers before Paradeigma III's DPS lasers for every pull that lasts into them (p3_compact)."""
    fights, out = [f for f in data["fights"] if f["endTime"] - f["startTime"] > P3_WINDOW[0] * 1000], {}
    for i in range(0, len(fights), 8):
        part = fights[i:i + 8]
        q = "query($c:String!){reportData{report(code:$c){" + " ".join(WF_EVENTS % (f["id"], f["id"], f["startTime"] + int(P3_WINDOW[0] * 1000),
            min(f["endTime"], f["startTime"] + int(P3_WINDOW[1] * 1000)), "Enemies") for f in part) + "}}}"
        r = fflogs.gql(q, {"c": data["code"]})["reportData"]["report"]
        for f in part: out[str(f["id"])] = p3_compact(f, r[f"f{f['id']}"]["data"])
    data["p3"] = out


P2_WINDOW = (66, 83)   # seconds into the pull: Paradeigma II from the Souls landing to the towers resolving (lasers ~77 s, towers ~80.6)
P2_CASTS = ("Searing Radiance", "Shadowsear", "Astral Glow", "Umbral Glow", "Astral Advance", "Umbral Advance")


def p2_compact(f, events, abilities):
    """One pull's Paradeigma II, for the classifier (Pull.p2): {tethers: [[t, add instance, player id]], casts: [[t, name,
    source instance, target id or None, x, y]] (the adds' tether lasers, the Glows and the towers' Advance, where each
    came from), pos: [[t, player id, x, y]]}, times in seconds from the pull. The calculated hits miss a laser's holder
    when another laser killed them first, and the damage events hold only the hit players' positions."""
    players, seen, tethers, casts, pos = set(f["friendlyPlayers"]), set(), [], [], []
    xy = lambda r: (round((r["x"] - 10000) / 100, 2), round((r["y"] - 10000) / 100, 2)) if r and "x" in r else None
    for e in events:
        k = json.dumps(e, sort_keys=True)
        if k in seen: continue
        seen.add(k)
        t, nm = round((e["timestamp"] - f["startTime"]) / 1000, 3), abilities.get(str(e.get("abilityGameID")))
        if e["type"] == "tether" and e.get("targetID") in players: tethers.append([t, e.get("sourceInstance"), e["targetID"]])
        if e["type"] in ("begincast", "cast") and nm in P2_CASTS and (p := xy(e.get("sourceResources"))):
            casts.append([t, nm, e.get("sourceInstance"), e.get("targetID") if e.get("targetID") in players else None, *p])
        for side in ("source", "target"):
            if e.get(f"{side}ID") in players and (p := xy(e.get(f"{side}Resources"))): pos.append([t, e[f"{side}ID"], *p])
    return dict(tethers=sorted(tethers), casts=sorted(casts, key=lambda c: c[0]), pos=sorted(pos))


def fetch_p2(data):
    """Paradeigma II's tethers, casts and positions for every pull that lasts into it (p2_compact)."""
    fights, out = [f for f in data["fights"] if f["endTime"] - f["startTime"] > P2_WINDOW[0] * 1000], {}
    for i in range(0, len(fights), 8):
        part, evs = fights[i:i + 8], collections.defaultdict(list)
        for h in ("Enemies", "Friendlies"):
            q = "query($c:String!){reportData{report(code:$c){" + " ".join(WF_EVENTS % (f["id"], f["id"], f["startTime"] + P2_WINDOW[0] * 1000,
                min(f["endTime"], f["startTime"] + P2_WINDOW[1] * 1000), h) for f in part) + "}}}"
            r = fflogs.gql(q, {"c": data["code"]})["reportData"]["report"]
            for f in part: evs[f["id"]] += r[f"f{f['id']}"]["data"]
        for f in part: out[str(f["id"])] = p2_compact(f, evs[f["id"]], data["abilities"])
    data["p2"] = out


SC1_WINDOW = (127, 151)   # seconds into the pull: Superchain I from its first resolution to the bright Souls' towers resolving
                          # (the lasers ~137 s, the towers drop ~145 s and resolve 3 s later)
SC1_VERSION = 2           # bumped when sc1_compact changes: caches holding another are fetched again


def sc1_compact(f, events, abilities):
    """One pull's Superchain I, for the classifier (Pull.sc1): {towers: [[t, aspect, x, y]] (each bright tower's
    Advance cast, where it dropped; the Glow's own source is often stale), cluster: [[t, "Burst" or "Coil", x, y]] (the
    clusters' orb and donut casts), pos: [[t, player id, x, y]]}, times in seconds from the pull. The damage events hold
    only the hit players' positions, so a soaker who never stepped into their tower has none there."""
    players, seen, towers, cluster, pos = set(f["friendlyPlayers"]), set(), [], [], []
    xy = lambda r: (round((r["x"] - 10000) / 100, 2), round((r["y"] - 10000) / 100, 2)) if r and "x" in r else None
    for e in events:
        k = json.dumps(e, sort_keys=True)
        if k in seen: continue
        seen.add(k)
        t, nm = round((e["timestamp"] - f["startTime"]) / 1000, 3), abilities.get(str(e.get("abilityGameID")))
        if e["type"] == "cast" and (p := xy(e.get("sourceResources"))):
            if nm in ("Astral Advance", "Umbral Advance"): towers.append([t, nm.split()[0], *p])
            if nm in ("Superchain Burst", "Superchain Coil"): cluster.append([t, nm.split()[1], *p])
        for side in ("source", "target"):
            if e.get(f"{side}ID") in players and (p := xy(e.get(f"{side}Resources"))): pos.append([t, e[f"{side}ID"], *p])
    return dict(towers=sorted(towers), cluster=sorted(cluster), pos=sorted(pos))


def fetch_sc1(data):
    """Superchain I's towers, clusters and positions for every pull that lasts into them (sc1_compact)."""
    fights, out = [f for f in data["fights"] if f["endTime"] - f["startTime"] > SC1_WINDOW[0] * 1000], {}
    for i in range(0, len(fights), 8):
        part, evs = fights[i:i + 8], collections.defaultdict(list)
        for h in ("Enemies", "Friendlies"):
            q = "query($c:String!){reportData{report(code:$c){" + " ".join(WF_EVENTS % (f["id"], f["id"], f["startTime"] + SC1_WINDOW[0] * 1000,
                min(f["endTime"], f["startTime"] + SC1_WINDOW[1] * 1000), h) for f in part) + "}}}"
            r = fflogs.gql(q, {"c": data["code"]})["reportData"]["report"]
            for f in part: evs[f["id"]] += r[f"f{f['id']}"]["data"]
        for f in part: out[str(f["id"])] = sc1_compact(f, evs[f["id"]], data["abilities"])
    data["sc1"], data["sc1_v"] = out, SC1_VERSION


def pot_gain(data, fid, y):
    """DPS over 0:00-2:00 a tincture added to this table row, as build_benchmark.py reckons the clears': the seconds under
    it at the player's 0:00-0:38 damage rate, times the tincture's share."""
    under, dmg = data.get("pots", {}).get(fid, {}).get(y["name"], (0, 0))
    return under * dmg / POT_RATE_S * POT["tank" if ROLE.get(y["job"]) == "Tank" else "dps"] / WINDOW


def fetch(code, refresh, bench):
    cf = fflogs.CACHE / f"report_{code}.json"
    if cf.exists() and not refresh:
        data = json.loads(cf.read_text())
        for key, fill, what in (("hp", lambda: fetch_hp(data, bench), "boss HP at the checkpoints"), ("wtables", lambda: fetch_windows(data), "damage per phase"),
                                ("otables", lambda: fetch_opener(data), "opener damage"), ("echo_pulls", lambda: fetch_echo(data), "the Echo check"),
                                ("tables_given", lambda: fetch_tables(data, [f for f in data["fights"] if str(f["id"]) in data["tables"]]),
                                 "the rDPS raid buffs gave others"),
                                ("pots", lambda: fetch_pots(data), "tinctures"), ("wf", lambda: fetch_wf(data), "positions at White Flame"),
                                ("p3", lambda: fetch_p3(data), "tethers at Paradeigma III"), ("sc1", lambda: fetch_sc1(data), "towers at Superchain I"),
                                ("p2", lambda: fetch_p2(data), "tethers and positions at Paradeigma II"),
                                ("servers", lambda: fetch_servers(data), "home worlds")):
            if key not in data or key == "sc1" and data.get("sc1_v") != SC1_VERSION:   # reports cached before this part existed, or changed
                if CACHED_ONLY: print(f"  {code}: no {what} in the cache, left out (--cached)", file=sys.stderr); continue
                print(f"  {code}: fetching {what}", file=sys.stderr); fill(); cf.write_text(json.dumps(data))
        return data
    meta = fflogs.gql('''query($c:String!){reportData{report(code:$c){title startTime
        masterData{actors(type:"Player"){id name subType} abilities{gameID name}}
        fights(encounterID:91){id startTime endTime kill bossPercentage difficulty friendlyPlayers}}}}''', {"c": code})["reportData"]["report"]
    fights = [f for f in meta["fights"] if f.get("difficulty") == SAVAGE]
    if not fights: raise SystemExit(f"{code}: no Savage P1 (Athena) pulls in this report")
    print(f"  {code}: {len(fights)} pulls, fetching events", file=sys.stderr)
    data = dict(code=code, title=meta["title"], startTime=meta["startTime"], fights=fights,
                masterData={"actors": meta["masterData"]["actors"]},
                abilities={a["gameID"]: a["name"] for a in meta["masterData"]["abilities"]},
                deaths=fflogs.events(code, fights, "Deaths"),
                debuffs=fflogs.events(code, fights, "Debuffs"),
                dmg=fflogs.events(code, fights, "DamageTaken", resources=True))
    clean = [f for f in fights if first_mistake(data, f)[0] >= WINDOW]
    print(f"  {code}: {len(clean)} pulls clean through 2:00, fetching damage tables", file=sys.stderr)
    fetch_tables(data, clean)
    print(f"  {code}: fetching boss HP at the checkpoints, damage per phase and opener damage", file=sys.stderr)
    fetch_hp(data, bench)
    fetch_windows(data)
    fetch_opener(data)
    fetch_echo(data)
    fetch_pots(data)
    fetch_wf(data)
    fetch_p3(data)
    fetch_sc1(data)
    fetch_p2(data)
    fetch_servers(data)
    fflogs.CACHE.mkdir(exist_ok=True); cf.write_text(json.dumps(data))
    return data


def first_mistake(data, f):
    """Seconds into the pull of the first player death or Damage Down (the death event)."""
    fp, s, e = set(f["friendlyPlayers"]), f["startTime"], f["endTime"]
    ts = [x["timestamp"] for x in data["deaths"] if s <= x["timestamp"] <= e and x.get("targetID") in fp]
    ts += [x["timestamp"] for x in data["debuffs"] if x.get("abilityGameID") == DD and x["type"] in ("applydebuff", "refreshdebuff")
           and s <= x["timestamp"] <= e and x.get("targetID") in fp]
    return ((min(ts) - s) / 1000 if ts else (e - s) / 1000), bool(ts)


# ---------- analysis ----------
def mistakes_of(res):
    """Every distinct mistake in a pull: classifier entries with a culprit that are not just fallout of an earlier
    mistake, one per culprit per 2 s (a bait that kills four players is one mistake). Yields (culprit, t, cause, mechanic,
    kind, confidence, tag, share): kind is "death" when any of the mistake's events killed someone, else "DD" when one gave
    Damage Down, else "hit" (neither: both Superchain lasers on someone who lived); confidence is the surest of its entries';
    tag the rule's (cause_label names it); share how much of it is theirs (the classifier's: 1/n for one of n candidates,
    a party's share of a shortfall spread over it), the largest of its entries'. An entry about several failures at once
    (by_culprit) counts each culprit's as their own failure's cause and tag.
    Culprits an entry carries over from an earlier death are counted there."""
    out, rank = [], {"death": 0, "DD": 1, "hit": 2}
    for r in res:
        if r.get("derived") or not r["culprits"]: continue
        kind = r["kind"]
        for c in r["culprits"]:
            if c in r.get("carried", ()): continue
            same = next((i for i, m in enumerate(out) if m[0] == c and abs(m[1] - r["t"]) <= 2), None)
            sh = r.get("shares", {}).get(c, 1.0)
            cause, tag = r.get("by_culprit", {}).get(c, (r["cause"], r["tag"]))   # several failures at once: the culprit's own
            if same is None: out.append((c, r["t"], cause, r["mechanic"], kind, r["confidence"], tag, sh))
            else:
                m = out[same]
                out[same] = m[:4] + (min(m[4], kind, key=rank.get), min(m[5], r["confidence"], key=lambda x: CONF_ORDER.get(x, 1)), m[6], max(m[7], sh))
    return out


def lone_start(collapse, res):
    """Whether the collapse's first death did not lose the pull: alone (no other death within LONE_S), nothing later in
    the pull follows from it (no entry chains to it or names its victim as a culprit, after the wipe call too: a dead
    tank shows up as auto-attacks then), every later death in the collapse explained by a rule without it (an
    unexplained one may be its fallout), and the next step killing two or more (it would have lost the pull on its own;
    one lone death does not pass the wipe to the next). The user's rule, 2026-10-28: a dispensable player's death
    before an unrelated cascade (Zj8T pull 2: a Heavensflame player's donut, then the lasers) did not lose it."""
    r, later = collapse[0], collapse[1:]
    if later[0]["t"] - r["t"] <= LONE_S: return False
    if any(r["victim"] in q.get("follows", ()) or r["victim"] in q["culprits"] for q in res if q["t"] > r["t"] and q is not r): return False
    if any(not q["culprits"] or q["tag"] in UNCLEAR for q in later): return False
    return len({q["victim"] for q in later if q["t"] - later[0]["t"] <= LONE_S}) >= 2


def wipe_of(res):
    """Who lost the pull. A player jumping off the arena (a death without a hit) means the wipe was called, so only
    deaths before the first jump count, and a pull with none was called without one (the jump decides, no culprit).
    The collapse is the last run of deaths with less than CASCADE_GAP seconds between them; one player outliving the
    rest by more (an invulnerability) does not make a run of their own unless the wipe was called, and deaths after the
    whole party was dead (players raised after it, dying again) belong to the run before (party_dead). A mass death in it
    (four or more players to one ability within 3 s, or two to one that kills everyone left, RAIDWIDE) decides the
    wipe (with no culprit when its mechanic is not blamed); otherwise its first death does, or one with a culprit within
    1.5 s of it (the same hit, logged in any order).
    When no rule explains that first death and no mistake came before it in the pull (or its mechanic is not blamed
    yet), no one lost the pull, even if a later death has a culprit, since that may be its fallout. A first death that
    follows an earlier mistake without a rule tying it to one passes to the collapse's first death with a culprit;
    failing that, a collapse in a mechanic not blamed yet has no culprit, and any other the last attributed death before
    it. Deaths within SIMULTANEOUS_S of the deciding one, each to its own mistake, lost the pull with it; a raid-wide
    mass death is its own mistake's alone. Earlier deaths the group recovered from do not count. Returns (culprits,
    the deciding entry)."""
    jump = next((r for r in res if r.get("jump")), None)
    deaths = [r for r in res if r["kind"] == "death" and not r.get("jump") and (jump is None or r["t"] < jump["t"])]
    if not deaths: return [], jump
    run_start = lambda i: next(j for j in range(i, -1, -1) if j == 0 or deaths[j]["t"] - deaths[j - 1]["t"] > CASCADE_GAP)
    i = run_start(len(deaths) - 1)
    while jump is None and i > 0 and len({r["victim"] for r in deaths[i:]}) == 1: i = run_start(i - 1)
    # a run after the whole party was dead (players raised after the wipe, dying again) belongs to the run before
    while i > 0 and any(r.get("party_dead") for r in deaths[run_start(i - 1):i]): i = run_start(i - 1)
    collapse = deaths[i:]
    while len({r["victim"] for r in collapse[1:]}) > 1 and lone_start(collapse, res): collapse = collapse[1:]
    same_hit = lambda r: [q for q in collapse if q["ability"] == r["ability"] and 0 <= q["t"] - r["t"] <= 3]
    mass = next((r for r in collapse if (r["culprits"] or r["confidence"] == "not blamed") and (len(same_hit(r)) >= 4 or r["ability"] in RAIDWIDE
                                                           and len(same_hit(r)) >= 2 and r["t"] - collapse[0]["t"] <= RAIDWIDE_S)), None)
    if mass and not mass["culprits"]: return [], mass   # a mass death in a mechanic not blamed (yet, or on this day)
    first, near = collapse[0], next((r for r in collapse if r["culprits"] and r["t"] - collapse[0]["t"] <= 1.5), None)
    if not mass and not near and first["confidence"] in ("unattributed", "not blamed"): return [], first
    trig = mass or near or next((r for r in collapse if r["culprits"]), None)
    if not trig and (gated := next((r for r in collapse if r["confidence"] == "not blamed"), None)): return [], gated
    trig = trig or next((r for r in reversed(deaths[:i]) if r["culprits"]), None)
    if not trig: return [], None
    together = same_hit(trig) if trig is mass else []
    if not (trig is mass and trig["ability"] in RAIDWIDE): together += [q for q in collapse if abs(q["t"] - trig["t"]) <= SIMULTANEOUS_S]
    return list(dict.fromkeys(c for q in [trig] + together for c in q["culprits"])), trig



def wipe_shares(res, cul, trig):
    """{culprit: their share of the wipe}: the largest share the deciding entry, or another death of the same hit or step
    (wipe_of's mass death and simultaneous deaths), gives them."""
    near = [q for q in res if q["kind"] == "death" and (q is trig or abs(q["t"] - trig["t"]) <= 3)] if trig else []
    return {c: max((q.get("shares", {}).get(c, 1.0) for q in near if c in q["culprits"]), default=1.0) for c in cul}

def wipe_label(trig):
    """The site's name for what lost the pull."""
    if trig["culprits"]: return cause_label(trig["tag"], trig["mechanic"])
    if trig.get("jump"): return "Wipe called (left the arena)"
    return "Not blamed yet (no rules)" if trig["confidence"] == "not blamed" else "No culprit found"


def downtime(p, res, end):
    """Each mistake's lost time: a death is dead from the lethal hit until a raise (or the end of the pull), then the
    raise's Weakness / Brink of Death; a Damage Down costs DD_PENALTY of the player's damage until it wears off (or
    they die). Returns {player: [(start, end, share of damage lost, classifier entry)]}."""
    out = collections.defaultdict(list)
    deaths = sorted((r for r in res if r["kind"] == "death"), key=lambda r: r["t"])
    for r in deaths:
        nxt = next((q["t"] for q in deaths if q["victim"] == r["victim"] and q["t"] > r["t"]), end)
        rz = next((e for e in sorted(p.deb, key=lambda e: e["t"]) if e["who"] == r["victim"] and e["name"] in RAISE_PENALTY
                   and e["type"] == "applydebuff" and r["t"] < e["t"] < nxt), None)
        up = rz["t"] if rz else min(nxt, end)
        out[r["victim"]].append((r["t"], up, 1.0, r))
        if rz: out[r["victim"]].append((up, min(up + RAISE_S, nxt, end), RAISE_PENALTY[rz["name"]], r))
    for r in (r for r in res if r["kind"] == "DD"):
        off = next((e["t"] for e in sorted(p.deb, key=lambda e: e["t"]) if e["who"] == r["victim"] and e["name"] == "Damage Down"
                    and e["type"] == "removedebuff" and e["t"] > r["t"]), end)
        died = next((q["t"] for q in deaths if q["victim"] == r["victim"] and q["t"] >= r["t"]), end)
        if min(off, died) > r["t"]: out[r["victim"]].append((r["t"], min(off, died, end), DD_PENALTY, r))
    return out


def analyse(group, data, bench):
    echo = {str(i) for i in data.get("echo_pulls", [])}           # pulls with The Echo: no damage figures from them
    # 0:00-2:00 damage with tinctures taken out (rDPS and the party's total), like the clears' it is compared with
    tables = {k: [dict(y, rdps=y["rdps"] - g, total=y["total"] - g * WINDOW) for y in v for g in [pot_gain(data, k, y)]]
              for k, v in data["tables"].items()}
    data = dict(data, tables={k: v for k, v in tables.items() if k not in echo},
                wtables={k: v for k, v in data.get("wtables", {}).items() if k not in echo},
                otables={k: v for k, v in data.get("otables", {}).items() if k not in echo},
                hp={k: v for k, v in data.get("hp", {}).items() if k not in echo})
    names = {a["id"]: a["name"] for a in data["masterData"]["actors"] if a["subType"] in ROLE}
    rep = {"masterData": data["masterData"], "deaths": data["deaths"]}
    ev = {"abilities": data["abilities"], "dmg": data["dmg"], "debuffs": data["debuffs"], "wf": data.get("wf"), "p3": data.get("p3"), "sc1": data.get("sc1"), "p2": data.get("p2")}
    import acts                                 # the players' casts, for the rules that read them (the Glaukopis swap)
    A = acts.report(data["code"], data["fights"])
    pulls = [Pull(data["code"], f, rep, ev, acts=A.get(str(f["id"]))) for f in data["fights"]]
    lp = infer_light_parties(pulls)
    day = datetime.datetime.fromtimestamp(data["startTime"] / 1000).date().isoformat()   # the raid day, as build_site.py's
    attended, nmist, mcauses = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    nkind = collections.Counter()               # (player, "death" / "DD" / "hit") -> mistakes
    nwipe, wcauses = collections.Counter(), collections.defaultdict(collections.Counter)
    # the same counting each culprit's share of the mistake (1/n of one the classifier cannot tell n players' apart), and
    # the counts by confidence (how sure the reading of the log is: shown, not discounted)
    wmist, wkind, wwipe = collections.Counter(), collections.Counter(), collections.Counter()
    mconf, wconf = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    all_causes, wipe_causes, conf = collections.Counter(), collections.Counter(), collections.Counter()
    pull_rows, lives = [], []        # one record per pull (for build_site.py); each pull's lost time, for the costs below
    wsamples = collections.defaultdict(list)   # (player, job, window) -> clean phase samples
    pphase = collections.defaultdict(list)     # (player, job, pull) -> [(window, nDPS, seconds)] clean in that pull
    for n, (p, f) in enumerate(zip(pulls, data["fights"]), 1):
        for pid in f["friendlyPlayers"]:
            if pid in names: attended[names[pid]] += 1
        res, _ = classify(p, lp, day)
        dur = (f["endTime"] - f["startTime"]) / 1000
        row = dict(n=n, id=f["id"], at=data["startTime"] + f["startTime"], dur=round(dur, 1), boss=f.get("bossPercentage"), kill=bool(f.get("kill")),
                   first=round(first_mistake(data, f)[0], 1), deaths=sum(1 for r in res if r["kind"] == "death"), wipe=None, mistakes=[],
                   players=sorted(names[pid] for pid in f["friendlyPlayers"] if pid in names))
        pull_rows.append(row)
        cul, trig = wipe_of(res) if not f.get("kill") else ([], None)
        inc = [r for r in res if r["kind"] != "hit"]   # deaths and Damage Downs
        if inc:
            first = [r for r in inc if r["t"] <= inc[0]["t"] + 1.5]
            conf.update(r["confidence"] for r in first)
        if not f.get("kill") and inc:
            wipe_causes[wipe_label(trig) if trig else "Unclear"] += 1
            wsh = wipe_shares(res, cul, trig)
            for c in cul:
                nwipe[c] += 1; wcauses[c][wipe_label(trig)] += 1
                wwipe[c] += wsh[c]; wconf[c][trig["confidence"]] += 1
            if trig: row["wipe"] = dict(culprits=cul, t=round(trig["t"], 1), mechanic=trig["mechanic"], label=wipe_label(trig), cause=trig["cause"],
                                        confidence=trig["confidence"], **({"shares": {c: round(x, 3) for c, x in wsh.items()}} if any(x < 1 for x in wsh.values()) else {}))
        # every death with what killed them and whose fault it was; when: "lost" for the deaths that decided the wipe
        # (the deciding death and the rest of its mass death), "after" for the collapse after it, None before; saved: their death
        # was the price of saving the pull (a Superchain I tower held in its Strong Soul's place)
        lost_at = trig["t"] - 1 if trig else dur
        row["death_list"] = [dict(who=r["victim"], t=round(r["t"], 1), ability=r["ability"], mechanic=r["mechanic"], cause=r["cause"],
                                  culprits=r["culprits"], confidence=r["confidence"], **({"trace": r["trace"]} if r.get("trace") else {}),
                                  **({"shares": {c: round(x, 3) for c, x in r["shares"].items()}} if any(x < 1 for x in r.get("shares", {}).values()) else {}),
                                  **({"saved": True} if r.get("saved") else {}),   # died holding what would have lost the pull
                                  when="lost" if trig and (r is trig or r["ability"] == trig["ability"] and abs(r["t"] - trig["t"]) <= 3)
                                  else "after" if r["t"] >= lost_at else None)
                             for r in res if r["kind"] == "death"]
        # every mistake while the pull was still alive; what happens during the collapse is forced or noise
        cutoff = trig["t"] + MISTAKE_AFTER_WIPE if trig else dur
        traces = {r["cause"]: r["trace"] for r in res if r.get("trace")}   # the site shows a chained cause as a tree
        for c, t, cause, mech, kind, cf, tag, sh in mistakes_of(res):
            if t <= cutoff:
                lab = cause_label(tag, mech); nmist[c] += 1; mcauses[c][lab] += 1; all_causes[lab] += 1
                nkind[(c, kind)] += 1
                wmist[c] += sh; wkind[(c, kind)] += sh; mconf[c][cf] += 1
                row["mistakes"].append(dict(who=c, t=round(t, 1), mechanic=mech, label=lab, cause=cause, kind=kind, conf=cf, **({"share": round(sh, 3)} if sh < 1 else {}),
                                            **({"trace": traces[cause]} if cause in traces else {})))
        down = downtime(p, res, dur)
        lives.append((row, down, min(cutoff, dur)))
        # a phase is a clean sample for a player when they were alive and unweakened through it, before the pull was lost
        for wname, a, b in WINDOWS:
            for y in data.get("wtables", {}).get(str(f["id"]), {}).get(wname, []):
                if b <= cutoff and not any(s < b and e > a for s, e, _, _ in down.get(y["name"], [])):
                    wsamples[(y["name"], y["job"], wname)].append(dict(y, pull=n))
                    pphase[(y["name"], y["job"], n)].append((wname, y["ndps"], b - a))
    # damage lost to deaths, valued at the player's own rDPS in that phase of the fight
    rate = {}
    for (name, job, wname), v in wsamples.items():
        rate.setdefault(name, {})[wname] = st.mean(x["rdps"] for x in v)
    overall = {name: st.mean(r.values()) for name, r in rate.items()}
    boss = bench["hp_checkpoints"]["boss_hp"]

    def lost(name, s, e, share):
        out = 0.0
        for wname, a, b in WINDOWS:
            lo, hi = max(s, a), min(e, b if wname != WINDOWS[-1][0] else max(b, e))
            if hi > lo: out += (hi - lo) * share * rate.get(name, {}).get(wname, overall.get(name, 0.0))
        return out
    suffered, caused, dead_s = collections.Counter(), collections.Counter(), collections.Counter()
    event_cost = collections.defaultdict(list)   # "death" / "DD" -> boss HP lost to each one
    caused_by, lost_causes = collections.defaultdict(collections.Counter), collections.Counter()
    for row, down, until in lives:
        row["lost"], row["lost_dd"], by = 0.0, 0.0, collections.Counter()
        per_event = collections.defaultdict(float)
        for victim, spans in down.items():
            for s, e, share, r in spans:
                e = min(e, until)                    # time after the pull was lost does not matter
                if e <= s: continue
                hp = 100 * lost(victim, s, e, share) / boss
                if share == 1.0: dead_s[victim] += e - s
                suffered[victim] += hp; row["lost"] += hp
                if r["kind"] == "DD": row["lost_dd"] += hp
                per_event[(id(r), r["kind"])] += hp
                who = r["culprits"] or ["(no one)"]
                lab = cause_label(r["tag"], r["mechanic"]) if r["culprits"] else "No culprit found"
                lost_causes[lab] += hp
                for c in who:
                    caused[c] += hp / len(who); caused_by[c][lab] += hp / len(who); by[c] += hp / len(who)
        row["lost"], row["lost_dd"] = round(row["lost"], 2), round(row["lost_dd"], 2)
        for (_, kind), hp in per_event.items(): event_cost[kind].append(hp)
        row["lost_by"] = [dict(who=c, hp=round(v, 2)) for c, v in by.most_common()]
    import checks                               # rotation checks against the clears (imported here: it imports this module)
    rotation = checks.report(data, lives)
    ceil = ceilings()
    # opener damage (first OPENER_S seconds, alive throughout) against the clears' median on the job, or our other
    # players' when a kit change leaves too few clears (checks.KIT_CHANGES)
    odps, oref = collections.defaultdict(list), checks.clear_opener_dps()
    for (row, down, until), f in zip(lives, data["fights"]):
        for y in data.get("otables", {}).get(str(f["id"]), []):
            if not any(s < OPENER_S for s, e, share, _ in down.get(y["name"], []) if share == 1.0): odps[(y["name"], y["job"])].append(y["ndps"])
    for key, rot in rotation.items():
        if rot.get("opener") and odps.get(key) and rot["opener"]["source"] == "groups":   # kit change: our other players
            others = [o["dmg"] for o in checks.group_openers(key[1]) if o["who"] != key[0] and o["dmg"]]
            if len(others) >= 3:
                ref = dict(ndps=st.median(others), echo_corrected=False)
                rot["opener"]["dmg"] = dict(ndps=round(st.median(odps[key])), clears=round(ref["ndps"]), n=len(odps[key]),
                                            vs=round(st.median(odps[key]) / ref["ndps"] - 1, 3), echo_corrected=False, players=len(others))
        elif rot.get("opener") and odps.get(key) and key[1] in oref:
            ref = oref[key[1]]
            rot["opener"]["dmg"] = dict(ndps=round(st.median(odps[key])), clears=round(ref["ndps"]), n=len(odps[key]),
                                        vs=round(st.median(odps[key]) / ref["ndps"] - 1, 3), echo_corrected=ref["echo_corrected"])
        best = (rot.get("opener") or {}).get("best_dmg")   # the players of the reference opener
        if best and rot["opener"].get("dmg"): rot["opener"]["dmg"].update(best=best, vs_best=round(st.median(odps[key]) / best - 1, 3))
    played = {}                                  # (pull, player) -> job
    for f, row in zip(data["fights"], pull_rows):
        for name, job in A.get(str(f["id"]), {}).get("players", {}).values(): played[(row["n"], name)] = job

    def pull_detail(name, job):
        """One entry per pull the player played on this job: how it went for them."""
        rot = {x["n"]: x for x in (rotation.get((name, job)) or {}).get("per_pull", [])}
        out = []
        for row, down, until in lives:
            if played.get((row["n"], name)) != job: continue
            # deaths before the pull was lost; everyone dies once it is
            lost_at = row["wipe"]["t"] - 1 if row["wipe"] else until       # the deciding mistake's deaths are the wipe itself
            death = next(((s, r) for s, e, share, r in sorted(down.get(name, []), key=lambda x: x[0]) if share == 1.0 and s < lost_at), None)
            ref = {w["name"]: w["pools"]["clears"]["jobs"].get(job, {}).get("ndps") for w in bench.get("windows", [])}
            ph = [(nd / ref[w] - 1, sec) for w, nd, sec in pphase.get((name, job, row["n"]), []) if ref.get(w)]
            r = rot.get(row["n"], {})
            out.append(dict(n=row["n"], dur=row["dur"], kill=row["kill"], boss=row["boss"],
                            wipe=row["wipe"]["label"] if row["wipe"] else None,
                            caused=bool(row["wipe"] and name in row["wipe"]["culprits"]),
                            mistakes=[m["label"] for m in row["mistakes"] if m["who"] == name],
                            died=dict(t=round(death[0], 1), how=cause_label(death[1]["tag"], death[1]["mechanic"]) if death[1].get("culprits")
                                      else death[1].get("ability") or "unattributed") if death else None,
                            dmg=round(sum(v * sec for v, sec in ph) / sum(sec for _, sec in ph), 3) if ph else None, phases=len(ph),
                            loss=r.get("loss"), top=r.get("top"), dps=r.get("dps")))
        return out
    segs = [first_mistake(data, f)[0] for f in data["fights"]]
    samples = collections.defaultdict(list)
    for rows in data["tables"].values():
        for y in rows: samples[(y["name"], y["job"])].append(y)
    party = [sum(y["total"] for y in rows) / WINDOW for rows in data["tables"].values() if len(rows) == 8]
    bwin = {w["name"]: w for w in bench.get("windows", [])}
    players = []
    for name in attended:
        jobs = [j for (n, j) in samples if n == name] or [next(a["subType"] for a in data["masterData"]["actors"] if a["name"] == name)]
        for job in jobs:
            v = samples.get((name, job), [])
            xs = sorted((y["rdps"] for y in v), reverse=True)
            top = st.mean(xs[:max(2, len(xs) // 4)]) if xs else None
            cj = bench["pools"]["clears"]["jobs"]
            vs = (top / cj[job]["rdps"] - 1, cj[job]["players"], cj[job].get("echo_corrected", False)) if top and job in cj else None
            up = st.mean(y["active"] for y in v) if v else None
            phases = []
            for wname, a, b in WINDOWS:   # damage per phase: rotation (nDPS) and GCD uptime against clearers on the job
                sm = wsamples.get((name, job, wname), [])
                if not sm: phases.append(dict(window=wname, n=0)); continue
                nd, act = st.mean(x["ndps"] for x in sm), st.mean(x["active"] for x in sm)
                ref = bwin.get(wname, {}).get("pools", {}).get("clears", {}).get("jobs", {}).get(job)
                rup = bwin.get(wname, {}).get("pools", {}).get("clears", {}).get("role_uptime", {}).get(ROLE.get(job, "Melee"))
                phases.append(dict(window=wname, n=len(sm), ndps=nd, uptime=act, uptime_diff=act - rup if rup else None,
                                   vs=(nd / ref["ndps"] - 1, ref["players"], ref.get("echo_corrected", False)) if ref else None))
            players.append(dict(group=group, name=name, job=job, role=ROLE.get(job, "Melee"), pulls=attended[name],
                                # mrate, wrate and the _w counts count each culprit's share; the plain counts every mistake as 1
                                mistakes=nmist[name], mistakes_w=wmist[name], mrate=wmist[name] / attended[name], mrate_raw=nmist[name] / attended[name],
                                mdeath=nkind[(name, "death")], mdd=nkind[(name, "DD")], mdeath_w=wkind[(name, "death")], mdd_w=wkind[(name, "DD")],
                                mhit=nkind[(name, "hit")],
                                mconf=dict(mconf[name]), mcauses=mcauses[name].most_common(3),
                                wipes=nwipe[name], wipes_w=wwipe[name], wrate=wwipe[name] / attended[name], wrate_raw=nwipe[name] / attended[name],
                                wconf=dict(wconf[name]), wcauses=wcauses[name].most_common(3), samples=len(xs),
                                best_quarter=top, avg=st.mean(xs) if xs else None, vs=vs, uptime=up,
                                uptime_diff=up - bench["pools"]["clears"]["role_uptime"][ROLE.get(job, "Melee")] if up else None,
                                mcauses_all=dict(mcauses[name]), wcauses_all=dict(wcauses[name]),
                                clean_pulls=[dict(n=next(r["n"] for r in pull_rows if str(r["id"]) == fid), rdps=round(y["rdps"]), uptime=round(y["active"], 1),
                                                  given=round(y.get("given", 0)))
                                             for fid, rows in data["tables"].items() for y in rows if y["name"] == name and y["job"] == job],
                                ceiling=ceil.get(job, {}).get(name, {}).get("ceiling"),
                                ceiling_gcd=ceil.get(job, {}).get(name, {}).get("gcd"),
                                ceiling_key=ceil.get(job, {}).get(name, {}).get("rotation_key"),
                                dead_s=dead_s[name], lost_suffered=suffered[name], lost_caused=caused[name],
                                lost_caused_by=dict(caused_by[name]), phases=phases, rotation=rotation.get((name, job)),
                                pull_detail=pull_detail(name, job)))
    hp = {c["mechanic"]: sorted(100 * (1 - v[c["mechanic"]] / boss) for v in data["hp"].values() if c["mechanic"] in v)
          for c in bench["hp_checkpoints"]["mechanics"]}
    return dict(group=group, code=data["code"], hp=hp, date=datetime.datetime.fromtimestamp(data["startTime"] / 1000), pulls=len(data["fights"]),
                kills=sum(1 for f in data["fights"] if f.get("kill")), best=min(f["bossPercentage"] for f in data["fights"]),
                longest=max((f["endTime"] - f["startTime"]) / 1000 for f in data["fights"]), clean2=sum(s >= WINDOW for s in segs),
                party=st.mean(party) if party else None, causes=all_causes, wipe_causes=wipe_causes, coverage=conf, lp=lp, players=players,
                pull_rows=pull_rows, lost_total=sum(r["lost"] for r in pull_rows), lost_dd=sum(r["lost_dd"] for r in pull_rows), lost_causes=dict(lost_causes),
                cost_each={k: dict(n=len(v), hp=round(st.mean(v), 3)) for k, v in event_cost.items() if v},
                lost_unattributed=caused.get("(no one)", 0.0), burst=checks.bursts(data, lives),
                echo=dict(pulls=len(echo), of=len(data["fights"])) if echo else None)
