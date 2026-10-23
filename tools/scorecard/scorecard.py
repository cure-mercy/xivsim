"""The analysis behind the scorecard website: fetches an FFLogs report and works out, per raid group and player,
the mistakes and wipes (with classifier.py, against the party strategy in briefs.html), damage against other
groups' clears (benchmark.json), the damage lost to deaths, and damage per phase of the fight.

build_site.py is the command that uses it. Needs .fflogs_v2 at the repository root (see fflogs.py).
"""
import collections, datetime, json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fflogs
from classifier import Pull, classify, infer_light_parties

HERE = Path(__file__).resolve().parent
P1, SAVAGE, DD = 91, 101, 1002911
WINDOW = 120                     # seconds of damage measured from the pull, on pulls clean that long
# a tincture's share of the damage done under it (Medicated: +10.57% for DPS and healers, +10.42% for tanks), taken out
# of rDPS: neither the clears' (build_benchmark.py) nor the rotation ceiling has one
POT = {"tank": 0.1042 / 1.1042, "dps": 0.1057 / 1.1057}
POT_RATE_S = 38                  # the damage rate a tincture multiplies: the player's over 0:00-0:38, as for the clears
CACHED_ONLY = False              # build_site --cached: don't fetch parts a cached report lacks
ROLES = ["Tank", "Healer", "Melee", "Ranged", "Caster"]
ROLE = {"Paladin": "Tank", "Warrior": "Tank", "DarkKnight": "Tank", "Gunbreaker": "Tank", "WhiteMage": "Healer", "Scholar": "Healer",
        "Astrologian": "Healer", "Sage": "Healer", "Monk": "Melee", "Dragoon": "Melee", "Ninja": "Melee", "Samurai": "Melee", "Reaper": "Melee",
        "Viper": "Melee", "Bard": "Ranged", "Machinist": "Ranged", "Dancer": "Ranged", "BlackMage": "Caster", "Summoner": "Caster",
        "RedMage": "Caster", "Pictomancer": "Caster"}
# grade thresholds: mistakes per pull, share of pulls whose wipe the player caused, damage vs clears, uptime points
# vs clearers of the role. With eight players and one wipe a pull, a fair share of the wipes is 12.5%.
G_MIST, G_WIPE, G_DMG, G_UP = (0.30, 0.60), (0.10, 0.20), (-0.05, -0.12), (-0.5, -1.5)
CASCADE_GAP = 15                 # deaths closer together than this (seconds) belong to the same collapse
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
# causes, grouped for the summaries: (text in the classifier's cause, label)
CAUSES = [("Trinity of Souls", "Trinity of Souls: on the cleaved side"), ("green orb", "Green orb (Superchain)"),
          ("Ray of Light", "Ray of Light column"), ("donut", "Donut (Superchain)"),
          ("White Flame line-up", "Missed White Flame bait"), ("did not bait their White Flame", "Missed White Flame bait"),
          ("White Flame", "White Flame line"), ("tether laser", "Tether laser"), ("laser group", "Superchain laser group"),
          ("share", "Superchain laser group"), ("Heavensflame", "Heavensflame spread"), ("orange cone", "Orange cone overlap"),
          ("purple jack", "Purple pair"), ("Soul AoE", "Soul AoE"), ("the + ", "+ / X placement"), ("the X ", "+ / X placement"),
          ("arms of", "+ / X placement"), ("dash line", "Palladion dash line"), ("destroyed tile", "Destroyed tile"),
          ("auto-attacks", "Tank death to auto-attacks")]
# tower failures, labelled by mechanic and by what went wrong; the first match wins
TOWERS = [(("platform tower", "same tower"), "support tower left empty (Electrify)"),
          (("DPS soaked a support tower",), "DPS in a support tower"),
          (("died before dropping",), "Soul died before dropping their tower"),
          (("wrong quadrant", "sweep", "two towers dropped", "dropped their Soul"), "Soul tower in the wrong quadrant"),
          (("wrong side",), "tower dropped on the wrong side"),
          (("own tile instead", "at the centre instead"), "bright tower placed wrong"),
          (("before the bright Soul",), "stepped into the tower too early"),
          (("did not soak", "unsoaked because", "soaker could not", "cause unclear"), "tower not soaked"),
          (("soaked", "stepped into"), "wrong player in a tower")]
# tether laser failures (Paradeigma II and III), labelled the same way
TETHERS = [(("not stretched",), "tether not stretched far enough"),
           (("clipped them",), "tether laser clipped a soaking support"),
           (("stood in", "two DPS tether"), "stood in another player's tether laser")]
GROUPED = (("tether laser", TETHERS, "Tether"), ("tower", TOWERS, "Tower"), ("Soul in", TOWERS, "Tower"))
MECHS = {"Paradeigma II", "Superchain I", "Paradeigma III"}


def cause_label(text, mech=""):
    """Summary label for a classifier cause; tether and tower failures are named with their mechanic."""
    text = text.split("after their earlier")[-1].split("; earlier")[0]
    for trigger, table, generic in GROUPED:   # tethers first: "clipped ... soak from the tower's outer side" is a tether failure
        if trigger in text:
            for keys, kind in table:
                if any(k in text for k in keys):
                    return f"{mech}: {kind}" if mech in MECHS else f"{generic}: {kind}"
    return next((lab for key, lab in CAUSES if key in text), "Other")


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
    import gamedata
    for job, v in out.items():   # each job's action icons, for the compact rotation, its job icon and role
        v["icons"] = gamedata.icons(job, {r[1] for x in v["rotations"].values() for r in x["rotation"]})
        v["job_icon"] = gamedata.job_icon(job)
        v["role"] = ROLE.get(job, "Melee")
    return out


def fetch_echo(data):
    """Ids of the pulls played with The Echo (+20% damage, HP and healing): their damage is not comparable."""
    fs = data["fights"]
    t = fflogs.tables(data["code"], [(fs[0]["startTime"], fs[-1]["endTime"])], "Buffs")[0]
    bands = [(b["startTime"], b["endTime"]) for a in t.get("auras", []) if "echo" in a["name"].lower() for b in a.get("bands", [])]
    data["echo_pulls"] = [f["id"] for f in fs if any(s < f["endTime"] and e > f["startTime"] for s, e in bands)]


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
                                ("pots", lambda: fetch_pots(data), "tinctures")):
            if key not in data:   # reports cached before this part existed
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
    kind): kind is "death" when any of the mistake's events killed someone, else "DD" (Damage Down only)."""
    out = []
    for r in res:
        if r.get("derived") or not r["culprits"]: continue
        kind = "death" if r["kind"] == "death" else "DD"
        for c in r["culprits"]:
            same = next((i for i, m in enumerate(out) if m[0] == c and abs(m[1] - r["t"]) <= 2), None)
            if same is None: out.append((c, r["t"], r["cause"], r["mechanic"], kind))
            elif kind == "death": out[same] = out[same][:4] + ("death",)
    return out


def wipe_of(res):
    """Who lost the pull. The collapse is the last run of deaths with less than CASCADE_GAP seconds between them.
    A mass death in it (four or more players to one ability within 3 s, like a tower explosion or Electrify)
    decides the wipe; otherwise its first death with a culprit does, or failing that the last attributed death
    before it. Earlier deaths the group recovered from do not count. Returns (culprits, the deciding entry)."""
    deaths = [r for r in res if r["kind"] == "death"]
    if not deaths: return [], None
    i = len(deaths) - 1
    while i > 0 and deaths[i]["t"] - deaths[i - 1]["t"] <= CASCADE_GAP: i -= 1
    collapse = deaths[i:]
    mass = next((r for r in collapse if r["culprits"] and
                 sum(1 for q in collapse if q["ability"] == r["ability"] and 0 <= q["t"] - r["t"] <= 3) >= 4), None)
    trig = mass or next((r for r in collapse if r["culprits"]), None) or next((r for r in reversed(deaths[:i]) if r["culprits"]), None)
    return (trig["culprits"], trig) if trig else ([], None)


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
    ev = {"abilities": data["abilities"], "dmg": data["dmg"], "debuffs": data["debuffs"]}
    pulls = [Pull(data["code"], f, rep, ev) for f in data["fights"]]
    lp = infer_light_parties(pulls)
    attended, nmist, mcauses = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    nkind = collections.Counter()               # (player, "death" / "DD") -> mistakes
    nwipe, wcauses = collections.Counter(), collections.defaultdict(collections.Counter)
    all_causes, wipe_causes, conf = collections.Counter(), collections.Counter(), collections.Counter()
    pull_rows, lives = [], []        # one record per pull (for build_site.py); each pull's lost time, for the costs below
    wsamples = collections.defaultdict(list)   # (player, job, window) -> clean phase samples
    pphase = collections.defaultdict(list)     # (player, job, pull) -> [(window, nDPS, seconds)] clean in that pull
    for n, (p, f) in enumerate(zip(pulls, data["fights"]), 1):
        for pid in f["friendlyPlayers"]:
            if pid in names: attended[names[pid]] += 1
        res, _ = classify(p, lp)
        dur = (f["endTime"] - f["startTime"]) / 1000
        row = dict(n=n, id=f["id"], at=data["startTime"] + f["startTime"], dur=round(dur, 1), boss=f.get("bossPercentage"), kill=bool(f.get("kill")),
                   first=round(first_mistake(data, f)[0], 1), deaths=sum(1 for r in res if r["kind"] == "death"), wipe=None, mistakes=[],
                   players=sorted(names[pid] for pid in f["friendlyPlayers"] if pid in names))
        pull_rows.append(row)
        cul, trig = wipe_of(res) if not f.get("kill") else ([], None)
        if res:
            first = [r for r in res if r["t"] <= res[0]["t"] + 1.5]
            conf.update(r["confidence"] for r in first)
        if not f.get("kill") and res:
            wipe_causes[cause_label(trig["cause"], trig["mechanic"]) if trig else "Unclear"] += 1
            for c in cul: nwipe[c] += 1; wcauses[c][cause_label(trig["cause"], trig["mechanic"])] += 1
            if trig: row["wipe"] = dict(culprits=cul, t=round(trig["t"], 1), mechanic=trig["mechanic"],
                                        label=cause_label(trig["cause"], trig["mechanic"]), cause=trig["cause"])
        # every mistake while the pull was still alive; what happens during the collapse is forced or noise
        cutoff = trig["t"] + MISTAKE_AFTER_WIPE if trig else dur
        for c, t, cause, mech, kind in mistakes_of(res):
            if t <= cutoff:
                lab = cause_label(cause, mech); nmist[c] += 1; mcauses[c][lab] += 1; all_causes[lab] += 1
                nkind[(c, kind)] += 1
                row["mistakes"].append(dict(who=c, t=round(t, 1), mechanic=mech, label=lab, cause=cause, kind=kind))
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
                lab = cause_label(r["cause"], r["mechanic"]) if r["culprits"] else "No culprit found"
                lost_causes[lab] += hp
                for c in who:
                    caused[c] += hp / len(who); caused_by[c][lab] += hp / len(who); by[c] += hp / len(who)
        row["lost"], row["lost_dd"] = round(row["lost"], 2), round(row["lost_dd"], 2)
        for (_, kind), hp in per_event.items(): event_cost[kind].append(hp)
        row["lost_by"] = [dict(who=c, hp=round(v, 2)) for c, v in by.most_common()]
    import acts, checks                         # rotation checks against the clears (imported here: it imports this module)
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
        for name, job in acts.report(data["code"], data["fights"]).get(str(f["id"]), {}).get("players", {}).values(): played[(row["n"], name)] = job

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
                            died=dict(t=round(death[0], 1), how=cause_label(death[1]["cause"], death[1]["mechanic"]) if death[1].get("culprits")
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
                                mistakes=nmist[name], mrate=nmist[name] / attended[name],
                                mdeath=nkind[(name, "death")], mdd=nkind[(name, "DD")], mcauses=mcauses[name].most_common(3),
                                wipes=nwipe[name], wrate=nwipe[name] / attended[name], wcauses=wcauses[name].most_common(3), samples=len(xs),
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
