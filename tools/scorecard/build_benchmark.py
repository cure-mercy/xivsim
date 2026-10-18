"""Rebuilds benchmark.json: what other groups' players do over 0:00-2:00 of P12S P1, per job.

    python tools/scorecard/build_benchmark.py [--since 2025-01-01] [--until today] [--out benchmark.json]

1. Scans every Anabaseios report in the date range (half-month slices, split further when a slice has more
   than the API's 25 pages) for Savage Athena kills that took 5:30-7:50, the speed of a level 90 clear.
2. Keeps the kills played at level 90 with capped gear, like ours: every player level 90, no ability that
   needs level 92 or higher, and the logging player's main stat 3,400-3,560. Level 100 runs and the many
   lower-gear runs are dropped.
3. Takes rDPS, nDPS and GCD uptime over 0:00-2:00 for each player still alive at 2:00, removes the damage
   gained from tinctures (Medicated: +10.57% damage for DPS and healers, +10.42% for tanks, over its window),
   and averages per distinct player, then per job, separately for peer clears (7:10 or slower) and fast ones.

A full rebuild over two years reads several thousand report pages and can take an hour or more of API
budget; the script waits out the hourly rate limit on its own. Progress is cached in .cache/benchmark/.
"""
import argparse, calendar, collections, datetime, json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fflogs
from scorecard import ROLE, P1, SAVAGE

HERE = Path(__file__).resolve().parent
CACHE = fflogs.CACHE / "benchmark"
ZONE = 54                          # Anabaseios
MIN_S, MAX_S, PEER_S = 330, 470, 430
MAIN_STAT = (3400, 3560)
ENRAGE_S = 458                     # the slowest clears seen end at 7:38-7:39
# when each major mechanic's cast begins, seconds into the pull (the timeline is fixed)
CHECKPOINTS = [("Paradeigma II", 55.4), ("Superchain I", 112.4), ("Paradeigma III", 193.9), ("Palladion", 284.0),
               ("Superchain II (1st)", 349.0), ("Superchain II (2nd)", 399.1)]
POT = {"tank": 0.1042 / 1.1042, "dps": 0.1057 / 1.1057}
LEVEL92 = ["High Thunder", "High Thunder II", "Flare Star", "Solar Bahamut", "Sunflare", "Lux Solaris", "Necrotize", "Vice of Thorns",
           "Grand Impact", "Prefulgence", "Star Prism", "Rainbow Drip", "Ouroboros", "Leaping Opo", "Rising Raptor", "Pouncing Coeurl",
           "Fire's Reply", "Wind's Reply", "Elixir Burst", "Rise of the Dragon", "Lance Barrage", "Spiral Blow", "Starcross", "Kunai's Bane",
           "Deathfrog Medium", "Zesho Meppo", "Tenri Jindo", "Tendo Setsugekka", "Tendo Kaeshi Setsugekka", "Zanshin", "Gyofu", "Tendo Goken",
           "Perfectio", "Executioner's Gibbet", "Executioner's Gallows", "Sacrificium", "Resonant Arrow", "Radiant Encore", "Heartbreak Shot",
           "Excavator", "Full Metal Field", "Dance of the Dawn", "Last Dance", "Finishing Move", "Imperator", "Blade of Honor", "Primal Wrath",
           "Primal Ruination", "Damnation", "Disesteem", "Scarlet Delirium", "Comeuppance", "Torcleaver", "Impalement", "Reign of Beasts",
           "Noble Blood", "Lion Heart", "Fated Brand", "Glare IV", "Divine Caress", "Seraphism", "Concitation", "Accession", "Manifestation",
           "Baneful Impaction", "Oracle", "Sun Sign", "Helios Conjunction", "Philosophia", "Eukrasian Dyskrasia", "Psyche"]
# (Drakesbane, Supplication, Sepulchre and Blazing Shot were moved below level 90 in 7.0, so they prove nothing.)


def cached(name, fn):
    f = CACHE / f"{name}.json"
    if f.exists(): return json.loads(f.read_text())
    v = fn(); CACHE.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(v)); return v


def scan_slice(s, e):
    q = '''query($s:Float,$e:Float,$p:Int){reportData{reports(zoneID:%d,startTime:$s,endTime:$e,limit:50,page:$p){has_more_pages
           data{code startTime fights(encounterID:%d,killType:Kills){id startTime endTime difficulty}}}}}''' % (ZONE, P1)
    kills = []
    for page in range(1, 26):
        d = fflogs.gql(q, {"s": s, "e": e, "p": page})["reportData"]["reports"]
        kills += [dict(code=x["code"], fight=f["id"], start=f["startTime"], dur=(f["endTime"] - f["startTime"]) / 1000,
                       day=datetime.datetime.utcfromtimestamp(x["startTime"] / 1000).strftime("%Y-%m-%d"))
                  for x in d["data"] for f in (x["fights"] or []) if f.get("difficulty") == SAVAGE]
        if not d["has_more_pages"]: return kills
    mid = (s + e) // 2                         # more than 25 pages: split the slice and scan both halves
    return scan_slice(s, mid) + scan_slice(mid, e)


def scan(since, until):
    kills, d = [], since.replace(day=1)
    while d < until:
        for half in (1, 16):
            a = datetime.datetime(d.year, d.month, half)
            b = datetime.datetime(d.year, d.month, 16) if half == 1 else datetime.datetime(d.year + (d.month == 12), d.month % 12 + 1, 1)
            if b.date() <= since or a.date() > until: continue
            key = f"scan_{a:%Y%m%d}"
            done = a.date() < datetime.date.today() - datetime.timedelta(days=2)   # recent slices are rescanned
            got = cached(key, lambda: scan_slice(calendar.timegm(a.timetuple()) * 1000, calendar.timegm(b.timetuple()) * 1000)) if done else \
                scan_slice(calendar.timegm(a.timetuple()) * 1000, calendar.timegm(b.timetuple()) * 1000)
            kills += got
            print(f"  {a:%Y-%m-%d}: {len(got)} Savage kills", file=sys.stderr)
        d = datetime.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return [k for k in kills if MIN_S <= k["dur"] <= MAX_S]


def eligible(k):
    def check():
        fx = "ability.name IN (" + ",".join('"' + n + '"' for n in LEVEL92) + ")"
        r = fflogs.gql('''query($c:String!,$f:[Int]!,$fx:String){reportData{report(code:$c){
            dt:events(fightIDs:$f,dataType:Casts,hostilityType:Friendlies,filterExpression:$fx,limit:50){data}
            ci:events(fightIDs:$f,dataType:CombatantInfo,limit:100){data}}}}''', {"c": k["code"], "f": [k["fight"]], "fx": fx})["reportData"]["report"]
        ci = r["ci"]["data"]
        main = [max(e["strength"], e["dexterity"], e["intelligence"], e["mind"]) for e in ci if "strength" in e]
        return dict(level92=len(r["dt"]["data"]), levels=sorted({e.get("level") for e in ci}), main=main[0] if main else None)
    c = cached(f"check_{k['code']}_{k['fight']}", check)
    return c["level92"] == 0 and c["levels"] == [90] and c["main"] is not None and MAIN_STAT[0] <= c["main"] <= MAIN_STAT[1]


def kill_players(k):
    """Per player in one kill: pot-stripped rDPS / nDPS over 0:00-2:00 and uptime; players dead before 2:00 left out."""
    def get():
        f = fflogs.gql('query($c:String!){reportData{report(code:$c){fights(fightIDs:[%d]){startTime endTime}}}}' % k["fight"],
                       {"c": k["code"]})["reportData"]["report"]["fights"][0]
        s = f["startTime"]
        t120, t38 = fflogs.tables(k["code"], [(s, s + 120000), (s, s + 38000)])
        pots = fflogs.tables(k["code"], [(s - 30000, f["endTime"])], "Buffs", extra=",abilityID:1000049")[0]
        deaths = fflogs.tables(k["code"], [(s, s + 120000)], "Deaths")[0]
        return dict(start=s, t120=t120["entries"], t38=t38["entries"], pots=pots.get("auras", []), deaths=deaths.get("entries", []))
    d = cached(f"kill_{k['code']}_{k['fight']}", get)
    dead = {x["name"] for x in d["deaths"]}
    o38 = {y["name"]: y for y in d["t38"] if y["type"] in ROLE}
    bands = collections.defaultdict(list)
    for a in d["pots"]:
        if a.get("type") in ROLE: bands[a["name"]] += [(b["startTime"] - d["start"], b["endTime"] - d["start"]) for b in a.get("bands", [])]
    out, party = [], 0
    for y in d["t120"]:
        if y["type"] not in ROLE or y["name"] not in o38: continue
        kind = "tank" if ROLE[y["type"]] == "Tank" else "dps"
        overlap = sum(max(0, min(e, 120000) - max(b, 0)) for b, e in bands[y["name"]]) / 1000
        gain = overlap * o38[y["name"]]["total"] / 38 * POT[kind] / 120
        party += y["total"] / 120 - gain
        if y["name"] not in dead:
            out.append(dict(name=y["name"], job=y["type"], rdps=y["totalRDPS"] / 120 - gain, ndps=y["totalNDPS"] / 120 - gain, uptime=y["activeTime"] / 1200))
    return out, party


def kill_hp(k):
    """Boss HP % left when each mechanic starts, from the party's damage up to that moment over the kill's total."""
    def get():
        f = fflogs.gql('query($c:String!){reportData{report(code:$c){fights(fightIDs:[%d]){startTime endTime}}}}' % k["fight"],
                       {"c": k["code"]})["reportData"]["report"]["fights"][0]
        s, e = f["startTime"], f["endTime"]
        ts = fflogs.tables(k["code"], [(s, s + int(t * 1000)) for _, t in CHECKPOINTS] + [(s, e)])
        return [sum(y["total"] for y in t["entries"]) for t in ts]
    d = cached(f"hp_{k['code']}_{k['fight']}", get)
    return d[-1], [100 * (1 - x / d[-1]) for x in d[:-1]]


def checkpoints(kills):
    """Per mechanic, the HP % a kill at enrage (break-even) and 13 s earlier (comfortable) has left, from a line fitted
    through every benchmark kill: HP % at the mechanic against the kill's length."""
    rows = [(k["dur"], *kill_hp(k)) for k in kills]
    out = []
    for i, (name, t) in enumerate(CHECKPOINTS):
        xs = [r[0] for r in rows]; ys = [r[2][i] for r in rows]
        mx, my = st.mean(xs), st.mean(ys)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); a = my - b * mx
        r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** .5
        out.append(dict(mechanic=name, start_s=t, breakeven=round(a + b * ENRAGE_S, 1), comfortable=round(a + b * (ENRAGE_S - 13), 1),
                        kills_median=round(st.median(ys), 1), fit_r=round(r, 2)))
    return dict(boss_hp=round(st.median(r[1] for r in rows)), enrage_s=ENRAGE_S, kills=len(rows), mechanics=out)


def build(kills):
    res = {"built": datetime.date.today().isoformat(), "pools": {},
           "method": "Savage P1 (Athena) clears from FFLogs, level 90, no level-92+ abilities, logger main stat 3400-3560 (capped gear). "
                     "rDPS/nDPS over 0:00-2:00 with pots stripped (+10.57% DPS/healer, +10.42% tank for the Medicated window); deaths before 2:00 "
                     "excluded. Job values are averages of distinct players. peer = kills at 7:10 or slower, fast = faster.",
           "kills": [dict(code=k["code"], fight=k["fight"], dur=round(k["dur"], 1), day=k["day"]) for k in kills]}
    for pool in ("peer", "fast"):
        ks = [k for k in kills if (k["dur"] >= PEER_S) == (pool == "peer")]
        per, parties = collections.defaultdict(list), []
        for k in ks:
            ps, party = kill_players(k); parties.append(party)
            for p in ps: per[(p["name"], p["job"])].append(p)
        jobs = collections.defaultdict(list)
        for (n, j), v in per.items(): jobs[j].append({m: st.mean(x[m] for x in v) for m in ("rdps", "ndps", "uptime")})
        roles = collections.defaultdict(list)
        for j, v in jobs.items(): roles[ROLE[j]] += [x["uptime"] for x in v]
        res["pools"][pool] = dict(kills=len(ks), kill_median_s=round(st.median(k["dur"] for k in ks)) if ks else None,
                                  party_dps_median=round(st.median(parties)) if parties else None,
                                  role_uptime={r: round(st.mean(v), 2) for r, v in roles.items()},
                                  jobs={j: dict(rdps=round(st.mean(x["rdps"] for x in v)), ndps=round(st.mean(x["ndps"] for x in v)),
                                                uptime=round(st.mean(x["uptime"] for x in v), 2), players=len(v)) for j, v in jobs.items()})
    res["hp_checkpoints"] = checkpoints(kills)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", default="2025-01-01"); ap.add_argument("--until", default=datetime.date.today().isoformat())
    ap.add_argument("--out", default=str(HERE / "benchmark.json"))
    ap.add_argument("--checkpoints-only", action="store_true", help="only recompute the boss HP checkpoints for the kills already in --out")
    a = ap.parse_args()
    if a.checkpoints_only:
        res = json.loads(Path(a.out).read_text())
        kills = [dict(k, fight=k["fight"]) for k in res["kills"]]
        res["hp_checkpoints"] = checkpoints(kills)
        Path(a.out).write_text(json.dumps(res, indent=1))
        print(json.dumps(res["hp_checkpoints"], indent=1)); return
    since, until = datetime.date.fromisoformat(a.since), datetime.date.fromisoformat(a.until)
    cand = scan(since, until)
    print(f"{len(cand)} kills at level 90 speed; checking level and gear", file=sys.stderr)
    kills = [k for k in cand if eligible(k)]
    print(f"{len(kills)} kept; reading 0:00-2:00 tables", file=sys.stderr)
    res = build(kills)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(f"wrote {a.out}: " + ", ".join(f"{p} {v['kills']} kills / {sum(j['players'] for j in v['jobs'].values())} players" for p, v in res["pools"].items()))


if __name__ == "__main__":
    main()
