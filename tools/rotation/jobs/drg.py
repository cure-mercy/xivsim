"""Dragoon at level 90, Dawntrail patch 7.1 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/dragoon) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Melee Mastery (level 94) raises Fang and Claw, Wheeling Thrust, Drakesbane,
Raiden Thrust, Stardiver, Heavens' Thrust, Chaotic Spring and Wyrmwind Thrust there, and Starcross (100), Rise of the
Dragon and Dragon's Flight (92), Lance Barrage and Spiral Blow (96) lie above P12S. 7.1 set the level-90 Stardiver
(720), Nastrond (720 by Lance Mastery III, one stack per Geirskogul) and Mirage Dive (380); 7.2-7.3 only touched
level-94+ and AoE values.

FFLogs was down when this was written, so the level-90 potencies were measured in the scorecard's cached damage events
(.cache/acts_*: our groups' 311 pulls by six Dragoons, Sep-Oct 2026, and 11 benchmark clears): each player's plain-hit
cluster with Power Surge, Lance Charge and Life of the Dragon divided out and others' raid buffs left out, scaled to
High Jump (400: no trait or patch touches it). FFLogs' bonusPercent (the share of a hit's potency from its combo or
positional) confirms every split, e.g. Fang and Claw 61% = (260 - 100) / 260 in combo, 66% = (300 - 100) / 300 from the
flank. Both data sets agree within ~2%. calibrate.py's full-pull replay (legality, cast by cast) still waits for FFLogs.

Combos (Dawntrail: two five-step chains, 30 s, not broken by Piercing Talon):
  True Thrust / Raiden Thrust -> Vorpal Thrust -> Heavens' Thrust -> Fang and Claw (flank) -> Drakesbane
  True Thrust / Raiden Thrust -> Disembowel (Power Surge: +10%, 30 s) -> Chaotic Spring (rear; DoT) -> Wheeling Thrust
                                 (rear) -> Drakesbane
Drakesbane grants Draconian Fire (30 s, ended by any melee weaponskill), which turns True Thrust into Raiden Thrust;
Raiden Thrust sharpens one Firstminds' Focus (two at most) and Wyrmwind Thrust spends two.

Geirskogul grants Life of the Dragon (+15%, 20 s: Stardiver only under it) and one Nastrond Ready; High Jump grants
Dive Ready (Mirage Dive). Statuses come on with the cast, so a hit doesn't get the one its own action grants; Lance
Charge (+10%) and Battle Litany land 0.63 s after theirs. The jumps lock the player longer than other oGCDs (LOCK), so
Stardiver is single-woven.

Crits: Life Surge makes the next weaponskill a sure critical hit, and Battle Litany raises the own crit rate by 10% (a
sure crit under it gains that as crit damage instead). Both count at their expected worth over an average hit at the
player's CRIT rate (dps.py sets it, and leaves the Life Surge hits out when it measures a player's crit gain:
sure_crits).

Positionals (+40): Chaotic Spring and Wheeling Thrust from the rear, Fang and Claw from the flank; inside the fight's
`pinned` windows only True North gets them. Reach: the melee weaponskills (3 y) need the player beside Athena (see
jobs/rpr.py for the away windows); Piercing Talon, the jumps and the 15 y lines (Geirskogul, Nastrond, Wyrmwind Thrust)
reach from anywhere. Out of reach the search may jump back with Elusive Jump for an Enhanced Piercing Talon (350).
"""
import itertools, math
from engine import ANIM_LOCK, BASE_GCD, settle

# level-90 potencies from the logs (see above). (out of combo, in combo) for combo actions.
POTENCY = {"True Thrust": 230, "Raiden Thrust": 280, "Vorpal Thrust": (130, 280), "Heavens' Thrust": (100, 400),
           "Fang and Claw": (100, 260), "Disembowel": (140, 250), "Chaotic Spring": (100, 260),
           "Wheeling Thrust": (100, 260), "Drakesbane": 400, "Piercing Talon": (200, 350),
           "High Jump": 400, "Mirage Dive": 380, "Geirskogul": 280, "Nastrond": 720, "Stardiver": 720,
           "Dragonfire Dive": 500, "Wyrmwind Thrust": 420,
           "Doom Spike": 110, "Draconian Fury": 130, "Sonic Thrust": (100, 120), "Coerthan Torment": (100, 150)}  # AoE
POSITIONAL = 40                                 # Chaotic Spring, Wheeling Thrust (rear), Fang and Claw (flank)
POSITIONALS = ("Chaotic Spring", "Wheeling Thrust", "Fang and Claw")
# Chaotic Spring's DoT: 45 potency for 24 s by the tooltip; ticks land for 48-52 relative to High Jump in the logs, with
# the buffs they snapshot divided out (DoTs scale with skill speed and are computed differently: BLM's Thunder III too)
DOT, DOT_S = 50, 24.0
DOT_PHASE = 1.5                                 # server ticks land at DOT_PHASE + 3k seconds
AUTO, AUTO_DELAY = 86, 2.81                     # auto-attacks, from the logs (84 in the 2025 clears)
# seconds from executing an action to its damage landing, the logs' medians; buffs snapshot on execution
DELAY = {"True Thrust": 0.76, "Raiden Thrust": 0.62, "Vorpal Thrust": 1.02, "Heavens' Thrust": 0.71,
         "Fang and Claw": 0.62, "Disembowel": 1.65, "Chaotic Spring": 0.45, "Wheeling Thrust": 0.67, "Drakesbane": 1.65,
         "Piercing Talon": 0.85, "High Jump": 0.49, "Mirage Dive": 0.80, "Geirskogul": 0.63, "Nastrond": 0.76,
         "Stardiver": 1.29, "Dragonfire Dive": 0.80, "Wyrmwind Thrust": 1.20}
# animation locks longer than the usual oGCD's: the logs' 10th percentile to the next action, +0.02 s as for the others
LOCK = {"High Jump": 0.87, "Dragonfire Dive": 0.87, "Stardiver": 1.58, "Elusive Jump": 0.96}
WEAVE_SLACK = 0.05                              # a weave may clip the GCD by this much
POWER_SURGE, LANCE_CHARGE, LIFE = 1.10, 1.10, 1.15
BUFF_DELAY = 0.63                               # Lance Charge and Battle Litany land this long after the cast
LITANY_RATE = 0.10
COMBO_S, DF_S, PS_S, LC_S, BL_S, LOTD_S, NR_S, DR_S, LS_S, TN_S, EPT_S = 30, 30, 30, 20, 20, 20, 20, 15, 5, 10, 15
CDS = {"Life Surge": (40, 2), "Lance Charge": (60, 1), "Battle Litany": (120, 1), "Geirskogul": (60, 1),
       "Nastrond": (2, 1), "Stardiver": (30, 1), "High Jump": (30, 1), "Mirage Dive": (1, 1),
       "Dragonfire Dive": (120, 1), "Wyrmwind Thrust": (10, 1), "True North": (45, 2), "Elusive Jump": (30, 1),
       "Tincture": (270, 1)}
CRIT, CRIT_DMG = 0.25, 1.60                     # the player's crit rate (dps.py sets it) and crit damage
# combo steps: what each one follows, and the step it leaves the combo at when it lands in combo
FOLLOWS = {"Vorpal Thrust": "1", "Disembowel": "1", "Heavens' Thrust": "v", "Chaotic Spring": "d", "Fang and Claw": "h",
           "Wheeling Thrust": "c", "Drakesbane": "f", "Sonic Thrust": "aoe", "Coerthan Torment": "aoe2"}
LEADS = {"True Thrust": "1", "Raiden Thrust": "1", "Vorpal Thrust": "v", "Disembowel": "d", "Heavens' Thrust": "h",
         "Chaotic Spring": "c", "Fang and Claw": "f", "Wheeling Thrust": "f"}
NEXT = {None: (), "1": ("Vorpal Thrust", "Disembowel"), "v": ("Heavens' Thrust",), "d": ("Chaotic Spring",),
        "h": ("Fang and Claw",), "c": ("Wheeling Thrust",), "f": ("Drakesbane",)}
MELEE_ACTIONS = {"True Thrust", "Raiden Thrust", "Vorpal Thrust", "Heavens' Thrust", "Fang and Claw", "Disembowel",
                 "Chaotic Spring", "Wheeling Thrust", "Drakesbane"}        # 3 y: the rest reach 15-20 y
GCDS = sorted(MELEE_ACTIONS) + ["Piercing Talon", "Doom Spike", "Draconian Fury", "Sonic Thrust", "Coerthan Torment"]
LS_TARGETS = ("Heavens' Thrust", "Drakesbane")  # the 400-potency weaponskills: the search spends Life Surge on these
OGCD_ORDER = ["Tincture", "Lance Charge", "Battle Litany", "Life Surge", "Geirskogul", "Nastrond", "Stardiver",
              "High Jump", "Mirage Dive", "Dragonfire Dive", "Wyrmwind Thrust", "True North", "Elusive Jump"]
SPEED = 0.996                                   # skill speed factor on the GCD: 2.49 s, the benchmark clears' median
MELEE = True                                    # p12s.py gives it a melee's windows (M1 / M2)


class State:
    __slots__ = ("t", "gcd", "combo", "combo_until", "df_until", "focus", "ps_until", "lc_from", "lc_until", "bl_from",
                 "bl_until", "lotd_until", "nr_until", "dr_until", "ls_until", "tn_until", "ept_until", "dot", "cds",
                 "auto_next", "dmg", "dotp", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot", "ai",
                 "mlast", "near")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo, s.combo_until, s.df_until, s.focus = None, -1.0, -1.0, 0
        s.ps_until = s.lc_from = s.lc_until = s.bl_from = s.bl_until = s.lotd_until = -1.0
        s.nr_until = s.dr_until = s.ls_until = s.tn_until = s.ept_until = -1.0
        s.dot = None                                # (when Chaotic Spring's DoT landed, the multiplier it snapshot)
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.auto_next, s.dmg, s.dotp, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, None, True, None
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
        return (r(self.t), r(self.gcd), self.combo if self.combo_until > self.t else None, self.df_until > self.t,
                self.focus, round(max(self.ps_until - self.t, 0) / 2.5), left(self.lc_until), left(self.bl_until),
                left(self.lotd_until), self.nr_until > self.t, self.dr_until > self.t, self.ls_until > self.t,
                left(self.tn_until), self.ept_until > self.t,
                round(max(self.dot[0] + DOT_S - self.t, 0) / 2.5) if self.dot else None, self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()),
                self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.ai, r(min(self.t - self.mlast, 4)) if self.near else None)

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Firstminds' Focus overcapped", "Life Surge lapsed", "Dive Ready or Nastrond Ready lapsed")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at` (crits apart): raid buffs, tincture, Power Surge, Lance Charge, Life
    of the Dragon."""
    return (fight.mult(at, s.pot_at) * (POWER_SURGE if s.ps_until > at else 1) *
            (LANCE_CHARGE if s.lc_from <= at < s.lc_until else 1) * (LIFE if s.lotd_until > at else 1))


def crit_factor(s, at, sure=False):
    """A hit's expected crit worth over an average hit at the player's CRIT: Battle Litany adds 10% crit rate; a sure
    crit (Life Surge) deals the crit damage, plus the crit rate Battle Litany adds."""
    bl = LITANY_RATE if s.bl_from <= at < s.bl_until else 0.0
    avg = 1 + CRIT * (CRIT_DMG - 1)
    return ((CRIT_DMG + bl) if sure else 1 + (CRIT + bl) * (CRIT_DMG - 1)) / avg


def lapse(s, attr, to, i):
    u = getattr(s, attr)
    if u != -1.0 and u <= to: wasted(s, i); setattr(s, attr, -1.0)


def advance(s, fight, to):
    """Auto-attacks up to `to` (while the boss can be hit and the player is in reach), and procs that lapse."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a) * crit_factor(s, a)
        s.auto_next = a + AUTO_DELAY
    lapse(s, "ls_until", to, 1); lapse(s, "dr_until", to, 2); lapse(s, "nr_until", to, 2)


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


def hit(s, fight, at, potency, name, sure=False):
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land): s.dmg += potency * mult(s, fight, at) * crit_factor(s, at, sure)


def ticks(fight, a, b):
    """Server ticks in (a, b] inside the window while the boss can be hit."""
    k = math.floor((a - DOT_PHASE) / 3) + 1
    n = 0
    while DOT_PHASE + 3 * k <= b:
        t = DOT_PHASE + 3 * k
        if 0 <= t < fight.until and fight.targetable(t): n += 1
        k += 1
    return n


def apply_dot(s, fight, land, m):
    """Chaotic Spring's DoT on the boss at `land` with multiplier m, replacing the old one (its remaining ticks are
    lost). Its damage is counted now."""
    if s.dot and s.dot[0] + DOT_S > land:
        lost = ticks(fight, land, s.dot[0] + DOT_S) * DOT * s.dot[1]
        s.dmg -= lost; s.dotp -= lost
    gain = ticks(fight, land, land + DOT_S) * DOT * m
    s.dmg += gain; s.dotp += gain
    s.dot = (land, m)


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

def in_combo(s, name, at):
    return s.combo is not None and s.combo_until > at and FOLLOWS.get(name) == s.combo


def gcd_legal(s, name, at):
    df = s.df_until > at
    if name == "Raiden Thrust": return df
    if name == "True Thrust": return not df
    if name == "Drakesbane": return in_combo(s, name, at)
    if name == "Draconian Fury": return df
    if name == "Doom Spike": return not df
    return True


def potency(s, fight, name, at):
    p = POTENCY[name]
    if name == "Piercing Talon": return p[s.ept_until > at]
    if isinstance(p, tuple): p = p[in_combo(s, name, at)]
    if name in POSITIONALS: p += POSITIONAL * flank_rear(s, fight, at)
    return p


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
    combo = in_combo(s, name, snap)
    sure = s.ls_until > snap
    m = mult(s, fight, snap)
    hit(s, fight, snap, potency(s, fight, name, snap), name, sure)
    if sure: s.ls_until = -1.0
    if name == "Piercing Talon": s.ept_until = -1.0
    else:
        if name in MELEE_ACTIONS: s.df_until = -1.0          # any melee weaponskill ends Draconian Fire
        if name in ("Sonic Thrust", "Coerthan Torment", "Doom Spike", "Draconian Fury"):     # AoE, for replays only
            s.df_until = snap + DF_S if name == "Coerthan Torment" and combo else -1.0
            s.combo, s.combo_until = {"Doom Spike": "aoe", "Draconian Fury": "aoe", "Sonic Thrust": "aoe2"}.get(name), snap + COMBO_S
            if name == "Sonic Thrust" and combo: s.ps_until = snap + PS_S
            if name == "Draconian Fury": s.focus = min(2, s.focus + 1)
        elif name == "Drakesbane":
            s.combo, s.df_until = None, snap + DF_S
        elif name in ("True Thrust", "Raiden Thrust") or combo:
            s.combo, s.combo_until = LEADS[name], snap + COMBO_S
        else:
            s.combo = None                          # a combo action out of order breaks the combo
        if name == "Raiden Thrust":
            if s.focus == 2: wasted(s, 0)
            s.focus = min(2, s.focus + 1)
        if combo and name == "Disembowel": s.ps_until = snap + PS_S
        if combo and name == "Chaotic Spring": apply_dot(s, fight, snap + DELAY[name], m)
    s.t, s.gcd = start + ANIM_LOCK, start + BASE_GCD * SPEED
    s.near = away_soon(s, fight, s.t)
    s.log(start, name, gauge(s, "sure crit" if sure else ""))
    return s


def gauge(s, how):
    t = s.t
    on = [n for n, u in (("PS", s.ps_until), ("LotD", s.lotd_until), ("DF", s.df_until), ("Dive", s.dr_until),
                         ("Nastrond", s.nr_until)) if u > t]
    if s.lc_from <= t < s.lc_until: on.append("LC")
    if s.bl_from <= t < s.bl_until: on.append("BL")
    return f"{how:<9} combo {s.combo if s.combo_until > t and s.combo else '-':<2} focus {s.focus}  " + " ".join(on)


def ogcd_legal(s, name, at, fight, policy=True):
    if name in CDS:
        n, _ = charges(s, name, at)
        if n < 1: return False
    if name == "Mirage Dive": return s.dr_until > at
    if name == "Nastrond": return s.nr_until > at
    if name == "Stardiver": return s.lotd_until > at
    if name == "Wyrmwind Thrust": return s.focus >= 2
    if name == "Life Surge": return not (policy and s.ls_until > at)
    if name in ("Lance Charge", "Battle Litany", "Geirskogul", "High Jump", "Dragonfire Dive"): return at >= 0
    if name == "True North": return not policy or (s.tn_until <= at and (not flank_rear(s, fight, at + 2.5) or
                                                                         not flank_rear(s, fight, at + 5.0)))
    if name == "Elusive Jump": return not policy or (s.ept_until <= at and away_soon(s, fight, at))
    if name == "Tincture": return fight.pot and s.pot_at is None
    return False


HARM_OGCDS = {"Mirage Dive", "Nastrond", "Stardiver", "Wyrmwind Thrust", "Geirskogul", "High Jump", "Dragonfire Dive"}


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in HARM_OGCDS and not fight.targetable(at): return None
    use_cd(s, name, at)
    if name in HARM_OGCDS: hit(s, fight, at, POTENCY[name], name)       # before the status it grants
    if name == "Mirage Dive": s.dr_until = -1.0
    elif name == "Nastrond": s.nr_until = -1.0
    elif name == "Wyrmwind Thrust": s.focus -= 2
    elif name == "High Jump":
        if s.dr_until > at: wasted(s, 2)
        s.dr_until = at + DR_S
    elif name == "Geirskogul":
        if s.nr_until > at: wasted(s, 2)
        s.lotd_until, s.nr_until = at + LOTD_S, at + NR_S
    elif name == "Life Surge": s.ls_until = at + LS_S
    elif name == "Lance Charge": s.lc_from, s.lc_until = at + BUFF_DELAY, at + BUFF_DELAY + LC_S
    elif name == "Battle Litany": s.bl_from, s.bl_until = at + BUFF_DELAY, at + BUFF_DELAY + BL_S
    elif name == "True North": s.tn_until = at + TN_S
    elif name == "Elusive Jump": s.ept_until = at + EPT_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + LOCK.get(name, ANIM_LOCK)
    s.near = away_soon(s, fight, s.t)
    s.log(at, name, gauge(s, ""))
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next: the combo's next step (or a new combo), and Piercing Talon out of reach. Disembowel
    only when the DoT would be nearly out by the time its Chaotic Spring lands, or Power Surge is: the DoT is counted
    when applied, so an early refresh looks good for a while (it loses ticks the alternative keeps), and a narrow beam
    drops the Vorpal Thrust chain before it catches up."""
    nxt = NEXT[c.combo if c.combo_until > now else None]
    if "Disembowel" in nxt:
        land = now + 2 * BASE_GCD * SPEED + DELAY["Chaotic Spring"]
        if c.dot and c.dot[0] + DOT_S - land > 6.0 and c.ps_until - now > 15: nxt = ("Vorpal Thrust",)
    out = list(nxt) or ["Raiden Thrust" if c.df_until > now else "True Thrust"]
    if c.ept_until > now or not reach(c, fight, now, commit=False): out.append("Piercing Talon")
    return out


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD."""
    slots = int((s.gcd - s.t + WEAVE_SLACK) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready, k):
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None or (combo and c.t > s.gcd + WEAVE_SLACK): continue      # a jump's lock would clip the GCD
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, fight, now):
                # Life Surge, True North and Elusive Jump only right before the GCD they are for: anything else only
                # multiplies the states
                if "Life Surge" in combo and g not in LS_TARGETS: continue
                if "True North" in combo and g not in POSITIONALS: continue
                if "Elusive Jump" in combo and g != "Piercing Talon": continue
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                w = c.copy(); w.t = w.gcd = fight.back_up(now) if down else now + 0.5
                w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# what holding a resource is worth over the GCDs it displaces: a combo step the bonus still to come on the next one;
# Draconian Fire Raiden Thrust over True Thrust and half a Focus; a Focus half a Wyrmwind Thrust; Dive and Nastrond
# Ready their hit; Life Surge its crit on a 400; a second of a damage buff its share of the rotation's rate.
VALUE = dict(combo_1=140, combo_v=300, combo_d=110, combo_h=160, combo_c=160, combo_f=170, df=150, focus=200, dr=380,
             nr=720, ls=150, ept=150, ps=20, lc=22, lotd=35, bl=12)
RATE = 220                                            # potency per second, to compare states at slightly different times
# tune.py (2026-10-22, sweep): VALUE at 1.7-2.35 times beats 1.0 by 0.58% over the phase; RATE hardly matters
HEURISTICS = [(195, 1.7, 0.0), (190, 1.7, 0.0), (180, 2.35, 0.0), (185, 1.95, 0.0)]
WIDTH = 3000
SWEEP_WIDTH = 15000                                   # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: level (a beam this wide: -0.06%)
MOVE_WEIGHT = 0.0


def held(s):
    t = s.t
    v = VALUE.get(f"combo_{s.combo}", 0) if s.combo_until > t else 0
    v += VALUE["df"] * (s.df_until > t) + VALUE["focus"] * s.focus
    v += VALUE["dr"] * (s.dr_until > t) + VALUE["nr"] * (s.nr_until > t) + VALUE["ls"] * (s.ls_until > t)
    v += VALUE["ept"] * (s.ept_until > t)
    v += VALUE["ps"] * min(max(s.ps_until - t, 0), 30) + VALUE["lotd"] * max(s.lotd_until - t, 0)
    v += VALUE["lc"] * max(s.lc_until - max(t, s.lc_from), 0) + VALUE["bl"] * max(s.bl_until - max(t, s.bl_from), 0)
    return v


def rank(s, fight):
    return s.dmg + held(s) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the swings still to come before the window ends
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Dragoon", "2024-11-12"      # 7.1 set the level-90 Stardiver, Nastrond and Mirage Dive
OGCDS = set(OGCD_ORDER)
REFERENCE = ("High Jump", 400)                      # no trait or patch touches it
CAST = {}


def cast_time(s, name, at):
    return 0.0, None


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(combo=s.combo if s.combo_until > t else None, df=s.df_until > t, focus=s.focus, lotd=s.lotd_until > t,
                dive=s.dr_until > t, nastrond=s.nr_until > t, life_surge=s.ls_until > t)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name in ("Raiden Thrust", "Draconian Fury"): s.df_until = start + 1
    if name in ("True Thrust", "Doom Spike"): s.df_until = -1.0
    if name == "Drakesbane": s.combo, s.combo_until = "f", start + 1
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if name == "Mirage Dive": s.dr_until = t + 1
    if name == "Nastrond": s.nr_until = t + 1
    if name == "Stardiver": s.lotd_until = t + 1
    if name == "Wyrmwind Thrust": s.focus = 2
    if name in CDS:                                 # one charge, the recharge still running (Life Surge has two)
        rec, mx = CDS[name]
        s.cds[name] = (1, charges(s, name, t)[1] or (None if mx == 1 else t + rec))
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Positionals are grouped by True North,
    the one way the log shows one was surely taken; without it the model's potency is the miss."""
    if name not in POTENCY: return None
    p = POTENCY[name]
    if name == "Piercing Talon": return ("enhanced" if s.ept_until > t else ""), p[s.ept_until > t]
    if name in FOLLOWS and isinstance(p, tuple):
        combo = in_combo(s, name, t)
        g, v = ("combo" if combo else "no combo"), p[combo]
        if name in POSITIONALS:
            tn = s.tn_until > t; g += " TN" if tn else ""; v += POSITIONAL * tn
        return g, v
    if isinstance(p, tuple): return "", p[0]
    return "", p


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Power Surge, Lance Charge, Life of the
    Dragon; status ids from the scorecard's cached auras): FFLogs counts every damage-up on the hit, so dividing it out
    takes these away too."""
    b = h.get("buffs") or ""
    return ((POWER_SURGE if "1002720." in b else 1.0) * (LANCE_CHARGE if "1001864." in b else 1.0) *
            (LIFE if "1003177." in b else 1.0))


def sure_crits(p):
    """{(time, ability id)} of the hits Life Surge made sure crits in log p (the first weaponskill's hit after each Life
    Surge): dps.py leaves them out when it measures the player's own crit rate and gain."""
    n = p["names"]
    name = lambda x: n[str(x["abilityGameID"])]
    surges = [x["t"] for x in p["casts"] if x["type"] == "cast" and name(x) == "Life Surge"]
    ws = [(x["t"], x["abilityGameID"]) for x in p["casts"] if x["type"] == "cast" and name(x) in GCDS]
    hits = [(x["t"], x["abilityGameID"]) for x in p["hits"] if x["type"] == "damage" and not x.get("tick")]
    out = set()
    for t0 in surges:
        w = next(((t, a) for t, a in ws if 0 <= t - t0 < LS_S), None)
        if w is None: continue
        h = next(((ht, a) for ht, a in hits if a == w[1] and 0 <= ht - w[0] < 2.5), None)
        if h is not None: out.add(h)
    return out
