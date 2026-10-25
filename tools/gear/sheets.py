"""The scorecard site's gear sets: each job's best-in-slot set(s) from bis.py --combined, item by item, for display.

    python tools/gear/sheets.py [--job sam]          # prints the sets as the site gets them (build_site.py calls `sheets`)

Nothing is searched here: the sets in .cache/bis_<job>.json are rebuilt from gear_db.json with the model's own rules
(gear.Item.variants for each item's fill), so every item carries its stats after sync and melds, its materia slot by
slot (with what each meld adds under the item's cap), and the set its final stats, rates and GCD.

Sets: the best searched tier's, and the other searched tiers within TIE of it (the rotation search moves ~0.4% between
runs, so those are ties: tools/gear/README.md). A bis_<job>.json written before bis.py saved every searched tier's set
holds the best one only.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gear                                            # noqa: E402
from gear import JOBS, KEYS, Stats, vector             # noqa: E402

CACHE = HERE / ".cache"
TIE = 0.004                                            # searched tiers this close to the best are shown as sets too
HASTE = {"SAM": "Fuka", "VPR": "Swiftscaled", "BLM": "Ley Lines"}    # the buff a tier's second GCD is under (bis.BUFF_HASTE)
ROWS = {r["id"]: r for r in gear.DB["items"]}
MATERIA = {(m["stat"], m["value"]): m for m in gear.DB["materia"] if m["grade"] in (9, 10)}
FOOD = {f["name"]: f for f in gear.DB["food"]}


def _keyed(job, st):
    """An item's stats as {KEYS name: value} for the job (main stat, weapon damage, crit, dh, det, speed)."""
    return {k: v for k, v in zip(KEYS, vector(job, st)) if v}


def item(job, g):
    """One item of a set as the site shows it: identity, sync, its stats before and after its melds or relic substats,
    and its materia slot by slot ({stat, grade, value, added}: added < value where the item's cap cuts the meld)."""
    it = gear.Item(ROWS[g["id"]])
    out = dict(slot=g["slot"], id=it.id, name=it.name, ilvl=it.ilvl, synced=it.synced, source=it.row["source"],
               rarity=it.row["rarity"], relic=None, melds=[])
    if it.relic:
        final = dict(it.variants(job))[g["fill"]]
        big, small = g["fill"].removeprefix("relic ").split(" +")
        sp = lambda s: "speed" if s == JOBS[job][1] else s
        out["relic"] = dict(large=[sp(s) for s in big.split("/")], small=sp(small))
        out["base"] = _keyed(job, {k: v for k, v in final.items() if k not in gear.SUBSTATS})
        out["final"] = _keyed(job, final)
        return out
    useful = ("crit", "dh", "det", JOBS[job][1])
    st = {k: v for k, v in it.stats.items() if k in useful or k in (JOBS[job][0], "wdMag", "wdPhys")}
    out["base"] = _keyed(job, st)
    # melded as Item.variants does, which keeps an arbitrary one of the equivalent orders (it changes between runs): the
    # same grade's melds in any order give the same stats, so they are shown in a fixed one (crit, dh, det, speed)
    order = g["fill"].split("+") if g["fill"] else []
    rank = {s: k for k, s in enumerate(useful)}
    for val in {v for v, _ in it.melds}:
        idx = [k for k, (v, _) in enumerate(it.melds[:len(order)]) if v == val]
        for k, s in zip(idx, sorted((order[k] for k in idx), key=rank.get)): order[k] = s
    for (val, _), s in zip(it.melds, order):
        before = st.get(s, 0)
        st[s] = min(before + val, max(it.caps[s] or 0, before))
        m = MATERIA[(s, val)]
        out["melds"].append(dict(stat="speed" if s == JOBS[job][1] else s, grade=m["grade"], value=val,
                                 added=st[s] - before, id=m["id"], name=m["name"]))
    out["melds"] += [None] * (len(it.melds) - len(order))     # slots the set leaves empty
    out["final"] = _keyed(job, st)
    return out


def one(job, tier, d, best, food, food_bonus, gear_, totals):
    """A set: its items, food (with what it adds up to its max), final stats and materia count."""
    fb = {k: tuple(v) for k, v in food_bonus.items()}
    s, bare = Stats(job, totals, fb), Stats(job, totals)
    speed = JOBS[job][1]
    gains = {("speed" if k == speed else k): dict(got=s.raw["speed" if k == speed else k] - bare.raw["speed" if k == speed else k],
                                                  pct=p, max=m) for k, (p, m) in fb.items()}
    items = [item(job, g) for g in gear_]
    count = {}
    for i in items:
        for m in i["melds"]:
            if m: count.setdefault((m["stat"], m["grade"], m["id"], m["name"]), [0])[0] += 1
    f = FOOD.get(food, {})
    return dict(tier=tier, dps=d, rel=d / best - 1, items=items,
                food=dict(name=food, id=f.get("id"), ilvl=f.get("ilvl"), gains=gains),
                stats=dict(main=s.main, wd=s.wd, crit=s.crit, crit_rate=s.crit_rate, crit_dmg=s.crit_dmg, dh=s.dh,
                           dh_rate=s.dh_rate, det=s.det, det_multi=s.det_multi, speed=s.speed, dot_multi=s.dot_multi,
                           gcd=tier[0], hasted=tier[1] if len(tier) > 1 else None,
                           base_gcd=s.gcd(haste=0)),     # before a trait's haste (Monk, Ninja): the rotations' GCDs
                materia=[dict(stat=k[0], grade=k[1], id=k[2], name=k[3], n=v[0]) for k, v in
                         sorted(count.items(), key=lambda x: (-x[1][0], x[0][0]))],
                totals=list(totals))


def sheet(jobkey):
    """A job's entry: its set(s), best first, and its DPS per GCD tier (fitted over the grid, the grid's own searches and
    the searched tiers; whole phase, no raid buffs, the job's own constant multipliers left out: compare within the job
    only)."""
    f = CACHE / f"bis_{jobkey}.json"
    if not f.exists(): return None
    b = json.loads(f.read_text(encoding="utf-8"))
    job = b["job"]
    sets = b.get("sets") or [dict(tier=b["tier"], dps=b["dps"], food=b["food"], foodBonus=b["foodBonus"], gear=b["gear"],
                                  totals=b["totals"])]
    best = max(x["dps"] for x in sets)
    sets = sorted((x for x in sets if x["dps"] >= best * (1 - TIE)), key=lambda x: -x["dps"])
    key = lambda k: [float(v) for v in k.split("/")]
    tiers = {k: dict(tier=key(k), fitted=v) for k, v in b["fitted"].items()}
    for k, v in b["searched"].items(): tiers.setdefault(k, dict(tier=key(k)))["searched"] = v
    for k, v in b.get("grid", {}).items(): tiers.setdefault(k, dict(tier=key(k)))["grid"] = v     # one-round grid searches
    return dict(job=job, main=JOBS[job][0], speed=JOBS[job][1], haste=HASTE.get(job), tie=TIE, sync=gear.DB["sync"],
                sets=[one(job, x["tier"], x["dps"], best, x["food"], x["foodBonus"], x["gear"], x["totals"]) for x in sets],
                tiers=sorted(tiers.values(), key=lambda t: t["tier"]))


def sheets(names):
    """{job name as in the logs: sheet} for every job with a bis_<job>.json; `names` maps "SAM" to "Samurai"."""
    out = {}
    for abbr, name in names.items():
        s = sheet(abbr.lower())
        if s: out[name] = s
    return out


def ids(sheets_):
    """Every item, materia and food id the sheets show, for their icons."""
    out = set()
    for s in sheets_.values():
        for x in s["sets"]:
            out |= {i["id"] for i in x["items"]} | {m["id"] for i in x["items"] for m in i["melds"] if m}
            if x["food"]["id"]: out.add(x["food"]["id"])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--job", help="only this job (default: every job with a bis_<job>.json)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for k in [a.job] if a.job else [j.lower() for j in JOBS]:
        s = sheet(k)
        if not s: continue
        for x in s["sets"]:
            st = x["stats"]
            print(f"{s['job']} {'/'.join(f'{v:.2f}' for v in x['tier'])} ({x['rel']:+.2%})  {x['food']['name']}  main {st['main']} "
                  f"WD {st['wd']} crit {st['crit']} dh {st['dh']} det {st['det']} speed {st['speed']}")
            def meld(m):
                if not m: return "-"
                cut = "" if m["added"] == m["value"] else f"(+{m['added']})"
                return f"{m['stat']} {'X' if m['grade'] == 10 else 'IX'}{cut}"
            for i in x["items"]:
                melds = " ".join(meld(m) for m in i["melds"])
                print(f"  {i['slot']:<7} {i['ilvl']}{' synced' if i['synced'] else '       '} {i['name']:<46} {melds}  {i['final']}")
