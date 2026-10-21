"""Monk at level 90, Dawntrail patch 7.05 and later (no single-target change since), single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/monk) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values; the level-90 ones come from the guide's traits: Melee Mastery (84) sets
Bootshine 220, True Strike 300, Snap Punch 270, Twin Snakes 380, Demolish 320, Dragon Kick 280 and The Forbidden
Chakra 400; Melee Mastery II (94) raises Twin Snakes, Demolish, Dragon Kick, Six-sided Star and Phantom Rush beyond
P12S. Leaping Opo, Rising Raptor, Pouncing Coeurl and Elixir Burst are level 92, Wind's and Fire's Reply 96 and 100.
PENDING marks the values the guide doesn't give at level 90; they are to be measured from the logs (calibrate.py).

Forms: an opo-opo action (Bootshine, Dragon Kick) leads to raptor form, a raptor action (True Strike, Twin Snakes) to
coeurl, a coeurl action (Snap Punch, Demolish) back to opo-opo. Raptor and coeurl actions need their form; Formless
Fist (Form Shift, any Masterful Blitz) and Perfect Balance stand in for any form, and count as it for the form bonuses
(Bootshine's sure critical hit, Dragon Kick's Opo-opo's Fury). Fury: Dragon Kick +200 to the next Bootshine, Twin
Snakes +200 to the next True Strike, Demolish two stacks of +150 for Snap Punch.

Perfect Balance: three form actions in any order, each adding the beast chakra of the form it leads to (opo-opo action:
opo-opo chakra, and so on). Masterful Blitz then: three alike, Elixir Field (Lunar Nadi); three distinct, Rising Phoenix
(Solar Nadi); two kinds, Celestial Revolution (Lunar, or Solar if Lunar is open); both Nadi, Phantom Rush (closes both).

Chakra: a weaponskill that crits opens one (Bootshine in opo-opo form always does); the search counts the expected
CRIT of one per weaponskill, a replay of a log its actual crits. Under Meditative Brotherhood each own weaponskill opens
one more and every party member's weaponskill or spell has a 20% chance (PARTY_CHAKRA a second, a full party assumed,
as Reaper's Plentiful Harvest assumes eight stacks). Brotherhood lets ten be open; The Forbidden Chakra spends five.

Positionals: Snap Punch (flank) and Demolish (rear) gain 60 potency from the right side; inside the fight's `pinned`
windows only True North gets it. Reach: every weaponskill and The Forbidden Chakra need the player beside Athena
(Elixir Field and Rising Phoenix hit 5 y around the player: counted as melee); Enlightenment (10 y line), the
meditations and Form Shift work from anywhere. See jobs/rpr.py for the away windows.
"""
import itertools, math
from engine import ANIM_LOCK, BASE_GCD, settle

POTENCY = {"Bootshine": (220, 420), "True Strike": (300, 500), "Snap Punch": (270, 420),      # (plain, with Fury)
           "Dragon Kick": 280, "Twin Snakes": 380, "Demolish": 320,
           "Shadow of the Destroyer": 120, "Four-point Fury": 140, "Rockbreaker": 150,     # AoE: only in replays
           "Elixir Field": 800, "Rising Phoenix": 900, "Celestial Revolution": 600,
           "Phantom Rush": 1150,                    # PENDING: 1,500 at level 94 (Melee Mastery II); 1,150 is Endwalker's
           "Six-sided Star": 710,                   # PENDING: 780 at level 94 (Melee Mastery II)
           "The Forbidden Chakra": 400, "Enlightenment": 160}
SSS_CHAKRA = 80                                 # Six-sided Star: +80 a chakra open, closing them all
POSITIONAL = 60                                 # Snap Punch from the flank, Demolish from the rear
# auto-attacks: fist weapons have a 2.56 s delay; melee autos are 90 potency per 3 s of delay, and Greased Lightning
# shortens the delay (not the damage). PENDING: measure in the logs, as for Reaper.
AUTO, AUTO_DELAY = 77, 2.56 * 0.8
DELAY = {}                                      # PENDING: seconds from execution to the damage landing (0.6 by default)
HASTE = 0.8                                     # Enhanced Greased Lightning III: weaponskill recast -20%
WEAVE_SLACK = 0.05                              # a double weave in a 1.94 s GCD clips it by 0.01 s: allowed
SSS_RECAST = 4.0                                # Six-sided Star, before skill speed and Greased Lightning (PENDING: check)
RIDDLE_OF_FIRE, BROTHERHOOD = 1.15, 1.05
FIRE_S, BH_S, WIND_S, PB_S, FORM_S, FORMLESS_S, TN_S = 20, 20, 15, 20, 30, 30, 10
CRIT = 0.25                                     # the player's critical-hit rate: chakra per weaponskill (dps.py sets it)
PARTY_CHAKRA = 7 * 0.20 / 2.45                  # PENDING: seven party members, a GCD each ~2.45 s, 20% each
CDS = {"Perfect Balance": (40, 2), "Riddle of Fire": (60, 1), "Brotherhood": (120, 1), "Riddle of Wind": (90, 1),
       "True North": (45, 2), "Chakra": (1, 1), "Tincture": (270, 1)}
KIND = {"Bootshine": "o", "Dragon Kick": "o", "Shadow of the Destroyer": "o", "True Strike": "r", "Twin Snakes": "r",
        "Four-point Fury": "r", "Snap Punch": "c", "Demolish": "c", "Rockbreaker": "c"}
NEXT = {"o": "r", "r": "c", "c": "o"}
BLITZ = ("Elixir Field", "Rising Phoenix", "Celestial Revolution", "Phantom Rush")
MEDITATION = ("Forbidden Meditation", "Enlightened Meditation", "Steeled Meditation", "Inspirited Meditation")
GCDS = list(KIND) + list(BLITZ) + ["Six-sided Star", "Form Shift"] + list(MEDITATION)
HARM_GCDS = set(KIND) | set(BLITZ) | {"Six-sided Star"}
MELEE_ACTIONS = HARM_GCDS | {"The Forbidden Chakra"}
OGCD_ORDER = ["Tincture", "Brotherhood", "Riddle of Fire", "Perfect Balance", "Riddle of Wind", "The Forbidden Chakra",
              "Enlightenment", "True North"]
AUTO_CRIT = {"Bootshine"}                       # dps.py: hits that always crit (in opo-opo form) count at their own gain
SPEED = 0.97                                    # skill speed factor: 2.43 s unhasted, a 1.94 s GCD (PENDING: clears' median)
MELEE = True
LOG_CRIT = None                                 # a replay: {cast time (0.1 s): crit} of the log's weaponskills


class State:
    __slots__ = ("t", "gcd", "form", "form_until", "formless_until", "pb", "pb_until", "beast", "lunar", "solar",
                 "opo", "raptor", "coeurl", "chakra", "ct", "fire_until", "bh_until", "wind_until", "tn_until", "cds",
                 "auto_next", "dmg", "critp", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot", "ai",
                 "mlast", "near")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.form, s.form_until = None, -1.0
        s.formless_until = FORMLESS_S - 3.0         # Form Shift ~3 s before the pull
        s.pb, s.pb_until, s.beast, s.lunar, s.solar = 0, -1.0, (), False, False
        s.opo = s.raptor = s.coeurl = 0
        s.chakra, s.ct = 5.0, 0.0                   # meditated to five before the pull
        s.fire_until = s.bh_until = s.wind_until = s.tn_until = -1.0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.auto_next, s.dmg, s.critp, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, None, True, None
        s.waste = (0, 0.0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0
        s.ai, s.mlast, s.near = 0, -30.0, False
        return s

    def copy(self):
        c = State.__new__(State)
        for k in State.__slots__: setattr(c, k, getattr(self, k))
        c.cds = dict(self.cds)
        return c

    def key(self):
        r = lambda x: round(x, 1)
        left = lambda u: r(max(u - self.t, 0))
        return (r(self.t), r(self.gcd), self.form if self.form_until > self.t else None, left(self.formless_until) > 0,
                self.pb if self.pb_until > self.t else 0, tuple(sorted(self.beast)), self.lunar, self.solar,
                self.opo, self.raptor, self.coeurl, round(self.chakra * 4) / 4, left(self.fire_until),
                left(self.bh_until), left(self.wind_until), left(self.tn_until), self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()),
                self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.ai, r(min(self.t - self.mlast, 4)) if self.near else None)

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Fury overcapped", "chakra overcapped", "Perfect Balance stacks dropped")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


def add_chakra(s, at, n):
    cap = 10 if s.bh_until > at else 5
    v = s.chakra + n
    if v > cap: wasted(s, 1, v - cap)
    s.chakra = min(max(cap, s.chakra), v)          # what Brotherhood opened beyond five stays open


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, own Riddle of Fire and Brotherhood."""
    return (fight.mult(at, s.pot_at) * (RIDDLE_OF_FIRE if s.fire_until > at else 1) *
            (BROTHERHOOD if s.bh_until > at else 1))


def advance(s, fight, to):
    """Auto-attacks up to `to`, the party's chakra under Meditative Brotherhood, statuses that lapse."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + AUTO_DELAY * (0.5 if s.wind_until > a else 1)
    if to > s.ct:
        d = min(to, s.bh_until) - max(s.ct, s.bh_until - BH_S)
        if d > 0: add_chakra(s, min(to, s.bh_until) - 1e-6, PARTY_CHAKRA * d)
        s.ct = to
    if s.pb and s.pb_until <= to: wasted(s, 2, s.pb); s.pb = 0


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


def cd_name(name):
    return "Chakra" if name in ("The Forbidden Chakra", "Enlightenment") else name


def hit(s, fight, at, potency, name, crit=False):
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land):
        d = potency * mult(s, fight, at)
        s.dmg += d
        if crit: s.critp += d


def flank_rear(s, fight, at):
    """Can the player take a positional: True North, or a spot the strategy doesn't fix."""
    return s.tn_until > at or not any(a <= at < b for a, b in fight.pinned)


def reach(s, fight, t, commit=True):
    """May a melee action land at t (see rpr.reach)."""
    W, i = fight.away, s.ai
    while i < len(W) and W[i].lo < t:
        w = W[i]
        if min(t, w.hi) - max(s.mlast, w.lo) >= w.need - 1e-9: i += 1; continue
        if w.hi - max(t, w.lo) >= w.need - 1e-9: break
        return False
    if commit: s.ai, s.mlast = i, t
    return True


def out_of_reach(s, fight, t):
    for w in fight.away[s.ai:]:
        if w.lo > t: break
        a = max(s.mlast, w.lo)
        if a <= t < a + w.need: return True
    return False


def away_soon(s, fight, t, ahead=5.0):
    return any(w.lo <= t + ahead and w.hi > t for w in fight.away[s.ai:])


# --- actions -------------------------------------------------------------------------------------------------------

def balanced(s, at):
    return s.pb > 0 and s.pb_until > at


def in_form(s, kind, at):
    return balanced(s, at) or s.formless_until > at or (s.form == kind and s.form_until > at)


def blitz(s):
    """The Masterful Blitz the beast chakra make, or None."""
    if len(s.beast) < 3: return None
    if s.lunar and s.solar: return "Phantom Rush"
    return {1: "Elixir Field", 2: "Celestial Revolution", 3: "Rising Phoenix"}[len(set(s.beast))]


def gcd_legal(s, name, at):
    if name in KIND: return KIND[name] == "o" or in_form(s, KIND[name], at)
    if name in BLITZ: return blitz(s) == name
    if name in MEDITATION: return s.chakra < 5 - 1e-9 or at < 0
    return True                                 # Six-sided Star, Form Shift


def potency(s, fight, name, at):
    """(potency, sure crit)."""
    p = POTENCY[name]
    if name == "Bootshine": return p[s.opo > 0], in_form(s, "o", at)
    if name == "True Strike": return p[s.raptor > 0], False
    if name == "Snap Punch": return p[s.coeurl > 0] + POSITIONAL * flank_rear(s, fight, at), False
    if name == "Demolish": return p + POSITIONAL * flank_rear(s, fight, at), False
    if name == "Shadow of the Destroyer": return p, in_form(s, "o", at)
    if name == "Six-sided Star": return p + SSS_CHAKRA * s.chakra, False
    return p, False


def crit_chance(at):
    if LOG_CRIT is not None: return float(LOG_CRIT.get(round(at, 1), False))
    return CRIT


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    s = s.copy()
    if s.first and name in ("Form Shift",) + MEDITATION:     # before the pull: out of combat, no GCD taken
        if name == "Form Shift": s.formless_until = FORMLESS_S - 3.0
        else: s.chakra = 5.0
        s.log(-1.0, name, gauge(s, "pre-pull"))
        return s
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    harm = name in HARM_GCDS
    if harm and (not fight.targetable(start) or fight.next_down(start) <= start): return None
    if name in MELEE_ACTIONS and not reach(s, fight, start): return None
    s.first = False
    recast = (SSS_RECAST if name == "Six-sided Star" else BASE_GCD) * SPEED * HASTE
    snap, free, nxt = start, start + ANIM_LOCK, start + recast
    crit = False
    if harm:
        p, crit = potency(s, fight, name, snap)
        hit(s, fight, snap, p, name, crit)
    if name in KIND:
        k = KIND[name]
        if name == "Bootshine": s.opo = 0
        elif name == "True Strike": s.raptor = 0
        elif name == "Snap Punch": s.coeurl = max(0, s.coeurl - 1)
        elif name == "Dragon Kick" and in_form(s, "o", snap):
            if s.opo: wasted(s, 0)
            s.opo = 1
        elif name == "Twin Snakes":
            if s.raptor: wasted(s, 0)
            s.raptor = 1
        elif name == "Demolish":
            if s.coeurl: wasted(s, 0, s.coeurl)
            s.coeurl = 2
        if balanced(s, snap):
            s.pb -= 1; s.beast += (k,)
            if not s.pb: s.pb_until = -1.0
        s.formless_until = -1.0
        s.form, s.form_until = NEXT[k], snap + FORM_S
    elif name in BLITZ:
        if name == "Phantom Rush": s.lunar = s.solar = False
        elif name == "Elixir Field": s.lunar = True
        elif name == "Rising Phoenix": s.solar = True
        elif s.lunar: s.solar = True
        else: s.lunar = True
        s.beast = ()
        s.formless_until = snap + FORMLESS_S
    elif name == "Six-sided Star": s.chakra = 0.0
    elif name == "Form Shift": s.formless_until = snap + FORMLESS_S
    elif name in MEDITATION: add_chakra(s, snap, 1)
    if harm:                                    # chakra: a critical weaponskill, and Meditative Brotherhood
        n = (0.0 if name == "Six-sided Star" else 1.0 if crit else crit_chance(snap)) + (s.bh_until > snap)
        add_chakra(s, snap, n)
    s.t, s.gcd = free, nxt
    s.near = away_soon(s, fight, s.t)
    s.log(start, name, gauge(s, ""))
    return s


def gauge(s, how):
    form = "formless" if s.formless_until > s.t else (s.form or "-") if s.form_until > s.t else "-"
    return (f"{how:<8} {form:<8} fury {s.opo}{s.raptor}{s.coeurl}  chakra {s.chakra:4.1f}  "
            f"beast {''.join(s.beast):<3} {'L' if s.lunar else '-'}{'S' if s.solar else '-'}" +
            (f"  PB {s.pb}" if balanced(s, s.t) else ""))


def ogcd_legal(s, name, at, fight, policy=True):
    if name in CDS or cd_name(name) in CDS:
        n, _ = charges(s, cd_name(name), at)
        if n < 1: return False
    if name in ("The Forbidden Chakra", "Enlightenment"):
        if s.chakra < 5 - 1e-6: return False
        return name == "The Forbidden Chakra" or not policy or not reach(s, fight, at, commit=False)
    if name == "Perfect Balance": return at >= 0 and not s.beast and not (policy and balanced(s, at))
    if name in ("Riddle of Fire", "Brotherhood", "Riddle of Wind"): return at >= 0
    if name == "True North": return not policy or (s.tn_until <= at and (not flank_rear(s, fight, at + 2.0) or
                                                                         not flank_rear(s, fight, at + 4.0)))
    if name == "Tincture": return fight.pot and s.pot_at is None
    return False


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in MELEE_ACTIONS and not reach(s, fight, at): return None
    if name in ("The Forbidden Chakra", "Enlightenment") and not fight.targetable(at): return None
    use_cd(s, cd_name(name), at)
    if name in ("The Forbidden Chakra", "Enlightenment"):
        hit(s, fight, at, POTENCY[name], name); s.chakra -= 5
    elif name == "Perfect Balance": s.pb, s.pb_until = 3, at + PB_S
    elif name == "Riddle of Fire": s.fire_until = at + FIRE_S
    elif name == "Brotherhood": s.bh_until = at + BH_S; s.ct = max(s.ct, at)
    elif name == "Riddle of Wind": s.wind_until = at + WIND_S
    elif name == "True North": s.tn_until = at + TN_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.near = away_soon(s, fight, s.t)
    s.log(at, name, gauge(s, ""))
    return s


SEARCH_GCDS = ["Bootshine", "Dragon Kick", "True Strike", "Twin Snakes", "Snap Punch", "Demolish"]


def candidates(c, fight, now):
    """The GCDs worth trying next: the form actions, the Blitz the beast chakra make, Six-sided Star before the boss
    goes away (or the window ends), and the meditations and Form Shift only when nothing can hit or a stretch out of
    reach is near."""
    out = list(SEARCH_GCDS)
    b = blitz(c)
    if b: out.append(b)
    if min(fight.next_down(now), fight.until) - now < 8 or c.near: out.append("Six-sided Star")
    if not fight.targetable(now) or c.near or not reach(c, fight, now, commit=False):
        out += ["Forbidden Meditation", "Form Shift"]
    return out


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD."""
    slots = int((s.gcd - s.t + WEAVE_SLACK) / ANIM_LOCK + 1e-6)
    ready = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready, k):
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, fight, now):
                # True North only before the Snap Punch or Demolish it is for: anything else only multiplies the states
                if "True North" in combo and g not in ("Snap Punch", "Demolish"): continue
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = any_gcd or g in HARM_GCDS
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                # boss away: straight to when it is back, or to just before (a Form Shift to come back formless)
                back = fight.back_up(now)
                for to in ({back} | ({back - 2.5} if back - 2.5 > now + 0.5 else set())) if down else {now + 0.5}:
                    w = c.copy(); w.t = w.gcd = to
                    w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# what holding a resource is worth over the GCDs it displaces: a chakra is a fifth of a Forbidden Chakra; a Fury its
# bonus on the action it raises; a beast chakra a third of what a Blitz deals over a form action; a Nadi half of what
# Phantom Rush deals over the Blitz that opens it; a Perfect Balance stack a beast chakra to come.
VALUE = dict(chakra=70, opo=170, raptor=170, coeurl=130, beast=180, nadi=150, pb=150, formless=60)
RATE = 270                                            # potency per second, to compare states at slightly different times
HEURISTICS = [(r, 1.0, 0.0) for r in (240, 270, 300, 330)]
WIDTH = 3000
MOVE_WEIGHT = 0.0


def held(s):
    t = s.t
    v = VALUE["chakra"] * s.chakra + VALUE["opo"] * s.opo + VALUE["raptor"] * s.raptor + VALUE["coeurl"] * s.coeurl
    v += VALUE["beast"] * len(s.beast) + VALUE["nadi"] * (s.lunar + s.solar)
    v += VALUE["pb"] * (s.pb if balanced(s, t) else 0) + VALUE["formless"] * (s.formless_until > t)
    return v


def rank(s, fight):
    return s.dmg + held(s) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the swings still to come before the window ends
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Monk", "2025-01-01"         # single-target potencies unchanged since 7.05 (patchnotes.py)
OGCDS = set(OGCD_ORDER)
REFERENCE = ("The Forbidden Chakra", 400)           # set at level 84 by Melee Mastery, untouched by patches
CAST = {}


def cast_time(s, name, at):
    return 0.0, None


def prepare(p):
    """A replay of log p opens chakra on the log's own critical weaponskills."""
    global LOG_CRIT
    n = p["names"]
    hits = sorted((x["t"], n[str(x["abilityGameID"])], x.get("hitType") == 2) for x in p["hits"]
                  if x["type"] == "damage" and not x.get("tick"))
    LOG_CRIT = {}
    for x in p["casts"]:
        name = n[str(x["abilityGameID"])]
        if x["type"] == "cast" and name in HARM_GCDS:
            h = next((c for t, a, c in hits if a == name and 0 <= t - x["t"] < 1.5), False)
            LOG_CRIT[round(x["t"], 1)] = h


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(form=s.form if s.form_until > t else None, formless=s.formless_until > t,
                pb=s.pb if balanced(s, t) else 0, beast="".join(s.beast), lunar=s.lunar, solar=s.solar,
                fury=(s.opo, s.raptor, s.coeurl), chakra=round(s.chakra, 2))


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name in KIND: s.formless_until = start + 1
    if name in BLITZ:
        s.beast = {"Elixir Field": ("o",) * 3, "Rising Phoenix": ("o", "r", "c"), "Celestial Revolution": ("o", "o", "r"),
                   "Phantom Rush": ("o", "r", "c")}[name]
        if name == "Phantom Rush": s.lunar = s.solar = True
        elif name == "Rising Phoenix" and s.lunar and s.solar: s.solar = False
        elif name == "Elixir Field" and s.lunar and s.solar: s.lunar = False
    if name in MEDITATION: s.chakra = min(s.chakra, 4)
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if name in ("The Forbidden Chakra", "Enlightenment"): s.chakra = max(s.chakra, 5)
    if name == "Perfect Balance": s.beast = ()
    s.cds[cd_name(name)] = (1, None)
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Positionals are grouped by True North,
    the one way the log shows one was surely taken; without it the model's potency is the miss."""
    if name in ("Bootshine", "True Strike", "Snap Punch"):
        fury = (s.opo if name == "Bootshine" else s.raptor if name == "True Strike" else s.coeurl) > 0
        p = POTENCY[name][fury]
        g = "fury" if fury else "plain"
        if name == "Bootshine" and in_form(s, "o", t): g += " sure crit"
        if name == "Snap Punch":
            tn = s.tn_until > t; g += " TN" if tn else ""; p += POSITIONAL * tn
        return g, p
    if name == "Demolish":
        tn = s.tn_until > t
        return ("TN" if tn else ""), POTENCY[name] + POSITIONAL * tn
    if name == "Dragon Kick": return ("opo-opo form" if in_form(s, "o", t) else "no form"), POTENCY[name]
    if name == "Six-sided Star": return f"{s.chakra:.0f} chakra", potency(s, fight, name, t)[0]
    if name in POTENCY: return "", POTENCY[name]
    return None


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Riddle of Fire, their Brotherhood):
    FFLogs counts every damage-up on the hit, so dividing it out takes these away too. PENDING: check the status ids
    (Riddle of Fire 1181, Brotherhood 1185) in the logs."""
    b = h.get("buffs") or ""
    m = RIDDLE_OF_FIRE if "1001181." in b else 1.0
    if "1001185." in b:
        n = p["names"]
        if any(x["type"] == "cast" and n[str(x["abilityGameID"])] == "Brotherhood" and 0 <= h["t"] - x["t"] < BH_S + 1
               for x in p["casts"]): m *= BROTHERHOOD
    return m
