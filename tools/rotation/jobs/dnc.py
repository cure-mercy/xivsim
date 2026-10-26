"""Dancer at level 90, Dawntrail, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/dancer) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Dynamic Dancer (level 94) raises Cascade, Fountain, the procs, the Fan
Dances, Saber Dance and the finishes there, and Last Dance (92), Finishing Move (96) and Dance of the Dawn (100) lie
above P12S. So the level-90 kit is the Cascade -> Fountain combo, Reverse Cascade / Fountainfall on Silken (or
Flourishing) Symmetry / Flow, Fan Dance I / III / IV, Saber Dance on 50 Esprit, Standard Step (two steps) and
Technical Step (four), Tillana after Technical Finish, Devilment -> Starfall Dance and Flourish.

Level-90 values measured in the full FFLogs logs (2026-10-22, scratch/dnc): our 62 clean pulls by five Dancers and the
38 benchmark clears with one. Each player's plain-hit cluster over FFLogs' multiplier (others' and the Dancer's own
damage-ups divided out), tinctures left out, scaled to Fan Dance (150: the 7.1 notes raise it only with Dynamic Dancer):
Cascade 200, Fountain 100 / 260 in combo (bonusPercent 61 fits only these), Reverse Cascade 260, Fountainfall 320,
Saber Dance 500, Fan Dance III 200, Fan Dance IV 300, Double Standard Finish 800, Quadruple Technical Finish 1,200,
Tillana 600, Starfall Dance 600 (always a critical direct hit), auto-attacks ("Attack") 80 every 3.12 s.

Rules from the logs (scratch/dnc/rules.py, the acts caches of ~320 pulls):
- nothing breaks the combo: Fountain keeps its bonus across Reverse Cascade, Saber Dance and whole dances, for 30 s;
- every proc is 50% (Silken Symmetry 49.2% of 3,191 Cascades, Silken Flow 49.3% of combo Fountains, Threefold 49.3% of
  Fan Dances); a proc GCD spends the silken status before the flourishing one (214 of 214 with both up), so Flourish
  wastes nothing but a Threefold / Fourfold already held;
- Standard Step, Technical Step and the finishes run on a fixed 1.5 s recast, each step on 1.0 s, whatever the skill
  speed; no oGCD but defensives while dancing (the guide); Devilment goes ~0.67 s after Technical Finish;
- Standard Finish's and Devilment's statuses come with the cast, Technical Finish's 0.54 s after it (FFLogs logs a
  second, `fake` cast record then); Standard Finish +5% for 60 s with Esprit, Technical Finish +5% for 20 s;
- the opener: Standard Step before the pull (not logged), Standard Finish at ~0.9 s; the second Standard Step comes
  16.4 s at the earliest, so the pre-pull Step was at -13.6 s or earlier. The search presses it at -14 s (PREPULL_SS)
  and opens on Standard Finish at 0:00.

Randomness is counted at its expectation (as Bard's Repertoire): a 50% proc is half a token, usable at a whole one, and
a grant over a token already held is waste; a feather is half a token per Reverse Cascade / Fountainfall. A log replay
reads the procs from the log's statuses (prepare) and counts a feather on every chance (feathers aren't logged).

Esprit: 5 a Cascade / Fountain, 10 a Reverse Cascade / Fountainfall while the Esprit status is up (Standard Finish's
60 s, or Technical Finish's 20 s), 50 a Tillana, and the party's chances: the dance partner's while Standard Finish is
up, everyone's in the Technical Finish window, at expected rates per second (PARTY_RATE, TECH_RATE: scratch/dnc/
esprit.py and replays), only while Athena can be hit. With procs drawn (engine.DRAW: montecarlo.py) the party's come
as 10 Esprit or none on each member's GCD, on a fixed grid (PARTY_GCD) at the chance that gives the same rate.

Devilment's +20% critical and direct-hit rate counts on the Dancer's own hits at its expected worth (as Bard's Battle
Voice). Starfall Dance's sure critical direct hit (always under Devilment, whose rates it turns into damage) is kept in
s.critp at its plain potency and weighed at STAR_W; dps.py converts it at each player's own (AUTO_CRIT).

Every action is instant and reaches the plan's spots (Saber Dance 25 y, the finishes and Tillana 15 y around the Dancer
from Athena's 10.5 y hitbox), so R1, R2 and standing still play the same; only Palladion's downtime matters, where the
steps can be danced with no target and the finish waits for Athena.
"""
import itertools, math
import engine
from engine import ANIM_LOCK, BASE_GCD, SlotState, cd_key, settle

POTENCY = {"Cascade": 200, "Fountain": 100, "Reverse Cascade": 260, "Fountainfall": 320, "Saber Dance": 500,
           "Tillana": 600, "Starfall Dance": 600, "Fan Dance": 150, "Fan Dance II": 100, "Fan Dance III": 200, "Fan Dance IV": 300,
           "Double Standard Finish": 800, "Quadruple Technical Finish": 1200}
COMBO_POT = {"Fountain": 260}
# finishes: name -> (dance, steps it takes, potency, damage bonus). Only the full ones are searched; the rest are for
# replays (a handful in the logs; Dynamic Dancer raises only the full ones, and Triple Technical Finish measures 900)
FINISH = {"Double Standard Finish": ("std", 2, 800, 1.05), "Single Standard Finish": ("std", 1, 540, 1.02),
          "Standard Finish": ("std", 0, 360, 1.0),
          "Quadruple Technical Finish": ("tech", 4, 1200, 1.05), "Triple Technical Finish": ("tech", 3, 900, 1.03),
          "Double Technical Finish": ("tech", 2, 720, 1.02), "Single Technical Finish": ("tech", 1, 540, 1.01),
          "Technical Finish": ("tech", 0, 350, 1.0)}
FULL = {"std": "Double Standard Finish", "tech": "Quadruple Technical Finish"}
STEPS = {"std": 2, "tech": 4}
STEP_NAMES = ("Step", "Emboite", "Entrechat", "Jete", "Pirouette")   # the game picks the order; the search logs "Step"
DANCE_RECAST = {"Standard Step": 1.5, "Technical Step": 1.5}
STEP_RECAST, FINISH_RECAST = 1.0, 1.5
# statuses as long as the logs show them (they outlast the tooltips by ~0.5 s: unspent Silken procs lapse ~30.8 s after
# their grant, spent up to 30.7 s; Flourishing Starfall lapses at 20.5 s; dances finished up to 15.12 s after the Step)
DANCE_S, SF_S, TF_S, TF_LAG, DEV_S, STAR_S, FFIN_S, PROC_S = 15.2, 60.0, 20.15, 0.54, 20.0, 20.5, 30.5, 30.8
# (Technical Finish runs 20.04-20.18 s from its landing: calibrate's status check)
PREPULL_SS = -14.0                              # the search's pre-pull Standard Step (its two steps follow)
ESPRIT = {"Cascade": 5, "Fountain": 5, "Reverse Cascade": 10, "Fountainfall": 10}
# the party's Esprit, expected per second: the dance partner's while Standard Finish is up, and the six others' in the
# Technical Finish window, at the same chance each (TECH_RATE = 6 x PARTY_RATE). 0.7 balances, over every replayed log,
# the Esprit the model lacks at Saber Dances against what it overcaps (46 / 43 a pull; ours 35 / 27, the clears 65 / 69):
# ~17% for 10 Esprit on each member's GCD, 168 Esprit every two minutes. A deterministic expectation looks short where
# players spend a lucky draw at once (13% of logged Saber Dances, by ~10 Esprit each), mostly outside the window.
PARTY_RATE = 0.7
TECH_RATE = 4.2
PARTY_GCD = 2.5                                 # with procs drawn: each member's GCDs this far apart, the seven offset evenly
AUTO, AUTO_DELAY = 80, 3.12
# seconds from executing an action to its damage landing, the logs' medians
DELAY = {"Cascade": 0.80, "Fountain": 0.98, "Reverse Cascade": 0.63, "Fountainfall": 1.20, "Saber Dance": 0.45,
         "Tillana": 0.71, "Starfall Dance": 0.89, "Fan Dance": 0.63, "Fan Dance III": 0.63, "Fan Dance IV": 0.63}
COMBO_S = 30.0
CDS = {"Standard Step": (30, 1), "Technical Step": (120, 1), "Devilment": (120, 1), "Flourish": (60, 1),
       "Fan Dance": (1, 1), "Fan Dance II": (1, 1), "Fan Dance III": (1, 1), "Fan Dance IV": (1, 1), "Tincture": (270, 1)}
JITTER = 0.05                                   # a replay: the logs' Steps come up to 0.03 s inside their recast
GCDS = ["Cascade", "Fountain", "Reverse Cascade", "Fountainfall", "Saber Dance", "Tillana", "Starfall Dance",
        "Standard Step", "Technical Step"] + list(STEP_NAMES) + list(FINISH)
OGCD_ORDER = ["Tincture", "Devilment", "Flourish", "Fan Dance IV", "Fan Dance III", "Fan Dance"]
AUTO_CRIT = {"Starfall Dance"}
OWN_CRIT_BUFFS = {"1001825"}                    # Devilment: dps.py measures Starfall's sure gain under it (it always is)
CRIT_RATE, CRIT_DMG, DH_RATE, DH_DMG = 0.25, 1.60, 0.36, 1.25


def derive():
    """Devilment's worth and Starfall's weight from the rates (engine.configure calls it again after setting them):
    STAR_W is a sure critical direct hit over an average hit, its crit and direct-hit rates under Devilment turned
    into damage."""
    global DEV, STAR_W
    DEV = (1 + 0.20 * (CRIT_DMG - 1) / (1 + CRIT_RATE * (CRIT_DMG - 1))) * (1 + 0.20 * (DH_DMG - 1) / (1 + DH_RATE * (DH_DMG - 1)))
    STAR_W = (CRIT_DMG * DH_DMG * (1 + 0.20 * (CRIT_DMG - 1)) * (1 + 0.20 * (DH_DMG - 1))
              / ((1 + CRIT_RATE * (CRIT_DMG - 1)) * (1 + DH_RATE * (DH_DMG - 1))))


derive()
SPEED = 0.996                                   # skill speed factor: a 2.49 s GCD (the clears' and our Dancers' median)
LOG_PREPULL = None                              # a replay: (Step, when) the log's pre-pull dance began, or False (prepare)
LOG_PROCS = None                                # a replay: {status: times it was granted} from the log (prepare)


class State(SlotState):
    __slots__ = ("t", "gcd", "combo_until", "sym", "sym_until", "fsym_until", "flow", "flow_until", "fflow_until",
                 "feathers", "three", "three_until", "four_until", "esprit", "ep_t", "sf_until", "sf_m", "tf_from",
                 "tf_until", "tf_m", "dev_until", "star_until", "ffin_until", "dance", "steps", "dance_t", "dance_until",
                 "cds", "auto_next", "dmg", "critp", "lost", "waste", "pot_at", "first", "hist", "mvi", "acc", "free",
                 "spot")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo_until, s.sym, s.sym_until, s.fsym_until, s.flow, s.flow_until, s.fflow_until = -1.0, 0.0, -1.0, -1.0, 0.0, -1.0, -1.0
        s.feathers, s.three, s.three_until, s.four_until = 0.0, 0.0, -1.0, -1.0
        s.esprit, s.ep_t = 0.0, 0.0
        s.sf_until, s.sf_m, s.tf_from, s.tf_until, s.tf_m = -1.0, 1.0, -1.0, -1.0, 1.0
        s.dev_until, s.star_until, s.ffin_until = -1.0, -1.0, -1.0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        pre = ("Standard Step", PREPULL_SS) if LOG_PREPULL is None else LOG_PREPULL
        s.dance, s.steps, s.dance_t, s.dance_until = None, 0, None, -1.0
        if pre:                                         # the pre-pull Step and its steps: the finish is next
            step, at = pre
            kind = "std" if step == "Standard Step" else "tech"
            s.cds[step] = (0, at + CDS[step][0])
            s.dance, s.steps, s.dance_t, s.dance_until = kind, STEPS[kind], at, at + DANCE_S
        s.auto_next = 0.0
        s.dmg, s.critp, s.lost, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, None, True, None
        s.waste = (0.0, 0.0, 0.0, 0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0
        return s

    def key(self):
        return (round(self.t, 1), round(self.gcd, 1), round(max(self.combo_until - self.t, 0), 1), self.sym, self.flow,
                round(max(self.fsym_until - self.t, 0), 1), round(max(self.fflow_until - self.t, 0), 1), self.feathers,
                self.three, round(max(self.four_until - self.t, 0), 1), round(self.esprit),
                round(max(self.sf_until - self.t, 0), 1), round(max(self.tf_until - self.t, 0), 1),
                round(max(self.dev_until - self.t, 0), 1), round(max(self.star_until - self.t, 0), 1),
                round(max(self.ffin_until - self.t, 0), 1), self.dance, self.steps, self.pot_at is None,
                cd_key(self.cds))



WASTE = ("Esprit overcapped", "feathers overcapped", "Silken procs overwritten or lapsed", "Fan Dance III / IV lost",
         "dances lapsed")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time, buffs and cooldowns -------------------------------------------------------------------------------------

def mult(s, fight, at, dev=True):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, own Standard / Technical Finish and (at its
    expected worth) Devilment."""
    m = fight.mult(at, s.pot_at)
    if s.sf_until > at: m *= s.sf_m
    if s.tf_from <= at < s.tf_until: m *= s.tf_m
    if dev and s.dev_until > at: m *= DEV
    return m


def esprit_up(s, t):
    """The Esprit status: Standard Finish's, or Technical Finish's for its 20 s."""
    return s.sf_until > t or s.tf_from - TF_LAG <= t < s.tf_until


def gain(s, n):
    v = s.esprit + n
    if v > 100: wasted(s, 0, v - 100)
    s.esprit = min(100.0, v)


def party(s, fight, a, b):
    """The party's expected Esprit over [a, b]: the partner's while Standard Finish is up, everyone's in the Technical
    Finish window, only while Athena can be hit."""
    if b <= a: return 0.0
    inner = [x for x in (s.sf_until, s.tf_from, s.tf_until) if a < x < b]
    for lo, hi in fight.untargetable:
        if a < lo < b: inner.append(lo)
        if a < hi < b: inner.append(hi)
    pts = sorted({a, b, *inner}) if inner else (a, b)  # most spans hold no change of rate
    v = 0.0
    for x, y in zip(pts, pts[1:]):
        m = (x + y) / 2
        if not fight.targetable(m): continue
        r = (PARTY_RATE if s.sf_until > m else 0.0) + (TECH_RATE if s.tf_from <= m < s.tf_until else 0.0)
        v += r * (y - x)
    return v


def party_drawn(s, fight, a, b):
    """The party's Esprit over [a, b) with procs drawn (engine.DRAW: montecarlo.py): 10 or none on each member's GCD
    (PARTY_GCD apart, member j offset j / 7 of it), at the chance that gives party()'s rate: the partner's (j = 0) while
    Standard Finish is up, the six others' in the Technical Finish window, only while Athena can be hit."""
    v = 0.0
    for j in range(7):
        off, q = j * PARTY_GCD / 7, (PARTY_RATE if j == 0 else TECH_RATE / 6) * PARTY_GCD / 10
        for n in range(math.ceil((a - off) / PARTY_GCD - 1e-9), math.ceil((b - off) / PARTY_GCD - 1e-9)):
            t = off + n * PARTY_GCD
            up = s.sf_until > t if j == 0 else s.tf_from <= t < s.tf_until
            if up and fight.targetable(t) and engine.drawn(q, t, f"Esprit {j}"): v += 10
    return v


def advance(s, fight, to):
    """Auto-attacks and the party's Esprit up to `to`, and statuses that lapse."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a): s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + AUTO_DELAY
    if to > s.ep_t:
        drawn = engine.DRAW is not None and LOG_PROCS is None
        g = (party_drawn if drawn else party)(s, fight, max(s.ep_t, 0.0), to)
        if g: gain(s, g)
        s.ep_t = to
    if s.sym and s.sym_until <= to: wasted(s, 2, s.sym); s.sym = 0.0
    if s.flow and s.flow_until <= to: wasted(s, 2, s.flow); s.flow = 0.0
    if s.three and s.three_until <= to: wasted(s, 3, s.three); s.three = 0.0
    if s.dance and s.dance_until <= to: wasted(s, 4); s.dance, s.steps, s.dance_t = None, 0, None


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
    """Potency the cooldowns have lost sitting ready so far (CAPPED: what a second of their recast is worth)."""
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
    return name


def ready(s, name, t):
    n, nxt = charges(s, name, t)
    return t if n else nxt


# --- procs ---------------------------------------------------------------------------------------------------------

def logged(status, at):
    """A replay: did the log grant this status on the action at `at`?"""
    return any(abs(x - at) < 0.3 for x in LOG_PROCS.get(status, ()))


def grant(s, which, at, status):
    """A 50% chance of a Silken proc ("sym" / "flow") or Threefold ("three"): half a token in the search, the log's own
    in a replay, a whole one or none with procs drawn (engine.DRAW: montecarlo.py). A token over a whole one already
    held is wasted."""
    if LOG_PROCS is not None:
        if not logged(status, at): return
        n = 1.0
    elif engine.DRAW is not None:
        if not engine.drawn(0.5, at, status): return
        n = 1.0
    else: n = 0.5
    v = getattr(s, which) + n
    if v > 1: wasted(s, 3 if which == "three" else 2, v - 1)
    setattr(s, which, min(1.0, v)); setattr(s, which + "_until", at + PROC_S)


def feather(s, at):
    """Half a feather (a 50% chance) in the search; a replay can't see feathers, so it counts every chance; with procs
    drawn, a whole one or none."""
    if engine.DRAW is not None and LOG_PROCS is None:
        if not engine.drawn(0.5, at, "Fourfold Feather"): return
        v = s.feathers + 1.0
    else: v = s.feathers + (1.0 if LOG_PROCS is not None else 0.5)
    if v > 4: wasted(s, 1, v - 4)
    s.feathers = min(4.0, v)


def has_sym(s, t):
    return s.sym >= 1 - 1e-9 or s.fsym_until > t


def has_flow(s, t):
    return s.flow >= 1 - 1e-9 or s.fflow_until > t


# --- actions -------------------------------------------------------------------------------------------------------

def dancing(s, t):
    return s.dance is not None and s.dance_until > t


def gcd_legal(s, name, at):
    if dancing(s, at):
        if name in STEP_NAMES: return s.steps < STEPS[s.dance] or LOG_PROCS is not None
        return name in FINISH and FINISH[name][0] == s.dance and (LOG_PROCS is not None or s.steps == FINISH[name][1])
    if name in STEP_NAMES or name in FINISH: return False
    if name in ("Standard Step", "Technical Step"): return charges(s, name, at + (JITTER if LOG_PROCS is not None else 0))[0] >= 1
    if name == "Reverse Cascade": return has_sym(s, at)
    if name == "Fountainfall": return has_flow(s, at)
    if name == "Saber Dance": return s.esprit >= 50 - 1e-6
    if name == "Tillana": return s.ffin_until > at
    if name == "Starfall Dance": return s.star_until > at
    return name in ("Cascade", "Fountain")


def land(fight, at, name):
    """When a hit of `name` executed at `at` lands, if it lands on Athena inside the window (else None)."""
    t = at + DELAY.get(name, 0.54)
    return t if 0 <= t < fight.until and fight.targetable(t) else None


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    harm = name in POTENCY or name in FINISH
    if harm and not fight.targetable(start): return None
    s.first = False
    recast = BASE_GCD * SPEED
    note = ""
    if name in FINISH:
        kind, _, p, bonus = FINISH[name]
        if land(fight, start, name) is not None: s.dmg += p * mult(s, fight, start)
        if kind == "std": s.sf_until, s.sf_m = start + SF_S, bonus
        else:
            s.tf_from, s.tf_until, s.tf_m = start + TF_LAG, start + TF_LAG + TF_S, bonus
            s.ffin_until = start + FFIN_S
        s.dance, s.steps, s.dance_t, s.dance_until = None, 0, None, -1.0
        recast = FINISH_RECAST
    elif name in STEP_NAMES:
        s.steps = min(s.steps + 1, STEPS[s.dance])     # (a replay's wrong or extra steps don't count)
        recast = STEP_RECAST
    elif name in ("Standard Step", "Technical Step"):
        use_cd(s, name, start)
        s.dance, s.steps, s.dance_t, s.dance_until = ("std" if name == "Standard Step" else "tech"), 0, start, start + DANCE_S
        recast = DANCE_RECAST[name]
    else:
        combo = name == "Fountain" and s.combo_until > start
        p = COMBO_POT[name] if combo else POTENCY[name]
        t = land(fight, start, name)
        if t is not None:
            m = mult(s, fight, start, dev=name != "Starfall Dance")
            if name == "Starfall Dance": m *= fight.sure(start, dh=True)   # raid buffs as damage on a sure hit
            s.dmg += p * m
            if name == "Starfall Dance": s.critp += p * m
            if name in ESPRIT and esprit_up(s, start): gain(s, ESPRIT[name])
        if name == "Cascade":
            s.combo_until = start + COMBO_S
            grant(s, "sym", start, "Silken Symmetry")
        elif name == "Fountain":
            if combo or LOG_PROCS is not None: grant(s, "flow", start, "Silken Flow")
            s.combo_until = -1.0
        elif name == "Reverse Cascade":
            if s.sym >= 1 - 1e-9: s.sym -= 1.0
            else: s.fsym_until = -1.0
            feather(s, start)
        elif name == "Fountainfall":
            if s.flow >= 1 - 1e-9: s.flow -= 1.0
            else: s.fflow_until = -1.0
            feather(s, start)
        elif name == "Saber Dance": s.esprit -= 50
        elif name == "Tillana": s.ffin_until = -1.0; gain(s, 50)
        elif name == "Starfall Dance": s.star_until = -1.0
        if combo: note = "combo"
    s.t, s.gcd = start + ANIM_LOCK, start + recast
    s.log(start, name, gauge(s, note))
    return s


def gauge(s, note=""):
    t = s.t
    on = [x for x, u in (("SF", s.sf_until), ("Tech", s.tf_until), ("Devil", s.dev_until)) if u > t]
    return (f"esprit {s.esprit:5.1f}  feathers {s.feathers:.1f}  sym {s.sym:.1f}{'+F' if s.fsym_until > t else ''}"
            f"  flow {s.flow:.1f}{'+F' if s.fflow_until > t else ''}  3fold {s.three:.1f}{'  4fold' if s.four_until > t else ''}"
            + ("  " + " ".join(on) if on else "") + (f"  {note}" if note else ""))


def ogcd_legal(s, name, at, fight, policy=True):
    if name not in CDS or charges(s, name, at)[0] < 1 or dancing(s, at) and name != "Tincture": return False
    if name in ("Fan Dance", "Fan Dance II"): return s.feathers >= 1 - 1e-9
    if name == "Fan Dance III": return s.three >= 1 - 1e-9
    if name == "Fan Dance IV": return s.four_until > at
    if name == "Flourish": return not s.first                   # in combat
    if name == "Tincture": return fight.pot and s.pot_at is None
    return not (policy and s.first)


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in POTENCY and not fight.targetable(at): return None
    use_cd(s, name, at)
    if name in POTENCY:
        if land(fight, at, name) is not None: s.dmg += POTENCY[name] * mult(s, fight, at)
        if name in ("Fan Dance", "Fan Dance II"):          # (Fan Dance II, the AoE one: replays only)
            s.feathers -= 1
            grant(s, "three", at, "Threefold Fan Dance")
        elif name == "Fan Dance III": s.three -= 1.0
        elif name == "Fan Dance IV": s.four_until = -1.0
    elif name == "Devilment": s.dev_until, s.star_until = at + DEV_S, at + STAR_S
    elif name == "Flourish":
        if s.three: wasted(s, 3, s.three)
        if s.four_until > at: wasted(s, 3)
        s.fsym_until = s.fflow_until = s.four_until = s.three_until = at + PROC_S
        s.three = 1.0
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.log(at, name, gauge(s))
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next: while dancing the next step or the finish (nothing else), else the combo's next step
    and whatever is ready."""
    if dancing(c, now): return ["Step" if c.steps < STEPS[c.dance] else FULL[c.dance]]
    out = ["Fountain" if c.combo_until > now else "Cascade"]
    out += [g for g in ("Reverse Cascade", "Fountainfall", "Saber Dance", "Tillana", "Starfall Dance", "Standard Step",
                        "Technical Step") if gcd_legal(c, g, now)]
    return out


def dance(s, fight, step):
    """A whole dance as one step of the search: the Step, its steps and the finish (a state mid-dance has dealt nothing
    yet, so states that bank filler damage at once outranked it: forced on its cooldown, Standard Step gained 1.2%). The
    finish waits for Athena if she is away and the dance lasts; None if it can't be finished."""
    s = do_gcd(s, fight, step)
    while s is not None and dancing(s, max(s.t, s.gcd)):
        now = max(s.t, s.gcd)
        n = do_gcd(s, fight, candidates(s, fight, now)[0])
        if n is None:
            back = fight.back_up(now)
            if back <= now or back >= s.dance_until: return None
            s = s.copy(); s.t = s.gcd = back
            continue
        s = n
    return s


def weaves(s, fight):
    at = s.t
    return [o for o in OGCD_ORDER if ogcd_legal(s, o, at, fight)]


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD or a whole dance. While Athena is away: a wait
    until she is back (with room for two weaves), or a dance timed so that its finish comes as she returns."""
    now = max(s.t, s.gcd)
    if dancing(s, now):
        g = candidates(s, fight, now)[0]
        n = do_gcd(s, fight, g)
        if n is not None: return [n]
        back = fight.back_up(now)                       # the finish waits for Athena (or the dance lapses meanwhile)
        if back <= now: return []
        w = s.copy(); w.t = w.gcd = back
        w.log(s.t, "(boss away)")
        return [w]
    if not s.first and not fight.targetable(now):
        back = fight.back_up(now)
        w = s.copy(); w.t, w.gcd = max(s.t, back - 2 * ANIM_LOCK), back
        w.log(s.t, "(boss away)")
        out = [w]
        for step, kind in (("Standard Step", "std"), ("Technical Step", "tech")):
            at = back - DANCE_RECAST[step] - STEPS[kind] * STEP_RECAST
            if at < now or ready(s, step, at) > at: continue
            d = s.copy(); d.t = d.gcd = at
            d.log(s.t, "(boss away, dance)")
            d = dance(d, fight, step)
            if d is not None: out.append(d)
        return out
    slots = int((s.gcd - s.t) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready_ = weaves(s, fight) if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready_, k):
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            for g in candidates(c, fight, now):
                n = dance(c, fight, g) if g in DANCE_RECAST else do_gcd(c, fight, g)
                if n is not None: out.append(n)
    return out


# what holding a resource is worth (flat potency; engine.configure scales them): what it converts into less RATE times
# the GCD time it takes, as for the other jobs. An Esprit point a fiftieth of Saber Dance over a filler GCD; a feather
# its Fan Dance and half a Fan Dance III; a whole Silken token its proc GCD (with its Esprit and half feather) over the
# filler; the combo Fountain's bonus; Flourishing Starfall / Finish their Starfall Dance / Tillana over a filler. (A dance
# is one step of the search, so no state is left mid-dance but the opener's.)
VALUE = dict(esprit=5, feather=220, three=200, four=300, sym=160, flow=220, combo=160, star=500, ffin=600,
             cap_ss=10, cap_ts=10, cap_dev=8, cap_flo=15)
CAPPED = {"Standard Step": "cap_ss", "Technical Step": "cap_ts", "Devilment": "cap_dev", "Flourish": "cap_flo"}
CAP_W = 1.0
RATE = 230                                            # potency per second, to compare states at slightly different times
# tune.py --job dnc (2026-10-22, 36 settings, R1 whole phase): scales 0.25-0.35 at rates 160-255 all find 86,515, +0.5%
# over the first guesses (1.0); the held values priced at their full conversion tie the filler, as Summoner's. A single
# sweep at (225, 0.85) found 86,562, so the portfolio keeps one there too
HEURISTICS = [(255, 0.35, 0.0), (175, 0.25, 0.0), (225, 0.85, 0.0), (200, 0.6, 0.0)]
WIDTH = 1000
SWEEP_WIDTH = 2000                                    # 1,000-6,000 within 0.2% over the phase (~40 s)
MOVE_WEIGHT = 0.0
END_TAPER = 20.0                                      # held resources fade over the window's last seconds


def held(s, fight=None):
    t = s.t
    v = VALUE["esprit"] * s.esprit + VALUE["feather"] * s.feathers + VALUE["three"] * s.three
    v += VALUE["four"] * (s.four_until > t) + VALUE["sym"] * (s.sym + (s.fsym_until > t))
    v += VALUE["flow"] * (s.flow + (s.fflow_until > t)) + VALUE["combo"] * (s.combo_until > t)
    v += VALUE["star"] * (s.star_until > t) + VALUE["ffin"] * (s.ffin_until > t)
    return v


def score(s):
    """Damage with Starfall Dance's sure critical direct hits at their expected gain over an average hit."""
    return s.dmg + (STAR_W - 1) * s.critp


def rank(s, fight):
    return score(s) + held(s, fight) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - CAP_W * capped(s, s.t) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the autos still to come before the window ends
    return score(s) + (held(s, fight) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Dancer", "2024-08-06"        # 7.05: no level-90 value has changed since
OGCDS = set(OGCD_ORDER) | {"Fan Dance II"}
REFERENCE = ("Fan Dance", 150)                      # 150 at level 90 (the 7.1 notes)
CAST = {}


def cast_time(s, name, at):
    return 0.0, None


def prepare(p):
    """A replay of log p: the procs the log granted (Silken Symmetry / Flow, Threefold), and its pre-pull dance, if its
    first GCD is a finish, begun at the earliest the dance allows. A finish logged twice within a second (FFLogs flags
    the second Quadruple Technical Finish `fake`, not the second of a lesser one) is marked so here."""
    global LOG_PREPULL, LOG_PROCS
    n = p["names"]
    LOG_PROCS = {}
    for x in p.get("buffs", []):
        nm = n[str(x["abilityGameID"])]
        if nm in ("Silken Symmetry", "Silken Flow", "Threefold Fan Dance") and x["type"] in ("applybuff", "refreshbuff"):
            LOG_PROCS.setdefault(nm, []).append(x["t"])
    last = None
    for x in p["casts"]:
        nm = n[str(x["abilityGameID"])]
        if x["type"] != "cast" or nm not in FINISH: continue
        if last is not None and x["t"] - last < 1.0: x["fake"] = True
        else: last = x["t"]
    first = next((x for x in p["casts"] if x["type"] == "cast" and n[str(x["abilityGameID"])] in GCDS), None)
    kind = FINISH[n[str(first["abilityGameID"])]][0] if first and n[str(first["abilityGameID"])] in FINISH else None
    LOG_PREPULL = ("Standard Step" if kind == "std" else "Technical Step", first["t"] - DANCE_S + 0.05) if kind else False


def unprepare():
    global LOG_PREPULL, LOG_PROCS
    LOG_PREPULL = LOG_PROCS = None


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


STATUSES = {"Standard Step": lambda s, t: s.dance == "std" and s.dance_until > t,
            "Technical Step": lambda s, t: s.dance == "tech" and s.dance_until > t,
            "Standard Finish": lambda s, t: s.sf_until > t, "Technical Finish": lambda s, t: s.tf_from <= t < s.tf_until,
            "Devilment": lambda s, t: s.dev_until > t, "Flourishing Starfall": lambda s, t: s.star_until > t,
            "Flourishing Finish": lambda s, t: s.ffin_until > t, "Flourishing Symmetry": lambda s, t: s.fsym_until > t,
            "Flourishing Flow": lambda s, t: s.fflow_until > t, "Fourfold Fan Dance": lambda s, t: s.four_until > t}
# (the procs and feathers are expected values: not compared)


def status(s, t):
    return dict(esprit=round(s.esprit, 1), feathers=s.feathers, sym=s.sym, fsym=s.fsym_until > t, flow=s.flow,
                fflow=s.fflow_until > t, three=s.three, four=s.four_until > t, dance=(s.dance, s.steps) if dancing(s, t) else None)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name in STEP_NAMES and not dancing(s, start): s.dance, s.steps, s.dance_t, s.dance_until = "std", 0, start, start + DANCE_S
    if name in STEP_NAMES and s.steps >= STEPS[s.dance]: s.steps -= 1
    if name in FINISH: s.dance, s.steps, s.dance_t, s.dance_until = FINISH[name][0], FINISH[name][1], start, start + DANCE_S
    if name in ("Standard Step", "Technical Step"):
        s.cds[name] = (1, None); s.dance, s.dance_until = None, -1.0
    if name == "Reverse Cascade": s.sym = max(s.sym, 1.0)
    if name == "Fountainfall": s.flow = max(s.flow, 1.0)
    if name == "Saber Dance": s.esprit = max(s.esprit, 50.0)
    if name == "Tillana": s.ffin_until = start + 1
    if name == "Starfall Dance": s.star_until = start + 1
    if name in ("Cascade", "Fountain", "Reverse Cascade", "Fountainfall", "Saber Dance", "Tillana", "Starfall Dance"):
        s.dance, s.dance_until = None, -1.0
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if name in CDS: s.cds[name] = (1, None)
    if name in ("Fan Dance", "Fan Dance II"): s.feathers = max(s.feathers, 1.0)
    if name == "Fan Dance III": s.three = max(s.three, 1.0)
    if name == "Fan Dance IV": s.four_until = t + 1
    if name != "Tincture": s.dance, s.dance_until = None, -1.0
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s."""
    if name in FINISH:
        kind, n, p, _ = FINISH[name]
        return "", p
    if name not in POTENCY: return None
    if name == "Starfall Dance": return "sure crit", POTENCY[name]
    if name == "Fountain" and s.combo_until > t: return "combo", COMBO_POT[name]
    return "", POTENCY[name]


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the Dancer's own: Standard Finish and Technical Finish
    (FFLogs counts every damage-up on the hit, so dividing it out takes these away too)."""
    b = h.get("buffs") or ""
    return (1.05 if "1001821." in b else 1.0) * (1.05 if "1001822." in b else 1.0)
