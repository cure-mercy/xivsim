"""Red Mage at level 90, Dawntrail patch 7.05 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/redmage) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Enchanted Blade Mastery (level 94) raises nearly every potency there, and
Vice of Thorns (92), Grand Impact (96) and Prefulgence (100) lie above P12S. The patch notes since 7.0 only change those
level-94+ values, AoE falloff and Manafication's durations (7.01 and 7.05: 30 s).

FFLogs was down when this was written, so the level-90 potencies were measured in the scorecard's cached damage events
(.cache/acts_*: our groups' 267 pulls by five Red Mages, Sep-Oct 2026, and 18 benchmark clears): each player's plain-hit
cluster with others' damage buffs and the own Embolden divided out, scaled to Jolt III (360: Red Magic Mastery III at
84 sets it, nothing since touches it). They are Endwalker's level-90 values; FFLogs' bonusPercent confirms the combo
splits (Enchanted Redoublement 74% = (500 - 130) / 500).

The loop: a hard-cast spell grants Dualcast, which makes the next spell instant, so a 2 s spell (Jolt III, or Verfire /
Verstone on a proc) is hard-cast and the 5 s Verthunder III / Veraero III comes out instant. Black and White Mana (0-100
each) build from the spells; the enchanted melee combo (Riposte -> Zwerchhau -> Redoublement, 20 / 15 / 15 of each)
gives three Mana Stacks, which open Verflare or Verholy, then Scorch and Resolution as a combo. Manafication makes the
next three enchanted actions free (Magicked Swordplay) and lets them reach 25 y; Embolden raises the own magic damage
10% (Fleche, Contre Sixte, Corps-a-corps and Engagement are physical: the logs show no gain on them).

From the logs (none of it in the guide):
- Acceleration is spent before Dualcast and Swiftcast by an instant Verthunder / Veraero III, and Dualcast survives it
  (18 of 18 casts); Dualcast is spent before Swiftcast. A spell made instant never grants Dualcast.
- Verthunder / Veraero III proc their colour 49.4% of the time (4,158 casts), 100% under Acceleration.
- Sprint cancels Dualcast (it is a general action, not an ability).
- The enchanted combo's recasts are fixed at 1.5 / 1.5 / 2.2 s whatever the spell speed; Embolden's status lands 0.67 s
  after the cast, every other status on the cast.

MP: 10,000, +200 on each 3 s server tick; Jolt III, Verfire and Verstone cost 200, Verthunder / Veraero III 300,
Verflare, Verholy, Scorch and Resolution 400, the enchanted combo nothing (the logs' MP between casts; xivintheshell has
the Ver-IIIs at 400). Without more the
rotation runs dry by ~190 s (xivintheshell, 2026-10-25), so Lucid Dreaming (60 s) gives 550 more on each tick for
21 s: every pull of ours lasting 200 s or more uses it, about every 77 s. The model's MP matches 96-97% of the logged
snapshots (the rest a tick apart); MP potions aren't modelled (one Verraise after a Super-Ether replays short).

Procs are random. The search counts them at their expected worth (as the Bard's Repertoire): a Verthunder III raises
the chance that Verfire Ready is up by half of what is left, and casting "Verfire" means "Verfire if it is up, else
Verstone if that is, else Jolt III" (all cast in 2 s), at the mixture's potency and mana. A log replay knows which spell
was cast, so there a proc is "possibly up" once granted, and the spell is what the log says.

Reach: the melee combo and Engagement need the player within reach of Athena (3 y beyond her ~11 y hitbox), except the
combo under Manafication. Our plan keeps a ranged player in reach except at a few far spots (p12s.far), which the fight
gives as `away` windows.

Dashes (engine.dash): Corps-a-corps rushes to Athena, landing at her hitbox edge (10.5 y from her centre in our logs),
and Displacement backsteps 15 y (the tooltip's; Engagement with a backstep, sharing its charges). Where a run of our
plan goes straight to or from her (p12s.DASH), a dash covers that stretch and saves its running. The search may hold a
dash back to the run's start if it still fits before the next GCD (a player waits for the bait, then dashes), and
Corps-a-corps can't pull the player off a far spot before its snapshot; after it, it ends the stretch out of reach.
"""
import itertools
import engine
from engine import (ANIM_LOCK, BASE_GCD, RESOLVE, SLIDE, SlotState, cd_key, dash, dash_gain, gcd_times, move_credit,
                    open_move, settle, stand)
from jobs._common import cast_label, cooldowns, reach, wasted

# level-90 potencies from the logs (see above); (out of combo, in combo) for combo steps
POTENCY = {"Jolt III": 360, "Verthunder III": 380, "Veraero III": 380, "Verfire": 340, "Verstone": 340,
           "Verflare": 600, "Verholy": 600, "Scorch": 680, "Resolution": 750,
           "Enchanted Riposte": 280, "Enchanted Zwerchhau": (150, 340), "Enchanted Redoublement": (130, 500),
           "Enchanted Reprise": 340, "Fleche": 460, "Contre Sixte": 380, "Corps-a-Corps": 130, "Engagement": 180,
           "Displacement": 180,
           # replays only: the plain melee actions (too little mana), AoE spells
           "Riposte": 130, "Zwerchhau": (100, 150), "Redoublement": (100, 230), "Reprise": 100,
           "Verthunder II": 140, "Veraero II": 140, "Impact": 210}
PHYSICAL = {"Fleche", "Contre Sixte", "Corps-a-Corps", "Engagement", "Displacement", "Riposte", "Zwerchhau",
            "Redoublement", "Reprise"}
# mana gained (black, white) and spent (each colour)
GAIN = {"Jolt III": (2, 2), "Verthunder III": (6, 0), "Veraero III": (0, 6), "Verfire": (5, 0), "Verstone": (0, 5),
        "Verflare": (11, 0), "Verholy": (0, 11), "Scorch": (4, 4), "Resolution": (4, 4), "Verthunder II": (7, 0),
        "Veraero II": (0, 7), "Impact": (3, 3)}
COST = {"Enchanted Riposte": 20, "Enchanted Zwerchhau": 15, "Enchanted Redoublement": 15, "Enchanted Reprise": 5}
ENCHANTED = ("Enchanted Riposte", "Enchanted Zwerchhau", "Enchanted Redoublement")     # Magicked Swordplay covers these
# seconds from executing (a spell: resolving) to the damage landing, the logs' medians; buffs snapshot on execution
DELAY = {"Jolt III": 0.80, "Verfire": 0.80, "Verstone": 0.80, "Verthunder III": 0.76, "Veraero III": 0.76,
         "Verflare": 1.43, "Verholy": 1.43, "Scorch": 1.83, "Resolution": 1.56, "Enchanted Riposte": 0.63,
         "Enchanted Zwerchhau": 0.63, "Enchanted Redoublement": 0.63, "Enchanted Reprise": 0.62, "Fleche": 1.16,
         "Contre Sixte": 1.16, "Corps-a-Corps": 0.63, "Engagement": 0.58, "Displacement": 0.62}
CAST = {"Jolt III": 2.0, "Verfire": 2.0, "Verstone": 2.0, "Verthunder III": 5.0, "Veraero III": 5.0,
        "Verthunder II": 2.0, "Veraero II": 2.0, "Impact": 5.0, "Verraise": 10.0, "Vercure": 2.0}
ACCELERATED = ("Verthunder III", "Veraero III", "Impact")
RECAST = {"Enchanted Riposte": 1.5, "Enchanted Zwerchhau": 1.5, "Enchanted Redoublement": 2.2}   # fixed, not spell speed
EMBOLDEN, EMB_DELAY = 1.10, 0.67                # own magic damage; the status lands 0.67 s after the cast
PROC = 0.5                                      # a Verthunder / Veraero III's chance of its colour's proc
FIN_PROC = (1.0, 0.2)                           # Verflare / Verholy: when the other colour leads, else
DC_S, ACC_S, SWIFT_S, PROC_S, MS_S, EMB_S, COMBO_S = 15, 20, 10, 30, 30, 20, 30
MANA_S = 30.4      # logged at the cast, it runs past its 30 (ends 30.38-30.43 after the cast; calibrate's status check).
                   # Before 7.5 it was 6 stacks spent by GCDs (the 2025 clears): every log since is a plain 30 s status
MP_COST = {"Jolt III": 200, "Verfire": 200, "Verstone": 200, "Verthunder III": 300, "Veraero III": 300,
           "Verthunder II": 400, "Veraero II": 400, "Impact": 400, "Verflare": 400, "Verholy": 400, "Scorch": 400,
           "Resolution": 400, "Vercure": 500, "Verraise": 2400}
MP_TICK, LUCID_TICK, LUCID_S, TICK_PHASE = 200, 550, 21, 1.5    # server ticks land at TICK_PHASE + 3k seconds
LUCID_LAG = 0.62                                # Lucid Dreaming lands this long after the cast, then lasts its 21 s
CDS = {"Fleche": (25, 1), "Contre Sixte": (35, 1), "Corps-a-Corps": (35, 2), "Engagement": (35, 2),
       "Embolden": (120, 1), "Manafication": (110, 1), "Acceleration": (55, 2), "Swiftcast": (60, 1),
       "Lucid Dreaming": (60, 1), "Tincture": (270, 1)}
at = cooldowns(__name__)[5]                         # charges / use_cd are the job's own: Sprint has no CDS entry
OGCD_ORDER = ["Tincture", "Embolden", "Manafication", "Fleche", "Contre Sixte", "Acceleration", "Swiftcast",
              "Engagement", "Displacement", "Corps-a-Corps", "Lucid Dreaming"]
BACKSTEP = 15.0                                 # Displacement's backstep, yalms (the tooltip's: 3 uses in our logs)
DAMAGE_OGCDS = {"Fleche", "Contre Sixte", "Corps-a-Corps", "Engagement", "Displacement"}
MELEE_ACTIONS = {"Enchanted Riposte", "Enchanted Zwerchhau", "Enchanted Redoublement", "Engagement", "Riposte",
                 "Zwerchhau", "Redoublement", "Reprise"}     # 3 y (the enchanted three reach 25 y under Manafication)
NEXT = {"r": "Enchanted Zwerchhau", "z": "Enchanted Redoublement", "f": "Scorch", "s": "Resolution"}
SPEED = 1.0                                     # spell speed factor on casts and GCDs: 2.50 s, our players and the clears
# A colour's gains halve while it leads by more than 30 (tested in game, 2026-10-23: rdm-in-game-tests.md, test 2; the
# logs couldn't tell: players pass 30 in 22 of ~10,000 gains). The searched rotations never get there.
IMBALANCE_HALVES = True


class State(SlotState):
    __slots__ = ("t", "gcd", "black", "white", "stacks", "combo", "combo_until", "dc", "accel", "swift", "ms", "ms_until",
                 "mana_until", "emb_from", "emb_until", "vf", "vf_until", "vs", "vs_until", "cds", "dmg", "waste", "pot_at",
                 "first", "hist", "mvi", "acc", "free", "spot", "ai", "mlast", "dashed", "mp", "mp_t", "lucid")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.black = s.white = 0.0
        s.stacks, s.combo, s.combo_until = 0, None, -1.0
        s.dc = s.accel = s.swift = s.ms_until = s.mana_until = s.emb_from = s.emb_until = -1.0
        s.ms = 0
        s.vf = s.vs = 0.0
        s.vf_until = s.vs_until = -1.0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.dmg, s.pot_at, s.first, s.hist = 0.0, None, True, None
        s.waste = (0.0, 0.0, 0.0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0        # forced movement (engine.stand)
        s.ai, s.mlast = 0, -30.0                                # out of reach (fight.away)
        s.dashed = ()                                           # (move window, segment) dashed (engine.dash)
        s.mp, s.mp_t, s.lucid = 10000, 0.0, -1.0                # MP, ticked up to mp_t; Lucid Dreaming's end
        return s

    def key(self):
        return (round(self.t, 1), round(self.gcd, 1), round(self.black / 3), round(self.white / 3), self.stacks,
                self.combo if self.combo_until > self.t else None, self.dc > self.t, self.accel > self.t,
                self.swift > self.t, self.ms if self.ms_until > self.t else 0, self.mana_until > self.t,
                round(max(self.emb_until - self.t, 0), 1), round(self.vf * 4), round(self.vs * 4), self.pot_at is None,
                cd_key(self.cds), self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.ai,
                tuple(k for i, k in self.dashed if i == self.mvi), self.mp // 400, self.lucid > self.t)



WASTE = ("mana overcapped", "procs lost (granted again while up, or lapsed)", "Dualcast dropped")


# --- time passing --------------------------------------------------------------------------------------------------

def advance(s, fight, to):
    """MP ticks, and procs that lapse, by `to`."""
    if to > s.mp_t:
        for k in range(int((s.mp_t - TICK_PHASE) // 3) + 1, int((to - TICK_PHASE) // 3) + 1):
            s.mp = min(10000, s.mp + MP_TICK + (LUCID_TICK if lucid(s, TICK_PHASE + 3 * k) else 0))
        s.mp_t = to
    if s.vf_until != -1.0 and s.vf_until <= to:
        wasted(s, 1, s.vf); s.vf, s.vf_until = 0.0, -1.0
    if s.vs_until != -1.0 and s.vs_until <= to:
        wasted(s, 1, s.vs); s.vs, s.vs_until = 0.0, -1.0


def charges(s, name, at):
    if name not in CDS: return 1, None              # Sprint
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


def cd_name(name):
    return "Engagement" if name == "Displacement" else name


def lucid(s, at):
    return s.lucid - LUCID_S <= at < s.lucid


def mult(s, fight, at, name):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, and Embolden on magic damage."""
    m = fight.mult(at, s.pot_at)
    if name not in PHYSICAL and s.emb_from <= at < s.emb_until: m *= EMBOLDEN
    return m


def hit(s, fight, at, potency, name):
    land = at + DELAY.get(name, 0.8)
    if 0 <= land < fight.until and fight.targetable(land): s.dmg += potency * mult(s, fight, at, name)


def gain(s, b, w):
    """Mana gained, capped at 100 each (the rest is wasted)."""
    if IMBALANCE_HALVES:
        if s.black - s.white > 30: b /= 2
        if s.white - s.black > 30: w /= 2
    nb, nw = s.black + b, s.white + w
    over = max(0.0, nb - 100) + max(0.0, nw - 100)
    if over > 1e-9: wasted(s, 0, over)
    s.black, s.white = min(100.0, nb), min(100.0, nw)


def grant(s, colour, chance, at, ev):
    """A chance at Verfire Ready ("vf") or Verstone Ready ("vs"). The search counts its expectation: the chance it is up
    afterwards, and the part already up that the grant overwrites as waste. A replay (ev False) only knows it may be up.
    With procs drawn (engine.DRAW: montecarlo.py) it happens or doesn't."""
    p = getattr(s, colour)
    if ev and engine.DRAW is not None:
        if not engine.drawn(chance, at, colour): return
        chance = 1.0
    if ev:
        wasted(s, 1, p * chance)
        setattr(s, colour, 1 - (1 - p) * (1 - chance))
    else:
        setattr(s, colour, 1.0)
    setattr(s, colour + "_until", at + PROC_S)


# --- reach (as jobs/drg.py) ----------------------------------------------------------------------------------------

def needs_reach(s, name, at):
    return name in MELEE_ACTIONS and not (name in ENCHANTED and s.mana_until > at)


# --- actions -------------------------------------------------------------------------------------------------------

def cast_time(s, name, at):
    """Cast time and the instant it spends: Acceleration (Verthunder / Veraero III, Impact) first, then Dualcast, then
    Swiftcast."""
    if name not in CAST: return 0.0, None
    if name in ACCELERATED and s.accel > at: return 0.0, "acc"
    if s.dc > at: return 0.0, "dc"
    if s.swift > at: return 0.0, "swift"
    return CAST[name] * SPEED, None


def in_combo(s, name, at):
    return s.combo_until > at and s.combo is not None and NEXT.get(s.combo) == name


def payable(s, name, at):
    if name in ENCHANTED and s.ms > 0 and s.ms_until > at: return True
    c = COST.get(name, 0)
    return s.black >= c - 1e-6 and s.white >= c - 1e-6


def gcd_legal(s, name, at, ev):
    if s.mp < MP_COST.get(name, 0): return False
    if name in ("Verfire", "Verstone"):
        return (s.vf > 0.05 or s.vs > 0.05) if ev else getattr(s, "vf" if name == "Verfire" else "vs") > 0
    if name in ("Verflare", "Verholy"): return s.stacks == 3
    if name in ("Scorch", "Resolution"): return in_combo(s, name, at)
    if name in COST: return payable(s, name, at)
    return name in POTENCY or name in CAST


def do_gcd(s, fight, name, ev=False):
    """Cast a GCD as soon as possible; returns the new state or None when it cannot be cast. `ev`: the search's
    expected procs (see the module's docstring), else the spell is exactly what is named."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start, ev): return None
    harm = name not in ("Verraise", "Vercure")
    if harm and not fight.targetable(start): return None
    cast, used = cast_time(s, name, start)
    if s.first:
        s.first = False
        if cast: start = RESOLVE - cast                     # the opener is pre-cast to resolve at 0:00
    if cast and stand(s, fight, start, start + cast - SLIDE) is None: return None
    if harm and fight.next_down(start) <= start + max(cast - RESOLVE, 0) + DELAY.get(name, 0.8): return None
    if needs_reach(s, name, start) and not reach(s, fight, start): return None
    snap, free, nxt = gcd_times(start, cast, RECAST.get(name, BASE_GCD * SPEED))
    # instants: Acceleration leaves Dualcast up; anything else spends or cancels it
    if used == "acc": s.accel = -1.0
    else:
        if s.dc > start and used != "dc": wasted(s, 2)
        s.dc = -1.0
        if used == "swift": s.swift = -1.0
    combo = in_combo(s, name, snap)
    s.mp -= MP_COST.get(name, 0)
    note = ""
    if name in ("Verfire", "Verstone") and ev:
        # the named proc if it is up, else the other one if that is, else Jolt III; whichever is spent is gone, and the
        # other stays up only if it was and the named one was spent
        a, b = s.vf, s.vs
        if name == "Verfire": pf, ps = a, (1 - a) * b
        else: pf, ps = (1 - b) * a, b
        pj = 1 - pf - ps
        s.vf, s.vs = (0.0, a * b) if name == "Verfire" else (a * b, 0.0)
        if not s.vf: s.vf_until = -1.0
        if not s.vs: s.vs_until = -1.0
        hit(s, fight, snap, pf * POTENCY["Verfire"] + ps * POTENCY["Verstone"] + pj * POTENCY["Jolt III"], "Verfire")
        gain(s, pf * 5 + pj * 2, ps * 5 + pj * 2)
        note = f"Verfire {pf:.0%}, Verstone {ps:.0%}, Jolt III {pj:.0%}"
    else:
        p = POTENCY.get(name, 0)
        if isinstance(p, tuple): p = p[combo]
        if p: hit(s, fight, snap, p, name)
        if name == "Verfire": s.vf, s.vf_until = 0.0, -1.0
        if name == "Verstone": s.vs, s.vs_until = 0.0, -1.0
        if name in GAIN:
            b, w = GAIN[name]
            lead_w, lead_b = s.white > s.black, s.black > s.white
            gain(s, b, w)
            if name in ("Verthunder III", "Veraero III"):
                grant(s, "vf" if name == "Verthunder III" else "vs", 1.0 if used == "acc" else PROC, snap, ev)
            if name == "Verflare": grant(s, "vf", FIN_PROC[0] if lead_w else FIN_PROC[1], snap, ev)
            if name == "Verholy": grant(s, "vs", FIN_PROC[0] if lead_b else FIN_PROC[1], snap, ev)
    # mana, stacks and combos
    if name in COST:
        if name in ENCHANTED and s.ms > 0 and s.ms_until > snap: s.ms -= 1
        else: s.black -= COST[name]; s.white -= COST[name]
    # Mana Stacks (the gauge's): each enchanted melee combo action adds one, Verflare / Verholy spend them, any other GCD
    # clears them (oGCDs and Sprint don't), and they don't lapse (in game, 2026-10-23: test 3). A Riposte doesn't reset
    # them: a clear's Riposte -> Zwerchhau -> Manafication -> Riposte -> Verholy is legal
    if name in ENCHANTED: s.stacks = min(3, s.stacks + 1)
    else: s.stacks = 0
    if name in ("Enchanted Riposte", "Riposte"): s.combo, s.combo_until = "r", snap + COMBO_S
    elif name in ("Enchanted Zwerchhau", "Zwerchhau") and combo: s.combo, s.combo_until = "z", snap + COMBO_S
    elif name in ("Verflare", "Verholy"): s.combo, s.combo_until = "f", snap + COMBO_S
    elif name == "Scorch" and combo: s.combo, s.combo_until = "s", snap + COMBO_S
    else: s.combo = None
    if cast and used is None and name in CAST: s.dc = snap + DC_S          # a hard cast grants Dualcast
    s.t, s.gcd = max(free, snap), nxt
    how = f"{cast:.2f}s cast" if cast else ({"acc": "Acceleration", "dc": "Dualcast", "swift": "Swiftcast"}.get(used, "instant"))
    s.log(start, name, gauge(s, how) + (f"  ({note})" if note else ""))
    return s


def gauge(s, how):
    t = s.t
    on = [n for n, u in (("DC", s.dc), ("Accel", s.accel), ("Swift", s.swift), ("Mfic", s.mana_until)) if u > t]
    if s.emb_from <= t < s.emb_until: on.append("Emb")
    if s.ms and s.ms_until > t: on.append(f"MS{s.ms}")
    return (f"{how:<13} B{s.black:5.1f} W{s.white:5.1f} stacks {s.stacks}  VF {s.vf:.2f} VS {s.vs:.2f}  " + " ".join(on))


def ogcd_legal(s, name, at, fight, policy=True):
    if cd_name(name) in CDS:
        n, _ = charges(s, cd_name(name), at)
        if n < 1: return False
    if name in DAMAGE_OGCDS or name in ("Embolden", "Manafication"):
        if at < 0: return False
    if name == "Manafication":                  # cancels combos; spent before the enchanted combo it pays for
        return not policy or (s.stacks == 0 and not (s.ms > 0 and s.ms_until > at) and s.combo is None)
    if name == "Acceleration": return not (policy and s.accel > at)
    if name == "Swiftcast": return not (policy and s.swift > at)
    if name == "Tincture": return fight.pot and s.pot_at is None
    if name == "Lucid Dreaming": return not policy or s.mp <= 10000 - LUCID_TICK * 7
    if name == "Sprint": return not policy          # replays only: a general action, it cancels Dualcast
    # Displacement is Engagement with a backstep: the search only uses it where the backstep saves running
    if name == "Displacement": return not policy or dash_gain(s, fight, at, "out", BACKSTEP) is not None
    return name in CDS


DASHES = {"Corps-a-Corps": ("in", None), "Displacement": ("out", BACKSTEP)}


def dash_time(s, fight, name):
    """When the search makes a dash: right after the last action, or, if a move window with a stretch for it opens
    before the next GCD and the dash still fits before that GCD, at its start (a player waits for the mechanic, e.g.
    Paradeigma I's bait, and then dashes): whichever saves more running."""
    kind, dist = DASHES[name]
    best = (dash_gain(s, fight, s.t, kind, dist) or (0, 0.0))[1], s.t
    for w in fight.moves[s.mvi:]:
        if w.lo > s.gcd - ANIM_LOCK + 1e-9: break
        if w.lo > s.t and w.dash:
            c = s.copy(); settle(c, fight, w.lo)
            g = dash_gain(c, fight, w.lo, kind, dist)
            if g and g[1] > best[0] + 1e-9: best = g[1], w.lo
    return best[1]


def corps_lands(s, fight, t):
    """Corps-a-corps lands the player beside Athena: not while a far spot holds them (before its snapshot, the middle
    of its stretch out of reach); after the snapshot it ends the stretch early."""
    for i in range(s.ai, len(fight.away)):
        w = fight.away[i]
        if w.lo > t: break
        if t < w.hi:
            if t < (w.lo + w.hi) / 2 - 1e-9: return False
            s.ai, s.mlast = i + 1, t
    return True


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = dash_time(s, fight, name) if policy and name in DASHES else s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in DAMAGE_OGCDS and not fight.targetable(at): return None
    # Engagement and Displacement need reach; Corps-a-corps brings the player there
    if name in ("Engagement", "Displacement") and not reach(s, fight, at): return None
    if name == "Corps-a-Corps" and not corps_lands(s, fight, at): return None
    if cd_name(name) in CDS: use_cd(s, cd_name(name), at)
    saved = dash(s, fight, at, *DASHES[name]) if name in DASHES else 0
    if name in DAMAGE_OGCDS: hit(s, fight, at, POTENCY[name], name)
    elif name == "Embolden": s.emb_from, s.emb_until = at + EMB_DELAY, at + EMB_DELAY + EMB_S
    elif name == "Manafication":
        s.ms, s.ms_until, s.mana_until = 3, at + MS_S, at + MANA_S
        s.combo = None
    elif name == "Acceleration": s.accel = at + ACC_S
    elif name == "Swiftcast": s.swift = at + SWIFT_S
    elif name == "Tincture": s.pot_at = at
    elif name == "Lucid Dreaming": s.lucid = at + LUCID_LAG + LUCID_S
    elif name == "Sprint":
        if s.dc > at: wasted(s, 2)
        s.dc = -1.0
    s.t = at + ANIM_LOCK
    s.log(at, name, gauge(s, f"dash {saved:.2f}s" if saved else ""))
    return s


GCDS = ["Jolt III", "Verfire", "Verstone", "Verthunder III", "Veraero III", "Verflare", "Verholy", "Scorch",
        "Resolution", "Enchanted Riposte", "Enchanted Zwerchhau", "Enchanted Redoublement", "Enchanted Reprise",
        "Riposte", "Zwerchhau", "Redoublement", "Reprise", "Verthunder II", "Veraero II", "Impact", "Verraise", "Vercure"]


def candidates(c, fight, now):
    """The GCDs worth trying next. A combo or the finishers go on (their next step is all that is offered while it can
    be cast); under Dualcast only the 5 s spells (anything else wastes it); Verthunder / Veraero III otherwise only
    when Acceleration or Swiftcast makes them instant; the melee combo only whole (Magicked Swordplay or 50 of each
    mana: every logged finisher but four follows one unbroken combo; any other GCD clears the stacks), and only if its three hits stay clear of the stretches out of reach;
    Enchanted Reprise only in a move window."""
    nxt = NEXT.get(c.combo) if c.combo_until > now else None
    if nxt and gcd_legal(c, nxt, now, True) and not (needs_reach(c, nxt, now) and not reach(c, fight, now, commit=False)):
        return [nxt]
    if c.stacks == 3: return ["Verflare", "Verholy"]
    if c.dc > now: return ["Verthunder III", "Veraero III"]
    out = ["Jolt III"] + [g for g in ("Verfire", "Verstone") if gcd_legal(c, g, now, True)]
    if c.accel > now or c.swift > now or c.first: out += ["Verthunder III", "Veraero III"]
    whole = (c.ms == 3 and c.ms_until > now + 4) or min(c.black, c.white) >= 50 - 1e-6
    clear = c.mana_until > now + 3.0 or not any(w.lo < now + 3.0 + 1e-9 and w.hi > now for w in fight.away[c.ai:])
    if whole and clear: out.append("Enchanted Riposte")
    if payable(c, "Enchanted Reprise", now) and open_move(c, fight, now): out.append("Enchanted Reprise")
    return out


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD."""
    slots = int((s.gcd - s.t) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready = [o for o in OGCD_ORDER if ogcd_legal(s, o, dash_time(s, fight, o) if o in DASHES else s.t, fight)] if slots else []
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
                # Acceleration and Swiftcast only right before the spell they make instant, Manafication before the
                # combo it pays for: anything else only multiplies the states
                if ("Acceleration" in combo or "Swiftcast" in combo) and g not in CAST: continue
                if "Acceleration" in combo and g not in ACCELERATED: continue
                if "Manafication" in combo and g != "Enchanted Riposte": continue
                n = do_gcd(c, fight, g, ev=True)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                w = c.copy(); w.t = w.gcd = fight.back_up(now) if down else now + 0.5
                w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# What holding a resource is worth, set so that each step of the combo chain ranks about level with the Jolt III ->
# Verthunder III loop per second (a chain that dips mid-way gets dropped before it pays off): a point of mana what the
# chain makes of it over the loop, spread over the mana it costs net of the 27 the finishers give back (~7); each chain
# position (after Riposte, after Zwerchhau, three stacks, after Verflare, after Scorch) the chain's payoff still to
# come; a Magicked Swordplay stack the mana it saves; Dualcast, Acceleration and Swiftcast an instant Verthunder III
# over a loop step; a proc little (Verfire / Verstone about tie Jolt III with their mana); a second of Embolden its share
# of the rotation's rate.
VALUE = dict(mana=7, imbalance=3, chain_r=310, chain_z=490, chain_3=660, chain_f=500, chain_s=290, ms=230, dc=60,
             acc=50, swift=50, proc=20, emb=15, mp=0.03)
RATE = 220                                            # potency per second, to compare states at slightly different times
# tune.py (2026-10-22, sweep): VALUE at 1.15-1.5 times, +0.13% over the phase in R1 (level in R2); 0.5 loses 2%
HEURISTICS = [(185, 1.5, 0.0), (200, 1.15, 0.0), (230, 1.15, 0.0), (185, 1.15, 0.0)]
WIDTH = 1000
SWEEP_WIDTH = 1000                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: +0.08% (in half the time)
MOVE_WEIGHT = 0.0
FAR = True                                            # p12s.fight: out of reach at the plan's far spots
CHAIN = {"r": "chain_r", "z": "chain_z", "f": "chain_f", "s": "chain_s"}


def held(s):
    t = s.t
    v = VALUE["mana"] * (s.black + s.white) - VALUE["imbalance"] * max(0.0, abs(s.black - s.white) - 20)
    if s.stacks == 3: v += VALUE["chain_3"]
    elif s.combo_until > t and s.combo in CHAIN: v += VALUE[CHAIN[s.combo]]
    v += VALUE["ms"] * (s.ms if s.ms_until > t else 0)
    v += VALUE["dc"] * (s.dc > t) + VALUE["acc"] * (s.accel > t) + VALUE["swift"] * (s.swift > t)
    v += VALUE["proc"] * (s.vf + s.vs)
    v += VALUE["emb"] * max(s.emb_until - max(t, s.emb_from), 0)
    v += VALUE["mp"] * s.mp
    return v


def rank(s, fight):
    """No look-ahead at runs (the Black Mage's move_debt): tried at weights 1 and 2, it never found a better rotation;
    nor at dashes ahead (a value on charges kept for them): the opener's Corps-a-corps is back by Paradeigma I anyway."""
    return s.dmg + held(s) - RATE * (s.t - move_credit(s, fight))


def final(s, fight):
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "RedMage", "2024-08-06"      # 7.05: Manafication and Magicked Swordplay last 30 s
OGCDS = set(OGCD_ORDER) | {"Displacement", "Sprint"}
REFERENCE = ("Jolt III", 360)                       # no trait above level 84 or patch touches it


STATUSES = {"Dualcast": lambda s, t: s.dc > t, "Acceleration": lambda s, t: s.accel > t,
            "Swiftcast": lambda s, t: s.swift > t, "Magicked Swordplay": lambda s, t: s.ms > 0 and s.ms_until > t,
            "Manafication": lambda s, t: s.mana_until > t, "Embolden": lambda s, t: s.emb_from <= t < s.emb_until,
            "Lucid Dreaming": lambda s, t: lucid(s, t)}


def status(s, t):
    return dict(black=round(s.black, 1), white=round(s.white, 1), stacks=s.stacks,
                combo=s.combo if s.combo_until > t else None, dc=s.dc > t, acc=s.accel > t, swift=s.swift > t,
                ms=s.ms if s.ms_until > t else 0, vf=s.vf > 0, vs=s.vs > 0, mp=s.mp)


def force(s, fight, name, start):
    """Cast it anyway, with what it needs granted (the replay carries on after an illegal cast)."""
    s = s.copy()
    if name == "Verfire": s.vf, s.vf_until = 1.0, start + 1
    if name == "Verstone": s.vs, s.vs_until = 1.0, start + 1
    if name in ("Verflare", "Verholy"): s.stacks = 3
    if name in ("Scorch", "Resolution"): s.combo, s.combo_until = {"Scorch": "f", "Resolution": "s"}[name], start + 1
    if name in COST: s.black, s.white = max(s.black, COST[name]), max(s.white, COST[name])
    s.mp = max(s.mp, MP_COST.get(name, 0))
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if cd_name(name) in CDS:                        # one charge, the recharge still running (Acceleration has two)
        rec, mx = CDS[cd_name(name)]
        s.cds[cd_name(name)] = (1, charges(s, cd_name(name), t)[1] or (None if mx == 1 else t + rec))
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` cast at t from state s."""
    if name not in POTENCY: return None
    p = POTENCY[name]
    if isinstance(p, tuple):
        combo = in_combo(s, name, t) or (name == "Enchanted Zwerchhau" and s.combo == "r" and s.combo_until > t)
        return ("combo" if combo else "no combo"), p[combo]
    return "", p


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own: Embolden's 10% on magic damage (status id
    1001239 in the scorecard's cached auras). FFLogs counts every damage-up on the hit, so dividing it out takes this
    away too."""
    name = p["names"].get(str(h.get("abilityGameID")), "")
    return EMBOLDEN if "1001239." in (h.get("buffs") or "") and name not in PHYSICAL and name != "Attack" else 1.0
