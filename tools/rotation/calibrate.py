"""Replays logged casts through a job model to check it: every cast should be legal at its logged time, the model's MP
should match the logged MP, its cast times should match begin-cast -> cast, and its damage per hit should track the
logged plain hits (no crit, no direct hit, buffs divided out).

    python tools/rotation/calibrate.py [--job blm] [--since 2025-04-01] [--until 125] [--ours]

By default each log is replayed over the whole pull, up to the player's first death (a death strips the gauge and
procs, which the model doesn't follow). A job model supplies the hooks at the end of jobs/<job>.py: LOG_NAME,
LOGS_SINCE, OGCDS, REFERENCE, at, status, force, label, cast_label; optionally prepare(p) (read what the replay
takes from the log itself, e.g. Monk's critical hits) with unprepare() (forget it again afterwards), force_ogcd, HASTE
(a permanent GCD haste, e.g. Monk's 20%), HASTE_STATUSES (statuses whose haste comes and goes, e.g. Bard's Army's
Paeon: gcd_of leaves the GCDs under them out, as it does Ley Lines), STATUSES ({logged status: up(state, t)}: just
before each cast the model's view of the player's own statuses is checked against the log, both ways; damage buffs
never make a cast illegal, so a window that ends early or lands too soon shows up only here).
"""
import argparse, collections, contextlib, datetime, importlib, json, math, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import logs                                      # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import blm as J                        # noqa: E402

from engine import BASE_GCD, RESOLVE             # noqa: E402
import engine                                    # noqa: E402


def use(job):
    """Replay with this job's model (a jobs/ module name) from now on."""
    global J
    J = importlib.import_module(f"jobs.{job}")
    return J


def cd_of(name):
    return J.cd_name(name) if hasattr(J, "cd_name") else name


@contextlib.contextmanager
def prepared(p):
    """The job reads what a replay takes from log p (prepare) and forgets it afterwards (unprepare): a search or a
    rebuilt rotation later in the same process (dps.upto) must not start from that log's opener or its hits."""
    if hasattr(J, "prepare"): J.prepare(p)
    try: yield
    finally:
        if hasattr(J, "unprepare"): J.unprepare()


def replay(p, until, out, fight=None):
    with prepared(p): return _replay(p, until, out, fight)


def log_spans(p):
    """{status: [(on, off)]} for the player's own statuses on themselves; one already up at the pull (its first event a
    removal or refresh) from -inf, one still up at the end to inf."""
    n, me = p["names"], p.get("id")
    on, out = {}, collections.defaultdict(list)
    for x in sorted(p["buffs"], key=lambda x: x["t"]):
        if me is not None and x.get("sourceID", me) != me: continue
        k, ty = n[str(x["abilityGameID"])], x["type"]
        if k not in out and k not in on and ty in ("removebuff", "refreshbuff", "removebuffstack", "applybuffstack"):
            on[k] = -math.inf
        if ty == "applybuff": on.setdefault(k, x["t"])
        elif ty == "removebuff" and k in on: out[k].append((on.pop(k), x["t"]))
    for k, t in on.items(): out[k].append((t, math.inf))
    return out


STATUS_EPS = 0.02                                   # the log's state just before the cast (a use removes it at the cast)


def check_statuses(out, spans, s, t):
    """The model's statuses in state s at t against the log's just before t (out["status"])."""
    for name, up in J.STATUSES.items():
        m, w = bool(up(s, t)), spans.get(name, ())
        x = t - STATUS_EPS
        span = next(((a, b) for a, b in w if a <= x < b), None)
        r = out["status"][name]
        if m and span: r["both"] += 1
        elif not m and not span: r["neither"] += 1
        elif span:                                   # the log has it, the model doesn't: the model's window is short
            a, b = span
            r["log only"].append((("after it came on", x - a) if x - a < b - x else ("before it went", b - x)) + (t, out.get("who")))
        else:                                        # the model has it, the log doesn't: it lands early or lasts long
            nxt = min((a - x for a, b in w if a > x), default=math.inf)
            prv = min((x - b for a, b in w if b <= x), default=math.inf)
            r["model only"].append((("before it came on", nxt) if nxt < prv else ("after it went", prv)) + (t, out.get("who")))


def _replay(p, until, out, fight):
    n = p["names"]
    spans = log_spans(p) if hasattr(J, "STATUSES") and "status" in out else None
    if spans is not None: out["who"] = (p["name"], p.get("code"), p.get("fight"))
    fight = fight or Fight(until=until + 30, pot=True)
    s = J.State.initial(fight)
    seq = []
    last_begin = {}
    for x in p["casts"]:
        if x.get("fake"): continue              # FFLogs' second record of one cast (Dancer's Technical Finish)
        name = n[str(x["abilityGameID"])]
        if x["type"] == "begincast": last_begin[name] = x["t"]; continue
        if x["type"] != "cast" or x["t"] > until: continue
        b = last_begin.pop(name, None)
        seq.append((x["t"], b, name, x.get("sourceResources", {}).get("mp")))
    for t, b, name, mp in seq:
        if name.startswith("Grade") and "Gemdraught" in name: name = "Tincture"
        if name in J.GCDS:
            start = b if b is not None and t - b < max(4, max(J.CAST.values(), default=0) + 0.5) else t
            if not s.first:
                if s.gcd - start > 0.15: out["early"].append((p["name"], t, name, round(s.gcd - start, 2)))
                s.t = s.gcd = start
            pre = J.at(s, fight, start)
            if spans is not None and not s.first: check_statuses(out, spans, pre, start)
            if mp is not None and not s.first and hasattr(pre, "mp"): out["mp"].append((name, getattr(pre, "el", 0), pre.mp, mp, p["name"], t))
            c, _ = J.cast_time(pre, name, start)
            if b is not None and c: out["cast"][(name, J.cast_label(pre, name, start))].append((t - b + RESOLVE, c))
            ns = J.do_gcd(s, fight, name)
            if ns is None and not s.first:              # a charge or a timer back within the logs' timing noise
                late = s.copy(); late.t = late.gcd = start + 0.1
                ns = J.do_gcd(late, fight, name)
            if ns is None:
                out["illegal"].append((p["name"], round(t, 2), name, J.status(pre, start)))
                ns = J.force(s, fight, name, start)        # carry on with the rules relaxed
            s = ns
        elif name in J.OGCDS:
            s.t = t
            if spans is not None and t >= 0: check_statuses(out, spans, J.at(s, fight, t), t)
            ns = J.do_ogcd(s, fight, name, policy=False)
            nxt = J.charges(s, cd_of(name), t)[1]
            if ns is None and nxt is not None and nxt - t <= 0.1:      # a charge back within the logs' timing noise
                s.t = nxt; ns = J.do_ogcd(s, fight, name, policy=False)
            if ns is None:
                out["illegal"].append((p["name"], round(t, 2), name, {"charges": J.charges(s, cd_of(name), t), **J.status(s, t)}))
                ns = J.force_ogcd(s, fight, name, t) if hasattr(J, "force_ogcd") else s
            s = ns
        else:
            s.t = max(s.t, t)       # role actions and movement tools: they only take time
    return s


def first_death(p):
    """When the player first died in the pull (inf if they didn't), from the scorecard's cache of the clear, or of our
    groups' report for their own pulls."""
    cache = HERE.parent / "scorecard" / ".cache"
    f = cache / "benchmark" / f"phases_{p['code']}_{p['fight']}.json"
    if f.exists():
        return min((d["t"] for d in json.loads(f.read_text())["deaths"] if d["name"] == p["name"]), default=math.inf)
    f = cache / f"report_{p['code']}.json"
    if not f.exists() or "id" not in p: return math.inf
    r = json.loads(f.read_text())
    s0 = next((x["startTime"] for x in r["fights"] if x["id"] == p["fight"]), None)
    return min(((d["timestamp"] - s0) / 1000 for d in r["deaths"] if d.get("fight") == p["fight"] and d.get("targetID") == p["id"]),
               default=math.inf) if s0 is not None else math.inf


def cut_of(p, until=None):
    """The end of the replay: `until` (default the whole pull), or the player's first death if that comes first."""
    return min(until if until is not None else p["end"], first_death(p))


def gcd_of(p):
    """The player's unhasted GCD: the most common spacing of consecutive GCD starts outside Ley Lines and the job's other
    hasting statuses (over the job's permanent haste, if it has one). A job whose haste status is up nearly all the time
    (Viper's Swiftscaled) lists it in HASTED instead, {status: factor}: gaps starting under it are divided by it; and
    GCD_BASE, {action: recast}, scales the gap after a GCD with a recast other than 2.5 s."""
    n = p["names"]
    h = getattr(J, "HASTE", 1.0)
    base = getattr(J, "GCD_BASE", {})

    def spans_of(status):
        ev = [x["t"] for x in p["buffs"] if n[str(x["abilityGameID"])] == status and x["type"] in ("applybuff", "removebuff")]
        return list(zip(ev[0::2], ev[1::2] + [math.inf]))     # a status still on at the end of the pull
    spans = [w for status in ("Ley Lines",) + getattr(J, "HASTE_STATUSES", ()) for w in spans_of(status)]
    hasted = [(spans_of(status), f) for status, f in getattr(J, "HASTED", {}).items()]
    inll = lambda t: any(a <= t < b for a, b in spans)

    def unhasted(a, b, name):
        g = (b - a) / h * 2.5 / base.get(name, 2.5)
        for w, f in hasted:
            if any(x <= a < y for x, y in w): g /= f
        return g
    starts, lb = [], {}
    for x in p["casts"]:
        if x.get("fake"): continue
        name = n[str(x["abilityGameID"])]
        if x["type"] == "begincast": lb[name] = x["t"]; continue
        if x["type"] == "cast" and name in J.GCDS:
            b = lb.pop(name, None)
            starts.append((b if b is not None and x["t"] - b < 4 else x["t"], name))
    gaps = sorted(round(g, 2) for (a, na), (b, _) in zip(starts, starts[1:])
                  for g in [unhasted(a, b, na)] if 2.0 <= g <= 2.6 and not inll(a))
    return gaps[len(gaps) // 4] if gaps else None     # lower quartile: clean back-to-back GCDs, not delayed ones


def _haste_factor(job):
    """The job's buff haste on the GCD, as a recast factor: Fuka, Swiftscaled (HASTED), Ley Lines; None without one."""
    return next(iter(getattr(job, "HASTED", {}).values()), getattr(job, "LL_SPEED", None))


def hasted_gcd_of(p):
    """The player's GCD under the job's buff haste, as played: of the spacings (to 0.01 s) of GCD starts under Fuka or
    Swiftscaled (HASTED) or in Ley Lines' circle (Circle of Power), after a GCD with a 2.5 s recast, the fastest that
    holds at least a quarter as many as the commonest (a Samurai: 4 at 2.08, 270 at 2.09, 103 at 2.10 from timestamp
    jitter, 347 at 2.14 after other actions; a lower quartile read 0.01-0.03 s fast). None for a job without such a
    haste or with fewer than 8 such gaps."""
    statuses = list(getattr(J, "HASTED", {})) or (["Circle of Power"] if hasattr(J, "LL_SPEED") else [])
    if not statuses: return None
    n, base = p["names"], getattr(J, "GCD_BASE", {})
    ev = lambda s: [x["t"] for x in p["buffs"] if n[str(x["abilityGameID"])] == s and x["type"] in ("applybuff", "removebuff")]
    spans = [w for s in statuses for w in zip(ev(s)[0::2], ev(s)[1::2] + [math.inf])]
    starts, lb = [], {}
    for x in p["casts"]:
        if x.get("fake"): continue
        name = n[str(x["abilityGameID"])]
        if x["type"] == "begincast": lb[name] = x["t"]; continue
        if x["type"] == "cast" and name in J.GCDS:
            b = lb.pop(name, None)
            starts.append((b if b is not None and x["t"] - b < 4 else x["t"], name))
    gaps = collections.Counter(round(b - a, 2) for (a, na), (b, _) in zip(starts, starts[1:])
                               if base.get(na, 2.5) == 2.5 and 1.5 <= b - a <= 2.6 and any(x <= a and b <= y for x, y in spans))
    if sum(gaps.values()) < 8: return None
    top = max(gaps.values())
    return min(g for g, k in gaps.items() if k >= top / 4)


def _rounded(job):
    """Whether the job model times its GCD with engine.recast (the game's rounding), so the speed factor itself counts."""
    return getattr(job, "recast", None) is engine.recast


def speed_for(job, gcd, hasted=None):
    """The job's SPEED (the speed stat's per-mille factor / 1000) for a player at this GCD (gcd_of) and hasted GCD
    (hasted_gcd_of, if known). A model that rounds as the game does sees the factor itself: of the factors giving the
    hasted GCD (where known) and the GCD (after the trait haste, as gcd_of times it; else the nearest), the middle one,
    e.g. Black Mage's 2.32 s: 0.928-0.931 -> 0.930, whose 2.0 s casts are 1.86 s as logged. gcd_of divides gaps under
    Fuka or Swiftscaled by the haste, so a 2.40 s Samurai at 2.08 under Fuka reads 2.39: the hasted GCD decides. The
    other models scale continuously, exact at GCD / 2.5."""
    if not _rounded(job): return gcd / BASE_GCD
    h = getattr(job, "HASTE", 1.0)
    want, f = round(gcd * h, 2), _haste_factor(job)
    off = lambda pm: abs(engine.recast(BASE_GCD, pm / 1000, h) - want)
    every = list(range(800, 1001))
    fits = [pm for pm in every if hasted and f and engine.recast(BASE_GCD, pm / 1000, f) == hasted]
    if getattr(job, "HASTED", None) and fits:
        pms = fits                  # Fuka, Swiftscaled: up nearly all the time, most gaps are under them
    else:                           # Ley Lines: a sixth of the fight; it only narrows the GCD's tier
        tier = [pm for pm in every if off(pm) == min(map(off, every))]
        pms = [pm for pm in tier if pm in fits] or tier
    best = min(map(off, pms))
    pms = [pm for pm in pms if off(pm) == best]
    return pms[len(pms) // 2] / 1000


def gcd_at(job, speed):
    """The GCD (unhasted by buffs, as gcd_of gives it) a SPEED plays at."""
    return engine.recast(BASE_GCD, speed) if _rounded(job) else round(speed * BASE_GCD, 4)


def hasted_label(job, speed):
    """The GCD under the job's buff haste at this SPEED, where the GCD's tier holds more than one (Samurai's 2.40 s is
    2.08 or 2.09 s under Fuka by the factor), else None: the site keys such rotations by both."""
    f = _haste_factor(job)
    if not f or not _rounded(job): return None
    g = gcd_at(job, speed)
    tier = {engine.recast(BASE_GCD, pm / 1000, f) for pm in range(800, 1001) if engine.recast(BASE_GCD, pm / 1000) == g}
    return engine.recast(BASE_GCD, speed, f) if len(tier) > 1 else None


def fit_phase(p, until):
    """The server tick phase (0-3 s) that best explains the log: fewest illegal casts, then fewest MP mismatches."""
    best = None
    for i in range(30):
        J.TICK_PHASE = i / 10
        out = dict(illegal=[], early=[], mp=[], cast=collections.defaultdict(list))
        replay(p, until, out)
        score = (len(out["illegal"]), sum(1 for m in out["mp"] if abs(m[2] - m[3]) > 250))
        if best is None or score < best[0]: best = (score, i / 10)
    return best[1]


def replay_fight(p, fight):
    """The logged rotation's damage in this fight (its buffs and scoring window)."""
    out = dict(illegal=[], early=[], mp=[], cast=collections.defaultdict(list))
    return replay(p, fight.until, out, fight)


def plain_hits(p, until):
    """[(action, group, logged damage with buffs divided out, model potency)] for the player's plain hits (no crit,
    no direct hit, no tincture) up to `until`; the group is the job's label for the state at the cast."""
    return model_hits(p, until, lambda x: x.get("hitType") == 1 and not x.get("directHit"))


def model_hits(p, until, keep, hit=False):
    """The same for the hits `keep` picks (outside tinctures); `hit`: each tuple ends with the logged hit itself."""
    with prepared(p): return _model_hits(p, until, keep, hit)


def _model_hits(p, until, keep, hit):
    n = p["names"]
    pot = [x["t"] for x in p["buffs"] if n[str(x["abilityGameID"])] == "Medicated" and x["type"] == "applybuff"]
    plain = {}
    for x in p["hits"]:
        if x["type"] == "damage" and keep(x) and not x.get("tick") and not any(a <= x["t"] < a + 30 for a in pot):
            plain.setdefault(n[str(x["abilityGameID"])], []).append((x["t"], x["amount"] / x.get("multiplier", 1), x))
    fight = Fight(until=until + 30)
    s = J.State.initial(fight)
    out = []
    for x in p["casts"]:
        if x["type"] != "cast" or x["t"] > until or x.get("fake"): continue
        name = n[str(x["abilityGameID"])]
        if name in J.GCDS or name in J.OGCDS:
            lab = J.label(J.at(s, fight, x["t"]), fight, name, x["t"])
            late = max(1.5, getattr(J, "DELAY", {}).get(name, 0) + 0.5)     # Monk's Demolish lands 1.6 s after
            h = [(v, y) for ht, v, y in plain.get(name, []) if 0 <= ht - x["t"] < late]
            if h and lab: out.append((name, lab[0], h[0][0], lab[1]) + ((h[0][1],) if hit else ()))
        if name in J.GCDS:
            s.t = s.gcd = x["t"]
            s = J.do_gcd(s, fight, name) or J.force(s, fight, name, x["t"])
        elif name in J.OGCDS:
            s.t = x["t"]
            ns = J.do_ogcd(s, fight, name, policy=False)
            nxt = J.charges(s, cd_of(name), x["t"])[1]
            if ns is None and nxt is not None and nxt - x["t"] <= 0.1:
                s.t = nxt; ns = J.do_ogcd(s, fight, name, policy=False)
            s = ns or (J.force_ogcd(s, fight, name, x["t"]) if hasattr(J, "force_ogcd") else s)
    return out


def damage_check(L, until=None):
    """Model potency of each hit against the logged plain hit, scaled so the player's reference action matches the model."""
    ref, ref_pot = J.REFERENCE
    rows = collections.defaultdict(list)
    for p in L:
        hits = plain_hits(p, cut_of(p, until))
        r = [v for name, _, v, _ in hits if name == ref]
        if not r: continue
        k = st.median(r) / ref_pot
        for name, lab, v, model in hits: rows[(name, lab)].append((v / k, model))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="blm", help="job model in jobs/ (blm, rpr, mnk, brd, drg, rdm, vpr, sam, pct, mch, nin, smn, dnc)")
    ap.add_argument("--since", default=None, help="first day of logs used (default: the job model's)")
    ap.add_argument("--until", type=float, default=None, help="end of the replay, s (default: the whole pull)")
    ap.add_argument("--ours", action="store_true", help="our groups' clean pulls instead of the benchmark clears")
    a = ap.parse_args()
    use(a.job)
    since = a.since or J.LOGS_SINCE
    days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
    if a.ours: L = [p for p in logs.ours(J.LOG_NAME) if p["day"] >= since]
    else: L = [dict(p, day=days[(p["code"], p["fight"])]) for p in logs.clears(J.LOG_NAME) if days[(p["code"], p["fight"])] >= since]
    print(f"{len(L)} {J.LOG_NAME} logs since {since}, replayed " + (f"0:00-{a.until:.0f}s" if a.until else "over the whole pull") +
          ", up to the player's first death:")
    out = dict(illegal=[], early=[], mp=[], cast=collections.defaultdict(list),
               status=collections.defaultdict(lambda: collections.defaultdict(int, {"log only": [], "model only": []})))
    for p in L:
        cut = cut_of(p, a.until)
        n0 = len(out["illegal"])
        J.SPEED = speed_for(J, gcd_of(p), hasted_gcd_of(p))     # each player at their own spell speed
        ph = None
        if hasattr(J, "TICK_PHASE"): ph = J.TICK_PHASE = fit_phase(p, cut)
        replay(p, cut, out)
        died = first_death(p)
        print(f"  {p['day']} {p['name']:<18} 0:00-{cut:5.1f}s" + (f" (died at {died:.1f}s)" if died <= cut else "") +
              (f"  tick phase {ph:.1f}" if ph is not None else "") + f"  illegal {len(out['illegal']) - n0}")
    print(f"\nillegal casts: {len(out['illegal'])}")
    for x in out["illegal"][:40]: print("  ", x)
    print(f"\nGCDs started earlier than the model allows (>0.15 s): {len(out['early'])}")
    for x in out["early"][:15]: print("  ", x)
    if out["mp"]:
        bad = [m for m in out["mp"] if abs(m[2] - m[3]) > 250]
        print(f"\nMP mismatches (>250): {len(bad)} of {len(out['mp'])}")
        for x in bad[:25]: print(f"   {x[4][:14]:<14} {x[5]:7.2f} {x[0]:<13} el {x[1]:+d}  model {x[2]:>5}  log {x[3]:>5}")
    if out["status"]:
        print("\nstatuses just before each cast: model vs log (disagreements by the nearest logged edge: count, median and"
              " max distance, s)")
        for name, r in out["status"].items():
            line = f"   {name:<24} both {r['both']:5d}  neither {r['neither']:5d}"
            for side in ("log only", "model only"):
                g = collections.defaultdict(list)
                for edge, d, *_ in r[side]: g[edge].append(d)
                if g: line += f"\n      {side:<11}" + "  ".join(f"{e} {len(v)} ({st.median(v):.2f}, max {max(v):.2f})"
                                                          for e, v in sorted(g.items()))
            print(line)
    print(f"\ncast times: logged (begin->cast + {RESOLVE} s to the bar end) vs model at the player's GCD")
    for k, v in sorted(out["cast"].items(), key=str):
        print(f"   {k[0]:<17} {k[1]:<12}: logged {st.median(a for a, _ in v):.2f}  model {st.median(b for _, b in v):.2f}  ({len(v)})")
    print(f"\ndamage: logged plain hit (scaled to {J.REFERENCE[0]}) vs model potency, by action and state at the cast")
    for k, v in sorted(damage_check(L, a.until).items(), key=str):
        print(f"   {k[0]:<17} {k[1]:<14}: logged {st.median(a for a, _ in v):6.0f}  model {st.median(b for _, b in v):6.0f}  ({len(v)})")


if __name__ == "__main__":
    main()
