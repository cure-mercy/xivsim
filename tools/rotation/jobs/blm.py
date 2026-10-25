"""Black Mage at level 90, Dawntrail patch 7.2 and later, single target.

Potencies and rules follow the official job guide (na.finalfantasyxiv.com/jobguide/blackmage; it shows level-100 values,
so level-90 ones come from the logs where they differ) and the patch notes since (patchnotes.py), checked against the
clears over whole pulls: plain hits match the potencies within ~2%, cast times within 0.02 s, and every logged cast
replays as legal (calibrate.py).
"""
import itertools, math
from engine import (ANIM_LOCK, BASE_GCD, RESOLVE, SLIDE, SlotState, cd_key, gcd_times, move_credit, open_move, recast,
                    settle, stand)

# Fire III and Blizzard III were raised from 280 to 290 in patch 7.2 (its notes; the job guide and the clears agree)
POTENCY = {"Fire III": 290, "Fire IV": 300, "Despair": 350, "Paradox": 540, "Blizzard III": 290, "Blizzard IV": 300,
           "Thunder III": 120, "Xenoglossy": 890, "Umbral Soul": 0}
# A DoT tick's plain potency at base speed is its tooltip's 50 (Thunder III: 120, then 50 a tick for 27 s); dot_tick()
# puts on the speed bonus the game gives DoTs (1 + floor(130 x (speed stat - 400) / 1900) / 1000 = 2 - SPEED). Read
# from FFLogs' own 100% tick (T, expectedAmount), our players' and the clears' ticks deal the tooltip x0.99
# (scratch/gear/dot_t.py, 2026-10-23).
# The first tick lands ~1.5 s after the hit on average.
DOT_BASE, DOT_TICKS, DOT_FIRST = 50, 9, 1.5


def dot_tick():
    return DOT_BASE * (2 - SPEED)
# seconds from a spell resolving to its damage landing (animation), measured in our logs; buffs snapshot on resolution
DELAY = {"Fire III": 1.29, "Fire IV": 1.16, "Despair": 0.49, "Paradox": 0.62, "Blizzard III": 0.89, "Blizzard IV": 1.16,
         "Thunder III": 1.02, "Xenoglossy": 0.62}
CAST = {"Fire III": 3.5, "Fire IV": 2.0, "Despair": 2.0, "Blizzard III": 3.5, "Blizzard IV": 2.0}   # 7.2: Fire IV 2.8 -> 2.0, Despair 3.0 -> 2.0, Blizzard IV 2.5 -> 2.0
FIRE = {"Fire III", "Fire IV", "Despair"}
ICE = {"Blizzard III", "Blizzard IV"}
AF_FIRE = {0: 1.0, 1: 1.4, 2: 1.6, 3: 1.8}          # fire damage by Astral Fire stacks
UI_FIRE = {1: 0.9, 2: 0.8, 3: 0.7}                  # fire damage by Umbral Ice stacks
AF_ICE = {1: 0.9, 2: 0.8, 3: 0.7}                   # ice damage by Astral Fire stacks (Blizzard III from AF3 lands for 0.7)
ENOCHIAN = 1.22                                     # all spells while in either element; the opener's Fire III lands without it
# MP: 200 per server tick (3 s) unless in Astral Fire; landing an ice spell while already in Umbral Ice restores
# 2,500 / 5,000 / 10,000 MP at UI1 / UI2 / UI3 (Aspect Mastery). Ice spells cost nothing in Umbral Ice.
MP_BASE, UI_BONUS = 200, {-1: 2500, -2: 5000, -3: 10000}
UMBRAL_SOUL_MP = {-1: 2500, -2: 5000, -3: 10000}
TICK_PHASE = 1.5                                    # server ticks land at TICK_PHASE + 3k seconds
POLY_S, POLY_MAX = 30, 2
LL_S, LL_SPEED, TRIPLE_S, SWIFT_S = 20, 0.85, 15, 10     # 7.2: Ley Lines 30 -> 20 s
LL_DELAY = 0.49     # the circle (Circle of Power) lands this long after the cast (logs: 0.48-0.54, n=1,036); Ley Lines
                    # can't be cast again until it is gone (xivintheshell's rule; no logged recast comes sooner)
PROC_S = math.inf                                   # Thunderhead and Firestarter no longer expire (patch 7.2's notes);
                                                    # they are only lost by being granted again while held
CDS = {"Triplecast": (60, 2), "Swiftcast": (60, 1), "Ley Lines": (120, 2), "Manafont": (100, 1), "Amplifier": (120, 1),
       "Transpose": (5, 1), "Tincture": (270, 1), "Between the Lines": (3, 1)}
OGCD_ORDER = ["Tincture", "Manafont", "Transpose", "Amplifier", "Ley Lines", "Between the Lines", "Triplecast", "Swiftcast"]
SPEED = 0.930                                       # spell speed factor on casts and GCDs: 2.32 s GCD, the clears since 7.2;
                                                    # calibrate.speed_for's pick in its tier: 2.0 s casts are 1.86 s as logged


class State(SlotState):
    __slots__ = ("t", "gcd", "el", "hearts", "mp", "mp_t", "poly", "poly_next", "paradox", "fs", "th", "triple", "triple_until",
                 "swift", "ll", "ll_spot", "cds", "dot", "dmg", "dotp", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.el, s.hearts, s.mp, s.mp_t = 0, 0, 10000, 0.0
        s.poly, s.poly_next, s.paradox = 0, None, False
        s.fs = s.th = s.triple_until = s.swift = s.ll = -1.0
        s.triple = 0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.dot, s.dmg, s.dotp, s.pot_at, s.first, s.hist = None, 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0, 0)
        s.mvi, s.acc, s.free, s.spot, s.ll_spot = 0, 0.0, -30.0, 0, -1    # forced movement (engine.stand) and Ley Lines' spot
        return s

    def key(self):
        return (round(self.t, 1), round(self.gcd, 1), self.el, self.hearts, self.mp // 400, self.poly, self.paradox,
                self.fs > self.t, self.th > self.t, self.triple if self.triple_until > self.t else 0,
                self.swift > self.t, round(max(self.ll - self.t, 0), 1), self.pot_at is None, cd_key(self.cds),
                round(self.dot[0], 1) if self.dot else None, self.mvi, round(self.acc, 1), self.spot == self.ll_spot,
                round(min(self.t - self.free, 6), 1))



WASTE = ("Polyglot overcapped", "Firestarter overwritten", "Thunderhead overwritten", "Paradox overwritten")


def wasted(s, i):
    """Count a resource lost: a Polyglot gained at the cap, or a proc granted again while still held."""
    w = list(s.waste); w[i] += 1; s.waste = tuple(w)


# --- time passing --------------------------------------------------------------------------------------------------

def advance(s, to):
    """MP ticks, Polyglot and cooldown charges up to time `to` (the element does not change in between)."""
    if to > s.mp_t:
        k0 = int((s.mp_t - TICK_PHASE) // 3) + 1
        k1 = int((to - TICK_PHASE) // 3)
        for _ in range(max(0, k1 - k0 + 1)):
            if s.el <= 0: s.mp = min(10000, s.mp + MP_BASE)
        s.mp_t = to
    while s.poly_next is not None and s.poly_next <= to:
        if s.poly == POLY_MAX: wasted(s, 0)
        s.poly = min(POLY_MAX, s.poly + 1); s.poly_next += POLY_S


def charges(s, name, at):
    n, nxt = s.cds[name]
    if nxt is None or nxt > at: return n, nxt         # nothing comes back by `at` (most calls)
    rec, mx = CDS[name]
    while n < mx and nxt is not None and nxt <= at:
        n += 1; nxt = nxt + rec if n < mx else None
    return n, nxt


def use_cd(s, name, at):
    n, nxt = charges(s, name, at)
    rec, mx = CDS[name]
    if n == mx: nxt = at + rec
    s.cds[name] = (n - 1, nxt)


def set_element(s, el, at):
    """Switching element: Thunderhead on any change of element type, the Polyglot timer starts on the first; Paradox
    when leaving Astral Fire III for ice, or Umbral Ice III with three Umbral Hearts for fire (by any action)."""
    if (s.el == 3 and el < 0) or (s.el == -3 and s.hearts == 3 and el > 0):
        if s.paradox: wasted(s, 3)
        s.paradox = True
    if (el > 0) != (s.el > 0) or s.el == 0:
        if s.th > at: wasted(s, 2)
        s.th = at + PROC_S
    # the Polyglot timer starts when that first spell lands, not when it resolves: only a 1.0-1.5 s lag (Fire III's
    # 1.29 s flight) makes every Xenoglossy in the clears' full pulls legal
    if s.el == 0 and el != 0: s.poly_next = at + DELAY.get("Fire III", 0) + POLY_S
    s.el = el


def hit(s, fight, at, potency, name):
    """Damage snapshots buffs when the spell resolves (`at`) and counts when it lands, inside the scored window and
    while the boss can be hit."""
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land): s.dmg += potency * fight.mult(at, s.pot_at)


def ticks(fight, at, since=0.0):
    """Ticks of a Thunder III applied at `at` that land from `since` on, inside the window and while the boss can be
    hit (the clears log no ticks while Athena is away)."""
    return sum(1 for k in range(DOT_TICKS) if max(since, 0) <= at + DOT_FIRST + 3 * k < fight.until
               and fight.targetable(at + DOT_FIRST + 3 * k))


def dot(s, fight, at):
    """Apply Thunder III's DoT at `at`, replacing the old one (its remaining ticks are lost). Ticks are timed from the
    spell resolving: on average the first lands 1.5 s later, which matches the logged tick counts."""
    if s.dot:
        a, m = s.dot
        lost = ticks(fight, a, since=at)
        s.dmg -= lost * dot_tick() * m; s.dotp -= lost * dot_tick() * m
    m = fight.mult(at, s.pot_at)
    gain = ticks(fight, at) * dot_tick() * m
    s.dmg += gain; s.dotp += gain
    s.dot = (at, m)


# --- actions -------------------------------------------------------------------------------------------------------

def in_ll(s, at):
    """Ley Lines is up and the player still stands in its circle (s.ll: when the circle ends; it came LL_S before)."""
    return s.ll - LL_S <= at < s.ll and s.spot == s.ll_spot


def timed(s, base, at, ll=None):
    """A cast or recast of `base` seconds after spell speed and Ley Lines' haste, as the game rounds them."""
    return recast(base, SPEED, LL_SPEED if (in_ll(s, at) if ll is None else ll) else 1.0)


def cast_time(s, name, at, ll=None):
    """Cast time after Firestarter, Swiftcast, Triplecast and the fast-cast of Fire III in UI3 / Blizzard III in AF3;
    plus which buff it consumes. `ll`: whether Ley Lines speeds it (default: if the player stands in it)."""
    if name not in CAST: return 0.0, None
    if name == "Fire III" and s.fs > at: return 0.0, "fs"
    if s.swift > at: return 0.0, "swift"
    if s.triple > 0 and s.triple_until > at: return 0.0, "triple"
    c = timed(s, CAST[name], at, ll)
    if (name == "Fire III" and s.el == -3) or (name == "Blizzard III" and s.el == 3): c *= 0.5
    return c, None


def mp_cost(s, name):
    """Fire spells cost double in Astral Fire unless an Umbral Heart covers it; ice spells are free in Umbral Ice and,
    as the logs show (Blizzard III cast at 0 MP right after Despair), from Astral Fire too; Paradox is free in ice."""
    if name == "Fire IV": return 800 if s.el <= 0 or s.hearts else 1600
    if name == "Fire III":
        if s.el == -3: return 0     # hard-cast from Umbral Ice III it costs nothing: 4 of 4 such casts in the clears
        return 2000 if s.el <= 0 or s.hearts else 4000
    if name == "Paradox": return 1600 if s.el >= 0 else 0
    if name in ("Blizzard III", "Blizzard IV"): return 0 if s.el != 0 else 800
    return 0


def gcd_legal(s, name, at):
    if name == "Fire IV": return s.el > 0 and s.mp >= mp_cost(s, name)
    if name == "Despair": return s.el > 0 and s.mp >= 800
    if name == "Paradox": return s.paradox and s.mp >= mp_cost(s, name)
    if name == "Fire III": return s.fs > at or s.mp >= mp_cost(s, name)
    if name == "Blizzard IV": return s.el < 0
    if name == "Thunder III": return s.th > at
    if name == "Xenoglossy": return s.poly > 0
    if name == "Umbral Soul": return s.el < 0
    return name == "Blizzard III"


def do_gcd(s, fight, name):
    """Cast a GCD as soon as possible; returns the new state or None when it cannot be cast."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    harm = name != "Umbral Soul"                              # everything else needs the boss as a target
    if harm and not fight.targetable(start): return None
    # Ley Lines speeds the GCD if the player stands in it: not during an instant in a move window (that is when they
    # run), nor during a hard cast that only fits the run if part of it came before
    ll = in_ll(s, start) and not (name not in CAST and open_move(s, fight, start))
    cast, used = cast_time(s, name, start, ll)
    if s.first: start = RESOLVE - cast; s.first = False         # the opener is pre-cast to land at 0:00
    if cast:
        if stand(s, fight, start, start + cast - SLIDE, commit=False) and ll:
            ll = False; cast, used = cast_time(s, name, start, ll)
        if stand(s, fight, start, start + cast - SLIDE) is None: return None
    if harm and fight.next_down(start) <= start + max(cast - RESOLVE, 0): return None   # the boss leaves mid-cast
    snap, free, nxt = gcd_times(start, cast, timed(s, BASE_GCD, start, ll))
    if used == "swift": s.swift = -1.0
    elif used == "triple": s.triple -= 1
    elif used == "fs": s.fs = -1.0
    if not (name == "Fire III" and used == "fs"): s.mp -= mp_cost(s, name)
    if name in ("Fire IV", "Fire III") and s.el > 0 and s.hearts and used != "fs": s.hearts -= 1
    el = s.el
    pot = POTENCY[name]
    if name in FIRE: pot *= AF_FIRE[el] if el >= 0 else UI_FIRE[-el]
    if name in ICE and el > 0: pot *= AF_ICE[el]
    if el == 0: pot /= ENOCHIAN
    hit(s, fight, snap, pot, name)
    # gauge effects, applied when the spell lands
    advance(s, max(snap, s.mp_t))
    if name in ICE and el < 0: s.mp = min(10000, s.mp + UI_BONUS[el])
    if name == "Fire III": set_element(s, 3, snap)
    elif name == "Blizzard III": set_element(s, -3, snap)
    elif name == "Blizzard IV": s.hearts = 3
    elif name == "Despair": s.mp = 0; set_element(s, 3, snap)
    elif name == "Paradox":
        s.paradox = False
        if el > 0:
            if s.fs > snap: wasted(s, 1)
            s.fs = snap + PROC_S
    elif name == "Thunder III": s.th = -1.0; dot(s, fight, snap)
    elif name == "Xenoglossy": s.poly -= 1
    elif name == "Umbral Soul":
        s.mp = min(10000, s.mp + UMBRAL_SOUL_MP[el]); set_element(s, max(-3, el - 1), snap); s.hearts = min(3, s.hearts + 1)
    s.t, s.gcd = max(free, snap), nxt
    s.log(start, name, gauge(s, f"{cast:.2f}s cast" if cast else "instant"))
    return s


def gauge(s, how):
    el = f"AF{s.el}" if s.el > 0 else f"UI{-s.el}" if s.el < 0 else "--"
    return f"{how:<12} {el}  MP {s.mp:>5}  hearts {s.hearts}  poly {s.poly}" + ("  paradox" if s.paradox else "")


def ogcd_legal(s, name, at, fight, policy=True):
    """Can the oGCD be used now? With `policy`, also skip uses that only waste it (Manafont with MP left, Amplifier
    at full Polyglot), which keeps the search small."""
    n, _ = charges(s, name, at)
    if n < 1: return False
    if name == "Manafont": return s.el > 0 and (s.mp < 1600 or not policy)
    if name == "Amplifier": return s.el != 0 and (s.poly < POLY_MAX or not policy)
    if name == "Transpose": return s.el != 0
    if name == "Ley Lines": return s.ll <= at and not open_move(s, fight, at)       # put down where the player will stay
    if name == "Between the Lines": return s.ll > at and s.spot != s.ll_spot and not open_move(s, fight, at)
    if name == "Triplecast": return not (s.triple > 0 and s.triple_until > at)
    if name == "Swiftcast": return s.swift <= at
    if name == "Tincture": return fight.pot and s.pot_at is None
    return True


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    use_cd(s, name, at)
    if name == "Manafont":
        if s.paradox: wasted(s, 3)
        if s.th > at: wasted(s, 2)
        s.mp = 10000; s.hearts = 3; s.paradox = True; s.th = at + PROC_S; set_element(s, 3, at)
    elif name == "Amplifier":
        if s.poly == POLY_MAX: wasted(s, 0)
        s.poly = min(POLY_MAX, s.poly + 1)
    elif name == "Transpose": set_element(s, -1 if s.el > 0 else 1, at)
    elif name == "Ley Lines": s.ll = at + LL_DELAY + LL_S; s.ll_spot = s.spot
    elif name == "Between the Lines": s.spot = s.ll_spot                  # back into the circle once the mechanic is done
    elif name == "Triplecast": s.triple, s.triple_until = 3, at + TRIPLE_S
    elif name == "Swiftcast": s.swift = at + SWIFT_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.log(at, name, gauge(s, ""))
    return s


GCDS = ["Fire IV", "Despair", "Paradox", "Fire III", "Blizzard III", "Blizzard IV", "Thunder III", "Xenoglossy", "Umbral Soul"]


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD."""
    slots = int((s.gcd - s.t) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready, k):
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            any_gcd = False
            now = max(c.t, c.gcd)
            # do_gcd's first steps (advance, settle: idempotent) once for all the GCDs, then only the legal ones tried
            b = c.copy(); advance(b, now); settle(b, fight, now)
            for g in GCDS:
                if combo and ("Swiftcast" in combo or "Triplecast" in combo) and g not in CAST: continue   # only spend instants on casts
                if not gcd_legal(b, g, now): continue
                n = do_gcd(b, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):                # nothing castable (running), or the boss is away
                w = c.copy(); w.t = w.gcd = fight.back_up(now) if down else now + 0.5
                w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


VALUE = dict(mp=0.06, poly=600, paradox=250, fs=200, th=150, triple=150, hearts=60)
RATE = 220                                            # potency per second, to compare states at slightly different times
SWEEP_WIDTH = 1000                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: -0.13% (0.25 s layers: -0.02%)
SWEEP_STEP = 0.25                                     # its layers' length, s: at 0.5 s the beam's run time finds 0.11% less


def held(s):
    v = VALUE["poly"] * s.poly + VALUE["paradox"] * s.paradox + VALUE["fs"] * (s.fs > s.t) + VALUE["th"] * (s.th > s.t)
    v += VALUE["triple"] * (s.triple if s.triple_until > s.t else 0) + VALUE["hearts"] * s.hearts
    return v + VALUE["mp"] * s.mp * (1 if s.el > 0 else 0.5)


# Runs coming up: a hard-cast rotation leaves ~40% of the time free anyway (the slide and the caster tax), each instant
# GCD in hand frees ~1.4 s more, and whatever is left over has to be stood idle. Without this the search spends
# Triplecast and Swiftcast as soon as they are up, since a held charge is worth nothing to it.
MOVE_AHEAD = 25.0                                     # seconds of upcoming move windows the ranking looks at
HARD_FREE, INSTANT_FREE = 0.4, 1.4
MOVE_WEIGHT = 1.0                                     # potency per uncovered second of running, in units of RATE


def instants(s, at):
    """Instant GCDs in hand: Triplecast stacks and charges, Swiftcast, Polyglot, Paradox and the two procs."""
    n = s.poly + s.paradox + (s.fs > at) + (s.th > at) + (s.triple if s.triple_until > at else 0)
    return n + 3 * charges(s, "Triplecast", at)[0] + charges(s, "Swiftcast", at)[0] + (s.swift > at)


def move_debt(s, fight):
    """Seconds of running ahead (within MOVE_AHEAD) that neither the hard casts' free time nor the instants in hand cover."""
    W, i, need = fight.moves, s.mvi, 0.0
    while i < len(W) and W[i].lo < s.t + MOVE_AHEAD:
        w = W[i]
        left = max(0.0, w.hi - max(w.lo, s.t))
        need += max(0.0, w.need - (s.acc if i == s.mvi else 0.0) - HARD_FREE * left)
        i += 1
    return max(0.0, need - INSTANT_FREE * instants(s, s.t)) if need else 0.0


def rank(s, fight):
    return s.dmg + held(s) - RATE * (s.t - move_credit(s, fight) + MOVE_WEIGHT * move_debt(s, fight))


def final(s, fight):
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "BlackMage", "2025-04-01"    # FFLogs' name for the job; clears on the 7.2 kit
OGCDS = set(CDS)
REFERENCE = ("Xenoglossy", 890)                     # the spell whose plain hits scale a log's damage to potency


def at(s, fight, t):
    """A copy of the state advanced to t, to read it at a logged cast."""
    c = s.copy(); advance(c, t)
    return c


STATUSES = {"Ley Lines": lambda s, t: s.ll - LL_S <= t < s.ll, "Circle of Power": in_ll,
            "Triplecast": lambda s, t: s.triple > 0 and s.triple_until > t, "Swiftcast": lambda s, t: s.swift > t,
            "Thunderhead": lambda s, t: s.th > t, "Firestarter": lambda s, t: s.fs > t}


def status(s, t):
    """What a report of an illegal cast shows."""
    return dict(el=s.el, mp=s.mp, hearts=s.hearts, poly=s.poly, paradox=s.paradox, fs=s.fs > t, th=s.th > t)


def force(s, fight, name, start):
    """Cast it anyway, with the resources it needs granted (the replay carries on after an illegal cast)."""
    s = s.copy()
    if name == "Paradox": s.paradox = True
    if name == "Thunder III": s.th = start + 1
    if name == "Xenoglossy": s.poly = max(s.poly, 1)
    if name in ("Fire IV", "Despair"): s.el = max(s.el, 1); s.mp = max(s.mp, 1600)
    s.mp = max(s.mp, mp_cost(s, name))
    return do_gcd(s, fight, name) or s


def model_potency(name, el):
    """The model's potency for a GCD cast in element state `el` (element bonuses and Enochian included)."""
    pot = POTENCY[name] * ((AF_FIRE[el] if el >= 0 else UI_FIRE[-el]) if name in FIRE else 1)
    return pot * (AF_ICE[el] if name in ICE and el > 0 else 1) / (ENOCHIAN if el == 0 else 1)


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` cast at t from state s, or None if it isn't checked."""
    if name not in GCDS or not POTENCY.get(name): return None
    return f"el {s.el:+d}", model_potency(name, s.el)


def cast_label(s, name, t):
    return f"el {s.el:+d} LL {'y' if s.ll > t else 'n'}"
