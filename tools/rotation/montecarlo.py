"""What a rotation planned on expected procs deals when the procs are drawn: the job's optimized rotation (the site's,
over the whole phase) replayed under many draws (engine.DRAW).

    python tools/rotation/montecarlo.py --job rdm [--seeds 200] [--no-polish] [--restarts] [--replan 20 [--replan-width 300]] [--cache plan.pkl]

The search counts random procs at their expectation (Red Mage's Verfire / Verstone Ready, Bard's Repertoire and
Hawk's Eye, Dancer's Silken procs and feathers, Monk's chakra). A replay plays the plan's steps as a player who follows
it would: the planned step if its GCD can be cast (with as many of its oGCDs as are up), else its oGCDs with another
GCD in its place (the one the job ranks best: a Burst Shot for a Blast Arrow without the Soul Voice), and the plan goes
on with the next step. (Skipping to a later step instead drops the oGCDs between, a song among them, and a Bard's
replay fell 14% short.) A planned oGCD that isn't up yet (the replay a moment early, a song planned on the second its
recast ends) is woven as soon as it is, in the next CARRY steps: dropping it lost a Bard's Army's Paeon and the song
cycle after it. Each choice is made as the search
sees the state, procs ahead at their expectation, and only then played with the procs drawn, so no choice knows its
own luck. Where a draw before the action changes what is legal (Monk's party chakra arriving within the step), the
closest step that still is gets played: the same GCD with as many of its oGCDs as are up, else the best of the others
as the search ranks them. The replay with nothing drawn is the plan itself (checked).

--replan H plays a player who re-plans instead: before each step, a sweep (at --replan-width) over the next H seconds
from the state they are in, procs ahead at their expectation and what is held at its end at the job's values, and the
first step of its best. Played with nothing drawn too, it shows what the short horizon costs on its own.

draws() is the same replay for other callers: tools/gear/ceiling.py's proc luck on the 0:00-2:00 ceilings.
"""
import argparse, dataclasses, multiprocessing, pickle, statistics as st, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "scorecard"))
import dps, engine, polish, solve    # noqa: E402

CARRY = 4                   # a planned oGCD not up yet is tried with this many more steps

_W = {}


def _init(jobname, speed, setting, params, fight, hist, replan=None):
    try:
        job = engine.configure(jobname, speed, setting, params)
        steps, states = polish.split(job, fight, job.State.initial(fight), hist)
    except Exception as e:      # raised from _plan: a pool whose initializer fails respawns its workers forever
        _W.update(error=e); return
    _W.update(job=job, fight=fight, steps=steps, plan=job.final(states[-1], fight), replan=replan)


def _plan(_):
    if "error" in _W: raise _W["error"]
    return _W["plan"], len(_W["steps"])


def actions(s, c):
    """The actions the child c of s played."""
    out, h = set(), c.hist
    while h is not s.hist and h is not None: h, e = h; out.add(e[1])
    return out


def which(kids, c):
    """A child as (its actions, which of the children with those actions it is): a job may offer the same actions with
    different timing (Bard's and Monk's two waits for Athena)."""
    names = next(n for n, _, x in kids if x is c)
    return names, [x for n, _, x in kids if n == names].index(c)


def choose(job, fight, s, steps, k, carried=()):
    """(child as `which`, steps of the plan used, as planned) of the step to play from s, as the search sees it (nothing
    drawn): the planned step (with the `carried` oGCDs that are up), else its oGCDs with the best other GCD; past the
    plan's end, what the job ranks best."""
    kids = polish._kids(job, fight, s)
    if not kids: return None
    best = lambda key: which(kids, max(kids, key=key)[2])
    if k >= len(steps): return best(lambda x: job.rank(x[2], fight)), 0, False
    step = tuple(dict.fromkeys(tuple(carried) + steps[k][:-1])) + steps[k][-1:]
    c = polish._pick(job, fight, kids, step, steps[k + 1] if k + 1 < len(steps) else None)
    if c is not None: return which(kids, c), 1, True
    want = set(step[:-1])
    fit = lambda n: len(set(n[:-1]) & want) - len(set(n[:-1]) - want)
    return best(lambda x: (fit(x[0]), job.rank(x[2], fight))), 1, False


def replan(job, fight, s, horizon, width):
    """(child as `which`, 0, False) of the first step of the best play over the next `horizon` seconds from s (nothing
    drawn)."""
    kids = polish._kids(job, fight, s)
    if not kids: return None
    fallback = which(kids, max(kids, key=lambda x: job.rank(x[2], fight))[2]), 0, False
    sub = dataclasses.replace(fight, until=min(fight.until, s.t + horizon), carry=True)
    r = engine.sweep(job, sub, width, getattr(job, "SWEEP_STEP", 0.5), start=s)
    if r is None: return fallback
    ahead, h = [], r.hist
    while h is not s.hist and h is not None: h, e = h; ahead.append(e[:2])
    ahead.reverse()
    for _, entries, c in kids:
        if ahead[:len(entries)] == [e[:2] for e in entries]: return which(kids, c), 0, False
    return fallback


def realize(job, fight, s, child, seed):
    """(the child of s (as `which`) played with the procs drawn from `seed`, whether it is exactly that step): the
    closest one where a draw before the action changed what is legal."""
    engine.DRAW = seed
    kids = polish._kids(job, fight, s)
    names, j = child
    same = [x for n, _, x in kids if n == names]
    if len(same) > j: return same[j], True
    if not kids: return None, True
    c = polish._pick(job, fight, kids, names)
    if c is not None: return c, False
    have = {n: x for n, _, x in kids}
    engine.DRAW = None
    for n, _, x in sorted(polish._kids(job, fight, s), key=lambda x: -job.rank(x[2], fight)):
        if n in have: return have[n], False
    return None, False


def play(seed):
    """(final score, planned steps played as planned, other steps, steps changed by a draw, the history played) of the
    plan replayed with the procs drawn from `seed` (None: as the search counts them)."""
    job, fight, steps, rp = _W["job"], _W["fight"], _W["steps"], _W["replan"]
    s, k, planned, filler, changed, carry = job.State.initial(fight), 0, 0, 0, 0, {}
    while s.t < fight.until:
        engine.DRAW = None
        got = choose(job, fight, s, steps, k, carry) if rp is None else replan(job, fight, s, *rp)
        if got is None: break
        names, used, as_planned = got
        c, exact = realize(job, fight, s, names, seed)
        engine.DRAW = None
        if c is None: break
        if rp is None and k < len(steps):           # planned oGCDs not woven: carried to the next steps
            done = actions(s, c)
            carry = {o: n - 1 for o, n in carry.items() if o not in done and n > 1}
            carry.update({o: CARRY for o in steps[k][:-1] if o not in done and o not in carry})
        s, k, changed = c, k + used, changed + (not exact)
        if as_planned: planned += 1
        else: filler += 1
    return job.final(s, fight), planned, filler, changed, s.history()


def draws(jobname, fight, hist, setting, speed, params=None, seeds=200, replan=None):
    """The plan (a history searched at `setting`, `params` the job constants it was searched with) replayed with
    nothing drawn and under draws 1..seeds, by a player who follows it or re-plans (`replan`: (horizon, width)):
    dict(plan: its score, steps, ev: play(None), the replay with nothing drawn, runs: [play(seed)])."""
    with multiprocessing.Pool(initializer=_init, initargs=(jobname, speed, setting, params, fight, hist, replan)) as pool:
        plan, n = pool.apply(_plan, (None,))
        ev = pool.apply(play, (None,))
        runs = pool.map(play, range(1, seeds + 1))
    return dict(plan=plan, steps=n, ev=ev, runs=runs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="rdm", choices=sorted(solve.JOBS))
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--no-polish", action="store_true")
    ap.add_argument("--restarts", action="store_true", help="polish with restart passes (polish.py)")
    ap.add_argument("--replan", type=float, help="a player who re-plans this many seconds ahead before each step")
    ap.add_argument("--replan-width", type=int, default=300)
    ap.add_argument("--cache", help="keep the searched plan in this file and reuse it")
    a = ap.parse_args()
    mod = solve.JOBS[a.job][0]
    slot, fight = dps.site_fight(mod, dps.FULL)
    t0 = time.time()
    if a.cache and Path(a.cache).exists():
        setting, hist = pickle.loads(Path(a.cache).read_bytes())
    else:
        best, setting, _ = engine.search(a.job, fight, speed=mod.SPEED)
        if not a.no_polish:
            best, _ = polish.polish(a.job, fight, best, setting, mod.SPEED, log=lambda m: None, restarts=a.restarts)
        hist = best.history()
        if a.cache: Path(a.cache).write_bytes(pickle.dumps((setting, hist)))
    print(f"{a.job} {slot}, whole phase: plan searched ({time.time() - t0:.0f} s)", flush=True)
    rp = (a.replan, a.replan_width) if a.replan else None
    t0 = time.time()
    d = draws(a.job, fight, hist, setting, mod.SPEED, seeds=a.seeds, replan=rp)
    plan, ev, res, steps = d["plan"], d["ev"][0], d["runs"], range(d["steps"])
    print(f"  plan {plan:,.1f} in {len(steps)} steps")
    if rp:
        print(f"  re-planning {a.replan:.0f} s ahead (width {a.replan_width}), nothing drawn: {ev:,.1f} ({ev / plan - 1:+.2%} on the plan)", flush=True)
    elif abs(ev - plan) > 1e-6:
        print(f"  the plan replays at {ev:,.1f}, not {plan:,.1f}: the replay is off")
    v = sorted(r[0] for r in res)
    q = lambda f: v[min(len(v) - 1, int(f * len(v)))]
    m, sd = st.mean(v), st.stdev(v) if len(v) > 1 else 0.0
    print(f"  {len(v)} draws ({time.time() - t0:.0f} s): mean {m:,.1f} ({m / plan - 1:+.2%} on the plan, +- {sd / len(v) ** 0.5 / plan:.2%}), "
          f"sd {sd:,.0f} ({sd / plan:.2%})")
    print("  " + ", ".join(f"p{round(100 * f)} {q(f):,.0f} ({q(f) / plan - 1:+.1%})" for f in (0.05, 0.1, 0.5, 0.9, 0.95)))
    print(f"  per draw: " + (f"{st.mean(r[1] for r in res):.0f} of the plan's {len(steps)} steps as planned, {st.mean(r[2] for r in res):.1f} with another GCD, "
                             if not rp else "") + f"{st.mean(r[3] for r in res):.1f} steps changed by a draw")


if __name__ == "__main__":
    main()
