"""Black Mage at level 90, Dawntrail patch 7.2 and later, single target.

Potencies and rules follow the official job guide's level-90 values (na.finalfantasyxiv.com/jobguide/blackmage), checked
against the clears: plain hits match the potencies within ~2%, cast times within 0.03 s, and every logged cast replays as
legal (tools/rotation/calibrate.py).
"""
import itertools
from engine import ANIM_LOCK, BASE_GCD, SLIDE, gcd_times

POTENCY = {"Fire III": 280, "Fire IV": 300, "Despair": 350, "Paradox": 540, "Blizzard III": 280, "Blizzard IV": 300,
           "Thunder III": 120, "Xenoglossy": 890, "Umbral Soul": 0}
# Thunder III's DoT: 50 potency for 27 s by the tooltip; ticks land for 63 relative to Xenoglossy 890 in the logs (DoTs
# scale with spell speed and are computed differently), first tick ~1.5 s after the hit on average
DOT_TICK, DOT_TICKS, DOT_FIRST = 63, 9, 1.5
# seconds from a spell resolving to its damage landing (animation), measured in our logs; buffs snapshot on resolution
DELAY = {"Fire III": 1.29, "Fire IV": 1.16, "Despair": 0.49, "Paradox": 0.62, "Blizzard III": 0.89, "Blizzard IV": 1.16,
         "Thunder III": 1.02, "Xenoglossy": 0.62}
CAST = {"Fire III": 3.5, "Fire IV": 2.0, "Despair": 2.0, "Blizzard III": 3.5, "Blizzard IV": 2.0}   # 7.2: Fire IV 2.8 -> 2.0, Despair 3.0 -> 2.0
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
LL_S, LL_SPEED, TRIPLE_S, SWIFT_S, PROC_S = 20, 0.85, 15, 10, 30
CDS = {"Triplecast": (60, 2), "Swiftcast": (60, 1), "Ley Lines": (120, 2), "Manafont": (100, 1), "Amplifier": (120, 1),
       "Transpose": (5, 1), "Tincture": (270, 1)}
OGCD_ORDER = ["Tincture", "Manafont", "Transpose", "Amplifier", "Ley Lines", "Triplecast", "Swiftcast"]
SPEED = 0.928                                       # spell speed factor on casts and GCDs: 2.32 s GCD, the clears since 7.2


class State:
    __slots__ = ("t", "gcd", "el", "hearts", "mp", "mp_t", "poly", "poly_next", "paradox", "fs", "th", "triple", "triple_until",
                 "swift", "ll", "cds", "dot", "dmg", "dotp", "waste", "pot_at", "first", "hist")

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
        return s

    def copy(self):
        c = State.__new__(State)
        for k in State.__slots__: setattr(c, k, getattr(self, k))
        c.cds = dict(self.cds)
        return c

    def key(self):
        r = lambda x: round(x, 1)
        return (r(self.t), r(self.gcd), self.el, self.hearts, self.mp // 400, self.poly, self.paradox, self.fs > self.t, self.th > self.t,
                self.triple if self.triple_until > self.t else 0, self.swift > self.t, r(max(self.ll - self.t, 0)), self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()), r(self.dot[0]) if self.dot else None)

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Polyglot overcapped", "Firestarter unused", "Thunderhead unused", "Paradox unused")


def wasted(s, i):
    """Count a resource lost: a Polyglot gained at the cap, or a proc that expired or was overwritten unused."""
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
    if 0 < s.fs <= to: s.fs = -1.0; wasted(s, 1)
    if 0 < s.th <= to: s.th = -1.0; wasted(s, 2)


def charges(s, name, at):
    n, nxt = s.cds[name]
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
    if s.el == 0 and el != 0: s.poly_next = at + POLY_S
    s.el = el


def hit(s, fight, at, potency, name):
    """Damage snapshots buffs when the spell resolves (`at`) and counts when it lands, inside the scored window."""
    if 0 <= at + DELAY.get(name, 0.6) < fight.until: s.dmg += potency * fight.mult(at, s.pot_at)


def dot(s, fight, at):
    """Apply Thunder III's DoT at `at`, replacing the old one (its remaining ticks are lost). Ticks are timed from the
    spell resolving: on average the first lands 1.5 s later, which matches the logged tick counts."""
    if s.dot:
        a, m = s.dot
        lost = sum(1 for k in range(DOT_TICKS) if at <= a + DOT_FIRST + 3 * k < fight.until)
        s.dmg -= lost * DOT_TICK * m; s.dotp -= lost * DOT_TICK * m
    m = fight.mult(at, s.pot_at)
    gain = sum(1 for k in range(DOT_TICKS) if 0 <= at + DOT_FIRST + 3 * k < fight.until) * DOT_TICK * m
    s.dmg += gain; s.dotp += gain
    s.dot = (at, m)


# --- actions -------------------------------------------------------------------------------------------------------

def speed(s, at):
    return SPEED * (LL_SPEED if s.ll > at else 1.0)


def cast_time(s, name, at):
    """Cast time after Firestarter, Swiftcast, Triplecast and the fast-cast of Fire III in UI3 / Blizzard III in AF3;
    plus which buff it consumes."""
    if name not in CAST: return 0.0, None
    if name == "Fire III" and s.fs > at: return 0.0, "fs"
    if s.swift > at: return 0.0, "swift"
    if s.triple > 0 and s.triple_until > at: return 0.0, "triple"
    c = CAST[name] * speed(s, at)
    if (name == "Fire III" and s.el == -3) or (name == "Blizzard III" and s.el == 3): c *= 0.5
    return c, None


def mp_cost(s, name):
    """Fire spells cost double in Astral Fire unless an Umbral Heart covers it; ice spells are free in Umbral Ice and,
    as the logs show (Blizzard III cast at 0 MP right after Despair), from Astral Fire too; Paradox is free in ice."""
    if name == "Fire IV": return 800 if s.el <= 0 or s.hearts else 1600
    if name == "Fire III": return 2000 if s.el <= 0 or s.hearts else 4000
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
    if not gcd_legal(s, name, start): return None
    cast, used = cast_time(s, name, start)
    if s.first: start = SLIDE - cast; s.first = False         # the opener is pre-cast to land at 0:00
    if cast and fight.moving(start, start + cast - SLIDE): return None
    snap, free, nxt = gcd_times(start, cast, BASE_GCD * speed(s, start))
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
    if name == "Ley Lines": return s.ll <= at
    if name == "Triplecast": return not (s.triple > 0 and s.triple_until > at)
    if name == "Swiftcast": return s.swift <= at
    if name == "Tincture": return fight.pot and s.pot_at is None
    return True


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, at)
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
    elif name == "Ley Lines": s.ll = at + LL_S
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
            for g in GCDS:
                n = do_gcd(c, fight, g)
                if n is None: continue
                if combo and ("Swiftcast" in combo or "Triplecast" in combo) and g not in CAST: continue   # only spend instants on casts
                any_gcd = True
                out.append(n)
            if not any_gcd and not combo:                          # nothing castable now (moving): wait a little
                w = c.copy(); w.t = w.gcd = max(c.t, c.gcd) + 0.5; w.log(c.t, "(wait)"); out.append(w)
    return out


VALUE = dict(mp=0.06, poly=600, paradox=250, fs=200, th=150, triple=150, hearts=60)
RATE = 220                                            # potency per second, to compare states at slightly different times


def held(s):
    v = VALUE["poly"] * s.poly + VALUE["paradox"] * s.paradox + VALUE["fs"] * (s.fs > s.t) + VALUE["th"] * (s.th > s.t)
    v += VALUE["triple"] * (s.triple if s.triple_until > s.t else 0) + VALUE["hearts"] * s.hearts
    return v + VALUE["mp"] * s.mp * (1 if s.el > 0 else 0.5)


def rank(s, fight):
    return s.dmg + held(s) - RATE * s.t


def final(s, fight):
    return s.dmg + (held(s) if fight.carry else 0)
