"""Monk at level 90, Dawntrail patch 7.05 and later (no single-target change since), single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/monk) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values; the level-90 ones come from the guide's traits: Melee Mastery (84) sets
Bootshine 220, True Strike 300, Snap Punch 270, Twin Snakes 380, Demolish 320, Dragon Kick 280 and The Forbidden
Chakra 400; Melee Mastery II (94) raises Twin Snakes, Demolish, Dragon Kick, Six-sided Star and Phantom Rush beyond
P12S. Leaping Opo, Rising Raptor, Pouncing Coeurl and Elixir Burst are level 92, Wind's and Fire's Reply 96 and 100.
The guide doesn't give Phantom Rush and Six-sided Star at level 90, nor the auto-attacks, hit delays and recasts: those
were measured in the logs (2026-10-22: 19 benchmark clears and our 64 clean pulls; scratch/mnk).

Forms: an opo-opo action (Bootshine, Dragon Kick) leads to raptor form, a raptor action (True Strike, Twin Snakes) to
coeurl, a coeurl action (Snap Punch, Demolish) back to opo-opo. Raptor and coeurl actions need their form; Formless
Fist (Form Shift, any Masterful Blitz) and Perfect Balance stand in for any form, and count as it for the form bonuses
(Bootshine's sure critical hit: every Bootshine under either crits in the logs; Dragon Kick's Opo-opo's Fury). Fury: Dragon Kick +200 to the next Bootshine, Twin
Snakes +200 to the next True Strike, Demolish two stacks of +150 for Snap Punch.

Perfect Balance: three form actions in any order, each adding the beast chakra of the form it leads to (opo-opo action:
opo-opo chakra, and so on). It takes away the form held (and Formless Fist) and its actions grant none, so after it only
an opo-opo action or a Masterful Blitz follows (the logs: no form status in 1,552 endings; xivintheshell agrees). Form Shift under it grants no Formless Fist
(xivintheshell's rule; no logged Form Shift falls inside one). Masterful Blitz then: three alike, Elixir Field (Lunar Nadi); three distinct, Rising Phoenix
(Solar Nadi); two kinds, Celestial Revolution (Lunar, or Solar if Lunar is open); both Nadi, Phantom Rush (closes both).

Chakra: a weaponskill that crits opens one (Bootshine in opo-opo form always does); the search counts the expected
CRIT of one per weaponskill, a replay of a log its actual crits. Under Meditative Brotherhood each own weaponskill opens
one more and every party member's weaponskill or spell has a 20% chance (PARTY_CHAKRA a second, a full party assumed,
as Reaper's Plentiful Harvest assumes eight stacks). Brotherhood lets ten be open; The Forbidden Chakra spends five.
The logs bear the expected rate out (0.57 a second in our windows, 0.51 in the clears), but a window's real share swings
from about 0.4 to 0.7, so a replay of a log at the expected rate finds some Forbidden Chakras a chakra or two short.

Positionals: Snap Punch (flank) and Demolish (rear) gain 60 potency from the right side; inside the fight's `pinned`
windows only True North gets it. Reach: every weaponskill and The Forbidden Chakra need the player beside Athena
(Elixir Field and Rising Phoenix hit 5 y around the player: counted as melee); Enlightenment (10 y line), the
meditations and Form Shift work from anywhere. See jobs/rpr.py for the away windows.
"""
import itertools, math
import engine
from engine import ANIM_LOCK, BASE_GCD, SlotState, cd_key, recast, settle
from jobs._common import away_soon, cast_label, cooldowns, flank_rear, no_cast as cast_time, out_of_reach, reach, wasted

POTENCY = {"Bootshine": (220, 420), "True Strike": (300, 500), "Snap Punch": (270, 420),      # (plain, with Fury)
           "Dragon Kick": 280, "Twin Snakes": 380, "Demolish": 320,
           "Shadow of the Destroyer": 120, "Four-point Fury": 140, "Rockbreaker": 150,     # AoE: only in replays
           "Elixir Field": 800, "Rising Phoenix": 900, "Celestial Revolution": 600,
           "Phantom Rush": 1400,                    # logs: 1,400-1,415 (1,500 at level 94, Melee Mastery II)
           "Six-Sided Star": 710,                   # logs: 695 with no chakra open, 874 with two (780 at level 94)
           "The Forbidden Chakra": 400, "Enlightenment": 160}
SSS_CHAKRA = 80                                 # Six-sided Star: +80 a chakra open, closing them all
POSITIONAL = 60                                 # Snap Punch from the flank, Demolish from the rear
# auto-attacks: 78 potency (logs, scaled to The Forbidden Chakra) every 2.05 s, 1.03 s under Riddle of Wind
AUTO, AUTO_DELAY = 78, 2.05
# seconds from executing an action to its damage landing, the logs' medians; buffs snapshot on execution
DELAY = {"Bootshine": 1.11, "True Strike": 0.80, "Snap Punch": 0.76, "Dragon Kick": 1.29, "Twin Snakes": 0.85,
         "Demolish": 1.60, "Elixir Field": 1.07, "Rising Phoenix": 0.76, "Celestial Revolution": 0.89,
         "Phantom Rush": 0.40, "Six-Sided Star": 0.62, "The Forbidden Chakra": 1.47}
HASTE = 0.8                                     # Enhanced Greased Lightning III: weaponskill recast -20%
WEAVE_SLACK = 0.05                              # a double weave in a 1.94 s GCD clips it by 0.01 s: allowed
SSS_RECAST = 4.0                                # Six-sided Star: skill speed shortens it, Greased Lightning doesn't (3.9 s logged)
MEDITATION_RECAST = 1.0                         # the meditations: 1 s, fixed (0.98-0.99 s between them in the logs)
RIDDLE_OF_FIRE, BROTHERHOOD = 1.15, 1.05
BH_S, PB_S, FORM_S, FORMLESS_S = 20, 20, 30, 30
# statuses run ~0.5-0.8 s past their tooltip from the cast (their clock starts as the action lands; logged ends after
# the cast: Riddle of Fire 20.73-20.82, Riddle of Wind 15.78-15.82, True North 10.52-10.54); Brotherhood is logged on
# landing, 0.76 s after the cast, and lasts its 20 from there (calibrate's status check, scratch/timing/status_len.py)
FIRE_S, WIND_S, TN_S, BH_LAG = 20.75, 15.8, 10.5, 0.76
CRIT = 0.25                                     # the player's critical-hit rate: chakra per weaponskill (dps.py sets it)
PARTY_CHAKRA = 7 * 0.20 / 2.45                  # seven party members, a GCD each ~2.45 s, 20% each (logs: 0.51-0.57)
CDS = {"Perfect Balance": (40, 2), "Riddle of Fire": (60, 1), "Brotherhood": (120, 1), "Riddle of Wind": (90, 1),
       "True North": (45, 2), "Chakra": (1, 1), "Tincture": (270, 1)}
charges, use_cd, full_since, capped, ready, at = cooldowns(__name__)
KIND = {"Bootshine": "o", "Dragon Kick": "o", "Shadow of the Destroyer": "o", "True Strike": "r", "Twin Snakes": "r",
        "Four-point Fury": "r", "Snap Punch": "c", "Demolish": "c", "Rockbreaker": "c"}
NEXT = {"o": "r", "r": "c", "c": "o"}
BLITZ = ("Elixir Field", "Rising Phoenix", "Celestial Revolution", "Phantom Rush")
MEDITATION = ("Forbidden Meditation", "Enlightened Meditation", "Steeled Meditation", "Inspirited Meditation")
GCDS = list(KIND) + list(BLITZ) + ["Six-Sided Star", "Form Shift"] + list(MEDITATION)
HARM_GCDS = set(KIND) | set(BLITZ) | {"Six-Sided Star"}
MELEE_ACTIONS = HARM_GCDS | {"The Forbidden Chakra"}
OGCD_ORDER = ["Tincture", "Brotherhood", "Riddle of Fire", "Perfect Balance", "Riddle of Wind", "The Forbidden Chakra",
              "Enlightenment", "True North"]
AUTO_CRIT = {"Bootshine"}                       # dps.py: hits that always crit (in opo-opo form) count at their own gain
SPEED = 0.97                                    # skill speed factor: 2.43 s unhasted, a 1.94 s GCD (logs: 1.92-1.96)
MELEE = True
LOG_CRIT = None                                 # a replay: {cast time (0.1 s): crit} of the log's weaponskills


class State(SlotState):
    __slots__ = ("t", "gcd", "form", "form_until", "formless_until", "pb", "pb_until", "beast", "lunar", "solar",
                 "opo", "raptor", "coeurl", "chakra", "ct", "fire_until", "bh_until", "wind_until", "tn_until", "cds",
                 "auto_next", "dmg", "critp", "plainp", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot", "ai",
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
        s.auto_next, s.dmg, s.critp, s.plainp, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, 0.0, None, True, None
        s.waste = (0, 0.0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0
        s.ai, s.mlast, s.near = 0, -30.0, False
        return s

    def key(self):
        return (round(self.t, 1), round(self.gcd, 1), self.form if self.form_until > self.t else None,
                round(max(self.formless_until - self.t, 0), 1) > 0, self.pb if self.pb_until > self.t else 0,
                tuple(sorted(self.beast)), self.lunar, self.solar, self.opo, self.raptor, self.coeurl,
                round(self.chakra * 4) / 4, round(max(self.fire_until - self.t, 0), 1),
                round(max(self.bh_until - self.t, 0), 1), round(max(self.wind_until - self.t, 0), 1),
                round(max(self.tn_until - self.t, 0), 1), self.pot_at is None, cd_key(self.cds), self.mvi,
                round(min(self.acc, 4.0) * 2) / 2, self.ai,
                round(min(self.t - self.mlast, 4), 1) if self.near else None)



WASTE = ("Fury overcapped", "chakra overcapped", "Perfect Balance stacks dropped")


def brotherhood(s, at):
    return s.bh_until - BH_S <= at < s.bh_until


def add_chakra(s, at, n):
    cap = 10 if brotherhood(s, at) else 5
    v = s.chakra + n
    if v > cap: wasted(s, 1, v - cap)
    s.chakra = min(max(cap, s.chakra), v)          # what Brotherhood opened beyond five stays open


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, own Riddle of Fire and Brotherhood."""
    return (fight.mult(at, s.pot_at) * (RIDDLE_OF_FIRE if s.fire_until > at else 1) *
            (BROTHERHOOD if brotherhood(s, at) else 1))


def advance(s, fight, to):
    """Auto-attacks up to `to`, the party's chakra under Meditative Brotherhood, statuses that lapse."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + AUTO_DELAY * (0.5 if s.wind_until > a else 1)
    if to > s.ct:
        d = min(to, s.bh_until) - max(s.ct, s.bh_until - BH_S)
        if d > 0:
            at, n = min(to, s.bh_until) - 1e-6, PARTY_CHAKRA * d
            add_chakra(s, at, n if engine.DRAW is None else engine.drawn_count(n, at, "party chakra"))
        s.ct = to
    if s.pb and s.pb_until <= to: wasted(s, 2, s.pb); s.pb = 0


def cd_name(name):
    return "Chakra" if name in ("The Forbidden Chakra", "Enlightenment") else name


def hit(s, fight, at, potency, name, crit=False, drawn=None):
    """`drawn`: with procs drawn, the weaponskill's own crit (its chakra's, crit_chance): the damage stays expected, but
    the hit is booked as a sure crit (critp) or a plain one (plainp), so tools/gear/ceiling.py prices the luck that
    gave the chakra with it."""
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land):
        d = potency * mult(s, fight, at)
        if crit: d *= fight.sure(at)                        # raid crit buffs turn into damage on a sure crit
        s.dmg += d
        if crit or drawn: s.critp += d
        elif drawn is not None: s.plainp += d


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
    if name == "Six-Sided Star": return p + SSS_CHAKRA * s.chakra, False
    return p, False


def crit_chance(at):
    """A weaponskill's chakra from its own crit: the log's in a replay, drawn (engine.DRAW: montecarlo.py), else the
    expected CRIT."""
    if LOG_CRIT is not None: return float(LOG_CRIT.get(round(at, 1), False))
    if engine.DRAW is not None: return float(engine.drawn(CRIT, at, "crit"))
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
    rc = (MEDITATION_RECAST if name in MEDITATION else recast(SSS_RECAST, SPEED) if name == "Six-Sided Star"
          else recast(BASE_GCD, SPEED, HASTE))
    snap, free, nxt = start, start + ANIM_LOCK, start + rc
    crit = False
    if harm:
        p, crit = potency(s, fight, name, snap)
        drawn = (engine.drawn(CRIT, snap, "crit") if engine.DRAW is not None and LOG_CRIT is None and not crit
                 and name != "Six-Sided Star" else None)
        hit(s, fight, snap, p, name, crit, drawn)
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
        if balanced(s, snap):                       # no form: Perfect Balance took it, and its actions grant none
            s.pb -= 1; s.beast += (k,)
            if not s.pb: s.pb_until = -1.0
        else:
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
    elif name == "Six-Sided Star": s.chakra = 0.0
    elif name == "Form Shift" and not balanced(s, snap):     # takes the form; Formless Fist (none under PB)
        s.form_until, s.formless_until = -1.0, snap + FORMLESS_S
    elif name in MEDITATION: add_chakra(s, snap, 1)
    if harm:                                    # chakra: a critical weaponskill, and Meditative Brotherhood
        n = (0.0 if name == "Six-Sided Star" else 1.0 if crit else crit_chance(snap)) + brotherhood(s, snap)
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
    elif name == "Perfect Balance":                 # takes the form (and Formless Fist) away
        s.pb, s.pb_until = 3, at + PB_S
        s.form_until = s.formless_until = -1.0
    elif name == "Riddle of Fire": s.fire_until = at + FIRE_S
    elif name == "Brotherhood": s.bh_until = at + BH_LAG + BH_S; s.ct = max(s.ct, at)
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
    goes away (or the window ends: elsewhere it about ties the rotation per second and breaks its order, so players
    keep it for there), and the meditations and Form Shift only when nothing can hit or a stretch out of reach is near
    (Form Shift once Formless Fist is nearly out)."""
    out = list(SEARCH_GCDS)
    b = blitz(c)
    if b: out.append(b)
    if min(fight.next_down(now), fight.until) - now < 8: out.append("Six-Sided Star")
    if not fight.targetable(now) or c.near or not reach(c, fight, now, commit=False):
        out.append("Forbidden Meditation")
        if c.formless_until - now < 5 and not balanced(c, now): out.append("Form Shift")
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
            # do_gcd's first steps (advance, settle: idempotent) once for all the GCDs, then only the legal ones tried;
            # not before the pull, where do_gcd plays the pre-pull Form Shift and meditation without them
            b = c
            if not c.first: b = c.copy(); advance(b, fight, now); settle(b, fight, now)
            for g in candidates(c, fight, now):
                # True North only before the Snap Punch or Demolish it is for: anything else only multiplies the states
                if "True North" in combo and g not in ("Snap Punch", "Demolish"): continue
                if b is not c and not gcd_legal(b, g, now): continue
                n = do_gcd(b, fight, g)
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
RATE = 220                                            # potency per second, to compare states at slightly different times
# tune.py (2026-10-22, sweep): VALUE at 0.25-0.6 times is best in M1 (+0.37%), 1.0 in the 0-281 s window, so both;
# +0.11% in M2, the site's slot, which it wasn't tuned on
HEURISTICS = [(165, 0.25, 0.0), (225, 0.6, 0.0), (165, 0.3, 0.0), (200, 1.0, 0.0)]
WIDTH = 3000
SWEEP_WIDTH = 7500                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: +0.22%
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
            h = next((c for t, a, c in hits if a == name and 0 <= t - x["t"] < DELAY.get(name, 0.6) + 0.5), False)
            LOG_CRIT[round(x["t"], 1)] = h


def unprepare():
    """Forget the log (calibrate.prepared): searches and rebuilt rotations use the expected crit rate."""
    global LOG_CRIT
    LOG_CRIT = None


STATUSES = {"Opo-Opo Form": lambda s, t: s.form == "o" and s.form_until > t,
            "Raptor Form": lambda s, t: s.form == "r" and s.form_until > t,
            "Coeurl Form": lambda s, t: s.form == "c" and s.form_until > t,
            "Formless Fist": lambda s, t: s.formless_until > t, "Perfect Balance": balanced,
            "Riddle of Fire": lambda s, t: s.fire_until > t, "Riddle of Wind": lambda s, t: s.wind_until > t,
            "Brotherhood": brotherhood, "True North": lambda s, t: s.tn_until > t}


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
    rec, mx = CDS[cd_name(name)]                   # one charge, the recharge still running (Perfect Balance has two)
    s.cds[cd_name(name)] = (1, charges(s, cd_name(name), t)[1] or (None if mx == 1 else t + rec))
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
    if name == "Six-Sided Star": return f"{s.chakra:.0f} chakra", potency(s, fight, name, t)[0]
    if name in POTENCY: return "", POTENCY[name]
    return None


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Riddle of Fire, their Brotherhood):
    FFLogs counts every damage-up on the hit, so dividing it out takes these away too. Status ids from the logs: Riddle
    of Fire 1181, Brotherhood 1185."""
    b = h.get("buffs") or ""
    m = RIDDLE_OF_FIRE if "1001181." in b else 1.0
    if "1001185." in b:
        n = p["names"]
        if any(x["type"] == "cast" and n[str(x["abilityGameID"])] == "Brotherhood" and 0 <= h["t"] - x["t"] < BH_S + 1
               for x in p["casts"]): m *= BROTHERHOOD
    return m
