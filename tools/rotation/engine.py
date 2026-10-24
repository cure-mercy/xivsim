"""Rotation simulator core: GCD and cast timing, weaving, raid buffs on a timeline, forced movement, downtime and a beam
search over actions.

A job model (jobs/*.py) supplies a State with the job's resources and an `options(state, fight)` that lists the legal
actions; the engine times them, applies damage with the buffs active at the snapshot, and searches for the sequence
that deals the most damage by `fight.until`.
"""
import heapq, math
from dataclasses import dataclass, field
from operator import itemgetter

ANIM_LOCK = 0.65            # seconds an instant action locks the player (0.6 s animation plus typical latency), as in the logs
CASTER_TAX = 0.10           # a hard cast that is at least as long as the GCD delays the next GCD by this much
BASE_GCD = 2.5
SLIDE = 0.46                # the player may move this long before a hard cast's bar ends (slidecasting)
RESOLVE = 0.52              # and the spell resolves (damage, gauge) this long before: the logs' cast events, 0.51-0.54 s
                            # before the bar ends for every cast length (2.0 s, 1.75 s, 3.5 s; in and out of Ley Lines)
RUN = 6.0                   # yalms per second, running
REACH = 3.0                 # a run longer than this leaves the spot the player stood on (Ley Lines' circle)


@dataclass
class Move:
    """Somewhere in [lo, hi] the player has to run for `need` seconds, which they can only do while not hard-casting:
    to reach a mechanic's spot before it resolves, or to dodge. Any time not spent in a cast bar (up to its slide point)
    counts, split however the rotation likes. `relocate`: the run takes the player off the spot they stood on."""
    lo: float
    hi: float
    need: float
    relocate: bool = True
    why: str = ""
    # stretches of the path a dash can cover: (kind, yalms of the path before it, its length[, yalms of floor past its
    # end]). "in": straight toward the boss, down to where a gap closer lands; "out": straight away from her, starting
    # beside her (a backstep, which may overshoot the stretch and walk back only as far as the floor goes: P12S's arena
    # edge is a drop, not a wall)
    dash: tuple = ()


@dataclass
class Fight:
    """What the job plays against: when raid buffs are up, when it has to move, when the boss can't be hit, and the
    window being scored."""
    until: float = 120.0
    buffs: list = field(default_factory=list)       # [(name, start, end, multiplier)]
    moves: list = field(default_factory=list)       # [Move], sorted and not overlapping
    untargetable: list = field(default_factory=list)  # [(start, end)]: nothing can be cast at the boss, DoTs don't tick
    # melee: [Move] windows somewhere in which the player is out of reach for `need` seconds on end (no melee actions,
    # no auto-attacks), and [(start, end)] stretches where the strategy fixes their spot, so a positional needs True North
    away: list = field(default_factory=list)
    pinned: list = field(default_factory=list)
    pot: bool = False                               # may the job use a tincture (once)?
    pot_mult: float = 1.1057                        # a Grade 4 tincture: +10.57% damage for DPS and healers, measured
    carry: bool = False                             # value the resources still held at `until`
    # the crit and direct-hit raid buffs among `buffs`, [(start, end, crit rate added, direct-hit rate added)], and the
    # typical rates `buffs` priced them at (their expected worth on an ordinary hit; solve.py's CRIT, CRIT_DMG, DH)
    rates: list = field(default_factory=list)
    typical: tuple = (0.25, 1.60, 0.36)

    def __post_init__(self):
        self.moves = sorted(self.moves, key=lambda m: m.lo)
        for a, b in zip(self.moves, self.moves[1:]):
            if b.lo < a.hi - 1e-9: raise ValueError(f"move windows overlap: {a} and {b}")

    def mult(self, t, pot_at=None):
        m = 1.0
        for _, a, b, x in self.buffs:
            if a <= t < b: m *= x
        if pot_at is not None and pot_at <= t < pot_at + 30: m *= self.pot_mult
        return m

    def sure(self, t, dh=False):
        """The correction on a guaranteed crit (with `dh`, a guaranteed critical direct hit) for the crit / direct-hit
        raid buffs up at t: a sure hit takes a buff's rate as damage, x(1 + rate x (crit damage - 1)) (x(1 + rate x
        0.25) for a direct-hit buff), where `buffs` priced it at its worth on an ordinary hit (xivgear autoCritBuffDmg).
        A direct-hit buff on a sure crit that may still miss its direct hit is worth what `buffs` says."""
        p, c, q = self.typical
        m = 1.0
        for a, b, dc, dd in self.rates:
            if a <= t < b:
                if dc: m *= (1 + dc * (c - 1)) / (1 + dc * (c - 1) / (1 + p * (c - 1)))
                if dd and dh: m *= (1 + dd * 0.25) / (1 + dd * 0.25 / (1 + q * 0.25))
        return m

    def targetable(self, t):
        for a, b in self.untargetable:          # loops, not any() / min() over a generator: called for every action
            if a <= t < b: return False
        return True

    def next_down(self, t):
        """When the boss next becomes untargetable at or after t (inf if never)."""
        m = math.inf
        for a, _ in self.untargetable:
            if t <= a < m: m = a
        return m

    def back_up(self, t):
        """When the boss becomes targetable again, if it is untargetable at t."""
        return next((b for a, b in self.untargetable if a <= t < b), t)


class SlotState:
    """Base of a job's State (__slots__ only): gives it a `copy` of one straight-line assignment per slot, with the
    dicts named in DICTS copied too (the getattr / setattr loop it replaces took a fifth of a search), and its history:
    a chain of (t, action, note) entries."""
    __slots__ = ()
    DICTS = ("cds",)

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        body = "".join(f"\n    c.{k} = dict(s.{k})" if k in cls.DICTS else f"\n    c.{k} = s.{k}" for k in cls.__slots__)
        ns = {"new": cls.__new__, "cls": cls}
        exec(f"def copy(s):\n    c = new(cls){body}\n    return c", ns)
        cls.copy = ns["copy"]

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


def cd_key(cds):
    """A state key's part for its cooldowns {name: (charges, next charge at)}: the times to 0.1 s."""
    return tuple([(n, x if x is None else round(x, 1)) for n, x in cds.values()])


def gcd_times(start, cast, recast):
    """(when the spell resolves, when the player may act again, when the next GCD may start)."""
    if cast > 0:
        free = start + cast + (CASTER_TAX if cast >= recast - 1e-9 else 0.0)
        return start + cast - RESOLVE, free, max(start + recast, free)
    return start, start + ANIM_LOCK, start + recast


# --- forced movement -----------------------------------------------------------------------------------------------
# A state carries `mvi` (the first move window not yet over), `acc` (running time banked toward it), `free` (when the
# player last stopped casting) and `spot` (an id for where they stand: it changes whenever a run takes them away).

def _overlap(a, b, lo, hi):
    return max(0.0, min(b, hi) - max(a, lo))


def settle(s, fight, t):
    """Close the move windows that are over by t (they were feasible, or a cast would have been refused)."""
    W = fight.moves
    while s.mvi < len(W) and W[s.mvi].hi <= t:
        w = W[s.mvi]
        if w.relocate and w.need > 0: s.spot = s.mvi + 1
        s.mvi += 1; s.acc = 0.0


def stand(s, fight, a, b, commit=True):
    """The player stands still casting over [a, b]. Returns None when that leaves some move window without enough
    running time, else whether the player must already have run off their spot before the cast starts (the run is
    done as late as possible, so they stay put while the rest of it still fits after this cast)."""
    W = fight.moves
    i, acc, spot = s.mvi, s.acc, s.spot
    left = False
    while i < len(W) and W[i].lo < b:
        w = W[i]
        acc += _overlap(s.free, a, w.lo, w.hi)
        after = max(0.0, w.hi - max(b, w.lo))
        if acc + after < w.need - 1e-9: return None
        if w.relocate and w.need - after > 1e-9: left = True; spot = i + 1
        if w.hi > b: break
        if w.relocate and w.need > 0: spot = i + 1
        i += 1; acc = 0.0
    if commit: s.mvi, s.acc, s.free, s.spot = i, acc, b, spot
    return left


def open_move(s, fight, t):
    """The move window the player is in at t, if they still have running to do in it."""
    W = fight.moves
    i = s.mvi
    while i < len(W) and W[i].hi <= t: i += 1
    if i < len(W) and W[i].lo <= t and W[i].need > 0 and W[i].relocate: return W[i]
    return None


def dash_gain(s, fight, t, kind, dist=None):
    """(segment index, seconds of running) a dash of this kind at t saves in the move window open at t, or None. The
    free time so far in the window counts as run along the path (lazy accounting can't tell where the player is), so
    the dash covers what is left of its segment once the path before it is behind. A gap closer ("in", dist None) covers
    all of that; a backstep of `dist` yalms covers it too, or, overshooting a shorter rest, the rest less the walk back.
    Each segment takes one dash; the state keeps them in `dashed`."""
    W = fight.moves
    i = s.mvi
    while i < len(W) and W[i].hi <= t: i += 1
    if i >= len(W) or not W[i].lo <= t < W[i].hi: return None
    w = W[i]
    run = ((s.acc if i == s.mvi else 0.0) + _overlap(s.free, t, w.lo, w.hi)) * RUN
    for k, seg in enumerate(w.dash):
        kind_k, before, length = seg[:3]
        room = seg[3] if len(seg) > 3 else math.inf     # floor past the stretch's end before the drop (no wall)
        if kind_k != kind or (i, k) in s.dashed or run < before - 1e-9: continue
        rest = min(length, before + length - run)
        if dist is not None and dist - rest > room + 1e-9: continue     # the backstep would land off the platform
        saved = rest if dist is None else dist if rest >= dist else 2 * rest - dist
        if saved > 1e-9: return k, min(saved / RUN, w.need)
    return None


def dash(s, fight, t, kind, dist=None):
    """Make the dash (see dash_gain): bank the running it saves toward the open window. Returns the seconds saved."""
    settle(s, fight, t)
    g = dash_gain(s, fight, t, kind, dist)
    if g is None: return 0.0
    k, secs = g
    s.dashed = tuple(d for d in s.dashed if d[0] >= s.mvi) + ((s.mvi, k),)
    s.acc += secs
    return secs


def move_credit(s, fight):
    """Running time already banked toward the open window, worth what the job would otherwise lose standing idle."""
    if s.mvi < len(fight.moves): return min(s.acc, fight.moves[s.mvi].need)
    return 0.0


# The beam ranks states by damage so far, plus a guess at what the resources they hold are worth, minus the time they
# have used, minus the running ahead that the instants in hand won't cover (the job's move_debt). Over a whole phase
# the result moves by ~1% with that guess and no single setting is best, so `search` runs under several (time's
# worth in potency per second, scale on the job's resource values, weight on uncovered running) and keeps the best
# rotation: each one is a legal rotation, so the best of them is never worse than any.
HEURISTICS = [(r, v, m) for r, v in [(200, 0.5), (220, 0.5), (220, 0.1), (245, 0.5)] for m in (0.0, 1.0)]


def recast(base, speed, haste=1.0):
    """A recast or cast time of `base` seconds as the game times it (xivgear's xivmath sksToGcd / spsToGcd): the speed
    stat's per-mille factor (a job's SPEED: (1000 - floor(130 x (speed stat - 400) / 1900)) / 1000) in whole
    milliseconds, then a haste (0.87: 13% faster) in whole hundredths of a second. Under Fuka a 2.40 s GCD is 2.08 s or
    2.09 s by the factor, not 2.088 s."""
    ms = math.floor(round(speed * 1000) * base + 1e-6)
    return math.floor(ms * (100 - round(100 * (1 - haste))) / 1000 + 1e-6) / 100


def configure(jobname, speed, setting, params=None):
    """The job module set up for one heuristic setting (rate, scale, move weight), in this process. A job's derive()
    then recomputes what it builds from the constants `params` set (the worth of its own crit buffs from its rates)."""
    import importlib
    rate, scale, mw = setting
    job = importlib.import_module(f"jobs.{jobname}")
    job.SPEED, job.RATE, job.MOVE_WEIGHT = speed, rate, mw
    base = job.__dict__.setdefault("PARAMS0", {})       # the module's own values of every constant a task has set
    for k, v in base.items(): setattr(job, k, v)        # (a worker of search_many runs tasks with other params)
    for k, v in (params or {}).items():
        base.setdefault(k, getattr(job, k, None)); setattr(job, k, v)
    if hasattr(job, "derive"): job.derive()
    if not hasattr(job, "VALUE0"): job.VALUE0 = dict(job.VALUE)     # a worker may run several settings
    job.VALUE = {k: v * scale for k, v in job.VALUE0.items()}
    return job


def _search_one(args):
    jobname, speed, fight, width, (rate, scale, mw), params, layers = args
    job = configure(jobname, speed, (rate, scale, mw), params)
    s = sweep(job, fight, width, getattr(job, "SWEEP_STEP", 0.5)) if layers == "time" else beam(job, fight, width)
    h = s.history(); s.hist = None                  # the history is a deep chain of tuples: send it flat
    return job.final(s, fight), (rate, scale, mw), s, h


def search(jobname, fight, width=None, speed=None, settings=None, procs=None, params=None, layers="time"):
    """The best rotation over the heuristic settings (the job's own HEURISTICS if it has them), searched in parallel;
    `params` sets other job constants in the workers (e.g. Monk's CRIT). `layers`: "time" for `sweep` (at the job's
    SWEEP_WIDTH and SWEEP_STEP), "gcd" for `beam` (at its WIDTH). With polish on top the sweep found 0.3-0.6% more for
    BRD, RDM, MNK and SAM and was level elsewhere (within 0.04%; 2026-10-22). Returns (state, setting, all scores)."""
    return search_many(jobname, [(fight, speed, params)], width, settings, procs, layers)[0]


def search_many(jobname, tasks, width=None, settings=None, procs=None, layers="time"):
    """`search` for several [(fight, speed, params)] at once, each the same as alone: every task's settings go to one
    pool, so a run of many searches keeps the cores busy (one search uses as many as it has settings and then waits
    for its slowest), the long fights first. Returns [(state, setting, all scores)] in the tasks' order."""
    import importlib, multiprocessing
    job = importlib.import_module(f"jobs.{jobname}")
    settings = settings or getattr(job, "HEURISTICS", HEURISTICS)
    width = width or (getattr(job, "SWEEP_WIDTH", 1000) if layers == "time" else getattr(job, "WIDTH", 1000))
    args = [(jobname, speed or job.SPEED, fight, width, x, params, layers) for fight, speed, params in tasks for x in settings]
    order = sorted(range(len(args)), key=lambda i: -args[i][2].until)
    res = [None] * len(args)
    with multiprocessing.Pool(min(procs or multiprocessing.cpu_count(), len(args))) as pool:
        for i, r in zip(order, pool.imap(_search_one, [args[i] for i in order])): res[i] = r
    out = []
    for k in range(len(tasks)):
        mine = res[k * len(settings):(k + 1) * len(settings)]
        score, setting, s, h = max(mine, key=lambda r: r[0])
        for e in h: s.hist = (s.hist, e)
        out.append((s, setting, sorted((r[1], r[0]) for r in mine)))
    return out


def beam(job, fight, width=2000, log=None, start=None):
    """Best action sequence for the job in this fight. States are expanded one GCD at a time (any oGCDs woven before
    it come with it), and each layer keeps the `width` states with the best damage-so-far plus held-resource value.
    `start`: carry on from this state instead of the pull (polish.py finishes rotations with it)."""
    layer = [start or job.State.initial(fight)]
    best, best_v = None, -math.inf
    step = 0
    while layer:
        seen = {}
        for s in layer:
            for c in job.expand(s, fight):
                if c.t >= fight.until:
                    v = job.final(c, fight)
                    if v > best_v: best, best_v = c, v
                    continue
                k = c.key()
                v = job.rank(c, fight)
                if k in seen and seen[k][0] >= v: continue
                seen[k] = (v, c)
        layer = [c for _, c in heapq.nlargest(width, seen.values(), key=itemgetter(0))]
        step += 1
        if log and step % 10 == 0 and layer: log(f"  step {step}: {len(layer)} states, t={min(c.t for c in layer):.1f}-{max(c.t for c in layer):.1f}")
    return best


def sweep(job, fight, width=2000, step=0.5, log=None, start=None):
    """The beam with layers by time instead of by GCD count: states fall into `step`-second buckets by when they can
    act next (s.t), and the earliest bucket keeps its best `width * step / BASE_GCD` (as many per second as the beam
    keeps per GCD) and is expanded into later ones. States are only ranked against others at nearly the same time, so
    the rank's potency per second of time (RATE) moves the order by at most RATE * step."""
    per = max(1, round(width * step / BASE_GCD))
    buckets = {}
    best, best_v = None, -math.inf

    def push(c, b):
        k, v = c.key(), job.rank(c, fight)
        seen = buckets.setdefault(b, {})
        if k not in seen or seen[k][0] < v: seen[k] = (v, c)

    s0 = start or job.State.initial(fight)
    push(s0, int(s0.t // step))
    while buckets:
        b = min(buckets)
        if b * step >= fight.until: break
        layer = [c for _, c in heapq.nlargest(per, buckets.pop(b).values(), key=itemgetter(0))]   # ranked when pushed
        for s in layer:
            for c in job.expand(s, fight):
                if c.t >= fight.until:
                    v = job.final(c, fight)
                    if v > best_v: best, best_v = c, v
                    continue
                push(c, max(int(c.t // step), b + 1))     # a child that gains no time still moves on (no hang)
        if log and b % 100 == 0: log(f"  t={b * step:.1f}: {len(layer)} states, {len(buckets)} buckets ahead")
    return best
