"""What the job models share: cooldown charges and the cost of charges sitting full, a melee's reach and positionals
against the fight's `away` and `pinned` windows, and the calibration hooks most jobs leave trivial.

A job binds the cooldown helpers to its own tables once, after its CDS (and recast_of, if it has one) is defined:

    charges, use_cd, full_since, capped, ready, at = cooldowns(__name__)

CDS is {name: (recast, charges)}; CAPPED, if the job has it, is {name: VALUE key} (a cooldown sitting at full charges
is charged VALUE[key] a second to `s.lost`); recast_of(name), if the job has it, is a recast the speed stat shortens.
VALUE and CAPPED are read at each call, since engine.configure rescales VALUE and CAPPED is defined after the bind.
"""
import sys


def wasted(s, i, n=1):
    """Count n of the i-th resource in the job's WASTE lost."""
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


def cast_label(s, name, t):
    """A replay's note on a cast: nothing, for a job without cast-time states."""
    return ""


def no_cast(s, name, at):
    """cast_time of a job whose every action is instant."""
    return 0.0, None


# --- melee reach and positionals ------------------------------------------------------------------------------------
# A state carries `ai` (the first away window not yet done) and `mlast` (the last melee action).

def flank_rear(s, fight, at):
    """Can the player take a positional: True North, or a spot the strategy doesn't fix."""
    return s.tn_until > at or not any(a <= at < b for a, b in fight.pinned)


def reach(s, fight, t, commit=True):
    """May a melee action land at t: every away window begun by then either got its stretch out of reach since the
    last melee action, or can still get it after t. With `commit`, t becomes the last melee action."""
    W, i = fight.away, s.ai
    while i < len(W) and W[i].lo < t:
        w = W[i]
        if min(t, w.hi) - max(s.mlast, w.lo) >= w.need - 1e-9: i += 1; continue
        if w.hi - max(t, w.lo) >= w.need - 1e-9: break
        return False
    if commit: s.ai, s.mlast = i, t
    return True


def out_of_reach(s, fight, t):
    """Is the player away at t: inside an open away window, within `need` of their last melee action (or its start)."""
    for w in fight.away[s.ai:]:
        if w.lo > t: break
        a = max(s.mlast, w.lo)
        if a <= t < a + w.need: return True
    return False


def away_soon(s, fight, t, ahead=5.0):
    for w in fight.away[s.ai:]:                     # a loop, not any() over a generator: called for every action
        if w.lo <= t + ahead and w.hi > t: return True
    return False


# --- cooldowns -----------------------------------------------------------------------------------------------------

def cooldowns(modname):
    """(charges, use_cd, full_since, capped, ready, at) for the job module of that name (see the module docstring)."""
    job = sys.modules[modname]
    CDS = job.CDS
    rec_of = getattr(job, "recast_of", None) or (lambda name: CDS[name][0])

    def charges(s, name, at):
        """(charges held, when the next comes back) at `at`."""
        n, nxt = s.cds[name]
        if nxt is None or nxt > at: return n, nxt         # nothing comes back by `at` (most calls)
        rec, mx = rec_of(name), CDS[name][1]
        while n < mx and nxt is not None and nxt <= at:
            n += 1; nxt = nxt + rec if n < mx else None
        return n, nxt

    def use_cd(s, name, at):
        n, nxt = charges(s, name, at)
        if n == CDS[name][1]:
            capped_at = getattr(job, "CAPPED", None)
            if capped_at and name in capped_at:
                s.lost += job.VALUE[capped_at[name]] * max(at - max(full_since(s, name, at), 0.0), 0)
            nxt = at + rec_of(name)
        s.cds[name] = (n - 1, nxt)

    def full_since(s, name, t):
        """When the cooldown last came back to full charges, if it is full at t (else None); full at the pull counts
        from 0."""
        n, nxt = s.cds[name]
        mx = CDS[name][1]
        if n == mx: return 0.0
        f = nxt + (mx - n - 1) * rec_of(name)
        return f if f <= t else None

    def capped(s, t):
        """Potency the cooldowns have lost sitting full so far (CAPPED: what a second of their recharge is worth)."""
        v = s.lost
        for name, k in job.CAPPED.items():
            f = full_since(s, name, t)
            if f is not None: v += job.VALUE[k] * max(t - max(f, 0.0), 0)
        return v

    def ready(s, name, t):
        """When the cooldown next has a charge, from t."""
        n, nxt = charges(s, name, t)
        return t if n else nxt

    def at(s, fight, t):
        """A copy of the state advanced to t, to read it at a logged cast."""
        c = s.copy(); job.advance(c, fight, t)
        return c

    return charges, use_cd, full_since, capped, ready, at
