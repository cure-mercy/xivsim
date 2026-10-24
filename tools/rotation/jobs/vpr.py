"""Viper at level 90, Dawntrail patch 7.5 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/viper) and the patch notes since 7.0
(patchnotes.py). The guide shows level-100 actions, but no Viper trait above level 90 raises a potency (Melee Mastery
is level 74, Melee Mastery II 84), so its numbers hold at level 90; what level 90 lacks is Uncoiled Twinfang and
Twinblood (92), the fifth Anguine Tribute and Ouroboros (96) and the Legacies (100). 7.05 set most potencies and the
Honed statuses, 7.2 only touched the Legacies, 7.5 raised Vicewinder (540) and the Coils (630 / 680).

FFLogs was down when this was written, so the values were checked in the scorecard's cached damage events
(.cache/acts_*: our groups' 249 pulls by six Vipers, Sep-Oct 2026, and 24 benchmark clears): each player's plain-hit
cluster with Hunter's Instinct divided out and others' raid buffs left out, scaled to Death Rattle (280), matches the
guide within ~1% for every action. FFLogs' bonusPercent tells the positionals apart (a Coil's +50 is 7%; a finisher
with its venom shows 48% with the positional, 40% without).

Dual-wield combo (30 s; Vicewinder, the Coils, Uncoiled Fury and Reawaken's Generations don't break it):
  Steel Fangs / Reaving Fangs -> Hunter's Sting (Hunter's Instinct: +10%, 40 s) -> Flanksting Strike / Flanksbane Fang
                              -> Swiftskin's Sting (Swiftscaled: GCD and auto-attacks 15% faster, 40 s)
                                                                              -> Hindsting Strike / Hindsbane Fang
Steel Fangs grants Honed Reavers (Reaving Fangs 300), Reaving Fangs Honed Steel (Steel Fangs 300). Each finisher (+60
from its side, +10 Serpent Offerings) grants the venom of the next in the cycle Flanksting -> Hindsting -> Flanksbane
-> Hindsbane -> Flanksting (+100), and Death Rattle (an oGCD, lost with the next weaponskill).

Twinblade combo: Vicewinder (40 s, two charges, one Rattling Coil) -> Hunter's Coil and Swiftskin's Coil in either
order (+50 from the flank / rear, +5 Offerings, each refreshes its sting's status); after each Coil, Twinfang Bite and
Twinblood Bite (oGCDs, 120 or 170 with the venom the Coil or the first bite grants, lost with the next weaponskill).
Uncoiled Fury (20 y) spends a Rattling Coil (three at most; Serpent's Ire grants one). Reawaken spends 50 Offerings
or Ready to Reawaken (Serpent's Ire) for four Anguine Tribute: First to Fourth Generation, 680 each in order.

Timing, from the logs: the twinblade GCDs recast in 3.0 s, Uncoiled Fury 3.5 s, Reawaken 2.2 s, the Generations 2.0 s,
everything else 2.5 s, all scaled by skill speed and Swiftscaled (which the GCD granting it doesn't get). Statuses come
on with the cast, after its hit (a Hunter's Sting doesn't get the Hunter's Instinct it grants); Hunter's Instinct and
Swiftscaled are refreshed to 40 s, so both lapse over Palladion.

Positionals and reach as for the Dragoon (jobs/drg.py): the finishers and Coils need True North in the fight's `pinned`
spans; melee actions (the 3 y weaponskills, and Death Rattle, the bites and Reawaken at 5 y) need the player beside
Athena; Uncoiled Fury and Writhing Snap reach from anywhere.
"""
import itertools
from engine import ANIM_LOCK, BASE_GCD, recast, settle

POTENCY = {"Steel Fangs": (200, 300), "Reaving Fangs": (200, 300), "Hunter's Sting": 300, "Swiftskin's Sting": 300,
           "Flanksting Strike": 340, "Flanksbane Fang": 340, "Hindsting Strike": 340, "Hindsbane Fang": 340,
           "Death Rattle": 280, "Vicewinder": 540, "Hunter's Coil": 630, "Swiftskin's Coil": 630,
           "Twinfang Bite": (120, 170), "Twinblood Bite": (120, 170), "Uncoiled Fury": 680, "Reawaken": 750,
           "First Generation": (480, 680), "Second Generation": (480, 680), "Third Generation": (480, 680),
           "Fourth Generation": (480, 680), "Writhing Snap": 200}
FINISHER_POS, VENOM, COIL_POS = 60, 100, 50
FLANK = {"Flanksting Strike", "Flanksbane Fang", "Hunter's Coil"}
REAR = {"Hindsting Strike", "Hindsbane Fang", "Swiftskin's Coil"}
POSITIONALS = FLANK | REAR
# each finisher's venom enhances the next in the cycle
VENOM_OF = {"Flanksting Strike": "Hindsting Strike", "Hindsting Strike": "Flanksbane Fang",
            "Flanksbane Fang": "Hindsbane Fang", "Hindsbane Fang": "Flanksting Strike"}
FINISHERS = {"h": ("Flanksting Strike", "Flanksbane Fang"), "s": ("Hindsting Strike", "Hindsbane Fang")}
GENERATIONS = ("First Generation", "Second Generation", "Third Generation", "Fourth Generation")
AUTO = 80                                       # auto-attacks: 80 potency (logs, scaled to Death Rattle)
AUTO_DELAY, AUTO_DELAY_SS = 2.54, 2.27          # the logs' median spacing without and with Swiftscaled
# seconds from executing an action to its damage landing, the logs' medians; buffs snapshot on execution
DELAY = {"Steel Fangs": 1.16, "Reaving Fangs": 1.29, "Hunter's Sting": 0.89, "Swiftskin's Sting": 1.16,
         "Flanksting Strike": 1.65, "Flanksbane Fang": 1.60, "Hindsting Strike": 0.98, "Hindsbane Fang": 1.20,
         "Death Rattle": 1.69, "Vicewinder": 0.58, "Hunter's Coil": 0.98, "Swiftskin's Coil": 1.47,
         "Twinfang Bite": 0.63, "Twinblood Bite": 0.71, "Uncoiled Fury": 0.80, "Reawaken": 0.62,
         "First Generation": 1.69, "Second Generation": 1.47, "Third Generation": 1.47, "Fourth Generation": 1.47,
         "Writhing Snap": 0.49}
RECAST = {"Vicewinder": 3.0, "Hunter's Coil": 3.0, "Swiftskin's Coil": 3.0, "Uncoiled Fury": 3.5, "Reawaken": 2.2,
          **{g: 2.0 for g in GENERATIONS}}         # the rest 2.5 s, all before skill speed and Swiftscaled
SWIFT = 0.85
INSTINCT = 1.10
WEAVE_SLACK = 0.05                              # a weave may clip the GCD by this much
COMBO_S, COIL_S, HONED_S, VENOM_S, BUFF_S, RR_S, RA_S, TN_S = 30, 30, 60, 60, 40, 30, 30, 10
TRIBUTE = 4                                     # Anguine Tribute at level 90 (the fifth is level 96)
CDS = {"Vicewinder": (40, 2), "Serpent's Ire": (120, 1), "True North": (45, 2), "Tincture": (270, 1),
       "Death Rattle": (1, 1), "Twinfang Bite": (1, 1), "Twinblood Bite": (1, 1)}
MELEE_ACTIONS = {"Steel Fangs", "Reaving Fangs", "Hunter's Sting", "Swiftskin's Sting", "Flanksting Strike",
                 "Flanksbane Fang", "Hindsting Strike", "Hindsbane Fang", "Vicewinder", "Hunter's Coil",
                 "Swiftskin's Coil", "Reawaken", "Death Rattle", "Twinfang Bite", "Twinblood Bite"} | set(GENERATIONS)
GCDS = ["Steel Fangs", "Reaving Fangs", "Hunter's Sting", "Swiftskin's Sting", "Flanksting Strike", "Flanksbane Fang",
        "Hindsting Strike", "Hindsbane Fang", "Vicewinder", "Hunter's Coil", "Swiftskin's Coil", "Uncoiled Fury",
        "Reawaken", *GENERATIONS, "Writhing Snap"]
OGCD_ORDER = ["Tincture", "Serpent's Ire", "Death Rattle", "Twinfang Bite", "Twinblood Bite", "True North"]
SPEED = 0.998                                   # skill speed factor on the GCD: 2.49 s (2.12 s under Swiftscaled), the
                                                # benchmark clears' median (0.996 gives 2.11 under it); our Vipers' is 2.46 s
MELEE = True                                    # p12s.py gives it a melee's windows (M1 / M2)


class State:
    __slots__ = ("t", "gcd", "combo", "combo_until", "honed", "honed_until", "venom", "venom_until", "tail", "coil",
                 "coil_until", "bites", "hv", "sv", "rattle", "offer", "rr_until", "tribute", "gen", "ra_until",
                 "hi_until", "ss_until", "tn_until", "cds", "auto_next", "dmg", "waste", "pot_at", "first", "hist",
                 "mvi", "acc", "free", "spot", "ai", "mlast", "near")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo, s.combo_until = None, -1.0         # None, "1" (after a first step), "h" / "s" (after Hunter's / Swiftskin's Sting)
        s.honed, s.honed_until = None, -1.0         # "Steel Fangs" / "Reaving Fangs": the one enhanced
        s.venom, s.venom_until = None, -1.0         # the finisher enhanced
        s.tail = False                              # Death Rattle ready
        s.coil, s.coil_until = None, -1.0           # None, "v" (after Vicewinder), "h" / "s" (after Hunter's / Swiftskin's Coil)
        s.bites, s.hv, s.sv = 0, False, False       # bites left after a Coil; Hunter's / Swiftskin's Venom
        s.rattle, s.offer, s.rr_until = 0, 0, -1.0
        s.tribute, s.gen, s.ra_until = 0, 0, -1.0   # Anguine Tribute left, Generations done, Reawakened
        s.hi_until = s.ss_until = s.tn_until = -1.0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.auto_next, s.dmg, s.pot_at, s.first, s.hist = 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0)
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
        return (r(self.t), r(self.gcd), self.combo if self.combo_until > self.t else None,
                self.honed if self.honed_until > self.t else None, self.venom if self.venom_until > self.t else None,
                self.tail, self.coil if self.coil_until > self.t else None, self.bites, self.hv, self.sv, self.rattle,
                self.offer, self.rr_until > self.t, self.tribute if self.ra_until > self.t else 0, self.gen,
                round(max(self.hi_until - self.t, 0) / 2.5), round(max(self.ss_until - self.t, 0) / 2.5),
                left(self.tn_until), self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()),
                self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.ai, r(min(self.t - self.mlast, 4)) if self.near else None)

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Serpent Offerings overcapped", "Rattling Coil overcapped", "Death Rattle or a bite lost")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, Hunter's Instinct."""
    return fight.mult(at, s.pot_at) * (INSTINCT if s.hi_until > at else 1)


def advance(s, fight, to):
    """Auto-attacks up to `to` (while the boss can be hit and the player is in reach; faster under Swiftscaled), and
    Reawakened running out."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + (AUTO_DELAY_SS if s.ss_until > a else AUTO_DELAY)
    if s.tribute and s.ra_until <= to: s.tribute = 0


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
    return name


def hit(s, fight, at, potency, name):
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land): s.dmg += potency * mult(s, fight, at)


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

def step(s, at):
    return s.combo if s.combo_until > at else None


def coil_step(s, at):
    return s.coil if s.coil_until > at else None


def reawakened(s, at):
    return s.tribute > 0 and s.ra_until > at


def gcd_legal(s, name, at):
    if name in ("Hunter's Sting", "Swiftskin's Sting"): return step(s, at) == "1"
    if name in FINISHERS["h"]: return step(s, at) == "h"
    if name in FINISHERS["s"]: return step(s, at) == "s"
    if name == "Vicewinder": return charges(s, name, at)[0] > 0
    if name == "Hunter's Coil": return coil_step(s, at) in ("v", "s")
    if name == "Swiftskin's Coil": return coil_step(s, at) in ("v", "h")
    if name == "Uncoiled Fury": return s.rattle > 0
    if name == "Reawaken": return not reawakened(s, at) and (s.offer >= 50 or s.rr_until > at)
    if name in GENERATIONS: return reawakened(s, at)
    return True                                 # Steel / Reaving Fangs, Writhing Snap


def potency(s, fight, name, at):
    p = POTENCY[name]
    if name in ("Steel Fangs", "Reaving Fangs"): return p[s.honed == name and s.honed_until > at]
    if name in ("Twinfang Bite", "Twinblood Bite"): return p[s.hv if name == "Twinfang Bite" else s.sv]
    if name in GENERATIONS: return p[GENERATIONS.index(name) == s.gen]
    if name in VENOM_OF:
        p += VENOM * (s.venom == name and s.venom_until > at) + FINISHER_POS * flank_rear(s, fight, at)
    if name in ("Hunter's Coil", "Swiftskin's Coil"): p += COIL_POS * flank_rear(s, fight, at)
    return p


def gain(s, n):
    if s.offer + n > 100: wasted(s, 0, s.offer + n - 100)
    s.offer = min(100, s.offer + n)


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    if not fight.targetable(start) or fight.next_down(start) <= start + DELAY.get(name, 0.6): return None
    if name in MELEE_ACTIONS and not reach(s, fight, start): return None
    s.first = False
    snap = start
    haste = SWIFT if s.ss_until > snap else 1.0     # the GCD granting Swiftscaled isn't hasted by it
    hit(s, fight, snap, potency(s, fight, name, snap), name)
    if s.tail or s.bites: wasted(s, 2, s.tail + s.bites)
    s.tail, s.bites, s.hv, s.sv = False, 0, False, False
    if name in ("Steel Fangs", "Reaving Fangs"):
        s.combo, s.combo_until = "1", snap + COMBO_S
        s.honed, s.honed_until = ("Reaving Fangs" if name == "Steel Fangs" else "Steel Fangs"), snap + HONED_S
    elif name == "Hunter's Sting":
        s.combo, s.combo_until, s.hi_until = "h", snap + COMBO_S, snap + BUFF_S
    elif name == "Swiftskin's Sting":
        s.combo, s.combo_until, s.ss_until = "s", snap + COMBO_S, snap + BUFF_S
    elif name in VENOM_OF:
        s.combo, s.tail = None, True
        s.venom, s.venom_until = VENOM_OF[name], snap + VENOM_S
        gain(s, 10)
    elif name == "Vicewinder":
        use_cd(s, name, snap)
        if s.rattle == 3: wasted(s, 1)
        s.rattle = min(3, s.rattle + 1)
        s.coil, s.coil_until = "v", snap + COIL_S
    elif name in ("Hunter's Coil", "Swiftskin's Coil"):
        hunter = name == "Hunter's Coil"
        s.coil = ("h" if hunter else "s") if s.coil == "v" else None
        if hunter: s.hi_until = snap + BUFF_S
        else: s.ss_until = snap + BUFF_S
        s.bites, s.hv, s.sv = 2, hunter, not hunter
        gain(s, 5)
    elif name == "Uncoiled Fury":
        s.rattle -= 1
    elif name == "Reawaken":
        if s.rr_until > snap: s.rr_until = -1.0
        else: s.offer -= 50
        s.tribute, s.gen, s.ra_until = TRIBUTE, 0, snap + RA_S
    elif name in GENERATIONS:
        s.tribute -= 1; s.gen = GENERATIONS.index(name) + 1
        if not s.tribute: s.ra_until = -1.0
    s.t, s.gcd = start + ANIM_LOCK, start + recast(RECAST.get(name, 2.5), SPEED, haste)
    s.near = away_soon(s, fight, s.t)
    s.log(start, name, gauge(s, ""))
    return s


def gauge(s, how):
    t = s.t
    on = [n for n, u in (("HI", s.hi_until), ("SS", s.ss_until), ("RR", s.rr_until)) if u > t]
    if reawakened(s, t): on.append(f"tribute {s.tribute}")
    return (f"{how:<9} combo {step(s, t) or '-'}  coil {coil_step(s, t) or '-'}  offerings {s.offer:>3}  "
            f"rattle {s.rattle}  " + " ".join(on))


def ogcd_legal(s, name, at, fight, policy=True):
    if name in CDS:
        n, _ = charges(s, name, at)
        if n < 1: return False
    if name == "Death Rattle": return s.tail
    if name == "Twinfang Bite": return s.bites > 0 and (not policy or s.hv or not s.sv)
    if name == "Twinblood Bite": return s.bites > 0 and (not policy or s.sv or not s.hv)
    if name == "Serpent's Ire": return at >= 0
    if name == "True North": return not policy or (s.tn_until <= at and (not flank_rear(s, fight, at + 2.5) or
                                                                         not flank_rear(s, fight, at + 5.0)))
    if name == "Tincture": return fight.pot and s.pot_at is None
    return False


HARM_OGCDS = ("Death Rattle", "Twinfang Bite", "Twinblood Bite")


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in HARM_OGCDS and not fight.targetable(at): return None
    if name in MELEE_ACTIONS and not reach(s, fight, at): return None
    if name in CDS: use_cd(s, name, at)
    if name in HARM_OGCDS: hit(s, fight, at, potency(s, fight, name, at), name)
    if name == "Death Rattle": s.tail = False
    elif name == "Twinfang Bite":
        # the first bite after Hunter's Coil grants Swiftskin's Venom for the second
        s.bites -= 1; s.sv = s.sv or (s.hv and s.bites == 1); s.hv = False
    elif name == "Twinblood Bite":
        s.bites -= 1; s.hv = s.hv or (s.sv and s.bites == 1); s.sv = False
    elif name == "Serpent's Ire":
        if s.rattle == 3: wasted(s, 1)
        s.rattle, s.rr_until = min(3, s.rattle + 1), at + RR_S
    elif name == "True North": s.tn_until = at + TN_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.near = away_soon(s, fight, s.t)
    s.log(at, name, gauge(s, ""))
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next. Under Reawakened only the next Generation; otherwise the dual-wield combo's next
    step (both stings; the finisher with the venom, or both without one; the Honed first step, or both without one),
    the next Coil, Vicewinder when no Coil is pending, Reawaken, and Writhing Snap out of reach. Uncoiled Fury about
    ties the filler per second, so offering it at every step only fills the beam with orderings of the same rotation:
    it is offered at three Rattling Coils (the next would overcap), out of reach or close to it, before downtime, at the
    end of the window, and under raid buffs."""
    if reawakened(c, now): return [GENERATIONS[c.gen]]
    st = step(c, now)
    if st == "1": out = ["Hunter's Sting", "Swiftskin's Sting"]
    elif st in FINISHERS:
        v = c.venom if c.venom_until > now else None
        out = [v] if v in FINISHERS[st] else list(FINISHERS[st])
    else:
        h = c.honed if c.honed_until > now else None
        out = [h] if h else ["Steel Fangs", "Reaving Fangs"]
    cs = coil_step(c, now)
    if cs == "v": out += ["Hunter's Coil", "Swiftskin's Coil"]
    elif cs == "h": out.append("Swiftskin's Coil")
    elif cs == "s": out.append("Hunter's Coil")
    elif charges(c, "Vicewinder", now)[0] > 0: out.append("Vicewinder")
    if c.rattle == 3 or c.rattle and (not reach(c, fight, now, commit=False) or away_soon(c, fight, now) or
                                      fight.next_down(now) - now < 8 or fight.until - now < 15 or fight.mult(now) > 1):
        out.append("Uncoiled Fury")
    if not cs and (c.offer >= 50 or c.rr_until > now): out.append("Reawaken")
    if not reach(c, fight, now, commit=False): out.append("Writhing Snap")
    return out


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD. Death Rattle and the bites are lost with the
    next weaponskill, so they are always woven when they can be."""
    slots = min(2, int((s.gcd - s.t + WEAVE_SLACK) / ANIM_LOCK + 1e-6)) if not s.first else 0
    base, used = s, 0
    while used < slots:
        o = next((o for o in HARM_OGCDS if ogcd_legal(base, o, base.t, fight)), None)
        n = do_ogcd(base, fight, o) if o else None
        if n is None: break
        base, used = n, used + 1
    ready = [o for o in OGCD_ORDER if o not in HARM_OGCDS and ogcd_legal(base, o, base.t, fight)] if slots > used else []
    out = []
    for k in range(0, slots - used + 1):
        for combo in itertools.combinations(ready, k):
            c = base
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, fight, now):
                if "True North" in combo and g not in POSITIONALS: continue
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                w = c.copy(); w.t = w.gcd = fight.back_up(now) if down else now + 0.5
                w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# what holding a resource is worth: what it converts into, its hits (under Hunter's Instinct) and what they grant, less
# RATE times the GCDs they take, so spending it leaves the rank where it was. A pending Coil 693 + two bites 374 -
# 2.54 s x 290 = 330; a combo step the finisher, Death Rattle and venom still to come; a Serpent Offering 1/50 of a
# Reawaken window's gain, Ready to Reawaken all of it, a Tribute one Generation; Death Rattle and a bite their hit; a
# venom or Honed status its +100; a Rattling Coil a little (Uncoiled Fury about ties the filler, but works out of
# reach); a second of Hunter's Instinct or Swiftscaled its share of the rotation's rate. (The filler, a three-step combo
# and its Death Rattle with auto-attacks, makes ~275 potency a second; a Coil and its bites ~440, a Reawaken window
# ~440, Uncoiled Fury ~250.) Values much above these hold resources too long: at 1.5 times them the search loses ~5%.
VALUE = dict(combo_1=50, combo_h=335, combo_s=335, coil_v=660, coil_h=330, coil_s=330, tail=300, bite=185, venom=100,
             honed=100, offer=26, rr=1300, tribute=255, rattle=60, hi=25, ss=40)
RATE = 320                                            # potency per second, to compare states at slightly different times
# the search (beam): rates below the filler's own ~275 / s made time look cheap and lost ~1.5%; tune.py (2026-10-22,
# sweep): (270, 0.45) is now the best by a little, +0.03% over the old grid
HEURISTICS = [(270, 0.45, 0.0), (350, 1.0, 0.0), (415, 1.0, 0.0), (340, 0.9, 0.0)]
WIDTH = 3000
SWEEP_WIDTH = 3000                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: +0.05% (in 3/4 of the time)
MOVE_WEIGHT = 0.0


def held(s):
    t = s.t
    v = VALUE.get(f"combo_{step(s, t)}", 0) + VALUE.get(f"coil_{coil_step(s, t)}", 0)
    v += VALUE["tail"] * s.tail + VALUE["bite"] * s.bites
    v += VALUE["venom"] * (s.venom_until > t) + VALUE["honed"] * (s.honed_until > t)
    v += VALUE["offer"] * s.offer + VALUE["rr"] * (s.rr_until > t) + VALUE["rattle"] * s.rattle
    v += VALUE["tribute"] * (s.tribute if s.ra_until > t else 0)
    v += VALUE["hi"] * min(max(s.hi_until - t, 0), 30) + VALUE["ss"] * min(max(s.ss_until - t, 0), 30)
    return v


END_TAPER = 15.0                                      # held resources fade over the window's last seconds


def rank(s, fight):
    # what is still held at the end of the window is worth nothing (final), so its value fades before then: otherwise
    # a state that never spends its last 50 Offerings ranks well to the end (one Reawaken, ~1% of the phase, lost)
    return s.dmg + held(s) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the swings still to come before the window ends
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Viper", "2026-04-28"        # 7.5 raised Vicewinder and the Coils
OGCDS = set(OGCD_ORDER)
REFERENCE = ("Death Rattle", 280)                   # unchanged since 7.05
CAST = {}
HASTED = {"Swiftscaled": SWIFT}                     # calibrate.gcd_of divides gaps that start under it by this
GCD_BASE = RECAST                                   # ...and gaps after these by their recast over 2.5 s


def cast_time(s, name, at):
    return 0.0, None


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(combo=step(s, t), coil=coil_step(s, t), offerings=s.offer, rattle=s.rattle, ready=s.rr_until > t,
                tribute=s.tribute if s.ra_until > t else 0, tail=s.tail, bites=s.bites)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name in ("Hunter's Sting", "Swiftskin's Sting"): s.combo, s.combo_until = "1", start + 1
    if name in FINISHERS["h"]: s.combo, s.combo_until = "h", start + 1
    if name in FINISHERS["s"]: s.combo, s.combo_until = "s", start + 1
    if name == "Hunter's Coil": s.coil, s.coil_until = "v", start + 1
    if name == "Swiftskin's Coil": s.coil, s.coil_until = "v", start + 1
    if name == "Vicewinder":                        # one charge, the recharge still running (it has two)
        s.cds[name] = (1, charges(s, name, start)[1] or start + CDS[name][0])
    if name == "Uncoiled Fury": s.rattle = max(s.rattle, 1)
    if name == "Reawaken": s.rr_until = start + 1; s.tribute = 0
    if name in GENERATIONS: s.tribute, s.ra_until = max(s.tribute, 1), start + 1
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if name == "Death Rattle": s.tail = True
    if name in ("Twinfang Bite", "Twinblood Bite"): s.bites = max(s.bites, 1)
    if name in CDS:                                 # one charge, the recharge still running (True North has two)
        rec, mx = CDS[name]
        s.cds[name] = (1, charges(s, name, t)[1] or (None if mx == 1 else t + rec))
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Positionals are grouped by True North,
    the one way the log shows one was surely taken; without it the model's potency is the miss."""
    if name not in POTENCY: return None
    if name in POSITIONALS:
        tn = s.tn_until > t
        p = POTENCY[name] + (VENOM * (s.venom == name and s.venom_until > t) if name in VENOM_OF else 0)
        g = ("venom" if p > POTENCY[name] else "") + (" TN" if tn else "")
        return g.strip(), p + (FINISHER_POS if name in VENOM_OF else COIL_POS) * tn
    p = potency(s, fight, name, t)
    return ("enhanced" if isinstance(POTENCY[name], tuple) and p == POTENCY[name][1] else ""), p


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Hunter's Instinct; status id from the
    scorecard's cached auras): FFLogs counts every damage-up on the hit, so dividing it out takes it away too."""
    return INSTINCT if "1003668." in (h.get("buffs") or "") else 1.0
