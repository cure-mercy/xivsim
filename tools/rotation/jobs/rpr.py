"""Reaper at level 90, Dawntrail patch 7.5 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/reaper) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Melee Mastery III (level 94) raises most potencies by 40-200 there, so the
level-90 ones are measured in the logs (plain hits scaled to Communio 1,100, which no trait or patch has touched):
the benchmark clears (2025) and our groups' pulls (Sep-Oct 2026) agree on all of them except Gluttony, raised from 520
to 560 in 7.5. Checked against the logs over whole pulls with calibrate.py.

Positionals: Gibbet (flank) and Gallows (rear) gain 60 potency from the right side. The player can reach either side
whenever the fight lets them; inside the fight's `pinned` windows (where the strategy fixes their spot) only True North
gets the bonus, and the search decides where to spend its charges.

Reach: melee actions (3 y) need the player beside Athena. In each of the fight's `away` windows they are out of reach
for `need` seconds on end, somewhere in the window: no melee action may break that stretch, and auto-attacks stop
(counted from their last melee hit). Harpe, Harvest Moon, Communio, Plentiful Harvest and Gluttony reach from anywhere
in the arena; inside an away window the search may hard-cast Harpe, or dash with Hell's Ingress for an instant one.
"""
import itertools, math
from engine import ANIM_LOCK, BASE_GCD, RESOLVE, SLIDE, gcd_times, settle, stand

# level-90 potencies, from the logs (the guide's are Melee Mastery III's). Waxing / Infernal Slice: out of combo / in.
POTENCY = {"Slice": 320, "Waxing Slice": (160, 400), "Infernal Slice": (180, 500), "Shadow of Death": 300,
           "Soul Slice": 460, "Gibbet": 400, "Gallows": 400, "Void Reaping": 460, "Cross Reaping": 460,
           "Communio": 1100, "Harpe": 300, "Harvest Moon": 600, "Plentiful Harvest": 1000, "Soulsow": 0,
           "Blood Stalk": 340, "Unveiled Gibbet": 400, "Unveiled Gallows": 400, "Gluttony": 560, "Lemure's Slice": 240}
POSITIONAL, ENHANCED = 60, 60               # Gibbet / Gallows from the flank / rear; enhanced Gibbet, Gallows, Void, Cross
# Plentiful Harvest: 720 at one stack of Immortal Sacrifice, +40 a stack to 1,000 at the eight a full party gives
SACRIFICE = 8
AUTO, AUTO_DELAY = 96, 3.2                  # auto-attacks: 96 potency (logs, scaled to Communio) every 3.21 s
# seconds from executing an action to its damage landing, the logs' medians; buffs snapshot on execution
DELAY = {"Slice": 0.49, "Waxing Slice": 0.58, "Infernal Slice": 0.53, "Shadow of Death": 1.16, "Soul Slice": 1.02,
         "Gibbet": 0.49, "Gallows": 0.49, "Void Reaping": 0.53, "Cross Reaping": 0.62, "Communio": 0.62, "Harpe": 0.89,
         "Harvest Moon": 1.16, "Plentiful Harvest": 1.16, "Blood Stalk": 0.89, "Unveiled Gibbet": 0.53,
         "Unveiled Gallows": 0.53, "Gluttony": 1.07, "Lemure's Slice": 0.71}
CAST = {"Harpe": 1.3, "Communio": 1.3, "Soulsow": 5.0}
REAPING_GCD = 1.5                           # Void / Cross Reaping: fixed, not affected by skill speed
DEATHS_DESIGN, DD_ADD, DD_MAX = 1.10, 30, 60
CIRCLE, CIRCLE_S, BLOODSOWN_S = 1.03, 20, 6
COMBO_S, REAVER_S, ENH_S, REAPING_ENH_S, SHROUD_S, IDEAL_S, SACRIFICE_S, TN_S, HARPE_S = 30, 30, 60, 30, 30, 30, 30, 10, 10
CDS = {"Soul Slice": (30, 2), "Gluttony": (60, 1), "Blood Stalk": (1, 1), "Enshroud": (5, 1), "Lemure's Slice": (1, 1),
       "Arcane Circle": (120, 1), "True North": (45, 2), "Hell's Ingress": (20, 1), "Tincture": (270, 1)}
AVATAR = {"Blood Stalk", "Unveiled Gibbet", "Unveiled Gallows"}       # one action on the hotbar, one recast
MELEE_ACTIONS = {"Slice", "Waxing Slice", "Infernal Slice", "Shadow of Death", "Soul Slice", "Gibbet", "Gallows",
                 "Void Reaping", "Cross Reaping", "Lemure's Slice"} | AVATAR          # 3 y: the rest reach 15-25 y
OGCD_ORDER = ["Tincture", "Arcane Circle", "Gluttony", "Blood Stalk", "Unveiled Gibbet", "Unveiled Gallows", "Enshroud",
              "Lemure's Slice", "True North", "Hell's Ingress"]
SPEED = 0.996                               # skill speed factor on the GCD: 2.49 s, the benchmark clears' median
MELEE = True                                # p12s.py gives it a melee's windows (M1 / M2)


class State:
    __slots__ = ("t", "gcd", "combo", "combo_until", "soul", "shroud", "reaver", "reaver_until", "enh", "enh_until",
                 "renh", "renh_until", "shroud_until", "lemure", "void", "ideal_until", "soulsow", "dd_until",
                 "circle_until", "bloodsown_until", "sacrifice", "sacrifice_until", "tn_until", "harpe_until", "cds",
                 "auto_next", "dmg", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot", "ai", "mlast", "near")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo, s.combo_until, s.soul, s.shroud = 0, -1.0, 0, 0
        s.reaver, s.reaver_until = 0, -1.0
        s.enh, s.enh_until = None, -1.0             # "Gibbet" / "Gallows": which one is enhanced
        s.renh, s.renh_until = None, -1.0           # "Void Reaping" / "Cross Reaping"
        s.shroud_until, s.lemure, s.void, s.ideal_until = -1.0, 0, 0, -1.0
        s.soulsow = True                            # sown before the pull (instant out of combat)
        s.dd_until = s.circle_until = s.bloodsown_until = s.sacrifice_until = s.tn_until = s.harpe_until = -1.0
        s.sacrifice = 0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.auto_next, s.dmg, s.pot_at, s.first, s.hist = 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0
        s.ai, s.mlast, s.near = 0, -30.0, False       # the first away window not yet done; the last melee action;
                                                    # whether an away window is open or close (then mlast matters)
        return s

    def copy(self):
        c = State.__new__(State)
        for k in State.__slots__: setattr(c, k, getattr(self, k))
        c.cds = dict(self.cds)
        return c

    def key(self):
        r = lambda x: round(x, 1)
        left = lambda u: r(max(u - self.t, 0))
        return (r(self.t), r(self.gcd), self.combo if self.combo_until > self.t else 0, self.soul, self.shroud,
                self.reaver if self.reaver_until > self.t else 0, self.enh if self.enh_until > self.t else None,
                self.renh if self.renh_until > self.t else None, left(self.shroud_until), self.lemure, self.void,
                self.ideal_until > self.t, self.soulsow, round(max(self.dd_until - self.t, 0) / 2.5), left(self.circle_until),
                left(self.bloodsown_until), self.sacrifice if self.sacrifice_until > self.t else 0, left(self.tn_until),
                self.pot_at is None, tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()),
                # running banked beyond a run's need and the last melee hit away from an away window change nothing:
                # kept coarse, so near-identical states don't crowd the beam
                self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.ai, r(min(self.t - self.mlast, 4)) if self.near else None)

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Soul Gauge overcapped", "Shroud Gauge overcapped", "Soul Reaver dropped")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


def gain(s, gauge, n):
    cap = 100
    v = getattr(s, gauge) + n
    if v > cap: wasted(s, 0 if gauge == "soul" else 1, v - cap)
    setattr(s, gauge, min(cap, v))


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, own Arcane Circle, Death's Design."""
    return fight.mult(at, s.pot_at) * (CIRCLE if s.circle_until > at else 1) * (DEATHS_DESIGN if s.dd_until > at else 1)


def advance(s, fight, to):
    """Auto-attacks up to `to` (they keep swinging while the boss can be hit), statuses that lapse, and the end of
    Enshroud."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + AUTO_DELAY
    if s.shroud_until <= to and s.lemure: s.lemure = s.void = 0
    if s.reaver_until <= to: s.reaver = 0


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
    return "Blood Stalk" if name in AVATAR else name


def hit(s, fight, at, potency, name):
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land): s.dmg += potency * mult(s, fight, at)


def shrouded(s, at):
    return s.lemure > 0 and s.shroud_until > at


def flank_rear(s, fight, at):
    """Can the player take Gibbet's or Gallows' positional: True North, or a spot the strategy doesn't fix."""
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
    return any(w.lo <= t + ahead and w.hi > t for w in fight.away[s.ai:])


# --- actions -------------------------------------------------------------------------------------------------------

def gcd_legal(s, name, at):
    sh = shrouded(s, at)
    if name in ("Gibbet", "Gallows"): return s.reaver > 0 and s.reaver_until > at
    if name in ("Void Reaping", "Cross Reaping", "Communio"): return sh
    if name == "Harvest Moon": return s.soulsow
    if name == "Soulsow": return not s.soulsow or s.first     # sown at the pull, still out of combat: instant
    if name == "Soul Slice": return not sh and charges(s, name, at)[0] > 0
    if name == "Plentiful Harvest": return not sh and s.sacrifice > 0 and s.sacrifice_until > at and s.bloodsown_until <= at
    return True                                 # the Slice combo, Shadow of Death, Harpe


def potency(s, fight, name, at):
    if name in ("Waxing Slice", "Infernal Slice"):
        lo, hi = POTENCY[name]
        need = 1 if name == "Waxing Slice" else 2
        return hi if s.combo == need and s.combo_until > at else lo
    p = POTENCY[name]
    if name in ("Gibbet", "Gallows"):
        p += ENHANCED * (s.enh == name and s.enh_until > at) + POSITIONAL * flank_rear(s, fight, at)
    if name in ("Void Reaping", "Cross Reaping"): p += ENHANCED * (s.renh == name and s.renh_until > at)
    if name == "Plentiful Harvest": p = min(1000, 720 + 40 * (s.sacrifice - 1))
    return p


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    harm = name != "Soulsow"
    if harm and not fight.targetable(start): return None
    cast = cast_time(s, name, start)[0]
    if s.first:
        if cast: start = RESOLVE - cast                 # a Harpe pre-cast to land at the pull
        s.first = False
    if cast and stand(s, fight, start, start + cast - SLIDE) is None: return None
    if harm and fight.next_down(start) <= start + max(cast - RESOLVE, 0): return None
    if name in MELEE_ACTIONS and not reach(s, fight, start): return None
    recast = REAPING_GCD if name in ("Void Reaping", "Cross Reaping") else BASE_GCD * SPEED
    snap, free, nxt = gcd_times(start, cast, recast)
    if harm: hit(s, fight, snap, potency(s, fight, name, snap), name)
    if name not in ("Gibbet", "Gallows") and s.reaver:      # any other weaponskill or spell ends Soul Reaver
        wasted(s, 2, s.reaver); s.reaver = 0
    if name == "Slice": s.combo, s.combo_until = 1, snap + COMBO_S; gain(s, "soul", 10)
    elif name == "Waxing Slice":
        if s.combo == 1 and s.combo_until > snap: s.combo, s.combo_until = 2, snap + COMBO_S; gain(s, "soul", 10)
        else: s.combo = 0
    elif name == "Infernal Slice":
        if s.combo == 2 and s.combo_until > snap: gain(s, "soul", 10)
        s.combo = 0
    elif name == "Shadow of Death": s.dd_until = min(max(s.dd_until, snap + DELAY[name]) + DD_ADD, snap + DELAY[name] + DD_MAX)
    elif name == "Soul Slice": use_cd(s, name, snap); gain(s, "soul", 50)
    elif name in ("Gibbet", "Gallows"):
        s.reaver -= 1
        s.enh, s.enh_until = ("Gallows" if name == "Gibbet" else "Gibbet"), snap + ENH_S
        gain(s, "shroud", 10)
    elif name in ("Void Reaping", "Cross Reaping"):
        s.lemure -= 1; s.void += 1
        s.renh, s.renh_until = ("Cross Reaping" if name == "Void Reaping" else "Void Reaping"), snap + REAPING_ENH_S
        if not s.lemure: s.void = 0; s.shroud_until = snap
    elif name == "Communio": s.lemure = s.void = 0; s.shroud_until = snap
    elif name == "Harpe":
        if s.harpe_until > start: s.harpe_until = -1.0
        gain(s, "soul", 10)
    elif name == "Harvest Moon": s.soulsow = False; gain(s, "soul", 10)
    elif name == "Soulsow": s.soulsow = True
    elif name == "Plentiful Harvest": s.sacrifice = 0; s.ideal_until = snap + IDEAL_S
    s.t, s.gcd = max(free, snap), nxt
    s.near = away_soon(s, fight, s.t)
    s.log(start, name, gauge(s, f"{cast:.2f}s cast" if cast else "", fight, snap))
    return s


def gauge(s, how, fight=None, at=None):
    sh = f"  shroud {s.lemure}L {s.void}V" if s.lemure else ""
    return (f"{how:<11} soul {s.soul:>3}  shroud {s.shroud:>3}  reaver {s.reaver}" + sh +
            (f"  DD {max(s.dd_until - at, 0):4.1f}s" if at is not None else ""))


def ogcd_legal(s, name, at, fight, policy=True):
    if name in CDS or name in AVATAR:
        n, _ = charges(s, cd_name(name), at)
        if n < 1: return False
    sh = shrouded(s, at)
    reaver = s.reaver > 0 and s.reaver_until > at
    if name in AVATAR:
        want = {"Blood Stalk": None, "Unveiled Gibbet": "Gibbet", "Unveiled Gallows": "Gallows"}[name]
        held = s.enh if s.enh_until > at else None
        return not sh and s.soul >= 50 and held == want and not (policy and reaver)
    if name == "Gluttony": return not sh and s.soul >= 50 and not (policy and reaver)
    if name == "Enshroud": return not sh and not reaver and (s.shroud >= 50 or s.ideal_until > at)
    if name == "Lemure's Slice": return sh and s.void >= 2
    if name == "Arcane Circle": return True
    if name == "True North": return not policy or (s.tn_until <= at and (not flank_rear(s, fight, at + 2.5) or
                                                                         not flank_rear(s, fight, at + 5.0)))
    if name == "Hell's Ingress": return not policy or (s.harpe_until <= at and away_soon(s, fight, at))
    if name == "Tincture": return fight.pot and s.pot_at is None
    return False


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in MELEE_ACTIONS and not reach(s, fight, at): return None
    use_cd(s, cd_name(name), at)
    if name in AVATAR or name == "Gluttony":
        hit(s, fight, at, POTENCY[name], name)
        s.soul -= 50
        n = 2 if name == "Gluttony" else 1
        if s.reaver_until > at and s.reaver: wasted(s, 2, s.reaver)
        s.reaver, s.reaver_until = n, at + REAVER_S
    elif name == "Enshroud":
        if s.ideal_until > at: s.ideal_until = -1.0
        else: s.shroud -= 50
        s.lemure, s.void, s.shroud_until = 5, 0, at + SHROUD_S
    elif name == "Lemure's Slice": hit(s, fight, at, POTENCY[name], name); s.void -= 2
    elif name == "Arcane Circle":
        s.circle_until, s.bloodsown_until = at + CIRCLE_S, at + BLOODSOWN_S
        s.sacrifice, s.sacrifice_until = SACRIFICE, at + SACRIFICE_S
    elif name == "True North": s.tn_until = at + TN_S
    elif name == "Hell's Ingress": s.harpe_until = at + HARPE_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.near = away_soon(s, fight, s.t)
    s.log(at, name, gauge(s, ""))
    return s


GCDS = ["Slice", "Waxing Slice", "Infernal Slice", "Shadow of Death", "Soul Slice", "Gibbet", "Gallows", "Void Reaping",
        "Cross Reaping", "Communio", "Plentiful Harvest", "Harvest Moon", "Harpe", "Soulsow"]


def next_combo(s, at):
    """The one Slice-combo step worth considering: the next in the chain."""
    c = s.combo if s.combo_until > at else 0
    return ["Slice", "Waxing Slice", "Infernal Slice"][c]


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
            now = max(c.t, c.gcd)
            step = next_combo(c, now)
            any_gcd = False
            for g in GCDS:
                if g in ("Slice", "Waxing Slice", "Infernal Slice") and g != step: continue
                if g == "Harpe" and c.harpe_until <= now and not c.first and reach(c, fight, now, commit=False):
                    continue                                    # hard-cast only out of reach (or pre-pull)
                if g not in ("Gibbet", "Gallows") and any(o in AVATAR or o == "Gluttony" for o in combo): continue
                # (Soul Reaver just granted would end unused); True North only before the Gibbet or Gallows it is for,
                # Hell's Ingress before its Harpe: anything else only multiplies the states
                if "True North" in combo and g not in ("Gibbet", "Gallows"): continue
                if "Hell's Ingress" in combo and g != "Harpe": continue
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                w = c.copy(); w.t = w.gcd = fight.back_up(now) if down and c.soulsow else now + 0.5
                w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# what holding a resource is worth over the GCDs it displaces: a Lemure Shroud stack buys a 520-potency Reaping on a
# 1.5 s GCD, ~190 more than 1.5 s of the filler; two Void Shroud a 240-potency weave. A gauge point is worth what it
# converts into: 50 Shroud an Enshroud (five stacks and the Communio), 50 Soul an avatar attack, a Gibbet and 10 Shroud.
VALUE = dict(soul=10, shroud=16, reaver=300, lemure=190, void=100, soulsow=250, ideal=800, sacrifice=700, dd=12, enh=60)
RATE = 220                                            # potency per second, to compare states at slightly different times
# the search: at width 3,000 every setting lands within 0.02% (at 1,000 they spread 3%), so a few settings are enough
HEURISTICS = [(r, 1.0, 0.0) for r in (200, 220, 245, 270)]
WIDTH = 3000
SWEEP_WIDTH = 3000                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: -0.04%
MOVE_WEIGHT = 0.0                                     # melee movement is a different problem (time out of range): not yet


def held(s):
    t = s.t
    v = VALUE["soul"] * s.soul + VALUE["shroud"] * s.shroud
    v += VALUE["reaver"] * (s.reaver if s.reaver_until > t else 0)
    if shrouded(s, t): v += VALUE["lemure"] * s.lemure + VALUE["void"] * s.void
    v += VALUE["soulsow"] * s.soulsow + VALUE["ideal"] * (s.ideal_until > t)
    v += VALUE["sacrifice"] * (s.sacrifice > 0 and s.sacrifice_until > t)
    v += VALUE["dd"] * min(max(s.dd_until - t, 0), 30)
    v += VALUE["enh"] * ((s.enh_until > t) + (s.renh_until > t))
    return v


def rank(s, fight):
    # no credit for running banked (a caster's idea): a Reaper's instants run for free, and the credit would only
    # shift states by where their time falls in a run window
    return s.dmg + held(s) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the swings still to come before the window ends
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Reaper", "2025-01-01"       # every clear in the benchmark is on the Dawntrail kit
OGCDS = set(OGCD_ORDER) | {"Hell's Ingress", "Hell's Egress"}
REFERENCE = ("Communio", 1100)                      # unchanged by traits and patches: scales a log's damage to potency


def cd_name(name):
    return "Blood Stalk" if name in AVATAR else "Hell's Ingress" if name == "Hell's Egress" else name


def cast_time(s, name, at):
    if name == "Harpe" and s.harpe_until > at: return 0.0, "harpe"
    if name == "Soulsow" and s.first: return 0.0, None
    return CAST.get(name, 0.0) * (SPEED if name != "Soulsow" else 1), None


def at(s, fight, t):
    """A copy of the state advanced to t, to read it at a logged cast."""
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    """What a report of an illegal cast shows."""
    return dict(soul=s.soul, shroud=s.shroud, reaver=s.reaver if s.reaver_until > t else 0, lemure=s.lemure, void=s.void,
                enshrouded=shrouded(s, t), ideal=s.ideal_until > t, sacrifice=s.sacrifice if s.sacrifice_until > t else 0,
                soulsow=s.soulsow)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name in ("Gibbet", "Gallows"): s.reaver, s.reaver_until = max(s.reaver, 1), start + REAVER_S
    if name in ("Void Reaping", "Cross Reaping", "Communio"): s.lemure, s.shroud_until = max(s.lemure, 1), start + 5
    if name == "Harvest Moon": s.soulsow = True
    if name == "Plentiful Harvest": s.sacrifice, s.sacrifice_until, s.bloodsown_until = SACRIFICE, start + 5, -1.0
    if name == "Soul Slice":                        # one charge, the recharge still running (it has two)
        s.cds[name] = (1, charges(s, name, start)[1] or start + CDS[name][0])
    return do_gcd(s, fight, name) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Gibbet and Gallows are grouped by True
    North, the one way the log shows a positional was surely taken; without it the model's potency is the miss."""
    if name in ("Waxing Slice", "Infernal Slice"):
        lo, hi = POTENCY[name]
        return ("combo", hi) if potency(s, fight, name, t) == hi else ("no combo", lo)
    if name in ("Gibbet", "Gallows"):
        enh = s.enh == name and s.enh_until > t
        tn = s.tn_until > t
        return ("enh" if enh else "plain") + (" TN" if tn else ""), POTENCY[name] + ENHANCED * enh + POSITIONAL * tn
    if name in ("Void Reaping", "Cross Reaping"):
        enh = s.renh == name and s.renh_until > t
        return ("enh" if enh else "plain"), POTENCY[name] + ENHANCED * enh
    if name == "Plentiful Harvest": return f"{s.sacrifice} stacks", potency(s, fight, name, t)
    if name in POTENCY and POTENCY[name]: return "", POTENCY[name]
    return None


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Death's Design, their Arcane Circle):
    FFLogs counts every damage-up on the hit, so dividing it out takes these away too."""
    b = h.get("buffs") or ""
    m = DEATHS_DESIGN if "1002586." in b else 1.0
    if "1002599." in b:
        n = p["names"]
        if any(x["type"] == "cast" and n[str(x["abilityGameID"])] == "Arcane Circle" and 0 <= h["t"] - x["t"] < CIRCLE_S + 1
               for x in p["casts"]): m *= CIRCLE
    return m
