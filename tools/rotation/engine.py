"""Rotation simulator core: GCD and cast timing, weaving, raid buffs on a timeline, forced movement, downtime and a beam
search over actions.

A job model (jobs/*.py) supplies a State with the job's resources and an `options(state, fight)` that lists the legal
actions; the engine times them, applies damage with the buffs active at the snapshot, and searches for the sequence
that deals the most damage by `fight.until`.
"""
import heapq, math
from dataclasses import dataclass, field

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

    def targetable(self, t):
        return not any(a <= t < b for a, b in self.untargetable)

    def next_down(self, t):
        """When the boss next becomes untargetable at or after t (inf if never)."""
        return min((a for a, _ in self.untargetable if a >= t), default=math.inf)

    def back_up(self, t):
        """When the boss becomes targetable again, if it is untargetable at t."""
        return next((b for a, b in self.untargetable if a <= t < b), t)


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


def move_credit(s, fight):
    """Running time already banked toward the open window, worth what the job would otherwise lose standing idle."""
    if s.mvi < len(fight.moves): return min(s.acc, fight.moves[s.mvi].need)
    return 0.0


# The beam ranks states by damage so far, plus a guess at what the resources they hold are worth, minus the time they
# have used, minus the running ahead that the instants in hand won't cover (the job's move_debt). Over a whole phase
# the result moves by ~1% with that guess and no single setting is best, so `search` runs the beam under several (time's
# worth in potency per second, scale on the job's resource values, weight on uncovered running) and keeps the best
# rotation: each one is a legal rotation, so the best of them is never worse than any.
HEURISTICS = [(r, v, m) for r, v in [(200, 0.5), (220, 0.5), (220, 0.1), (245, 0.5)] for m in (0.0, 1.0)]


def _search_one(args):
    import importlib
    jobname, speed, fight, width, (rate, scale, mw), params = args
    job = importlib.import_module(f"jobs.{jobname}")
    job.SPEED, job.RATE, job.MOVE_WEIGHT = speed, rate, mw
    for k, v in (params or {}).items(): setattr(job, k, v)
    if not hasattr(job, "VALUE0"): job.VALUE0 = dict(job.VALUE)     # a worker may run several settings
    job.VALUE = {k: v * scale for k, v in job.VALUE0.items()}
    s = beam(job, fight, width)
    h = s.history(); s.hist = None                  # the history is a deep chain of tuples: send it flat
    return job.final(s, fight), (rate, scale, mw), s, h


def search(jobname, fight, width=None, speed=None, settings=None, procs=None, params=None):
    """The best rotation over the heuristic settings (the job's own HEURISTICS and WIDTH if it has them), searched in
    parallel; `params` sets other job constants in the workers (e.g. Monk's CRIT). Returns (state, setting, all
    scores)."""
    import importlib, multiprocessing
    job = importlib.import_module(f"jobs.{jobname}")
    settings = settings or getattr(job, "HEURISTICS", HEURISTICS)
    width = width or getattr(job, "WIDTH", 1000)
    args = [(jobname, speed or job.SPEED, fight, width, x, params) for x in settings]
    with multiprocessing.Pool(min(procs or len(args), len(args))) as pool:
        res = pool.map(_search_one, args)
    score, setting, s, h = max(res, key=lambda r: r[0])
    for e in h: s.hist = (s.hist, e)
    return s, setting, sorted((r[1], r[0]) for r in res)


def beam(job, fight, width=2000, log=None):
    """Best action sequence for the job in this fight. States are expanded one GCD at a time (any oGCDs woven before
    it come with it), and each layer keeps the `width` states with the best damage-so-far plus held-resource value."""
    layer = [job.State.initial(fight)]
    best = None
    step = 0
    while layer:
        nxt, seen = [], {}
        for s in layer:
            for c in job.expand(s, fight):
                if c.t >= fight.until:
                    if best is None or job.final(c, fight) > job.final(best, fight): best = c
                    continue
                k = c.key()
                v = job.rank(c, fight)
                if k in seen and seen[k][0] >= v: continue
                seen[k] = (v, c)
        layer = heapq.nlargest(width, (c for _, c in seen.values()), key=lambda c: job.rank(c, fight))
        step += 1
        if log and step % 10 == 0 and layer: log(f"  step {step}: {len(layer)} states, t={min(c.t for c in layer):.1f}-{max(c.t for c in layer):.1f}")
    return best
