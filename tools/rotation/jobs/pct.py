"""Pictomancer at level 90, Dawntrail patch 7.3 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/pictomancer) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Pictomancy Mastery IV (level 94) raises most potencies there, and Rainbow
Drip and Rainbow Bright (92), the Claw / Maw motifs, Living Muse's third charge and Retribution of the Madeen (96) and Star
Prism (100) lie above P12S. The guide's traits give the level-90 values (Pictomancy Mastery III, level 84), and the 7.2 and
7.3 notes change them to what the guide shows now; Hammer Brush, Polishing Hammer and Comet in Black have no level-84
step, so theirs are the 7.3 base values.

Checked in the scorecard's cached damage events (.cache/acts_*: our groups' ~200 pulls by three Pictomancers, Sep-Oct
2026): each player's plain-hit cluster with others' damage buffs and their own Starry Muse divided out, scaled to Pom
Muse (800, set at level 84 since 7.2) lands within 1% of the model for every action: Fire / Aero / Water in Blue 420 /
460 / 500, Blizzard / Stone / Thunder 750 / 790 / 830, Holy in White 500, Comet in Black 830, Winged Muse 800, Mog of
the Ages 1,000. The hammers always land as critical direct hits; their sure-hit clusters stand 540 : 560 : 580.

The loop: Fire in Red -> Aero in Green -> Water in Blue (Aetherhues I and II carry the step for 30 s); each Water gives 25
Palette Gauge and a White Paint (up to 5), spent by Holy in White (instant). Subtractive Palette (an oGCD, 50 gauge) gives
three stacks that turn the same steps into Blizzard in Cyan -> Stone in Yellow -> Thunder in Magenta (2.3 s casts on a
3.3 s recast; Thunder gives a paint) and Monochrome Tones, under which the next paint is spent by Comet in Black instead.
The three canvases are painted by motifs (3 s casts on a 4 s recast, neither scaled by spell speed) and rendered by
oGCDs: Living Muse (two charges on 40 s at level 90) alternates Pom Muse and Winged Muse, and a Winged Muse paints the
Moogle Portrait for Mog of the Ages; Striking Muse (two charges on 60 s) gives three Hammer Time stacks for Hammer
Stamp -> Brush -> Polishing Hammer (instants); Starry Muse (120 s) raises damage 5% for 20 s and grants Subtractive
Spectrum (one Subtractive Palette without gauge) and five Hyperphantasia stacks under Inspiration.

From the logs (none of it in the guide):
- Inspiration takes 25% off the cast and recast of the six colour spells and of Holy and Comet, and each of those takes a
  Hyperphantasia stack (the hammers and motifs don't); it ends when the stacks run out or the landscape does (~22 s
  after the cast, the 20 s landscape plus a server tick), and its statuses land 0.58 s after the cast. Starry Muse's own
  status (+5%) is on from the cast for 20.5 s.
- The landscape is a circle around where Starry Muse was cast: players keep Inspiration up to ~8 y from it (casts with
  it on reach 8.4 y; lost from 6.5 y, blurred by the 3 s tick). Our runs of more than 8 y leave it (LANDSCAPE): the 15 y
  dash into Superchain I's second doughnut is where our players and the benchmark ones lose it.
- Every canvas is painted at the pull (7.1: a pom, a hammer and a starry sky appear on entering or restarting), Living
  Muse and Striking Muse start with both charges, the gauge and paint empty. Monochrome Tones lasts until Comet;
  Subtractive Palette is never used with it up (383 of 384) nor Striking Muse with Hammer Time up. Subtractive Spectrum is
  spent before the gauge. The hammers keep their order across other GCDs (no combo timer). Aetherhues lapses after
  30 s (logged at 30.8 s), Subtractive Palette's stacks never do (every loss without a cast is a death).
- MP never binds (lowest logged 2,000), so the model leaves it out; Smudge, Tempera Coat / Grassa, Lucid Dreaming and
  Addle only take time in a replay.

A log replay has no movement, so it counts every Starry Muse window as spent inside the landscape (our players leave it
early in ~1 window of 3): that only makes the replay more permissive.
"""
import itertools, math
from engine import ANIM_LOCK, BASE_GCD, RESOLVE, RUN, SLIDE, SlotState, _overlap, cd_key, gcd_times, settle, stand

# level-90 potencies (see above)
POTENCY = {"Fire in Red": 420, "Aero in Green": 460, "Water in Blue": 500, "Blizzard in Cyan": 750,
           "Stone in Yellow": 790, "Thunder in Magenta": 830, "Holy in White": 500, "Comet in Black": 830,
           "Hammer Stamp": 540, "Hammer Brush": 560, "Polishing Hammer": 580,
           "Pom Muse": 800, "Winged Muse": 800, "Mog of the Ages": 1000}
BASE = ("Fire in Red", "Aero in Green", "Water in Blue")              # by the Aetherhues step: none, I, II
SUBTRACTIVE = ("Blizzard in Cyan", "Stone in Yellow", "Thunder in Magenta")
HAMMERS = ("Hammer Stamp", "Hammer Brush", "Polishing Hammer")       # at Hammer Time 3, 2, 1
MOTIFS = {"Pom Motif": "creature", "Wing Motif": "creature", "Hammer Motif": "weapon", "Starry Sky Motif": "landscape"}
CAST = {**{n: 1.5 for n in BASE}, **{n: 2.3 for n in SUBTRACTIVE}}
RECAST = {**{n: 3.3 for n in SUBTRACTIVE}, "Comet in Black": 3.3}     # the rest 2.5; all scaled by spell speed
MOTIF_CAST, MOTIF_RECAST = 3.0, 4.0                                   # fixed (begin -> cast 2.49 s at every GCD)
INSPIRED = set(BASE) | set(SUBTRACTIVE) | {"Holy in White", "Comet in Black"}   # -25% under Inspiration, a stack each
INSP_F = 0.75
AUTO_CRIT = set(HAMMERS)                                              # critical direct hits; dps.py: at their own gain
# the search weighs a sure critical direct hit by its gain over an average hit at typical rates (our players: crit
# 18-28%, direct hit 17-48%); s.dmg stays plain potency and dps.py converts the hammers (critp) apart
CRIT_RATE, CRIT_DMG, DH_RATE, DH_DMG = 0.25, 1.60, 0.30, 1.25


def derive():
    """SURE_W from the rates (engine.configure calls it again after setting them: the gear model's set's own)."""
    global SURE_W
    SURE_W = CRIT_DMG * DH_DMG / ((1 + CRIT_RATE * (CRIT_DMG - 1)) * (1 + DH_RATE * (DH_DMG - 1)))


derive()
# seconds from executing (a spell: resolving) to the damage landing, our logs' medians; buffs snapshot on execution
DELAY = {"Fire in Red": 0.85, "Aero in Green": 0.89, "Water in Blue": 0.98, "Blizzard in Cyan": 0.76,
         "Stone in Yellow": 0.80, "Thunder in Magenta": 0.85, "Holy in White": 1.34, "Comet in Black": 1.87,
         "Hammer Stamp": 1.38, "Hammer Brush": 1.11, "Polishing Hammer": 2.09, "Pom Muse": 0.63, "Winged Muse": 0.98,
         "Mog of the Ages": 1.16}
SM_MULT, SM_S = 1.05, 20.5                      # Starry Muse on the Pictomancer: from the cast
INSP_DELAY, INSP_S, HYPER = 0.58, 22.0, 5       # Inspiration and Hyperphantasia: land 0.58 s after; last until ~22 s
AH_S, HT_S, SPEC_S, SWIFT_S = 30, 30, 30, 10
SP_S = math.inf                                 # Subtractive Palette's stacks stay until spent (no logged lapse)
GAUGE_MAX, PAINT_MAX = 100, 5
SMUDGE_Y, SMUDGE_LOCK, SMUDGE_MIN = 15.0, 0.9, 1.0   # Smudge: a 15 y dash any way the player faces; it locks them
                                                # 0.9 s (the logs' 10th percentile to the next action); the search
                                                # only dashes where it saves at least SMUDGE_MIN seconds of running
LANDSCAPE = 8.0                                 # yalms: a longer run takes the player out of Starry Muse's landscape
CDS = {"Living Muse": (40, 2), "Striking Muse": (60, 2), "Starry Muse": (120, 1), "Mog of the Ages": (30, 1),
       "Subtractive Palette": (1, 1), "Swiftcast": (60, 1), "Smudge": (20, 1), "Tincture": (270, 1)}
OGCD_ORDER = ["Tincture", "Starry Muse", "Striking Muse", "Pom Muse", "Winged Muse", "Mog of the Ages",
              "Subtractive Palette", "Swiftcast", "Smudge"]
DAMAGE_OGCDS = {"Pom Muse", "Winged Muse", "Mog of the Ages"}
SPEED = 0.98                                    # spell speed factor on casts and GCDs: 2.45 s, the median of our three
                                                # Pictomancers (2.31-2.49 s) and the benchmark clears' two (2.22, 2.46 s)


class State(SlotState):
    __slots__ = ("t", "gcd", "ah", "ah_until", "gauge", "paint", "mono", "sp", "sp_until", "ht", "ht_until", "creature",
                 "nxt", "weapon", "landscape", "moogle", "spec_until", "sm_from", "sm_until", "hyper", "insp_from",
                 "insp_until", "land_from", "swift", "cds", "lost", "dmg", "critp", "waste", "pot_at", "first", "hist", "mvi",
                 "acc", "free", "spot")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.ah, s.ah_until = 0, -1.0
        s.gauge, s.paint, s.mono = 0, 0, False
        s.sp, s.sp_until, s.ht, s.ht_until = 0, -1.0, 0, -1.0
        s.creature, s.nxt, s.weapon, s.landscape, s.moogle = "pom", "wing", True, True, False   # painted at the pull
        s.spec_until = s.sm_from = s.sm_until = s.insp_from = s.insp_until = s.swift = -1.0
        s.hyper, s.land_from = 0, 0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.lost = 0.0
        s.dmg, s.critp, s.pot_at, s.first, s.hist = 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0        # forced movement (engine.stand)
        return s

    def key(self):
        t = self.t
        return (round(t, 1), round(self.gcd, 1), step(self, t), self.sp if self.sp_until > t else 0, self.gauge // 5,
                self.paint, self.mono, self.ht if self.ht_until > t else 0, self.creature, self.nxt, self.weapon,
                self.landscape, self.moogle, self.spec_until > t, round(max(self.sm_until - t, 0), 1),
                self.hyper if self.insp_until > t else 0, self.swift > t, self.pot_at is None, cd_key(self.cds),
                self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.spot, self.land_from)



WASTE = ("Palette Gauge overcapped", "White Paint overcapped", "Moogle Portrait overwritten", "Hammer Time lapsed")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- statuses and charges ------------------------------------------------------------------------------------------

def step(s, t):
    """The Aetherhues step: 0 (Fire in Red / Blizzard in Cyan), 1 (Aero / Stone), 2 (Water / Thunder)."""
    return s.ah if s.ah_until > t else 0


def subtractive(s, t):
    return s.sp > 0 and s.sp_until > t


def hammer_time(s, t):
    return s.ht > 0 and s.ht_until > t


def advance(s, fight, to):
    """Hammer Time stacks that lapse by `to`."""
    if s.ht and s.ht_until <= to:
        wasted(s, 3, s.ht); s.ht = 0


def charges(s, name, at):
    n, nxt = s.cds[name]
    if nxt is None or nxt > at: return n, nxt         # nothing comes back by `at` (most calls)
    rec, mx = CDS[name]
    while n < mx and nxt is not None and nxt <= at:
        n += 1; nxt = nxt + rec if n < mx else None
    return n, nxt


def full_since(s, name, t):
    """When the cooldown last came back to full charges, if it is full at t (else None); full at the pull counts from 0."""
    n, nxt = s.cds[name]
    rec, mx = CDS[name]
    if n == mx: return 0.0
    f = nxt + (mx - n - 1) * rec
    return f if f <= t else None


def capped(s, t):
    """Potency the muses' charges have lost sitting full so far (CAPPED: what a second of their recharge is worth)."""
    v = s.lost
    for name, k in CAPPED.items():
        f = full_since(s, name, t)
        if f is not None: v += VALUE[k] * max(t - max(f, 0.0), 0)
    return v


def use_cd(s, name, at):
    n, nxt = charges(s, name, at)
    rec, mx = CDS[name]
    if n == mx:
        if name in CAPPED: s.lost += VALUE[CAPPED[name]] * max(at - max(full_since(s, name, at), 0.0), 0)
        nxt = at + rec
    s.cds[name] = (n - 1, nxt)


def cd_name(name):
    return "Living Muse" if name in ("Pom Muse", "Winged Muse") else name


# --- Starry Muse's landscape ---------------------------------------------------------------------------------------

def in_landscape(s, fight):
    """The player still stands in the landscape: no run longer than LANDSCAPE since Starry Muse was cast has been (even
    partly) made. Runs are made as late as they fit (engine.stand), as for the Black Mage's Ley Lines."""
    if fight is None: return True
    W = fight.moves
    for i in range(s.land_from, min(s.mvi + 1, len(W))):
        if W[i].need * RUN > LANDSCAPE + 1e-9 and (i < s.mvi or s.spot > i): return False
    return True


def inspired(s, fight, at):
    """Inspiration is up at `at`: Hyperphantasia stacks left, the landscape still there and the player in it."""
    return s.hyper > 0 and s.insp_from <= at < s.insp_until and in_landscape(s, fight)


# --- actions -------------------------------------------------------------------------------------------------------

def cast_time(s, name, at, insp=None):
    """Cast time and the instant it spends (Swiftcast). `insp`: whether Inspiration shortens it (default: if it is up,
    the player in the landscape as far as the state knows)."""
    if name in MOTIFS: c = MOTIF_CAST
    elif name in CAST:
        if insp is None: insp = inspired(s, None, at)
        c = CAST[name] * SPEED * (INSP_F if insp else 1.0)
    else: return 0.0, None
    if s.swift > at: return 0.0, "swift"
    return c, None


def recast(name, insp):
    if name in MOTIFS: return MOTIF_RECAST
    return RECAST.get(name, BASE_GCD) * SPEED * (INSP_F if insp and name in INSPIRED else 1.0)


def gcd_legal(s, name, at):
    if name in BASE: return not subtractive(s, at) and BASE[step(s, at)] == name
    if name in SUBTRACTIVE: return subtractive(s, at) and SUBTRACTIVE[step(s, at)] == name
    if name == "Holy in White": return s.paint > 0 and not s.mono
    if name == "Comet in Black": return s.paint > 0 and s.mono
    if name in HAMMERS: return hammer_time(s, at) and HAMMERS[3 - s.ht] == name
    if name in ("Pom Motif", "Wing Motif"): return s.creature is None and name.startswith(s.nxt.title())
    if name == "Hammer Motif": return not s.weapon and not hammer_time(s, at)
    if name == "Starry Sky Motif": return not s.landscape and s.sm_until <= at
    return False


def mult(s, fight, at):
    m = fight.mult(at, s.pot_at)
    if s.sm_from <= at < s.sm_until: m *= SM_MULT
    return m


def hit(s, fight, at, potency, name):
    land = at + DELAY.get(name, 0.8)
    if 0 <= land < fight.until and fight.targetable(land):
        d = potency * mult(s, fight, at)
        if name in AUTO_CRIT: d *= fight.sure(at, dh=True)  # raid crit / direct-hit buffs as damage on a sure hit
        s.dmg += d
        if name in AUTO_CRIT: s.critp += d


def do_gcd(s, fight, name):
    """Cast a GCD as soon as possible; returns the new state or None when it cannot be cast."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    harm = name not in MOTIFS                       # motifs need no target: painted while Athena is away
    if harm and not fight.targetable(start): return None
    insp = name in INSPIRED and inspired(s, fight, start)
    cast, used = cast_time(s, name, start, insp)
    if s.first:
        s.first = False
        if cast: start = RESOLVE - cast             # the opener is pre-cast to resolve at 0:00
    if cast:
        if insp:                                    # a cast the run has to start before leaves the landscape
            c = s.copy()
            if stand(c, fight, start, start + cast - SLIDE) is not None and not in_landscape(c, fight):
                insp = False; cast, used = cast_time(s, name, start, False)
        if stand(s, fight, start, start + cast - SLIDE) is None: return None
    if harm and fight.next_down(start) <= start + max(cast - RESOLVE, 0) + DELAY.get(name, 0.8): return None
    snap, free, nxt = gcd_times(start, cast, recast(name, insp))
    if used == "swift": s.swift = -1.0
    if insp:
        s.hyper -= 1
        if not s.hyper: s.insp_until = snap
    if name in POTENCY: hit(s, fight, snap, POTENCY[name], name)
    if name in BASE or name in SUBTRACTIVE:
        k = step(s, start)
        s.ah, s.ah_until = (k + 1) % 3, snap + AH_S
        if name in SUBTRACTIVE:
            s.sp -= 1
            if not s.sp: s.sp_until = -1.0
        if k == 2:                                  # Water in Blue / Thunder in Magenta: a White Paint
            if s.paint == PAINT_MAX: wasted(s, 1)
            s.paint = min(PAINT_MAX, s.paint + 1)
            if name == "Water in Blue":
                if s.gauge + 25 > GAUGE_MAX: wasted(s, 0, s.gauge + 25 - GAUGE_MAX)
                s.gauge = min(GAUGE_MAX, s.gauge + 25)
    elif name == "Holy in White": s.paint -= 1
    elif name == "Comet in Black": s.paint -= 1; s.mono = False
    elif name in HAMMERS:
        s.ht -= 1
        if not s.ht: s.ht_until = -1.0
    elif name in MOTIFS:
        canvas = MOTIFS[name]
        if canvas == "creature": s.creature = "pom" if name == "Pom Motif" else "wing"
        else: setattr(s, canvas, True)
    s.t, s.gcd = max(free, snap), nxt
    how = f"{cast:.2f}s cast" if cast else ("Swiftcast" if used == "swift" else "instant")
    s.log(start, name, gauge(s, how + (" insp" if insp else "")))
    return s


def gauge(s, how):
    t = s.t
    on = [f"{n}" for n, u in (("Swift", s.swift), ("Spectrum", s.spec_until)) if u > t]
    if s.sm_from <= t < s.sm_until: on.append("Starry")
    if s.hyper and s.insp_until > t: on.append(f"Hyper{s.hyper}")
    if subtractive(s, t): on.append(f"SP{s.sp}")
    if hammer_time(s, t): on.append(f"HT{s.ht}")
    if s.mono: on.append("Mono")
    if s.moogle: on.append("Moogle")
    canv = (s.creature[0].upper() if s.creature else "-") + ("H" if s.weapon else "-") + ("S" if s.landscape else "-")
    return f"{how:<17} AH{step(s, t)} gauge {s.gauge:3d} paint {s.paint}  canvas {canv}  " + " ".join(on)


def ogcd_legal(s, name, at, fight, policy=True):
    if cd_name(name) in CDS:
        n, _ = charges(s, cd_name(name), at)
        if n < 1: return False
    if name in DAMAGE_OGCDS and (at < 0 or not fight.targetable(at)): return False
    if name == "Pom Muse": return s.creature == "pom"
    if name == "Winged Muse": return s.creature == "wing"
    if name == "Mog of the Ages": return s.moogle
    if name == "Striking Muse": return at >= 0 and s.weapon and not (policy and hammer_time(s, at))
    if name == "Starry Muse": return at >= 0 and s.landscape
    if name == "Subtractive Palette":
        return (not subtractive(s, at) and (s.gauge >= 50 or s.spec_until > at)
                and not (policy and s.mono))        # with Monochrome Tones up it would be lost
    if name == "Swiftcast": return not (policy and s.swift > at)
    if name == "Smudge": return not policy or smudge_gain(s, fight, at) >= SMUDGE_MIN
    if name == "Tincture": return fight.pot and s.pot_at is None
    return name in CDS


def smudge_gain(s, fight, t):
    """Seconds of running Smudge saves at t: up to its 15 y of what is left of the run open at t, the free time so far
    counting as run (as engine.dash_gain, but along any stretch: the player dashes the way they face). Enhanced Smudge's
    5 s of faster running is left out (by how much isn't known)."""
    W, i = fight.moves, s.mvi
    if i >= len(W) or not W[i].lo <= t < W[i].hi or not W[i].need: return 0.0
    left = W[i].need - s.acc - _overlap(s.free, t, W[i].lo, W[i].hi)
    return max(0.0, min(SMUDGE_Y / RUN, left))


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if cd_name(name) in CDS: use_cd(s, cd_name(name), at)
    if name in DAMAGE_OGCDS: hit(s, fight, at, POTENCY[name], name)
    if name in ("Pom Muse", "Winged Muse"):
        s.creature, s.nxt = None, "wing" if name == "Pom Muse" else "pom"
        if name == "Winged Muse":
            if s.moogle: wasted(s, 2)
            s.moogle = True
    elif name == "Mog of the Ages": s.moogle = False
    elif name == "Striking Muse":
        if hammer_time(s, at): wasted(s, 3, s.ht)
        s.weapon, s.ht, s.ht_until = False, 3, at + HT_S
    elif name == "Starry Muse":
        s.landscape = False
        s.sm_from, s.sm_until, s.spec_until = at, at + SM_S, at + SPEC_S
        s.hyper, s.insp_from, s.insp_until = HYPER, at + INSP_DELAY, at + INSP_S
        s.land_from = s.mvi + (1 if s.spot > s.mvi else 0)     # a run already begun was made before the cast
    elif name == "Subtractive Palette":
        if s.spec_until > at: s.spec_until = -1.0
        else: s.gauge -= 50
        s.sp, s.sp_until, s.mono = 3, at + SP_S, True
    elif name == "Swiftcast": s.swift = at + SWIFT_S
    elif name == "Tincture": s.pot_at = at
    saved = 0.0
    if name == "Smudge":
        saved = smudge_gain(s, fight, at); s.acc += saved
    s.t = at + (SMUDGE_LOCK if name == "Smudge" else ANIM_LOCK)
    s.log(at, name, gauge(s, f"dash {saved:.2f}s" if saved else ""))
    return s


GCDS = list(BASE) + list(SUBTRACTIVE) + ["Holy in White", "Comet in Black"] + list(HAMMERS) + list(MOTIFS)


def candidates(c, now):
    """The GCDs worth trying next: the colour spell of the current step (only one is legal), Holy or Comet, the next
    hammer, and any motif whose canvas is empty."""
    return [g for g in GCDS if gcd_legal(c, g, now)]


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD."""
    slots = int((s.gcd - s.t) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready, k):
            if "Pom Muse" in combo and "Winged Muse" in combo: continue
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, now):
                # Swiftcast only right before a hard cast, Subtractive Palette before the spells it opens or the Comet
                # it allows: anything else only multiplies the states
                if "Swiftcast" in combo and g not in CAST and g not in MOTIFS: continue
                if "Subtractive Palette" in combo and g not in SUBTRACTIVE and g != "Comet in Black": continue
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                w = c.copy(); w.t = w.gcd = fight.back_up(now) if down else now + 0.5
                w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# What holding a resource is worth: what it converts into, less RATE times the GCD time that takes, at the rate that
# makes the colour loop break even (~215 potency a second: a 2.45 s GCD costs ~525, a 3.2 s one ~690), so spending a
# resource leaves the rank where it was (jobs/vpr.py: inflated values make the beam hoard). A Subtractive stack its spell
# over its GCD (~100); Monochrome Tones a Comet over its GCD (~165); a gauge point a fiftieth of three stacks and a
# Monochrome; an Aetherhues step what its next steps are worth over theirs (Water's gauge and paint); a Hammer Time
# stack its hammer at SURE_W over a GCD (~380); a painted creature canvas its Muse (an oGCD: 800), the Moogle Portrait
# its Mog, a hammer canvas three stacks; a starry sky Starry Muse's worth (Spectrum, five hasted GCDs, 5% for 20 s); a
# Hyperphantasia stack a quarter of a GCD; a second of Starry Muse 5% of the burst's rate; Swiftcast a motif standing.
VALUE = dict(gauge=9, paint=5, mono=165, sp=95, ah1=105, ah2=170, ht=380, creature=800, moogle=1000, weapon=1140,
             landscape=1450, spectrum=440, hyper=150, starry=15, swift=50, cap_living=40, cap_striking=90, cap_starry=24)
# A cooldown sitting at full charges loses what its recharge would have brought, and pushes every later use back: the
# rank charges each second of it (capped) twice its share, a second of Living Muse two fortieths of a Muse, of Striking
# Muse two sixtieths of three hammers (at SURE_W), of Starry Muse two 120ths of its worth. Without it the search left
# Living Muse full for ~30 s after the opener, painting the next pom only when nothing else was worth more than a 4 s
# motif. Weights tried (CAP_W, one sweep at width 1,000, R1 and standing still): 0.5-1 times the share +0-0.2%, 1.5-2
# times +0.2-0.6%, 3-6 times -0.7% to +0.1%.
CAPPED = {"Living Muse": "cap_living", "Striking Muse": "cap_striking", "Starry Muse": "cap_starry"}
CAP_W = 1.0
RATE = 215                                            # potency per second, to compare states at slightly different times
# tune.py --job pct (2026-10-22, 36 settings in R1 over the whole phase): values at 0.45-0.65 of these do best (+0.43%
# over the first guesses' portfolio in R1, +0.05% in R2); at 1.4 they lose ~2% (the beam holds canvases and gauge)
HEURISTICS = [(210, 0.65, 0.0), (215, 0.45, 0.0), (200, 0.45, 0.0), (225, 0.45, 0.0)]
WIDTH = 1000                                          # the beam (--layers gcd): wider found less (1,000 / 2,000 / 3,000:
                                                      # 101.1k / 100.9k / 99.7k at one setting)
SWEEP_WIDTH = 1000                                    # engine.sweep (layers by time), against the beam at WIDTH, taking about
                                                      # as long (33 s / 28 s): +1.2%; at 2,000 and 3,000 within 0.1%
MOVE_WEIGHT = 0.0
END_TAPER = 15.0                                      # held resources fade over the window's last seconds


def ready(s, name, t):
    """When the cooldown next has a charge, from t."""
    n, nxt = charges(s, name, t)
    return t if n else nxt


def held(s, fight=None):
    """What the held resources are worth (VALUE); a canvas or the Moogle Portrait only if what renders it is back before
    the window ends (a sky painted after the last Starry Muse ranked as if it would be used, over a Comet)."""
    t = s.t
    use = lambda name: fight is None or ready(s, name, t) < fight.until - 1.0
    v = VALUE["gauge"] * s.gauge + VALUE["paint"] * s.paint + VALUE["mono"] * s.mono
    v += VALUE["sp"] * (s.sp if subtractive(s, t) else 0) + VALUE["ah1"] * (step(s, t) == 1) + VALUE["ah2"] * (step(s, t) == 2)
    v += VALUE["ht"] * (s.ht if hammer_time(s, t) else 0)
    v += VALUE["creature"] * (s.creature is not None and use("Living Muse"))
    v += VALUE["moogle"] * (s.moogle and use("Mog of the Ages")) + VALUE["weapon"] * (s.weapon and use("Striking Muse"))
    v += VALUE["landscape"] * (s.landscape and use("Starry Muse"))
    v += VALUE["spectrum"] * (s.spec_until > t) + VALUE["hyper"] * (s.hyper if s.insp_until > t and in_landscape(s, fight) else 0)
    v += VALUE["starry"] * max(s.sm_until - max(t, s.sm_from), 0) + VALUE["swift"] * (s.swift > t)
    return v


def score(s):
    """Damage with the hammers' critical direct hits at their expected gain over an average hit."""
    return s.dmg + (SURE_W - 1) * s.critp


def rank(s, fight):
    return score(s) + held(s, fight) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - CAP_W * capped(s, s.t) - RATE * s.t


def final(s, fight):
    return score(s) + (held(s, fight) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Pictomancer", "2025-08-05"   # 7.3: the current potencies
OGCDS = set(OGCD_ORDER)
REFERENCE = ("Pom Muse", 800)                       # set at level 84; 7.2 moved it there, nothing since


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(step=step(s, t), gauge=s.gauge, paint=s.paint, mono=s.mono, sp=s.sp if subtractive(s, t) else 0,
                ht=s.ht if hammer_time(s, t) else 0, creature=s.creature, nxt=s.nxt, weapon=s.weapon,
                landscape=s.landscape, moogle=s.moogle, hyper=s.hyper if s.insp_until > t else 0)


def force(s, fight, name, start):
    """Cast it anyway, with what it needs granted (the replay carries on after an illegal cast)."""
    s = s.copy()
    if name in BASE: s.sp, s.ah, s.ah_until = 0, BASE.index(name), start + 1
    if name in SUBTRACTIVE: s.sp, s.sp_until, s.ah, s.ah_until = max(s.sp, 1), start + 1, SUBTRACTIVE.index(name), start + 1
    if name == "Holy in White": s.paint, s.mono = max(s.paint, 1), False
    if name == "Comet in Black": s.paint, s.mono = max(s.paint, 1), True
    if name in HAMMERS: s.ht, s.ht_until = 3 - HAMMERS.index(name), start + 1
    if name in ("Pom Motif", "Wing Motif"): s.creature, s.nxt = None, "pom" if name == "Pom Motif" else "wing"
    if name == "Hammer Motif": s.weapon, s.ht = False, 0
    if name == "Starry Sky Motif": s.landscape, s.sm_until = False, -1.0
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if cd_name(name) in CDS:                        # one charge, the recharge still running
        rec, mx = CDS[cd_name(name)]
        s.cds[cd_name(name)] = (1, charges(s, cd_name(name), t)[1] or (None if mx == 1 else t + rec))
    if name == "Pom Muse": s.creature = "pom"
    if name == "Winged Muse": s.creature = "wing"
    if name == "Mog of the Ages": s.moogle = True
    if name == "Striking Muse": s.weapon = True
    if name == "Starry Muse": s.landscape = True
    if name == "Subtractive Palette": s.sp, s.gauge = 0, max(s.gauge, 50)
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` cast at t from state s."""
    if name not in POTENCY: return None
    if name in AUTO_CRIT: return "sure crit", POTENCY[name]
    return "", POTENCY[name]


def cast_label(s, name, t):
    return "insp" if name in INSPIRED and inspired(s, None, t) else ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own: Starry Muse's 5% (status id 1003685 in the
    scorecard's cached auras). FFLogs counts every damage-up on the hit, so dividing it out takes this away too."""
    return SM_MULT if "1003685." in (h.get("buffs") or "") else 1.0
