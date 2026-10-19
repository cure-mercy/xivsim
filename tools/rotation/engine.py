"""Rotation simulator core: GCD and cast timing, weaving, raid buffs on a timeline, and a beam search over actions.

A job model (jobs/*.py) supplies a State with the job's resources and an `options(state, fight)` that lists the legal
actions; the engine times them, applies damage with the buffs active at the snapshot, and searches for the sequence
that deals the most damage by `fight.until`.
"""
import heapq, math
from dataclasses import dataclass, field

ANIM_LOCK = 0.65            # seconds an instant action locks the player (0.6 s animation plus typical latency), as in the logs
CASTER_TAX = 0.10           # a hard cast that is at least as long as the GCD delays the next GCD by this much
BASE_GCD = 2.5
SLIDE = 0.46                # a hard cast resolves (damage, gauge) this long before its cast bar ends; the player may move then


@dataclass
class Fight:
    """What the job plays against: when raid buffs are up, when it has to move, and the window being scored."""
    until: float = 120.0
    buffs: list = field(default_factory=list)       # [(name, start, end, multiplier)]
    moves: list = field(default_factory=list)       # [(start, end)]: no hard cast may overlap these
    pot: bool = False                               # may the job use a tincture (once)?
    pot_mult: float = 1.1057                        # a Grade 4 tincture: +10.57% damage for DPS and healers, measured
    carry: bool = False                             # value the resources still held at `until`

    def mult(self, t, pot_at=None):
        m = 1.0
        for _, a, b, x in self.buffs:
            if a <= t < b: m *= x
        if pot_at is not None and pot_at <= t < pot_at + 30: m *= self.pot_mult
        return m

    def moving(self, a, b):
        return any(s < b and a < e for s, e in self.moves)


def gcd_times(start, cast, recast):
    """(when the spell resolves, when the player may act again, when the next GCD may start)."""
    if cast > 0:
        free = start + cast + (CASTER_TAX if cast >= recast - 1e-9 else 0.0)
        return start + cast - SLIDE, free, max(start + recast, free)
    return start, start + ANIM_LOCK, start + recast


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
