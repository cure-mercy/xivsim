"""Detailed per-player logs for calibrating a job model: casts (with begin-casts and MP), hits (with the buffs on them)
and the player's own statuses, for every clear in the scorecard benchmark that has the job. Cached in .cache/."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scorecard"))
import fflogs                                  # noqa: E402

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


def clears(job):
    """Every player log of the job across the benchmark's clears."""
    kills = json.loads(BENCH.read_text())["kills"]
    out = []
    for k in kills:
        acts = json.loads((fflogs.CACHE / "benchmark" / f"acts_{k['code']}_{k['fight']}.json").read_text())
        if any(v[1] == job for v in acts["players"].values()): out += [dict(p, dur=k["dur"]) for p in player_log(k["code"], k["fight"], job) if p["casts"]]
    return out


SITE = HERE.parent / "scorecard" / "site" / "data.json"


def ours(job):
    """Detailed logs of our players on the job, for their pulls that were clean through 2:00, with the scorecard's
    0:00-2:00 rDPS of each pull attached."""
    reports = json.loads(SITE.read_text())["reports"]
    out = []
    for r in reports.values():
        fights = json.loads((fflogs.CACHE / f"report_{r['code']}.json").read_text())["fights"]
        for p in r["players"]:
            if p["job"] != job: continue
            for c in p.get("clean_pulls") or []:
                fid = fights[c["n"] - 1]["id"]
                got = [x for x in player_log(r["code"], fid, job) if x["name"] == p["name"] and x["casts"]]
                out += [dict(x, rdps=c["rdps"], group=r["group"], day=r["day"], n=c["n"]) for x in got]
    return out


if __name__ == "__main__":
    logs = clears(sys.argv[1] if len(sys.argv) > 1 else "BlackMage")
    print(f"{len(logs)} player logs:", ", ".join(f"{p['name']} ({len(p['casts'])} casts)" for p in logs))
