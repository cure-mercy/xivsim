"""Local search on the rotation the beam found (engine.search): small edits the beam's layer-by-layer pruning can miss,
each scored over the whole fight.

A rotation is a list of steps, a step being the action names one of the job's `expand` children appends (its oGCDs,
then its GCD or a wait), so any job model works unchanged. Edits: put another of the state's children in a step's place,
swap two neighbouring steps' GCDs, move an oGCD up to SHIFT steps earlier or later, or drop a step. An edited rotation
is replayed through `expand`: a step that no longer fits loses the oGCDs that aren't up (or is dropped if its GCD can't
be cast), and if the steps run out before the end a small beam finishes it. Every pass scores all edits of the best
rotation so far in parallel, then takes the improving ones, best first, as long as each still improves the whole
rotation. A result is always a legal rotation, never worse than the beam's.
"""
import multiprocessing, time

import engine

SHIFT = 3                   # an oGCD moves up to this many steps earlier or later
FINISH_WIDTH = 10           # beam width for the steps after an edited rotation's own run out
MAX_DROPS = 3               # an edited rotation with this many steps in a row that no longer fit is given up
EPS = 1e-6

_W = {}                     # worker state: the configured job, the fight, and the current rotation's states


def _kids(job, fight, s):
    """[(names, entries, child)]: the actions each child of s appends, by name and as history entries."""
    out = []
    for c in job.expand(s, fight):
        entries, h = [], c.hist
        while h is not s.hist and h is not None: h, e = h; entries.append(e)
        entries.reverse()
        out.append((tuple(e[1] for e in entries), entries, c))
    return out


def _same(a, b):
    return a[-1] == b[-1] and set(a[:-1]) == set(b[:-1])


def _pick(job, fight, kids, want, nxt=None):
    """The child that best matches the step `want`: the same GCD (or wait), as many of its oGCDs as are legal and no
    others. Among equally good ones (a job may offer the same actions with different timing, like Monk's two waits for
    Athena), the first, by rank, from which the step `nxt` can follow exactly. None if no child casts that GCD."""
    want_o = set(want[:-1])
    found = []
    for names, _, c in kids:
        if names[-1] != want[-1]: continue
        have = set(names[:-1])
        found.append((len(have & want_o) - len(have - want_o), job.rank(c, fight), c))
    if not found: return None
    top = max(m for m, _, _ in found)
    tied = sorted((x for x in found if x[0] == top), key=lambda x: -x[1])
    if nxt is not None and len(tied) > 1:
        for _, _, c in tied:
            if any(_same(n, nxt) for n, _, _ in _kids(job, fight, c)): return c
    return tied[0][2]


def run(job, fight, s, steps):
    """The final state of the rotation `steps` played from s, repaired where a step no longer fits and finished by a
    small beam if it runs out early; None if it gets stuck, or if MAX_DROPS steps in a row don't fit (the edit broke
    the plan: not worth finishing)."""
    dropped = 0
    for k, want in enumerate(steps):
        c = _pick(job, fight, _kids(job, fight, s), want, steps[k + 1] if k + 1 < len(steps) else None)
        if c is None:
            dropped += 1
            if dropped >= MAX_DROPS: return None
            continue
        s, dropped = c, 0
        if s.t >= fight.until: return s
    return engine.beam(job, fight, FINISH_WIDTH, start=s)


def split(job, fight, s, entries):
    """(steps, states) of a rotation from its history: states[i] is the state before steps[i]. Of two children that
    log the same entries, the one the next entries can follow from."""
    steps, states, i = [], [s], 0
    while i < len(entries):
        found = [(names, got, c) for names, got, c in _kids(job, fight, s) if got == entries[i:i + len(got)]]
        if not found: raise ValueError(f"polish: can't replay the rotation at {entries[i]}")
        names, got, c = found[0]
        if len(found) > 1 and i + len(got) < len(entries):
            j = i + len(got)
            names, got, c = next((x for x in found if any(g == entries[j:j + len(g)] for _, g, _ in _kids(job, fight, x[2]))),
                                 found[0])
        steps.append(names); states.append(c); s = c; i += len(got)
    return steps, states


def _score(job, fight, s):
    return job.final(s, fight) if s is not None else -1.0


# --- edits: (kind, i, ...) on a list of steps, None for a dropped one ------------------------------------------------

def apply(edit, steps):
    kind, i = edit[0], edit[1]
    out = list(steps)
    if kind == "set": out[i] = edit[2]
    elif kind == "drop": out[i] = None
    elif kind == "swap":
        a, b = out[i], out[i + 1]
        if a is None or b is None: return None
        out[i], out[i + 1] = a[:-1] + b[-1:], b[:-1] + a[-1:]
    elif kind == "move":
        j, o = edit[2], edit[3]
        a, b = out[i], out[j]
        if a is None or b is None or o not in a[:-1] or o in b[:-1]: return None
        out[i] = tuple(x for x in a if x != o)
        out[j] = b[:-1] + (o,) + b[-1:]
    return out


def _lo(edit):
    return min(edit[1], edit[2]) if edit[0] == "move" else edit[1]


def edits_at(job, fight, steps, states, i):
    st = steps[i]
    out = [("set", i, names) for names in dict.fromkeys(n for n, _, _ in _kids(job, fight, states[i])) if names != st]
    out.append(("drop", i))
    if i + 1 < len(steps) and st[-1] != steps[i + 1][-1]: out.append(("swap", i))
    for o in st[:-1]:
        for j in range(max(0, i - SHIFT), min(len(steps), i + SHIFT + 1)):
            if j != i and o not in steps[j][:-1]: out.append(("move", i, j, o))
    return out


# --- workers ---------------------------------------------------------------------------------------------------------

def _init(jobname, speed, setting, params, fight):
    _W.update(job=engine.configure(jobname, speed, setting, params), fight=fight, version=None)


def _load(version, steps):
    """The current rotation's states (cached per version)."""
    if _W["version"] != version:
        job, fight = _W["job"], _W["fight"]
        s = run(job, fight, job.State.initial(fight), steps)
        _W.update(version=version, states=split(job, fight, job.State.initial(fight), s.history())[1], score=_score(job, fight, s))
    return _W["states"], _W["score"]


def _evaluate(args):
    """[(gain, edit)] of the edits at steps lo..hi that improve the rotation."""
    version, steps, lo, hi = args
    job, fight = _W["job"], _W["fight"]
    states, base = _load(version, steps)
    out = []
    for i in range(lo, hi):
        for e in edits_at(job, fight, steps, states, i):
            new = apply(e, steps)
            if new is None: continue
            k = _lo(e)
            v = _score(job, fight, run(job, fight, states[k], [x for x in new[k:] if x]))
            if v > base + EPS: out.append((v - base, e))
    return out


def _combine(args):
    """Take the improving edits, best first, while each still improves the whole rotation. Returns the result as
    (score, steps, flat history, final state without its history)."""
    steps, found = args
    job, fight = _W["job"], _W["fight"]
    s0 = job.State.initial(fight)
    cur, best = list(steps), run(job, fight, s0, steps)
    for _, e in sorted(found, key=lambda x: -x[0]):
        new = apply(e, cur)
        if new is None: continue
        s = run(job, fight, s0, [x for x in new if x])
        if _score(job, fight, s) > _score(job, fight, best) + EPS: cur, best = new, s
    h = best.history()
    steps = split(job, fight, s0, h)[0]
    best.hist = None
    return _score(job, fight, best), steps, h, best


def _start(entries):
    """The beam's rotation as steps, and its score as replayed here."""
    job, fight = _W["job"], _W["fight"]
    s0 = job.State.initial(fight)
    steps = split(job, fight, s0, entries)[0]
    return _score(job, fight, run(job, fight, s0, steps)), steps


def polish(jobname, fight, best, setting, speed, params=None, procs=None, budget=600, log=print):
    """The beam's best rotation improved by local search under its own heuristic setting (which only breaks ties in
    the repair and steers the beam that finishes a rotation; edits are scored by the job's `final`). Stops when a pass
    finds nothing or after `budget` seconds. Returns (state, passes)."""
    import importlib
    job = importlib.import_module(f"jobs.{jobname}")
    beam_score = job.final(best, fight)
    procs = procs or multiprocessing.cpu_count()
    t0 = time.time()
    with multiprocessing.Pool(procs, initializer=_init, initargs=(jobname, speed, setting, params, fight)) as pool:
        try:
            score, steps = pool.apply(_start, (best.history(),))
        except ValueError as e:
            log(f"{e}; kept as it was")
            return best, 0
        if score < beam_score - EPS:
            log(f"polish: the beam's rotation replays at {score:,.1f}, not {beam_score:,.1f}; kept as it was")
            return best, 0
        result, passes = None, 0
        while time.time() - t0 < budget:
            passes += 1
            n = len(steps)
            chunk = max(1, n // (procs * 4))
            found = [x for r in pool.imap_unordered(_evaluate, [(passes, steps, a, min(n, a + chunk)) for a in range(0, n, chunk)])
                     for x in r]
            if not found: break
            new, steps, h, s = pool.apply(_combine, ((steps, found),))
            log(f"  pass {passes}: {len(found)} improving edits, {score:,.1f} -> {new:,.1f} ({time.time() - t0:.0f} s)")
            if new <= score + EPS: break
            score, result = new, (h, s)
    if result is None: return best, passes
    h, s = result
    for e in h: s.hist = (s.hist, e)
    return s, passes
