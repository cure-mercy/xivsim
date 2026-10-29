"""Detailed per-player logs for calibrating a job model: casts (with begin-casts and MP), hits (with the buffs on them)
and the player's own statuses, for every clear in the scorecard benchmark that has the job. Cached in .cache/."""
import collections, json, math, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scorecard"))
import acts, fflogs                            # noqa: E402

CACHE = HERE / ".cache"
BENCH = HERE.parent / "scorecard" / "benchmark.json"

Q = '''query($c:String!,$f:[Int]!,$s:Int!,$a:Float!,$b:Float!){reportData{report(code:$c){
  c:events(fightIDs:$f,startTime:$a,endTime:$b,dataType:Casts,sourceID:$s,includeResources:true,limit:10000){data}
  d:events(fightIDs:$f,startTime:$a,endTime:$b,dataType:DamageDone,sourceID:$s,limit:10000){data}
  u:events(fightIDs:$f,startTime:$a,endTime:$b,dataType:Buffs,targetID:$s,limit:10000){data}}}}'''
META = '''query($c:String!,$f:[Int]!){reportData{report(code:$c){fights(fightIDs:$f){startTime endTime}
  masterData{actors(type:"Player"){id name subType} abilities{gameID name}}}}}'''


def player_log(code, fight, job):
    """[{name, start, end, casts, hits, buffs, names}] for each player of the job in this fight, times in seconds from the pull."""
    cf = CACHE / f"{job}_{code}_{fight}.json"
    if cf.exists(): return json.loads(cf.read_text())
    m = fflogs.gql(META, {"c": code, "f": [fight]})["reportData"]["report"]
    f = m["fights"][0]
    s0 = f["startTime"]
    names = {a["gameID"]: a["name"] for a in m["masterData"]["abilities"]}
    out = []
    for a in m["masterData"]["actors"]:
        if a["subType"] != job: continue
        r = fflogs.gql(Q, {"c": code, "f": [fight], "s": a["id"], "a": s0 - 30000, "b": f["endTime"]})["reportData"]["report"]
        rel = lambda x: dict(x, t=round((x["timestamp"] - s0) / 1000, 3))
        casts = [rel(x) for x in r["c"]["data"] if x.get("sourceID") == a["id"]]
        hits = [rel(x) for x in r["d"]["data"] if x.get("sourceID") == a["id"]]
        buffs = [rel(x) for x in r["u"]["data"] if x.get("targetID") == a["id"]]
        used = {x["abilityGameID"] for x in casts + hits + buffs}
        out.append(dict(name=a["name"], id=a["id"], code=code, fight=fight, end=round((f["endTime"] - s0) / 1000, 3),
                        casts=casts, hits=hits, buffs=buffs, names={str(g): names.get(g, str(g)) for g in sorted(used)}))
    CACHE.mkdir(exist_ok=True)
    cf.write_text(json.dumps(out))
    return out


ECHO = 1.20   # The Echo: +20% damage dealt (build_benchmark.py's ECHO)


def clears(job):
    """Every player log of the job across the benchmark's clears. A kill with The Echo has its hits' damage divided by
    ECHO (and `echo` set), so damage per potency compares across clears: one Ninja's Echo kill had put the clears'
    conversions 40% apart instead of 15%."""
    kills = json.loads(BENCH.read_text())["kills"]
    out = []
    for k in kills:
        acts = json.loads((fflogs.CACHE / "benchmark" / f"acts_{k['code']}_{k['fight']}.json").read_text())
        if not any(v[1] == job for v in acts["players"].values()): continue
        for p in player_log(k["code"], k["fight"], job):
            if not p["casts"]: continue
            if k.get("echo"):
                p = dict(p, echo=True, hits=[dict(h, amount=h["amount"] / ECHO) if "amount" in h else h for h in p["hits"]])
            out.append(dict(p, dur=k["dur"]))
    return out


SITE = HERE.parent / "scorecard" / "site" / "data.json"


def ours(job, names=None):
    """Detailed logs of our players on the job (only these names, if given), for their pulls that were clean through
    2:00, with the scorecard's 0:00-2:00 rDPS of each pull attached."""
    reports = json.loads(SITE.read_text())["reports"]
    out = []
    for r in reports.values():
        fights = json.loads((fflogs.CACHE / f"report_{r['code']}.json").read_text())["fights"]
        for p in r["players"]:
            if p["job"] != job or names is not None and p["name"] not in names: continue
            for c in p.get("clean_pulls") or []:
                fid = fights[c["n"] - 1]["id"]
                got = [x for x in player_log(r["code"], fid, job) if x["name"] == p["name"] and x["casts"]]
                out += [dict(x, rdps=c["rdps"], group=r["group"], day=r["day"], n=c["n"]) for x in got]
    return out


ACTS = HERE.parent / "scorecard" / ".cache"
CHANGE = {1: "applybuff", 0: "removebuff"}


def from_acts(a, pid, code, fight, own=lambda p, h: 1.0):
    """A player's log as player_log gives it, built from the scorecard's acts cache of the pull, for when FFLogs is down.
    The cache has no crit / direct-hit flags (dps.flag_hits sets them), FFLogs multipliers or others' buffs on a hit:
    hits under others' raid buffs (acts.buff_uses) and in tinctures are left out, and the rest carry the player's own
    statuses as `buffs` and their own damage-ups (the job's own_factor, from those statuses) as `multiplier`."""
    N = collections.defaultdict(lambda: "?", {str(k): v for k, v in a["names"].items()})
    spans, on = collections.defaultdict(list), {}
    for t, p, s, ch in a["auras"]:
        if str(p) != pid: continue
        if ch in (1, 2, 3): on.setdefault(s, t)
        elif ch == 0 and s in on: spans[s].append((on.pop(s), t))
    for s, t in on.items(): spans[s].append((t, math.inf))
    pot = [b for s, w in spans.items() if N[str(s)] == "Medicated" for b, _ in w]
    away = [(t, t + acts.BUFF_S) for t, _, _, src in acts.buff_uses(a) if str(src) != pid] + [(t, t + 30) for t in pot]
    casts = sorted([dict(t=t, type="cast", abilityGameID=ab) for t, p, ab in a["casts"] if str(p) == pid] +
                   [dict(t=t, type="begincast", abilityGameID=ab) for t, p, ab in a["begins"] if str(p) == pid],
                   key=lambda x: (x["t"], x["type"] == "cast"))
    out = dict(name=a["players"][pid][0], id=int(pid), code=code, fight=fight, end=a["end"], casts=casts, hits=[],
               buffs=[dict(t=t, type=CHANGE[ch], abilityGameID=s) for t, p, s, ch in a["auras"] if str(p) == pid and ch in CHANGE],
               names=N)
    for t, p, ab, amt, tick, bonus in a["dmg"]:
        if str(p) != pid or any(lo <= t < hi for lo, hi in away): continue
        h = dict(t=t, type="damage", abilityGameID=ab, amount=amt, tick=bool(tick), bonusPercent=bonus,
                 buffs="".join(f"{s}." for s, w in spans.items() if any(lo <= t < hi for lo, hi in w)))
        h["multiplier"] = own(out, h)
        out["hits"].append(h)
    return out


def ours_offline(job, own=lambda p, h: 1.0):
    """ours() from the scorecard's acts caches (from_acts) instead of FFLogs: the same clean pulls, without crit flags,
    hits under others' raid buffs or tincture hits. Built in memory only: player_log would take a cached copy for a full
    log."""
    reports = json.loads(SITE.read_text())["reports"]
    out = []
    for r in reports.values():
        fights = json.loads((fflogs.CACHE / f"report_{r['code']}.json").read_text())["fights"]
        pulls = json.loads((ACTS / f"acts_{r['code']}.json").read_text(encoding="utf-8"))
        for p in r["players"]:
            if p["job"] != job: continue
            for c in p.get("clean_pulls") or []:
                fid = fights[c["n"] - 1]["id"]
                a = pulls.get(str(fid))
                pid = next((k for k, (nm, j) in (a or {"players": {}})["players"].items() if nm == p["name"] and j == job), None)
                if pid is None: continue
                x = from_acts(a, pid, r["code"], fid, own)
                if x["casts"]: out.append(dict(x, rdps=c["rdps"], group=r["group"], day=r["day"], n=c["n"]))
    return out


CUT = {"Damage Down", "Weakness", "Brink of Death"}   # a player's own state that lowers their hits: their pull ends there


def ours_more(job, own=lambda p, h: 1.0, until=120, names=None):
    """Our players' other pulls on the job, the ones not clean through 2:00, from the acts caches (from_acts, so without
    crit flags: dps.flag_hits sets them), each cut at the player's own first death or Damage Down and at `until`: more
    hits for measuring their crit / direct-hit gain than the clean pulls alone. Pulls with The Echo are left out."""
    reports = json.loads(SITE.read_text())["reports"]
    out = []
    for r in reports.values():
        rep = json.loads((fflogs.CACHE / f"report_{r['code']}.json").read_text())
        fights, echo = rep["fights"], {str(i) for i in rep.get("echo_pulls", [])}
        pulls = json.loads((ACTS / f"acts_{r['code']}.json").read_text(encoding="utf-8"))
        for p in r["players"]:
            if p["job"] != job or names is not None and p["name"] not in names: continue
            clean = {c["n"] for c in p.get("clean_pulls") or []}
            for d in p.get("pull_detail") or []:
                fid = str(fights[d["n"] - 1]["id"])
                if d["n"] in clean or fid in echo or fid not in pulls: continue
                a = pulls[fid]
                pid = next((k for k, (nm, j) in a["players"].items() if nm == p["name"] and j == job), None)
                if pid is None: continue
                N = a["names"]
                hurt = [t for t, q, s, ch in a["auras"] if str(q) == pid and ch == 1 and N.get(str(s)) in CUT]
                cut = min([until, d["dur"]] + ([d["died"]["t"]] if d.get("died") else []) + hurt)
                if cut < 20: continue
                x = from_acts(a, pid, r["code"], int(fid), own)
                x["hits"] = [h for h in x["hits"] if h["t"] < cut]
                if x["casts"] and x["hits"]: out.append(dict(x, group=r["group"], day=r["day"], n=d["n"], cut=cut))
    return out


if __name__ == "__main__":
    logs = clears(sys.argv[1] if len(sys.argv) > 1 else "BlackMage")
    print(f"{len(logs)} player logs:", ", ".join(f"{p['name']} ({len(p['casts'])} casts)" for p in logs))
