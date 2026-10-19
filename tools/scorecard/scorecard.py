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
ROLES = ["Tank", "Healer", "Melee", "Ranged", "Caster"]
ROLE = {"Paladin": "Tank", "Warrior": "Tank", "DarkKnight": "Tank", "Gunbreaker": "Tank", "WhiteMage": "Healer", "Scholar": "Healer",
        "Astrologian": "Healer", "Sage": "Healer", "Monk": "Melee", "Dragoon": "Melee", "Ninja": "Melee", "Samurai": "Melee", "Reaper": "Melee",
        "Viper": "Melee", "Bard": "Ranged", "Machinist": "Ranged", "Dancer": "Ranged", "BlackMage": "Caster", "Summoner": "Caster",
        "RedMage": "Caster", "Pictomancer": "Caster"}
# grade thresholds: mistakes per pull, share of pulls whose wipe the player caused, damage vs fast clears, uptime points
# vs peer clearers of the role. With eight players and one wipe a pull, a fair share of the wipes is 12.5%.
G_MIST, G_WIPE, G_DMG, G_UP = (0.30, 0.60), (0.10, 0.20), (-0.05, -0.12), (-0.5, -1.5)
CASCADE_GAP = 15                 # deaths closer together than this (seconds) belong to the same collapse
MISTAKE_AFTER_WIPE = 2           # mistakes are counted up to this long after the one that decided the wipe
# the fight's phases, each from the start of one major mechanic to the next (the HP checkpoints' boundaries)
WINDOWS = [("Opener & Paradeigma I", 0.0, 55.4), ("Paradeigma II", 55.4, 112.4), ("Superchain I & Dialogos", 112.4, 193.9),
           ("Paradeigma III & Ultima Blade", 193.9, 284.0), ("Palladion & Theos's Ultima", 284.0, 349.0),
           ("Superchain IIA", 349.0, 399.1), ("Superchain IIB", 399.1, 458.0)]
# after a raise: share of damage lost for the debuff's 100 s, measured on these logs (Damage Down costs nothing measurable)
RAISE_PENALTY, RAISE_S = {"Weakness": 0.049, "Brink of Death": 0.068}, 100
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


def fetch(code, refresh, bench):
    cf = fflogs.CACHE / f"report_{code}.json"
    if cf.exists() and not refresh:
        data = json.loads(cf.read_text())
        for key, fill, what in (("hp", lambda: fetch_hp(data, bench), "boss HP at the checkpoints"), ("wtables", lambda: fetch_windows(data), "damage per phase")):
            if key not in data:   # reports cached before this part existed
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
    tabs = fflogs.tables(code, [(f["startTime"], f["startTime"] + WINDOW * 1000) for f in clean])
    data["tables"] = {str(f["id"]): [dict(name=y["name"], job=y["type"], total=y["total"], rdps=y["totalRDPS"] / WINDOW,
                                         ndps=y["totalNDPS"] / WINDOW, active=y["activeTime"] / (10 * WINDOW))
                                    for y in t["entries"] if y["type"] in ROLE] for f, t in zip(clean, tabs)}
    print(f"  {code}: fetching boss HP at the checkpoints and damage per phase", file=sys.stderr)
    fetch_hp(data, bench)
    fetch_windows(data)
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
    mistake, one per culprit per 2 s (a bait that kills four players is one mistake). Yields (culprit, t, cause, mechanic)."""
    out = []
    for r in res:
        if r.get("derived") or not r["culprits"]: continue
        for c in r["culprits"]:
            if not any(m[0] == c and abs(m[1] - r["t"]) <= 2 for m in out): out.append((c, r["t"], r["cause"], r["mechanic"]))
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
    """Each death's lost time: dead from the lethal hit until a raise (or the end of the pull), then the raise's
    Weakness / Brink of Death. Returns {player: [(start, end, share of damage lost, classifier entry)]}."""
    out = collections.defaultdict(list)
    deaths = sorted((r for r in res if r["kind"] == "death"), key=lambda r: r["t"])
    for r in deaths:
        nxt = next((q["t"] for q in deaths if q["victim"] == r["victim"] and q["t"] > r["t"]), end)
        rz = next((e for e in sorted(p.deb, key=lambda e: e["t"]) if e["who"] == r["victim"] and e["name"] in RAISE_PENALTY
                   and e["type"] == "applydebuff" and r["t"] < e["t"] < nxt), None)
        up = rz["t"] if rz else min(nxt, end)
        out[r["victim"]].append((r["t"], up, 1.0, r))
        if rz: out[r["victim"]].append((up, min(up + RAISE_S, nxt, end), RAISE_PENALTY[rz["name"]], r))
    return out


def analyse(group, data, bench):
    names = {a["id"]: a["name"] for a in data["masterData"]["actors"] if a["subType"] in ROLE}
    rep = {"masterData": data["masterData"], "deaths": data["deaths"]}
    ev = {"abilities": data["abilities"], "dmg": data["dmg"], "debuffs": data["debuffs"]}
    pulls = [Pull(data["code"], f, rep, ev) for f in data["fights"]]
    lp = infer_light_parties(pulls)
    attended, nmist, mcauses = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    nwipe, wcauses = collections.Counter(), collections.defaultdict(collections.Counter)
    all_causes, wipe_causes, conf = collections.Counter(), collections.Counter(), collections.Counter()
    pull_rows, lives = [], []        # one record per pull (for build_site.py); each pull's lost time, for the costs below
    wsamples = collections.defaultdict(list)   # (player, job, window) -> clean phase samples
    for n, (p, f) in enumerate(zip(pulls, data["fights"]), 1):
        for pid in f["friendlyPlayers"]:
            if pid in names: attended[names[pid]] += 1
        res, _ = classify(p, lp)
        dur = (f["endTime"] - f["startTime"]) / 1000
        row = dict(n=n, id=f["id"], dur=round(dur, 1), boss=f.get("bossPercentage"), kill=bool(f.get("kill")),
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
        for c, t, cause, mech in mistakes_of(res):
            if t <= cutoff:
                lab = cause_label(cause, mech); nmist[c] += 1; mcauses[c][lab] += 1; all_causes[lab] += 1
                row["mistakes"].append(dict(who=c, t=round(t, 1), mechanic=mech, label=lab, cause=cause))
        down = downtime(p, res, dur)
        lives.append((row, down, min(cutoff, dur)))
        # a phase is a clean sample for a player when they were alive and unweakened through it, before the pull was lost
        for wname, a, b in WINDOWS:
            for y in data.get("wtables", {}).get(str(f["id"]), {}).get(wname, []):
                if b <= cutoff and not any(s < b and e > a for s, e, _, _ in down.get(y["name"], [])):
                    wsamples[(y["name"], y["job"], wname)].append(dict(y, pull=n))
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
    caused_by, lost_causes = collections.defaultdict(collections.Counter), collections.Counter()
    for row, down, until in lives:
        row["lost"], by = 0.0, collections.Counter()
        for victim, spans in down.items():
            for s, e, share, r in spans:
                e = min(e, until)                    # time after the pull was lost does not matter
                if e <= s: continue
                hp = 100 * lost(victim, s, e, share) / boss
                if share == 1.0: dead_s[victim] += e - s
                suffered[victim] += hp; row["lost"] += hp
                who = r["culprits"] or ["(no one)"]
                lab = cause_label(r["cause"], r["mechanic"]) if r["culprits"] else "No culprit found"
                lost_causes[lab] += hp
                for c in who:
                    caused[c] += hp / len(who); caused_by[c][lab] += hp / len(who); by[c] += hp / len(who)
        row["lost"] = round(row["lost"], 2)
        row["lost_by"] = [dict(who=c, hp=round(v, 2)) for c, v in by.most_common()]
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
            vs = {pool: (top / bench["pools"][pool]["jobs"][job]["rdps"] - 1, bench["pools"][pool]["jobs"][job]["players"])
                  if top and job in bench["pools"][pool]["jobs"] else None for pool in ("peer", "fast")}
            up = st.mean(y["active"] for y in v) if v else None
            phases = []
            for wname, a, b in WINDOWS:   # damage per phase: rotation (nDPS) and GCD uptime against clearers on the job
                sm = wsamples.get((name, job, wname), [])
                if not sm: phases.append(dict(window=wname, n=0)); continue
                nd, act = st.mean(x["ndps"] for x in sm), st.mean(x["active"] for x in sm)
                ref = {pool: bwin.get(wname, {}).get("pools", {}).get(pool, {}).get("jobs", {}).get(job) for pool in ("peer", "fast")}
                rup = bwin.get(wname, {}).get("pools", {}).get("peer", {}).get("role_uptime", {}).get(ROLE.get(job, "Melee"))
                phases.append(dict(window=wname, n=len(sm), ndps=nd, uptime=act, uptime_diff=act - rup if rup else None,
                                   peer=(nd / ref["peer"]["ndps"] - 1, ref["peer"]["players"]) if ref["peer"] else None,
                                   fast=(nd / ref["fast"]["ndps"] - 1, ref["fast"]["players"]) if ref["fast"] else None))
            players.append(dict(group=group, name=name, job=job, role=ROLE.get(job, "Melee"), pulls=attended[name],
                                mistakes=nmist[name], mrate=nmist[name] / attended[name], mcauses=mcauses[name].most_common(3),
                                wipes=nwipe[name], wrate=nwipe[name] / attended[name], wcauses=wcauses[name].most_common(3), samples=len(xs),
                                best_quarter=top, avg=st.mean(xs) if xs else None, peer=vs["peer"], fast=vs["fast"], uptime=up,
                                uptime_diff=up - bench["pools"]["peer"]["role_uptime"][ROLE.get(job, "Melee")] if up else None,
                                mcauses_all=dict(mcauses[name]), wcauses_all=dict(wcauses[name]),
                                clean_pulls=[dict(n=next(r["n"] for r in pull_rows if str(r["id"]) == fid), rdps=round(y["rdps"]), uptime=round(y["active"], 1))
                                             for fid, rows in data["tables"].items() for y in rows if y["name"] == name and y["job"] == job],
                                dead_s=dead_s[name], lost_suffered=suffered[name], lost_caused=caused[name],
                                lost_caused_by=dict(caused_by[name]), phases=phases))
    hp = {c["mechanic"]: sorted(100 * (1 - v[c["mechanic"]] / boss) for v in data["hp"].values() if c["mechanic"] in v)
          for c in bench["hp_checkpoints"]["mechanics"]}
    return dict(group=group, code=data["code"], hp=hp, date=datetime.datetime.fromtimestamp(data["startTime"] / 1000), pulls=len(data["fights"]),
                kills=sum(1 for f in data["fights"] if f.get("kill")), best=min(f["bossPercentage"] for f in data["fights"]),
                longest=max((f["endTime"] - f["startTime"]) / 1000 for f in data["fights"]), clean2=sum(s >= WINDOW for s in segs),
                party=st.mean(party) if party else None, causes=all_causes, wipe_causes=wipe_causes, coverage=conf, lp=lp, players=players,
                pull_rows=pull_rows, lost_total=sum(r["lost"] for r in pull_rows), lost_causes=dict(lost_causes),
                lost_unattributed=caused.get("(no one)", 0.0))
