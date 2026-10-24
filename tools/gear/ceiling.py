"""The scorecard site's ceilings from the gear model: each job's 0:00-2:00 ceiling with its best-in-slot set at the
combined optimum's GCD tier (bis.py --combined), and how far crit and direct-hit luck spreads a pull around it.

    python tools/gear/ceiling.py [--job blm]          # writes .cache/bis_site.json; build_site.py picks it up
    python tools/gear/ceiling.py --factors            # check: each job's measured damage per potency against the model's

The ceiling: the job's rotation searched over 0:00-2:00 alone (the scorecard's window, our strategy's runs at the role's
worst slot, as dps.py's ceilings) at the set's speed factor and rates, its potency split by how it scales (normal hits,
DoT ticks, sure crits, autos) and priced at the set's stats (bis.value), in nDPS: no raid buffs. The gear formula takes
game potency; a job model whose potencies are in other units says so (UNIT): Black Mage's include Enochian (x1.22,
blm.ENOCHIAN), every other job's are game potency. The check (--factors, `measured`): every uploader whose stats FFLogs
logs (CombatantInfo: our groups' reports and the benchmark clears), at capped gear, their plain hits against the stats'
prediction times that unit: 2026-10-23, Black Mage 1.216 / 1.22, the other measured jobs 0.99-1.02 (one to six
uploaders each, weapon damage inferred), none for Bard, Dragoon, Pictomancer and Ninja.

The spread: the standard deviation of a pull's 0:00-2:00 damage from crit and direct-hit rolls alone (not the +-5%
damage roll, not procs), at the set's rates. The rotation's hits are recorded one by one in a replay (Acc: s.dmg keeps
its increments): a hit of plain potency b at damage K per potency varies by b^2 K^2 v, v the variance of crit x direct
hit (crit rate p at x c, direct hit q at x1.25):

  normal hits, autos, DoT ticks   v = (1 + p(c^2 - 1))(1 + 0.5625 q) - ((1 + p(c - 1))(1 + 0.25 q))^2
  sure crits (Monk, Samurai)      v = c^2 x 0.0625 q (1 - q): only the direct hit rolls
  sure critical direct hits       0 (Machinist's tools, Pictomancer's hammers, Starfall)
  Wildfire (Machinist's DoT)      0 (it neither crits nor direct-hits)

The models book a DoT at application, so its share counts as ticks of the job's tick potency. Own crit and direct-hit
buffs (Devilment, Battle Voice, Battle Litany) are priced into the hits' potency at expected value; their extra
spread under the buff is left out (it's small: a fifth of the rates on a fifth of the hits).
"""
import argparse, itertools, json, math, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE), str(ROOT / "tools" / "rotation"), str(ROOT / "tools" / "scorecard")]
import bis, gear                                     # noqa: E402
from gear import Stats                               # noqa: E402

CACHE = HERE / ".cache"
OUT = CACHE / "bis_site.json"
CI = CACHE / "ci"
UNIT = {"blm": "ENOCHIAN"}     # a job model whose potencies include a multiplier the game applies on top of potency
_seq = itertools.count()


class Acc(float):
    """A running total that keeps its increments as a persistent chain (earlier chain, sequence number, amount): a
    state's copies share it and each child extends it on its own."""

    def __new__(cls, v, log=None):
        o = super().__new__(cls, v)
        o.log = log
        return o

    def __add__(self, x):
        return Acc(float(self) + x, (self.log, next(_seq), x))

    def __sub__(self, x):
        return Acc(float(self) - x, (self.log, next(_seq), -x))


class Auto(float):
    """Auto-attack potency: its products stay tagged, so a damage increment made of it is known for an auto-attack."""

    def __mul__(self, o):
        return Auto(float(self) * o)

    __rmul__ = __mul__


def _log(a):
    out, node = [], getattr(a, "log", None)
    while node:
        node, seq, x = node
        out.append((seq, x))
    return out[::-1]


def _tick(job):
    """The job model's DoT tick potency at its speed (dot_tick; 0: its DoT share neither crits nor direct-hits,
    Machinist's Wildfire)."""
    if job.__name__.endswith("mch"): return 0.0
    f = getattr(job, "dot_tick", None)
    if f is None: return None
    base = getattr(job, "DOT_BASE", None)
    return st.mean(f(n) for n in base) if isinstance(base, dict) else f()


def record(jobkey, hist, speed, params, until):
    """The rotation's hits over 0:00-`until`, replayed at the speed factor and rates: {kind: (sum, sum of squares)},
    kinds normal, auto, sure, dot (dot's squares as ticks of the model's tick potency)."""
    dps = bis._rot()
    import polish
    job = dps.JOBS[jobkey][0]
    fight = dps.site_fight(job, until)[1]
    copies = []
    with bis.configured(job, speed, params):
        keep = {k: getattr(job, k) for k in ("AUTO", "SURE_W", "STAR_W") if hasattr(job, k)}
        copy = job.State.copy

        def capture(s):
            c = copy(s); copies.append(c); return c
        try:
            if "AUTO" in keep: job.AUTO = Auto(job.AUTO)
            for k in ("SURE_W", "STAR_W"):
                if k in keep: setattr(job, k, 1.0)     # final() then adds nothing for the sure crits' weight
            s = job.State.initial(fight)
            for k in ("dmg", "dotp", "critp"):
                if hasattr(s, k): setattr(s, k, Acc(getattr(s, k)))
            steps, states = polish.split(job, fight, s, hist)
            job.State.copy = capture
            del copies[:]
            total = job.final(states[-1], fight)       # the swings and ticks to the window's end, on a copy
        finally:
            job.State.copy = copy
            for k, v in keep.items(): setattr(job, k, v)
    last = copies[-1] if copies else states[-1]
    dmg = [(q, x) for q, x in _log(total) if x]
    paired, kind = set(), {}
    for chan in ("dotp", "critp"):
        for q, x in _log(getattr(last, chan, None)):
            if not x: continue
            m = next((i for i, (q2, x2) in enumerate(dmg) if i not in paired and abs(q2 - q) <= 6 and x2 == x), None)
            if m is not None: paired.add(m); kind[m] = "dot" if chan == "dotp" else "sure"
    out = {k: [0.0, 0.0] for k in ("normal", "auto", "sure", "dot")}
    tick = _tick(job)
    for i, (q, x) in enumerate(dmg):
        k = kind.get(i) or ("auto" if isinstance(x, Auto) else "normal")
        out[k][0] += x
        out[k][1] += x * x if k != "dot" else math.copysign(abs(x) * min(abs(x), tick if tick is not None else abs(x)), x)
    if abs(sum(v[0] for v in out.values()) - float(total)) > 1e-6 * max(1.0, abs(float(total))):
        raise ValueError(f"{jobkey}: recorded hits {sum(v[0] for v in out.values()):,.1f} != final {float(total):,.1f}")
    return {k: tuple(v) for k, v in out.items()}


def spread(job, s, rec):
    """Standard deviation of the window's damage (in the gear model's units) from crit and direct-hit rolls."""
    p, c, q = s.crit_rate, s.crit_dmg, s.dh_rate
    ec, ec2, ed, ed2 = 1 + p * (c - 1), 1 + p * (c * c - 1), 1 + 0.25 * q, 1 + 0.5625 * q
    v_hit = ec2 * ed2 - (ec * ed) ** 2
    v_sure = 0.0 if job in bis.SURE_DH else c * c * (ed2 - ed * ed)
    base = s.main_multi * s.det_multi * s.wd_multi
    k = dict(normal=s.trait * base, auto=base * s.dot_multi, sure=s.trait * base, dot=s.trait * base)   # a DoT's speed
    # bonus is in its potency already: the models' dot_tick
    v = dict(normal=v_hit, auto=v_hit, sure=v_sure, dot=0.0 if job in bis.PLAIN_DOT else v_hit)
    return math.sqrt(sum(k[x] ** 2 * v[x] * max(rec[x][1], 0.0) for x in rec))


# ------------------------------------------------------------------------------------------------- per-job factor

def factor(jobkey):
    """The game's damage per model potency over per game potency: the job model's own unit (UNIT), else 1."""
    job = bis._rot().JOBS[jobkey][0]
    return getattr(job, UNIT[jobkey]) if jobkey in UNIT else 1.0


def _ci(code, fight):
    """A pull's CombatantInfo and players, fetched once into .cache/ci/."""
    f = CI / f"{code}_{fight}.json"
    if not f.exists():
        import fflogs
        CI.mkdir(parents=True, exist_ok=True)
        q = '''query($c:String!,$f:[Int]!){reportData{report(code:$c){
          ci:events(fightIDs:$f,dataType:CombatantInfo,limit:100){data}
          ma:masterData{actors(type:"Player"){id name subType}}}}}'''
        try:
            r = fflogs.gql(q, {"c": code, "f": [fight]})["reportData"]["report"]
        except Exception as e:     # an archived report refuses its events
            r = {"error": str(e)[:200]}
        f.write_text(json.dumps(r), encoding="utf-8")
    return json.loads(f.read_text(encoding="utf-8"))


def uploaders():
    """[(source, report code, fight, player, job name, stats)] for every logged stat sheet: one pull of each of our groups'
    reports (the scorecard's caches) and every benchmark kill."""
    sc = ROOT / "tools" / "scorecard"
    pulls = []
    for f in sorted((sc / ".cache").glob("report_*.json")):
        rep = json.loads(f.read_text(encoding="utf-8"))
        ids = [x["id"] for x in rep.get("fights", []) if x.get("difficulty")]
        if ids: pulls.append(("ours", rep["code"], ids[-1]))
    pulls += [("clears", k["code"], k["fight"]) for k in json.loads((sc / "benchmark.json").read_text(encoding="utf-8"))["kills"]]
    out = []
    for src, code, fight in pulls:
        r = _ci(code, fight)
        actors = {a["id"]: a for a in (r.get("ma") or {}).get("actors", [])}
        for e in (r.get("ci") or {}).get("data", []):
            a = actors.get(e.get("sourceID"))
            if a and "criticalHit" in e: out.append((src, code, fight, a["name"], a["subType"], e))
    return out


def measured(jobkey, log=lambda m: None):
    """The check on `factor`: the job's measured damage per potency over the gear model's prediction, each uploader at
    capped gear (their logged main stat and determination, the weapon synced to 660 or a 665 one), their plain hits
    over 0:00-2:00 (calibrate.plain_hits, median, as dps.py's k), the median over uploaders. (ratio, uploaders);
    (None, 0) without one."""
    import calibrate, logs
    dps = bis._rot()
    job, name = dps.JOBS[jobkey]
    J = jobkey.upper()
    calibrate.use(jobkey)
    main_key = {"int": "intelligence", "dex": "dexterity", "str": "strength"}[gear.JOBS[J][0]]
    mod = gear.DB["jobs"][J][gear.JOBS[J][0]]
    # the main stat of every slot at the 660 cap (a level-100 weapon synced): with no clan bonus, and +3 and a 665 weapon
    slots = ("head", "body", "gloves", "legs", "feet", "ears", "neck", "wrists", "ring", "ring", "weapon")
    full = sum(gear.cap(gear.JOBS[J][0], x, 660, None) for x in slots) + gear.fl(gear.MAIN * mod / 100)
    capped, wd665 = gear.fl(full * 1.05) - 6, gear.fl((full + 3) * 1.05) + 4
    pools = {}
    ratios = []
    for src, code, fight, player, jn, e in uploaders():
        if jn != name or e[main_key] < capped: continue
        if src not in pools: pools[src] = logs.ours(name) if src == "ours" else logs.clears(name)
        ps = [p for p in pools[src] if p["name"] == player and p["code"] == code and (src == "ours" or p["fight"] == fight)]
        hits = [h for p in ps for h in calibrate.plain_hits(p, dps.WINDOW + 5)]
        if len(hits) < 10: continue
        k = st.median(v / m for _, _, v, m in hits)
        main, det = e[main_key], e["determination"]
        wd = 132 if main >= wd665 else 131
        pred = ((math.trunc(gear.AP_MOD * (main - gear.MAIN) / gear.MAIN) + 100) / 100
                * (1000 + gear.fl(140 * (det - gear.MAIN) / gear.DIV)) / 1000
                * gear.fl(gear.MAIN * mod / 1000 + wd) / 100 * gear.JOBS[J][2])
        ratios.append(k / pred)
        log(f"    {src:<6} {player:<20} {len(ps)} pulls  main {main}  det {det}  k {k:.2f}  predicted {pred:.2f}  {k / pred:.4f}")
    return (st.median(ratios), len(ratios)) if ratios else (None, 0)


# -------------------------------------------------------------------------------------------------------- export

def job_ceiling(jobkey, log=print):
    """The site's entry for a job: its 0:00-2:00 ceiling with the combined optimum's set (nDPS), the spread from crit
    and direct-hit luck (one standard deviation), the set and how it was made."""
    dps = bis._rot()
    b = json.loads((CACHE / f"bis_{jobkey}.json").read_text(encoding="utf-8"))
    J, W = jobkey.upper(), dps.WINDOW
    s = Stats(J, b["totals"], {k: tuple(v) for k, v in b["foodBonus"].items()})
    hist = bis.rotation(jobkey, b["speed"], b["params"], until=W)
    rec = record(jobkey, hist, b["speed"], b["params"], W)
    m = bis.Mix(*(rec[k][0] for k in ("normal", "dot", "sure", "auto")))
    f = factor(jobkey)
    ceiling = f * bis.value(J, s, m) / W
    sd = f * spread(J, s, rec) / W
    log(f"{J}: tier {'/'.join(f'{x:.2f}' for x in b['tier'])}, {m}; potency unit x{f:.2f}; "
        f"ceiling 0:00-2:00 {ceiling:,.0f} nDPS, crit / direct-hit luck +-{sd:,.0f} ({sd / ceiling:.2%}) one SD")
    return dict(ceiling=round(ceiling), sd=round(sd), gcd=b["tier"][0], hasted=b["tier"][1] if len(b["tier"]) > 1 else None,
                crit_rate=s.crit_rate, crit_dmg=s.crit_dmg, dh_rate=s.dh_rate, potency=round(m.total), unit=f,
                food=b["food"], gear=b["gear"], window=W)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--job", help="only this job (default: every job with a bis_<job>.json)")
    ap.add_argument("--factors", action="store_true", help="check each job's potency unit against its uploaders' damage")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    dps = bis._rot()
    keys = [a.job] if a.job else [k for k in dps.JOBS if (CACHE / f"bis_{k}.json").exists()]
    if a.factors:
        for k in [a.job] if a.job else dps.JOBS:
            m, n = measured(k, print)
            f = factor(k)
            print(f"{k}: potency unit x{f:.2f}; measured " + (f"x{m:.4f} over {n} uploaders, {m / f - 1:+.2%}" if m else "-: no uploader"))
    else:
        saved = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        for k in keys: saved[dps.JOBS[k][1]] = job_ceiling(k)
        OUT.write_text(json.dumps(saved, indent=1), encoding="utf-8")
        print(f"saved {len(keys)} jobs to {OUT}")
