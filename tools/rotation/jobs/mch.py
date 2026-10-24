"""Machinist at level 90, Dawntrail patch 7.3 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/machinist) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Marksman's Mastery II (level 94) raises the combo, Blazing Shot and the
tools there, Enhanced Multiweapon (94) gives Drill a second charge, and Double Check / Checkmate (92), Excavator (96) and
Full Metal Field (100) lie above P12S. So the level-90 kit is the combo, Drill (one charge), Air Anchor, Chain Saw,
Hypercharge -> Blazing Shot, Gauss Round / Ricochet, Wildfire, Reassemble (two charges), Barrel Stabilizer
(Hypercharged only) and the Automaton Queen.

Level-90 values measured in our logs (2026-10-22, scratch/mch): the scorecard's cached events (our ~186 pulls by four
Machinists, Sep-Oct 2026, with the queen's hits under the owner) and the full FFLogs logs of our 38 clean pulls and the
seven benchmark clears with one. Each player's plain-hit cluster, others' damage buffs divided out and Reassembled hits
and tinctures left out, scaled to Gauss Round (130, untouched at level 90):
- Heated Split Shot 200, Heated Slug Shot 120 / 300 in combo, Heated Clean Shot 120 / 380 in combo (Marksman's Mastery,
  84); Drill, Air Anchor and Chain Saw 620 (7.3's base values); Blazing Shot 240 (taken as 220 + Overheated's 20);
  Gauss Round and Ricochet 130; auto-attacks ("Shot") 60 potency every 2.67 s;
- the queen's hits grow with the battery it was deployed with, linearly from 50 to 100: Arm Punch 2.2, Pile Bunker 6.15,
  Crowned Collider 7.0 potency a battery point (0.9 times the guide's tooltips); it punches five times (or Roller Dash
  for the first two, the same potency) 6.4-12.6 s after the deploy, then Pile Bunker at 14.7 s and Crowned Collider at
  17.4 s, so a deploy is worth ~24 potency a battery point. No one used Queen Overdrive; deploys were >= 21.8 s apart;
- Wildfire detonates 10.6 s after its cast for 240 a weaponskill landed under it (status from cast + 0.6 s), six at
  most; FFLogs logs the detonation as a tick, never a crit or direct hit, so it counts with the DoT ticks (dotp).

Rules from the logs: Drill, Air Anchor, Chain Saw, Hypercharge and Blazing Shot never break the combo; heat is +5 for
Heated Split Shot and each combo step, never below 50 at a paid Hypercharge; Blazing Shot's recast is a fixed 1.5 s
(1.47-1.51 at every skill speed) and takes 15 s off both Gauss Round and Ricochet; Overheated gives five stacks for 10 s;
37 of 45 full logs open with a Reassemble pressed before the pull (its status falls off on the first tool, its cast
isn't logged) and the search does the same (PREPULL_RA). Reassemble went on Drill, Air Anchor or Chain Saw every time.

Reassembled weaponskills are critical direct hits: s.critp holds their plain potency, the search weighs them at a sure
critical direct hit's gain (SURE_W, as Pictomancer's hammers) and dps.py converts them at each player's own (AUTO_CRIT
names the tools the logs' Reassembles went on, so dps.py measures that gain on them).

Every action is instant (Flamethrower, a channel, is left out) and reaches 25 y; the queen and the autos too. So the
strategy's running costs a Machinist nothing, only Palladion's downtime: R1, R2 and standing still play the same.
"""
import itertools
from engine import ANIM_LOCK, BASE_GCD, settle

POTENCY = {"Heated Split Shot": 200, "Heated Slug Shot": 120, "Heated Clean Shot": 120, "Drill": 620, "Air Anchor": 620,
           "Chain Saw": 620, "Blazing Shot": 220, "Gauss Round": 130, "Ricochet": 130}
COMBO = ("Heated Split Shot", "Heated Slug Shot", "Heated Clean Shot")
COMBO_POT = {"Heated Slug Shot": 300, "Heated Clean Shot": 380}
OH_BONUS = 20                                   # Overheated: +20 on single-target weaponskills
TOOLS = ("Drill", "Air Anchor", "Chain Saw")
BATTERY = {"Heated Clean Shot": 10, "Air Anchor": 20, "Chain Saw": 20}       # Clean Shot's only in combo
# the queen: (seconds after the deploy, potency a battery point), from the cached hits (Arm Punch x5, Pile Bunker,
# Crowned Collider); she stays out until the last, and can't be deployed again meanwhile
QUEEN = ((6.4, 2.2), (8.0, 2.2), (9.55, 2.2), (11.0, 2.2), (12.6, 2.2), (14.7, 6.15), (17.4, 7.0))
QUEEN_S = 17.5
WF_POT, WF_MAX, WF_LAG, WF_S = 240, 6, 0.6, 10.0  # Wildfire: a weaponskill landing in [cast + 0.6, cast + 10.6] counts
AUTO, AUTO_DELAY = 60, 2.67
# seconds from executing an action to its damage landing, the logs' medians
DELAY = {"Heated Split Shot": 0.76, "Heated Slug Shot": 0.80, "Heated Clean Shot": 0.80, "Drill": 1.16,
         "Air Anchor": 1.16, "Chain Saw": 1.03, "Blazing Shot": 0.85, "Gauss Round": 0.80, "Ricochet": 0.62}
COMBO_S, OH_S, OH_STACKS, HC_S, RA_S = 30.0, 10.0, 5, 30.3, 5.0     # Hypercharged: one log spends it 30.26 s on
BLAZING_RECAST, BLAZING_CUT = 1.5, 15.0
PREPULL_RA = -4.5                               # the search's pre-pull Reassemble (its status lasts 5 s)
CDS = {"Drill": (20, 1), "Air Anchor": (40, 1), "Chain Saw": (60, 1), "Reassemble": (55, 2), "Gauss Round": (30, 3),
       "Ricochet": (30, 3), "Hypercharge": (10, 1), "Wildfire": (120, 1), "Barrel Stabilizer": (120, 1),
       "Automaton Queen": (6, 1), "Tincture": (270, 1)}
GCDS = list(COMBO) + list(TOOLS) + ["Blazing Shot"]
OGCD_ORDER = ["Tincture", "Barrel Stabilizer", "Wildfire", "Hypercharge", "Reassemble", "Automaton Queen",
              "Gauss Round", "Ricochet"]
AUTO_CRIT = set(TOOLS)                          # where the logs' Reassembles go: dps.py measures the sure gain on them
CRIT_RATE, CRIT_DMG, DH_RATE, DH_DMG = 0.25, 1.60, 0.30, 1.25


def derive():
    """SURE_W from the rates (engine.configure calls it again after setting them: the gear model's set's own)."""
    global SURE_W
    SURE_W = CRIT_DMG * DH_DMG / ((1 + CRIT_RATE * (CRIT_DMG - 1)) * (1 + DH_RATE * (DH_DMG - 1)))


derive()
SPEED = 0.98                                    # skill speed factor: a 2.45 s GCD (our Machinists: 2.41-2.50)
LOG_PREPULL = None                              # a replay: when the log's pre-pull Reassembled fell off (prepare)


class State:
    __slots__ = ("t", "gcd", "combo", "combo_until", "heat", "batt", "hc_until", "oh", "oh_until", "ra_until",
                 "wf_t", "wf_n", "wf_m", "queen_until", "cds", "auto_next", "dmg", "dotp", "critp", "lost", "waste",
                 "pot_at", "first", "hist", "mvi", "acc", "free", "spot")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo, s.combo_until, s.heat, s.batt = 0, -1.0, 0, 0
        s.hc_until, s.oh, s.oh_until = -1.0, 0, -1.0
        s.wf_t, s.wf_n, s.wf_m, s.queen_until = None, 0, 1.0, -1.0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        ra = PREPULL_RA if LOG_PREPULL is None else LOG_PREPULL
        s.ra_until = -1.0
        if ra is not False:                             # pre-pull Reassemble: one charge recharging, the status up
            s.cds["Reassemble"] = (1, ra + CDS["Reassemble"][0])
            s.ra_until = ra + RA_S + 0.05               # (a replay's falls off on the first tool's cast)
        s.auto_next = 0.0
        s.dmg, s.dotp, s.critp, s.lost, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0
        return s

    def copy(self):
        c = State.__new__(State)
        for k in State.__slots__: setattr(c, k, getattr(self, k))
        c.cds = dict(self.cds)
        return c

    def key(self):
        r = lambda x: round(x, 1)
        left = lambda u: r(max(u - self.t, 0))
        return (r(self.t), r(self.gcd), self.combo if self.combo_until > self.t else 0, self.heat, self.batt,
                left(self.hc_until), self.oh if self.oh_until > self.t else 0, left(self.ra_until),
                self.wf_n if self.wf_t is not None and self.wf_t + WF_LAG + WF_S > self.t else -1, left(self.queen_until),
                self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()))

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("heat overcapped", "battery overcapped", "Blazing Shot cuts lost on full charges", "Overheated stacks dropped")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time and cooldowns --------------------------------------------------------------------------------------------

def advance(s, fight, to):
    """Auto-attacks up to `to`, and Overheated stacks that lapse."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a): s.dmg += AUTO * fight.mult(a, s.pot_at)
        s.auto_next = a + AUTO_DELAY
    if s.oh and s.oh_until <= to: wasted(s, 3, s.oh); s.oh = 0


def recast_of(name):
    """Drill, Air Anchor and Chain Saw are weaponskills: skill speed shortens their recast (Drill 19.3 s at 2.41)."""
    return CDS[name][0] * (SPEED if name in TOOLS else 1.0)


def charges(s, name, at):
    n, nxt = s.cds[name]
    rec, mx = recast_of(name), CDS[name][1]
    while n < mx and nxt is not None and nxt <= at:
        n += 1; nxt = nxt + rec if n < mx else None
    return n, nxt


def full_since(s, name, t):
    """When the cooldown last came back to full charges, if it is full at t (else None); full at the pull counts from 0."""
    n, nxt = s.cds[name]
    rec, mx = recast_of(name), CDS[name][1]
    if n == mx: return 0.0
    f = nxt + (mx - n - 1) * rec
    return f if f <= t else None


def capped(s, t):
    """Potency the cooldowns have lost sitting full so far (CAPPED: what a second of their recharge is worth)."""
    v = s.lost
    for name, k in CAPPED.items():
        f = full_since(s, name, t)
        if f is not None: v += VALUE[k] * max(t - max(f, 0.0), 0)
    return v


def use_cd(s, name, at):
    n, nxt = charges(s, name, at)
    rec, mx = recast_of(name), CDS[name][1]
    if n == mx:
        if name in CAPPED: s.lost += VALUE[CAPPED[name]] * max(at - max(full_since(s, name, at), 0.0), 0)
        nxt = at + rec
    s.cds[name] = (n - 1, nxt)


def cut(s, name, at, secs):
    """Take secs off the recharge (Blazing Shot on Gauss Round and Ricochet); lost on a full cooldown."""
    n, nxt = charges(s, name, at)
    rec, mx = recast_of(name), CDS[name][1]
    if n == mx:
        wasted(s, 2)
        if name in CAPPED: s.lost += VALUE[CAPPED[name]] * secs
        return
    nxt -= secs
    if nxt <= at:
        n += 1
        if n == mx: s.cds[name] = (mx - 1, at); return       # full from now (full_since reads it so)
        nxt += rec
    s.cds[name] = (n, nxt)


def cd_name(name):
    return name


def ready(s, name, t):
    """When the cooldown next has a charge, from t."""
    n, nxt = charges(s, name, t)
    return t if n else nxt


# --- actions -------------------------------------------------------------------------------------------------------

def overheated(s, t):
    return s.oh > 0 and s.oh_until > t


def combo_step(s, t):
    return s.combo if s.combo_until > t else 0


def gcd_legal(s, name, at):
    if name == "Blazing Shot": return overheated(s, at)
    if name in TOOLS: return charges(s, name, at)[0] >= 1
    return name in COMBO


def potency(s, name, at):
    p = POTENCY[name]
    if name in COMBO_POT and combo_step(s, at) == COMBO.index(name): p = COMBO_POT[name]
    return p + (OH_BONUS if overheated(s, at) else 0)


def land(s, fight, at, name):
    """When a hit of `name` executed at `at` lands, if it lands on Athena inside the window (else None)."""
    t = at + DELAY.get(name, 0.8)
    return t if 0 <= t < fight.until and fight.targetable(t) else None


def wildfire(s, fight, t):
    """A weaponskill landing at t counts for the Wildfire on Athena (its 240 booked now, if it detonates in the window)."""
    if s.wf_t is None or s.wf_n >= WF_MAX or not s.wf_t + WF_LAG <= t <= s.wf_t + WF_LAG + WF_S: return
    s.wf_n += 1
    boom = s.wf_t + WF_LAG + WF_S
    if boom < fight.until and fight.targetable(boom):
        d = WF_POT * s.wf_m
        s.dmg += d; s.dotp += d


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start) or not fight.targetable(start): return None
    s.first = False
    p = potency(s, name, start)
    t = land(s, fight, start, name)
    if t is not None:
        d = p * fight.mult(start, s.pot_at)
        if s.ra_until > start: d *= fight.sure(start, dh=True)     # raid crit / direct-hit buffs as damage on a sure hit
        s.dmg += d
        if s.ra_until > start: s.critp += d
        wildfire(s, fight, t)
    if s.ra_until > start: s.ra_until = -1.0
    hit = name in COMBO and (name == COMBO[0] or combo_step(s, start) == COMBO.index(name))
    if name in COMBO:
        if hit:
            h = s.heat + 5
            if h > 100: wasted(s, 0, h - 100)
            s.heat = min(100, h)
        if name == "Heated Clean Shot" and hit: s.combo, s.combo_until = 0, -1.0
        elif hit: s.combo, s.combo_until = COMBO.index(name) + 1, start + COMBO_S
        else: s.combo, s.combo_until = 0, -1.0
    if name in BATTERY and (name in TOOLS or hit):
        b = s.batt + BATTERY[name]
        if b > 100: wasted(s, 1, b - 100)
        s.batt = min(100, b)
    if name in TOOLS: use_cd(s, name, start)
    if name == "Blazing Shot":
        s.oh -= 1
        for g in ("Gauss Round", "Ricochet"): cut(s, g, start, BLAZING_CUT)
    recast = BLAZING_RECAST if name == "Blazing Shot" else BASE_GCD * SPEED
    s.t, s.gcd = start + ANIM_LOCK, start + recast
    s.log(start, name, gauge(s))
    return s


def gauge(s):
    t = s.t
    return (f"heat {s.heat:3d}  battery {s.batt:3d}" + (f"  overheated {s.oh}" if overheated(s, t) else "")
            + ("  hypercharged" if s.hc_until > t else "") + ("  reassembled" if s.ra_until > t else "")
            + (f"  wildfire {s.wf_n}" if s.wf_t is not None and s.wf_t + WF_LAG + WF_S > t else ""))


def ogcd_legal(s, name, at, fight, policy=True):
    if name not in CDS or charges(s, name, at)[0] < 1: return False
    if name == "Hypercharge": return not overheated(s, at) and (s.hc_until > at or s.heat >= 50)
    if name == "Automaton Queen": return s.batt >= 50 and s.queen_until <= at
    if name == "Barrel Stabilizer": return at >= 0          # in combat
    if name == "Reassemble": return not (policy and s.ra_until > at)
    if name == "Tincture": return fight.pot and s.pot_at is None
    return not (policy and s.first)                 # the search opens with a GCD


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    # the queen too: whether she can be deployed with Athena away (her first hit 6.4 s later) isn't in the logs
    if name in ("Gauss Round", "Ricochet", "Wildfire", "Automaton Queen") and not fight.targetable(at): return None
    use_cd(s, name, at)
    if name in ("Gauss Round", "Ricochet"):
        t = land(s, fight, at, name)
        if t is not None: s.dmg += POTENCY[name] * fight.mult(at, s.pot_at)
    elif name == "Hypercharge":
        if s.hc_until > at: s.hc_until = -1.0
        else: s.heat -= 50
        s.oh, s.oh_until = OH_STACKS, at + OH_S
    elif name == "Barrel Stabilizer": s.hc_until = at + HC_S
    elif name == "Reassemble": s.ra_until = at + RA_S
    elif name == "Wildfire": s.wf_t, s.wf_n, s.wf_m = at, 0, fight.mult(at, s.pot_at)
    elif name == "Automaton Queen":
        for off, k in QUEEN:
            t = at + off
            if 0 <= t < fight.until and fight.targetable(t): s.dmg += k * s.batt * fight.mult(t, s.pot_at)
        s.batt, s.queen_until = 0, at + QUEEN_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.log(at, name, gauge(s))
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next: Blazing Shot while Overheated (nothing else), else the next combo step and any tool
    that is ready."""
    if overheated(c, now): return ["Blazing Shot"]
    return [COMBO[combo_step(c, now)]] + [x for x in TOOLS if charges(c, x, now)[0] >= 1]


def weaves(s, fight):
    """The oGCDs worth weaving now. Gauss Round and Ricochet are the same action on two recasts: alone, only the one with
    more charges (or the sooner next one) is offered; Wildfire only next to a Hypercharge, in an Overheated window still
    to come, or before the boss goes away or the window ends."""
    at = s.t
    bs = ogcd_legal(s, "Barrel Stabilizer", at, fight)
    return [o for o in OGCD_ORDER if ogcd_legal(s, o, at, fight) or o == "Hypercharge" and bs      # Hypercharged by it
            and charges(s, o, at)[0] >= 1 and not overheated(s, at)]


def gr_key(s, name, at):
    n, nxt = charges(s, name, at)
    return (n, -(nxt if nxt is not None else -1))


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD; while Athena is away, a wait until she is
    back (with room for two weaves before the first GCD)."""
    now = max(s.t, s.gcd)
    if not s.first and not fight.targetable(now):
        back = fight.back_up(now)
        w = s.copy(); w.t, w.gcd = max(s.t, back - 2 * ANIM_LOCK), back
        w.log(s.t, "(boss away)")
        return [w]
    slots = int((s.gcd - s.t) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready_ = weaves(s, fight) if slots else []
    both = "Gauss Round" in ready_ and "Ricochet" in ready_
    lone = (min(("Gauss Round", "Ricochet"), key=lambda g: gr_key(s, g, s.t)) if both else None)
    end = min(fight.next_down(s.t), fight.until)
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready_, k):
            if lone in combo and len([g for g in combo if g in ("Gauss Round", "Ricochet")]) == 1: continue
            if "Wildfire" in combo and "Hypercharge" not in combo and not (end - s.t < 12): continue
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            for g in candidates(c, fight, now):
                if "Reassemble" in combo and g not in TOOLS: continue        # Reassemble only right before a tool
                if "Hypercharge" in combo and g != "Blazing Shot": continue
                n = do_gcd(c, fight, g)
                if n is not None: out.append(n)
    return out


# what holding a resource is worth (flat potency; engine.configure scales them): what it converts into less RATE times
# the GCD time it takes. A heat point a fiftieth of a Hypercharge (five Blazing Shots and their 150 s of Gauss Round /
# Ricochet over 7.5 s); a battery point two thirds of what the queen makes of it (~24, booked at the deploy: valued at
# all 24, a scale above 1 made the beam hold battery, 5 queens instead of 11 and -3.5%; at 12-18 scales 1.0 and 1.4 tie);
# a combo step what the rest of the combo brings over Heated Split Shots; Hypercharged a Hypercharge; an Overheated
# stack its Blazing Shot over 1.5 s; Reassembled a tool's sure critical direct hit.
VALUE = dict(heat=7, batt=16, combo1=280, combo2=180, hc=350, oh=80, ra=375,
             cap_gr=9, cap_drill=12, cap_aa=18, cap_cs=12, cap_ra=7, cap_wf=12, cap_bs=6)
# A cooldown sitting at full charges loses what its recharge would bring (pct.py's CAPPED, at its share a second)
CAPPED = {"Gauss Round": "cap_gr", "Ricochet": "cap_gr", "Drill": "cap_drill", "Air Anchor": "cap_aa",
          "Chain Saw": "cap_cs", "Reassemble": "cap_ra", "Wildfire": "cap_wf", "Barrel Stabilizer": "cap_bs"}
CAP_W = 1.0
RATE = 200                                            # potency per second, to compare states at slightly different times
# tune.py --job mch (2026-10-22, 36 settings, R1 whole phase): scales 1.25-1.95 at rates 160-210 all find 111,688, +0.43%
# over the first guesses (scale 0.5-1.0); R2 the same (every action is instant, so the slots tie)
HEURISTICS = [(200, 1.25, 0.0), (175, 1.55, 0.0), (175, 1.9, 0.0), (185, 1.4, 0.0)]
WIDTH = 1000                                          # the beam (--layers gcd): 500-4,000 within 0.3% (35 s at 1,000)
SWEEP_WIDTH = 2000                                    # engine.sweep (layers by time): 500-2,000 tie, +0.5% over the beam at
                                                      # 1,000 in 20 s; 4,000 found 0.2% less
MOVE_WEIGHT = 0.0
END_TAPER = 20.0                                      # held resources fade over the window's last seconds


def held(s, fight=None):
    t = s.t
    v = VALUE["heat"] * s.heat + VALUE["batt"] * s.batt + VALUE["hc"] * (s.hc_until > t)
    v += VALUE["combo1"] * (combo_step(s, t) == 1) + VALUE["combo2"] * (combo_step(s, t) == 2)
    v += VALUE["oh"] * (s.oh if overheated(s, t) else 0) + VALUE["ra"] * (s.ra_until > t)
    return v


def score(s):
    """Damage with the Reassembled hits' critical direct hits at their expected gain over an average hit."""
    return s.dmg + (SURE_W - 1) * s.critp


def rank(s, fight):
    return score(s) + held(s, fight) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - CAP_W * capped(s, s.t) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the shots still to come before the window ends
    return score(s) + (held(s, fight) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Machinist", "2025-08-05"     # 7.3: Drill, Air Anchor and Chain Saw at their current values
OGCDS = set(OGCD_ORDER)
REFERENCE = ("Gauss Round", 130)                    # no trait or patch touches it at level 90
CAST = {}


def cast_time(s, name, at):
    return 0.0, None


def prepare(p):
    """A replay of log p opens with the log's pre-pull Reassemble, if it had one (the status falls off before any is
    applied: its cast isn't logged), pressed at the earliest it can have been (its 5 s before it fell off)."""
    global LOG_PREPULL
    n = p["names"]
    ev = [x for x in p.get("buffs", []) if n[str(x["abilityGameID"])] == "Reassembled" and x["type"] in ("applybuff", "removebuff")]
    LOG_PREPULL = ev[0]["t"] - RA_S if ev and ev[0]["type"] == "removebuff" else False


def unprepare():
    global LOG_PREPULL
    LOG_PREPULL = None


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(combo=combo_step(s, t), heat=s.heat, batt=s.batt, oh=s.oh if overheated(s, t) else 0,
                hc=s.hc_until > t, ra=s.ra_until > t, queen=s.queen_until > t)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name == "Blazing Shot": s.oh, s.oh_until = max(s.oh, 1), max(s.oh_until, start + 1)
    if name in TOOLS: s.cds[name] = (0, start)
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if name in CDS:                                 # one charge, the recharge still running
        rec, mx = recast_of(name), CDS[name][1]
        s.cds[name] = (1, charges(s, name, t)[1] or (None if mx == 1 else t + rec))
    if name == "Hypercharge": s.heat, s.oh, s.oh_until = max(s.heat, 50), 0, -1.0
    if name == "Automaton Queen": s.batt, s.queen_until = max(s.batt, 50), -1.0
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s."""
    if name not in POTENCY: return None
    p = potency(s, name, t) if name in GCDS else POTENCY[name]
    if name in GCDS and s.ra_until > t: return "sure crit", p
    combo = name in COMBO_POT and combo_step(s, t) == COMBO.index(name)
    return ("combo" if combo else "") + (" OH" if overheated(s, t) and name in GCDS else ""), p


def cast_label(s, name, t):
    return ""
