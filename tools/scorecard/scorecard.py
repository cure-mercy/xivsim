"""P12S P1 player scorecards from FFLogs reports, printed as Discord-ready messages.

    python tools/scorecard/scorecard.py <report link> [<report link> ...]

Each link is one raid group (G1, G2, ... in the order given). For every Savage P1 pull it attributes each death
and Damage Down with classifier.py against the party strategy in briefs.html, counts every player's mistakes and
works out whose mistake lost the pull, and measures 0:00-2:00 damage and GCD uptime on the pulls that stayed
clean that long. Players are compared
with other clears on the same job, and each group's boss HP at the start of every major mechanic with the HP
a clear needs there (both from benchmark.json; rebuild it with build_benchmark.py).

Options:
    --refresh   fetch the reports again instead of using .cache/ (for logs that were still being uploaded)
    --json FILE also write the per-player numbers to FILE

Messages are split to stay under Discord's 2,000 characters. Notes on data quality are printed after them.
Needs .fflogs_v2 at the repository root (see fflogs.py).
"""
import argparse, collections, datetime, json, statistics as st, sys
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
AB = {"Paladin": "PLD", "Warrior": "WAR", "DarkKnight": "DRK", "Gunbreaker": "GNB", "WhiteMage": "WHM", "Scholar": "SCH", "Astrologian": "AST",
      "Sage": "SGE", "Monk": "MNK", "Dragoon": "DRG", "Ninja": "NIN", "Samurai": "SAM", "Reaper": "RPR", "Viper": "VPR", "Bard": "BRD",
      "Machinist": "MCH", "Dancer": "DNC", "BlackMage": "BLM", "Summoner": "SMN", "RedMage": "RDM", "Pictomancer": "PCT"}
# grade thresholds: mistakes per pull, share of pulls whose wipe the player caused, damage vs fast clears, uptime points
# vs peer clearers of the role. With eight players and one wipe a pull, a fair share of the wipes is 12.5%.
G_MIST, G_WIPE, G_DMG, G_UP = (0.30, 0.60), (0.10, 0.20), (-0.05, -0.12), (-0.5, -1.5)
CASCADE_GAP = 15                 # deaths closer together than this (seconds) belong to the same collapse
MISTAKE_AFTER_WIPE = 2           # mistakes are counted up to this long after the one that decided the wipe
# causes, grouped for the summaries: (text in the classifier's cause, label, short form for the focus bullets)
CAUSES = [("Trinity of Souls", "Trinity of Souls: on the cleaved side", "Trinity side"), ("green orb", "Green orb (Superchain)", "green orb"),
          ("Ray of Light", "Ray of Light column", "Ray of Light"), ("donut", "Donut (Superchain)", "donut"),
          ("White Flame line-up", "Missed White Flame bait", "missed White Flame bait"),
          ("did not bait their White Flame", "Missed White Flame bait", "missed White Flame bait"), ("White Flame", "White Flame line", "White Flame line"),
          ("tether laser", "Tether laser", "tether laser"), ("laser group", "Superchain laser group", "laser group"),
          ("share", "Superchain laser group", "laser group"), ("Heavensflame", "Heavensflame spread", "Heavensflame"),
          ("orange cone", "Orange cone overlap", "orange cone"), ("purple jack", "Purple pair", "purple pair"), ("Soul AoE", "Soul AoE", "Soul AoE"),
          ("the + ", "+ / X placement", "+/X"), ("the X ", "+ / X placement", "+/X"), ("arms of", "+ / X placement", "+/X"),
          ("dash line", "Palladion dash line", "dash line"), ("destroyed tile", "Destroyed tile", "destroyed tile"),
          ("auto-attacks", "Tank death to auto-attacks", "tank autos")]
# tower failures, labelled by mechanic and by what went wrong; the first match wins
TOWERS = [(("platform tower", "same tower"), "support tower left empty (Electrify)", "support tower"),
          (("DPS soaked a support tower",), "DPS in a support tower", "DPS in support tower"),
          (("died before dropping",), "Soul died before dropping their tower", "dead Soul's tower"),
          (("wrong quadrant", "sweep", "two towers dropped", "dropped their Soul"), "Soul tower in the wrong quadrant", "tower quadrant"),
          (("wrong side",), "tower dropped on the wrong side", "tower side"),
          (("own tile instead", "at the centre instead"), "bright tower placed wrong", "tower placement"),
          (("before the bright Soul",), "stepped into the tower too early", "tower too early"),
          (("did not soak", "unsoaked because", "soaker could not", "cause unclear"), "tower not soaked", "tower not soaked"),
          (("soaked", "stepped into"), "wrong player in a tower", "wrong soaker")]
MECH_SHORT = {"Paradeigma II": "P2", "Superchain I": "SC1", "Paradeigma III": "P3"}


def cause_label(text, mech=""):
    """Summary label for a classifier cause; tower failures are named with their mechanic."""
    text = text.split("after their earlier")[-1].split("; earlier")[0]
    if "tower" in text or "Soul in" in text:
        for keys, kind, _ in TOWERS:
            if any(k in text for k in keys):
                return f"{mech}: {kind}" if mech in MECH_SHORT else "Tower: " + kind
    return next((lab for key, lab, _ in CAUSES if key in text), "Other")


def short_label(label):
    mech, _, kind = label.partition(": ")
    if kind and (mech in MECH_SHORT or mech == "Tower"):
        short = next((sh for _, k, sh in TOWERS if k == kind), kind)
        return f"{MECH_SHORT.get(mech, '')} {short}".strip()
    return next((sh for _, lab, sh in CAUSES if lab == label), label)


# ---------- fetching ----------
def fetch_hp(data, bench):
    """Party damage up to each checkpoint's start, for every pull that lasted that long."""
    cps = bench["hp_checkpoints"]["mechanics"]
    jobs = [(f, i) for f in data["fights"] for i, c in enumerate(cps) if (f["endTime"] - f["startTime"]) / 1000 >= c["start_s"]]
    tabs = fflogs.tables(data["code"], [(f["startTime"], f["startTime"] + int(cps[i]["start_s"] * 1000)) for f, i in jobs])
    data["hp"] = collections.defaultdict(dict)
    for (f, i), t in zip(jobs, tabs): data["hp"][str(f["id"])][cps[i]["mechanic"]] = sum(y["total"] for y in t["entries"])


def fetch(code, refresh, bench):
    cf = fflogs.CACHE / f"report_{code}.json"
    if cf.exists() and not refresh:
        data = json.loads(cf.read_text())
        if "hp" not in data:
            print(f"  {code}: fetching boss HP at the checkpoints", file=sys.stderr)
            fetch_hp(data, bench); cf.write_text(json.dumps(data))
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
    print(f"  {code}: fetching boss HP at the checkpoints", file=sys.stderr)
    fetch_hp(data, bench)
    fflogs.CACHE.mkdir(exist_ok=True); cf.write_text(json.dumps(data))
    return data


def first_mistake(data, f):
    """Seconds into the pull of the first player death or Damage Down (the death event, as in the scorecards)."""
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


def analyse(group, data, bench):
    names = {a["id"]: a["name"] for a in data["masterData"]["actors"] if a["subType"] in ROLE}
    rep = {"masterData": data["masterData"], "deaths": data["deaths"]}
    ev = {"abilities": data["abilities"], "dmg": data["dmg"], "debuffs": data["debuffs"]}
    pulls = [Pull(data["code"], f, rep, ev) for f in data["fights"]]
    lp = infer_light_parties(pulls)
    attended, nmist, mcauses = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    nwipe, wcauses = collections.Counter(), collections.defaultdict(collections.Counter)
    all_causes, wipe_causes, conf = collections.Counter(), collections.Counter(), collections.Counter()
    pull_rows = []                   # one record per pull, for build_site.py
    for n, (p, f) in enumerate(zip(pulls, data["fights"]), 1):
        for pid in f["friendlyPlayers"]:
            if pid in names: attended[names[pid]] += 1
        res, _ = classify(p, lp)
        row = dict(n=n, id=f["id"], dur=round((f["endTime"] - f["startTime"]) / 1000, 1), boss=f.get("bossPercentage"), kill=bool(f.get("kill")),
                   first=round(first_mistake(data, f)[0], 1), deaths=sum(1 for r in res if r["kind"] == "death"), wipe=None, mistakes=[],
                   players=sorted(names[pid] for pid in f["friendlyPlayers"] if pid in names))
        pull_rows.append(row)
        if not res: continue
        first = [r for r in res if r["t"] <= res[0]["t"] + 1.5]
        conf.update(r["confidence"] for r in first)
        cul, trig = wipe_of(res) if not f.get("kill") else ([], None)
        if not f.get("kill"):
            wipe_causes[cause_label(trig["cause"], trig["mechanic"]) if trig else "Unclear"] += 1
            for c in cul: nwipe[c] += 1; wcauses[c][cause_label(trig["cause"], trig["mechanic"])] += 1
            if trig: row["wipe"] = dict(culprits=cul, t=round(trig["t"], 1), mechanic=trig["mechanic"],
                                        label=cause_label(trig["cause"], trig["mechanic"]), cause=trig["cause"])
        # every mistake while the pull was still alive; what happens during the collapse is forced or noise
        cutoff = trig["t"] + MISTAKE_AFTER_WIPE if trig else float("inf")
        for c, t, cause, mech in mistakes_of(res):
            if t <= cutoff:
                lab = cause_label(cause, mech); nmist[c] += 1; mcauses[c][lab] += 1; all_causes[lab] += 1
                row["mistakes"].append(dict(who=c, t=round(t, 1), mechanic=mech, label=lab, cause=cause))
    segs = [first_mistake(data, f)[0] for f in data["fights"]]
    samples = collections.defaultdict(list)
    for rows in data["tables"].values():
        for y in rows: samples[(y["name"], y["job"])].append(y)
    party = [sum(y["total"] for y in rows) / WINDOW for rows in data["tables"].values() if len(rows) == 8]
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
            players.append(dict(group=group, name=name, job=job, role=ROLE.get(job, "Melee"), pulls=attended[name],
                                mistakes=nmist[name], mrate=nmist[name] / attended[name], mcauses=mcauses[name].most_common(3),
                                wipes=nwipe[name], wrate=nwipe[name] / attended[name], wcauses=wcauses[name].most_common(3), samples=len(xs),
                                best_quarter=top, avg=st.mean(xs) if xs else None, peer=vs["peer"], fast=vs["fast"], uptime=up,
                                uptime_diff=up - bench["pools"]["peer"]["role_uptime"][ROLE.get(job, "Melee")] if up else None,
                                mcauses_all=dict(mcauses[name]), wcauses_all=dict(wcauses[name]),
                                clean_pulls=[dict(n=next(r["n"] for r in pull_rows if str(r["id"]) == fid), rdps=round(y["rdps"]), uptime=round(y["active"], 1))
                                             for fid, rows in data["tables"].items() for y in rows if y["name"] == name and y["job"] == job]))
    boss = bench["hp_checkpoints"]["boss_hp"]
    hp = {c["mechanic"]: sorted(100 * (1 - v[c["mechanic"]] / boss) for v in data["hp"].values() if c["mechanic"] in v)
          for c in bench["hp_checkpoints"]["mechanics"]}
    return dict(group=group, code=data["code"], hp=hp, date=datetime.datetime.fromtimestamp(data["startTime"] / 1000), pulls=len(data["fights"]),
                kills=sum(1 for f in data["fights"] if f.get("kill")), best=min(f["bossPercentage"] for f in data["fights"]),
                longest=max((f["endTime"] - f["startTime"]) / 1000 for f in data["fights"]), clean2=sum(s >= WINDOW for s in segs),
                party=st.mean(party) if party else None, causes=all_causes, wipe_causes=wipe_causes, coverage=conf, lp=lp, players=players,
                pull_rows=pull_rows)


# ---------- output ----------
def grade(v, cuts, higher_better=True):
    if v is None: return " "
    good, ok = cuts
    return "✓" if v >= good else ("~" if v >= ok else "!")


def grades(p):
    """(mistakes, wipes, damage, uptime)"""
    return (grade(-p["mrate"], (-G_MIST[0], -G_MIST[1])), grade(-p["wrate"], (-G_WIPE[0], -G_WIPE[1])),
            grade(p["fast"][0] if p["fast"] else None, G_DMG), grade(p["uptime_diff"], G_UP))


def pct(t):
    if not t: return "   – "
    return f"{100 * t[0]:+4.0f}%".replace("-", "−") + ("*" if t[1] < 3 else " ")


def mmss(s): return f"{int(s // 60)}:{int(s % 60):02d}"


def pack(title, sections, limit=1940):
    """Pack sections (lists of lines that belong together) into ```-fenced messages under Discord's limit."""
    msgs, cur = [], []
    size = lambda lines: len(title) + 12 + sum(len(l) + 1 for l in lines)
    for sec in sections:
        if cur and size(cur + sec) > limit: msgs.append(cur); cur = []
        cur += sec
    if cur: msgs.append(cur)
    n = len(msgs)
    return ["```\n" + (f"{title} ({i}/{n})" if n > 1 else title) + "\n" + "\n".join(m) + "\n```" for i, m in enumerate(msgs, 1)]


def checkpoint_sections(groups, bench):
    """Where each group was when every major mechanic began, against the HP a clear needs there."""
    hc = bench["hp_checkpoints"]
    lines = [f"Be at or below these HP % when the mechanic starts (enrage ~{mmss(hc['enrage_s'])}).",
             f"Clear = on pace to kill at enrage, Comfy = ~13 s to spare ({hc['kills']} clears fitted).",
             "Group cells: best / median of the pulls that got there (number of pulls).",
             "✓ best at Comfy or better   ~ at Clear or better   ! behind", ""]
    def cell(g, c):
        v = g["hp"].get(c["mechanic"], [])
        if not v: return "not reached"
        gr = "✓" if v[0] <= c["comfortable"] else ("~" if v[0] <= c["breakeven"] else "!")
        return f"{v[0]:.1f} / {st.median(v):.1f} ({len(v)}) {gr}"
    if len(groups) == 1:
        rows = [f"{'Mechanic':<19} Start | Clear  Comfy | Ours"]
        rows += [f"{c['mechanic']:<19} {mmss(c['start_s']):>5} | {c['breakeven']:4.1f}%  {c['comfortable']:4.1f}% | {cell(groups[0], c)}"
                 for c in hc["mechanics"]]
        return [lines, rows]
    # several groups: stacked, two groups per line, so it fits a Discord message without wrapping
    secs = [lines]
    for c in hc["mechanics"]:
        sec = [f"{c['mechanic']} ({mmss(c['start_s'])})   Clear {c['breakeven']:.1f}%  Comfy {c['comfortable']:.1f}%"]
        cells = [f"{g['group']} {cell(g, c):<21}" for g in groups]
        sec += ["  " + "  ".join(cells[i:i + 2]).rstrip() for i in range(0, len(cells), 2)]
        secs.append(sec)
    return secs


def render(groups, bench):
    multi = len(groups) > 1
    allp = [p for g in groups for p in g["players"]]
    date = min(g["date"] for g in groups).strftime("%a %d %b")
    head = []
    for g in groups:
        head.append((f"{g['group']}: " if multi else "") + f"{g['pulls']} pulls | {'cleared! ' if g['kills'] else ''}best {g['best']:.1f}% HP | longest "
                    f"{mmss(g['longest'])} | clean through 2:00: {g['clean2']} of {g['pulls']}")
        if g["party"]: head.append((f"{g['group']}: " if multi else "") + f"Party DPS 0:00–2:00: {g['party'] / 1e3:.1f}k "
                                   f"(peer clears ~{bench['pools']['peer']['party_dps_median'] / 1e3:.0f}k, fast clears ~{bench['pools']['fast']['party_dps_median'] / 1e3:.0f}k)")
    legend = ["", "Mistakes = your mistakes per pull, judged against our strategy (every one,",
              "           not just the first). Being killed by someone else's error doesn't count.",
              "           Counted until the pull is lost; the collapse after that is not.",
              "Wipes   = share of your pulls where your mistake is what lost the pull",
              "Peer/Fast = rDPS 0:00–2:00 from your best quarter of clean pulls vs the",
              "           average clearer on your job (peer = 7:10–7:40 clears, fast = under 7:10)",
              "Uptime  = active GCD time 0:00–2:00 vs clearers of your role",
              "Grades:  ✓ good   ~ ok   ! focus        * = only 1–2 clearers to compare with",
              f"Mistakes ✓ ≤{G_MIST[0]:.2f} ~ ≤{G_MIST[1]:.2f} a pull | Wipes ✓ ≤{100 * G_WIPE[0]:.0f}% ~ ≤{100 * G_WIPE[1]:.0f}%",
              f"Dmg vs fast ✓ within {-100 * G_DMG[0]:.0f}% ~ within {-100 * G_DMG[1]:.0f}% | Uptime ✓ within {-G_UP[0]} pt ~ within {-G_UP[1]} pt", ""]
    colhead = f"Player              Job{' Grp' if multi else ''} | Mistakes | Wipes  | vs Peer vs Fast   | Uptime"
    sections = [head + legend + [colhead]]
    for role in ROLES:
        rr = sorted((p for p in allp if p["role"] == role), key=lambda p: (p["wrate"], p["mrate"], p["name"]))
        if not rr: continue
        lines = [role]
        for p in rr:
            gm, gw, gd, gu = grades(p)
            dmg = (f"{pct(p['peer'])} {pct(p['fast'])} {gd}" if (p["peer"] or p["fast"]) else
                   (f"  no {AB.get(p['job'], p['job'])} clears    " if p["samples"] else "  no clean 2:00 pull"))
            up = f"{p['uptime']:4.1f}% {gu}" if p["uptime"] is not None else "   –   "
            lines.append(f" {p['name'][:18]:<19}{AB.get(p['job'], p['job'][:3])}{' ' + p['group'] if multi else ''} | {p['mrate']:5.2f} {gm}  |"
                         f"{100 * p['wrate']:4.0f}% {gw} | {dmg} | {up}")
        sections.append(lines)
    out = pack(f"**P12S P1 — Player scorecard, {date}**", sections)
    out += pack(f"**P12S P1 — Boss HP checkpoints, {date}**", checkpoint_sections(groups, bench))
    # takeaways
    t = []
    allgood = sorted({p["name"] for p in allp if grades(p) == ("✓", "✓", "✓", "✓")})
    if allgood: t += [f"✓ across the board: {', '.join(allgood)}", ""]
    causes = collections.Counter()
    for g in groups: causes.update(g["causes"])
    nmist = sum(causes.values())
    t.append(f"All mistakes ({nmist}, until each pull was lost)")
    t += [f" {n:>3} {lab}" for lab, n in causes.most_common()]
    wc = collections.Counter()
    for g in groups: wc.update(g["wipe_causes"])
    if wc:
        t += ["", f"What wiped us ({sum(wc.values())} wipes)"] + [f" {n:>3} {lab}" for lab, n in wc.most_common()]
    focus = collections.OrderedDict()   # one bullet per player: wipes, mistakes, then uptime and damage
    for p in sorted(allp, key=lambda p: (-p["wrate"], -p["mrate"])):
        gm, gw, gd, gu = grades(p)
        parts = focus.setdefault(p["name"], [])
        if gw == "!" and not any(x.startswith("wipes") for x in parts):
            parts.append(f"wipes {p['wipes']} of {p['pulls']} (" + ", ".join(f"{short_label(lab)} ×{n}" for lab, n in p["wcauses"]) + ")")
        if gm == "!" and not any(x.startswith("mistakes") for x in parts):
            parts.append(f"mistakes {p['mrate']:.2f} a pull (" + ", ".join(f"{short_label(lab)} ×{n}" for lab, n in p["mcauses"]) + ")")
        if gu == "!": parts.append(f"uptime {p['uptime']:.1f}% (clearers {bench['pools']['peer']['role_uptime'][p['role']]:.1f}%)")
        if gd == "!": parts.append(f"{AB.get(p['job'])} damage {100 * p['fast'][0]:.0f}% vs fast clears".replace("-", "−")
                                   + (" (1–2 clearers, rough)" if p["fast"][1] < 3 else ""))
    bullets = [f"• {n}: " + "; ".join(parts) for n, parts in focus.items() if parts]
    if bullets: t += ["", "Focus points"] + bullets
    solid = [p for p in allp if p["peer"] and p["peer"][1] >= 3]
    if solid:
        above = sorted((p for p in solid if p["peer"][0] >= 0), key=lambda q: -q["peer"][0])
        best = ", ".join("%s %+.0f%%" % (q["name"].split()[0], 100 * q["peer"][0]) for q in above[:3])
        t += ["", "Damage", f"• {len(above)} of {len(solid)} players with a solid comparison are at or above peer clears"
              + (f" ({best})" if above else "")]
    out += pack(f"**P12S P1 — Player scorecard, {date}: takeaways**", [[l] for l in t])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("links", nargs="+", help="FFLogs report links or codes, one per raid group")
    ap.add_argument("--refresh", action="store_true", help="refetch reports instead of using the cache")
    ap.add_argument("--json", help="also write per-player numbers to this file")
    a = ap.parse_args()
    bench = json.loads((HERE / "benchmark.json").read_text())
    groups = []
    for i, link in enumerate(a.links, 1):
        code = fflogs.report_code(link)
        print(f"G{i}: {code}", file=sys.stderr)
        groups.append(analyse(f"G{i}", fetch(code, a.refresh, bench), bench))
    msgs = render(groups, bench)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n\n".join(msgs))
    print("\n--- notes (not for Discord) ---")
    for g in groups:
        c = g["coverage"]; tot = sum(c.values())
        print(f"{g['group']} {g['code']}: first mistakes attributed {100 * (c['high'] + c['medium']) / tot:.0f}% ({dict(c)}) | "
              f"light parties: LP1 {', '.join(sorted(g['lp'][0]))} / LP2 {', '.join(sorted(g['lp'][1]))}")
        thin = [f"{p['name']} ({p['samples']})" for p in g["players"] if p["samples"] < 4]
        if thin: print(f"   few clean 2:00 pulls for damage: {', '.join(thin)}")
    print(f"benchmark: {bench['pools']['peer']['kills'] + bench['pools']['fast']['kills']} clears, built {bench['built']}")
    if a.json:
        Path(a.json).write_text(json.dumps([dict(p) for g in groups for p in g["players"]], indent=1, default=str))


if __name__ == "__main__":
    main()
