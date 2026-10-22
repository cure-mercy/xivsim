"""Samurai at level 90, Dawntrail patch 7.1 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/samurai) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Way of the Samurai III (level 94) raises Jinpu, Shifu, Gekko, Kasha,
Yukikaze, Higanbana's DoT, Midare Setsugekka and Kaeshi: Setsugekka, Shoha, Ogi Namikiri and Kaeshi: Namikiri there,
and Enhanced Hissatsu (94) brings Hissatsu: Senei down to 60 s. Gyofu (92), Zanshin (96) and Tendo (100) lie above
P12S. 7.05 set most single-target values and made Tsubame-gaeshi a follow-up of every Iaijutsu but Higanbana; 7.1
shortened Hissatsu: Gyoten to 5 s; 7.2-7.5 only touched level-94+ and AoE values.

FFLogs was down when this was written, so the level-90 values were measured in the scorecard's cached damage events
(.cache/acts_*: our groups' 199 pulls by four Samurais, Sep-Oct 2026, and 12 benchmark clears): each player's plain-hit
cluster with Fugetsu divided out and others' raid buffs left out, scaled to Hissatsu: Shinten (250, untouched by traits
and patches). FFLogs' bonusPercent confirms each combo / positional split, e.g. Gekko 70% = (370 - 110) / 370 from the
rear in combo. The sure crits (Midare, the Kaeshis, Ogi) have no plain hits: Midare's lowest cluster over the player's
crit multiplier (Shinten's crit cluster over its plain one) is 620, Kaeshi: Setsugekka matches it, and Ogi Namikiri and
Kaeshi: Namikiri come to 1.38 times Midare (both sure crits under the same buffs in the same pull): 860.

Combos (30 s; Iaijutsu, the Kaeshis, Ogi Namikiri and Enpi don't break them):
  Hakaze -> Jinpu (Fugetsu: +13% damage, 40 s) -> Gekko (Getsu; +50 from the rear)
  Hakaze -> Shifu (Fuka: GCD recast and auto-attacks 13% faster, 40 s) -> Kasha (Ka; +50 from the flank)
  Hakaze -> Yukikaze (Setsu)
Meikyo Shisui (two charges, 55 s; one is used before the pull, ~13 s ahead) makes the next three weaponskills count as
combo finishers, Gekko granting Fugetsu and Kasha Fuka. Iaijutsu (a 1.3 s cast, not shortened by Fuka) spends the Sen:
three for Midare Setsugekka (a sure crit; Tsubame-gaeshi Ready for Kaeshi: Setsugekka, 30 s), one for Higanbana (DoT
60 s). Ikishoten (120 s) gives 50 Kenki and Ogi Namikiri Ready (30 s): Ogi Namikiri (1.3 s cast) then Kaeshi: Namikiri,
both sure crits. Iaijutsu and Ogi Namikiri each give a Meditation stack; three make Shoha (15 s). The Kaeshis don't.

Kenki (0-100): Hakaze 5, Jinpu / Shifu 5 and Gekko / Kasha / Yukikaze 15 in combo (or under Meikyo), Enpi 10,
Ikishoten 50, Tengentsu 10 when the player is hit under it (the fight's HITS: our pulls' raidwides), Meditate 10 a tick;
Hissatsu: Shinten (250, 1 s) and Senei (800, 120 s at level 90) cost 25, Gyoten and Yaten 10. The guide gives Gekko and
Kasha 10, but only 15 replays our pulls' spending legal (246 Hissatsu short at 10, 2 at 15; no other source fits); whether
5 of it needs the positional the logs can't tell (430 missed positionals never left a spender short), so it's flat.
Statuses come on with the hit that grants them, Meikyo, Tsubame-gaeshi Ready and Ogi Namikiri Ready with the cast.

Meditate (60 s) stands the player still: each 3 s tick gives a Meditation stack (the clears' Shohas right after Palladion
need exactly the ticks their Meditate status lasted) and Kenki (10, the in-game value; the logs can't confirm it). The
search meditates only while Athena is away, as the clears do at Palladion's end: one step takes the player through the
downtime (Tengentsu on the hits it catches, then Meditate ending as she returns), so its ranking doesn't charge the
downtime as time.

Positionals (Gekko rear, Kasha flank) and reach as for the Viper (jobs/vpr.py): every weaponskill, Iaijutsu and Hissatsu
needs the player beside Athena (assumed: their 6-10 y ranges may reach a little further), only Enpi reaches from anywhere.
Out of reach, Hissatsu: Yaten buys an Enhanced Enpi.
"""
import itertools, math
from engine import ANIM_LOCK, BASE_GCD, RESOLVE, SLIDE, gcd_times, settle, stand

# level-90 potencies from the logs (see above). (out of combo, in combo) for combo actions.
POTENCY = {"Hakaze": 200, "Jinpu": (120, 280), "Shifu": (120, 280), "Gekko": (110, 320), "Kasha": (110, 320),
           "Yukikaze": (110, 290), "Midare Setsugekka": 620, "Kaeshi: Setsugekka": 620, "Higanbana": 200,
           "Ogi Namikiri": 860, "Kaeshi: Namikiri": 860, "Enpi": (100, 260), "Hissatsu: Shinten": 250,
           "Hissatsu: Senei": 800, "Shoha": 560, "Hissatsu: Gyoten": 100, "Hissatsu: Yaten": 100,
           "Tenka Goken": 300, "Kaeshi: Goken": 300, "Hissatsu: Kyuten": 100, "Hissatsu: Guren": 400}   # AoE: replays only
POSITIONAL = 50
POSITIONALS = ("Gekko", "Kasha")
# Higanbana's DoT: ~50 a tick in the logs (48-52 per player, relative to Shinten), 60 s
DOT, DOT_S = 50, 60.0
DOT_PHASE = 1.5                                 # server ticks land at DOT_PHASE + 3k seconds
AUTO = 80                                       # auto-attacks: 80 potency (logs, scaled to Shinten)
AUTO_DELAY, AUTO_DELAY_FUKA = 2.66, 2.32        # the logs' median spacing without and with Fuka
# seconds from executing an action (a hard cast: from its resolve) to its damage landing, the logs' medians
DELAY = {"Hakaze": 0.63, "Jinpu": 0.63, "Shifu": 0.80, "Gekko": 0.76, "Kasha": 0.63, "Yukikaze": 0.80,
         "Midare Setsugekka": 0.63, "Kaeshi: Setsugekka": 0.63, "Higanbana": 0.63, "Ogi Namikiri": 0.49,
         "Kaeshi: Namikiri": 0.49, "Enpi": 0.71, "Hissatsu: Shinten": 0.63, "Hissatsu: Senei": 0.67, "Shoha": 0.58,
         "Hissatsu: Gyoten": 0.49, "Hissatsu: Yaten": 0.45, "Tenka Goken": 0.63, "Kaeshi: Goken": 0.62}
CAST = {"Midare Setsugekka": 1.3, "Higanbana": 1.3, "Tenka Goken": 1.3, "Ogi Namikiri": 1.3}  # flat: begin -> cast 0.76 s at every speed, with Fuka or not
FUGETSU, FUKA = 1.13, 0.87
WEAVE_SLACK = 0.05                              # a weave may clip the GCD by this much
COMBO_S, BUFF_S, MEIKYO_S, TSUBAME_S, OGI_S, TN_S, EE_S, TENGENTSU_S = 30, 40, 20, 30, 30, 10, 15, 4
MEIKYO_PREPULL = -13.0                          # the pre-pull Meikyo Shisui: its charge comes back at 42.2-42.7 s in the clears
CDS = {"Meikyo Shisui": (55, 2), "Ikishoten": (120, 1), "Hissatsu: Senei": (120, 1), "Shoha": (15, 1),
       "Hissatsu: Shinten": (1, 1), "Tengentsu": (15, 1), "True North": (45, 2), "Hissatsu: Gyoten": (5, 1),
       "Hissatsu: Yaten": (10, 1), "Hagakure": (5, 1), "Meditate": (60, 1), "Tincture": (270, 1),
       "Hissatsu: Kyuten": (1, 1), "Hissatsu: Guren": (120, 1)}
SHARED = {"Hissatsu: Guren": "Hissatsu: Senei"}
KENKI_COST = {"Hissatsu: Shinten": 25, "Hissatsu: Senei": 25, "Hissatsu: Gyoten": 10, "Hissatsu: Yaten": 10,
              "Hissatsu: Kyuten": 25, "Hissatsu: Guren": 25}
KENKI_GAIN = {"Hakaze": 5, "Jinpu": 5, "Shifu": 5, "Gekko": 15, "Kasha": 15, "Yukikaze": 15}    # combo steps, in combo
SEN = {"Gekko": "getsu", "Kasha": "ka", "Yukikaze": "setsu"}
IAI = {1: "Higanbana", 2: "Tenka Goken", 3: "Midare Setsugekka"}
# when the player is hit (Tengentsu's Foresight in our pulls, cluster medians where it paid off 70%+ of the time it was
# up): On the Soul, Searing Radiance, Trinity of Souls, Superchain Burst, Dialogos, Ultima Blade, Palladion's
# shockwaves, Theos's Ultima and a few others
HITS = (13.7, 39.1, 44.1, 76.8, 91.5, 130.1, 137.7, 147.1, 174.4, 182.4, 216.3, 233.2, 269.4, 293.2, 296.2, 314.4,
        337.4, 391.5)
LOG_HITS = None                                 # a replay: the log's own Foresight times (prepare)
MEDITATE_TICK, MEDITATE_KENKI = 3.0, 10         # a Meditation stack a tick (the clears' Shohas after Palladion); Kenki: the
                                                # in-game value (the guide only says "gradually"), not testable in the logs
LOG_MEDITATE = None                             # a replay: {cast time (0.1 s): ticks} from the log's Meditate status
FOLLOWS = {"Jinpu": "1", "Shifu": "1", "Yukikaze": "1", "Gekko": "j", "Kasha": "s"}
LEADS = {"Hakaze": "1", "Jinpu": "j", "Shifu": "s"}
COMBO_WS = {"Hakaze", "Jinpu", "Shifu", "Gekko", "Kasha", "Yukikaze"}
MELEE_ACTIONS = COMBO_WS | {"Midare Setsugekka", "Kaeshi: Setsugekka", "Higanbana", "Ogi Namikiri", "Kaeshi: Namikiri",
                            "Hissatsu: Shinten", "Hissatsu: Senei", "Shoha", "Hissatsu: Yaten", "Tenka Goken",
                            "Kaeshi: Goken", "Hissatsu: Kyuten", "Hissatsu: Guren"}
GCDS = sorted(COMBO_WS) + ["Midare Setsugekka", "Kaeshi: Setsugekka", "Higanbana", "Ogi Namikiri", "Kaeshi: Namikiri",
                           "Enpi", "Tenka Goken", "Kaeshi: Goken", "Meditate"]     # Meditate takes the GCD's cooldown
OGCD_ORDER = ["Tincture", "Meikyo Shisui", "Ikishoten", "Hissatsu: Senei", "Shoha", "Hissatsu: Shinten", "Tengentsu",
              "True North", "Hissatsu: Yaten"]
REPLAY_OGCDS = ["Hissatsu: Gyoten", "Hagakure", "Hissatsu: Kyuten", "Hissatsu: Guren"]
AUTO_CRIT = {"Midare Setsugekka", "Kaeshi: Setsugekka", "Ogi Namikiri", "Kaeshi: Namikiri"}  # dps.py: at their own gain
# the search weighs a sure crit's potency by its expected gain over an average hit (typical rates: 25% crit, x1.60), so
# trading it against other hits is fair; s.dmg stays plain potency and dps.py converts sure crits (critp) apart. (Not
# named CRIT: dps.py would then search each player at their own crit rate, which only Monk's chakra needs.)
CRIT_RATE, CRIT_DMG = 0.25, 1.60
SURE_W = CRIT_DMG / (1 + CRIT_RATE * (CRIT_DMG - 1))
LOG_OPENER = None                               # a replay: (Meikyo stacks, until, charges) from the log (prepare)
SPEED = 0.96                                    # skill speed factor on the GCD: 2.40 s (2.09 s under Fuka), our four
                                                # Samurais' and the benchmark clears' median
MELEE = True                                    # p12s.py gives it a melee's windows (M1 / M2)


class State:
    __slots__ = ("t", "gcd", "combo", "combo_until", "sen", "kenki", "med", "meikyo", "ms_until", "fug_until",
                 "fuka_until", "tsubame_until", "ogi_until", "kn_until", "tn_until", "ee_until", "ten_hit", "dot", "cds",
                 "auto_next", "dmg", "dotp", "critp", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot",
                 "ai", "mlast", "near")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo, s.combo_until = None, -1.0         # None, "1" (after Hakaze), "j" / "s" (after Jinpu / Shifu)
        s.sen = frozenset()                         # of "setsu", "getsu", "ka"
        s.kenki, s.med = 0, 0
        s.meikyo, s.ms_until = 3, MEIKYO_PREPULL + MEIKYO_S     # the pre-pull Meikyo Shisui
        s.fug_until = s.fuka_until = s.tsubame_until = s.ogi_until = s.kn_until = s.tn_until = s.ee_until = -1.0
        s.ten_hit = None                            # when a pending Tengentsu pays its Kenki
        s.dot = None                                # (when Higanbana's DoT landed, the multiplier it snapshot)
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.cds["Meikyo Shisui"] = (1, MEIKYO_PREPULL + CDS["Meikyo Shisui"][0])
        if LOG_OPENER is not None: s.meikyo, s.ms_until, s.cds["Meikyo Shisui"] = LOG_OPENER
        s.auto_next, s.dmg, s.dotp, s.critp, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0, 0)
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
        return (r(self.t), r(self.gcd), self.combo if self.combo_until > self.t else None, self.sen, self.kenki,
                self.med, self.meikyo if self.ms_until > self.t else 0, round(max(self.fug_until - self.t, 0) / 2.5),
                round(max(self.fuka_until - self.t, 0) / 2.5), self.tsubame_until > self.t, self.ogi_until > self.t,
                self.kn_until > self.t, left(self.tn_until), self.ee_until > self.t, self.ten_hit,
                round(max(self.dot[0] + DOT_S - self.t, 0) / 2.5) if self.dot else None, self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()),
                self.mvi, round(min(self.acc, 4.0) * 2) / 2, self.ai, r(min(self.t - self.mlast, 4)) if self.near else None)

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Kenki overcapped", "Sen overwritten", "Meditation overcapped", "Meikyo Shisui stacks lapsed")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, Fugetsu."""
    return fight.mult(at, s.pot_at) * (FUGETSU if s.fug_until > at else 1)


def gain(s, n):
    if s.kenki + n > 100: wasted(s, 0, s.kenki + n - 100)
    s.kenki = min(100, s.kenki + n)


def advance(s, fight, to):
    """Auto-attacks up to `to` (while the boss can be hit and the player is in reach; faster under Fuka), Tengentsu's
    Kenki when its hit comes, and Meikyo Shisui's stacks running out."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + (AUTO_DELAY_FUKA if s.fuka_until > a else AUTO_DELAY)
    if s.ten_hit is not None and s.ten_hit <= to: gain(s, 10); s.ten_hit = None
    if s.meikyo and s.ms_until <= to: wasted(s, 3, s.meikyo); s.meikyo = 0


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
    return SHARED.get(name, name)


def hit(s, fight, at, potency, name):
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land):
        d = potency * mult(s, fight, at)
        s.dmg += d
        if name in AUTO_CRIT: s.critp += d


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
    """Higanbana's DoT on the boss at `land` with multiplier m, replacing the old one (its remaining ticks are lost).
    Its damage is counted now."""
    if s.dot and s.dot[0] + DOT_S > land:
        lost = ticks(fight, land, s.dot[0] + DOT_S) * DOT * s.dot[1]
        s.dmg -= lost; s.dotp -= lost
    g = ticks(fight, land, land + DOT_S) * DOT * m
    s.dmg += g; s.dotp += g
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


def hit_coming(at):
    """When the player is next hit inside Tengentsu's 4 s (None if not): the log's hits in a replay, else the fight's."""
    for h in (LOG_HITS if LOG_HITS is not None else HITS):
        if at < h <= at + TENGENTSU_S: return h
    return None


# --- actions -------------------------------------------------------------------------------------------------------

def step(s, at):
    return s.combo if s.combo_until > at else None


def meikyo(s, at):
    return s.meikyo > 0 and s.ms_until > at


def in_combo(s, name, at):
    """Does a combo weaponskill land as a combo step (Meikyo Shisui makes every one count)?"""
    return name in FOLLOWS and (meikyo(s, at) or step(s, at) == FOLLOWS[name])


def gcd_legal(s, name, at):
    n = len(s.sen)
    if name in IAI.values(): return IAI.get(n) == name
    if name == "Kaeshi: Setsugekka": return s.tsubame_until > at
    if name == "Kaeshi: Goken": return s.tsubame_until > at
    if name == "Ogi Namikiri": return s.ogi_until > at
    if name == "Kaeshi: Namikiri": return s.kn_until > at
    return True                                 # the combo weaponskills, Enpi


def potency(s, fight, name, at):
    p = POTENCY[name]
    if name == "Enpi": return p[s.ee_until > at]
    if isinstance(p, tuple): p = p[in_combo(s, name, at)]
    if name in POSITIONALS: p += POSITIONAL * flank_rear(s, fight, at)
    return p


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    if name == "Meditate": return do_meditate(s, fight, (LOG_MEDITATE or {}).get(round(max(s.t, s.gcd), 1), 0))
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    if not fight.targetable(start): return None
    cast = CAST.get(name, 0.0)
    if cast and stand(s, fight, start, start + cast - SLIDE) is None: return None
    if fight.next_down(start) <= start + max(cast - RESOLVE, 0) + DELAY.get(name, 0.6): return None
    if name in MELEE_ACTIONS and not reach(s, fight, start): return None
    s.first = False
    haste = FUKA if s.fuka_until > start else 1.0     # the GCD granting Fuka isn't hasted by it
    snap, free, nxt = gcd_times(start, cast, BASE_GCD * SPEED * haste)
    combo = in_combo(s, name, snap)
    m = mult(s, fight, snap)
    hit(s, fight, snap, potency(s, fight, name, snap), name)
    land = snap + DELAY.get(name, 0.6)
    if name in COMBO_WS:
        if meikyo(s, snap): s.meikyo -= 1
        if name == "Hakaze" or combo: gain(s, KENKI_GAIN[name])
        if name in LEADS and (name == "Hakaze" or combo): s.combo, s.combo_until = LEADS[name], snap + COMBO_S
        else: s.combo = None                    # a finisher, or a step out of order, ends the combo
        if combo and name in ("Jinpu", "Gekko"): s.fug_until = land + BUFF_S
        if combo and name in ("Shifu", "Kasha"): s.fuka_until = land + BUFF_S
        if combo and name in SEN:
            if SEN[name] in s.sen: wasted(s, 1)
            s.sen = s.sen | {SEN[name]}
    elif name in IAI.values():
        s.sen = frozenset()
        if s.med == 3: wasted(s, 2)
        s.med = min(3, s.med + 1)
        if name == "Higanbana": apply_dot(s, fight, land, m)
        else: s.tsubame_until = snap + TSUBAME_S
    elif name in ("Kaeshi: Setsugekka", "Kaeshi: Goken"): s.tsubame_until = -1.0
    elif name == "Ogi Namikiri":
        if s.med == 3: wasted(s, 2)
        s.med = min(3, s.med + 1)
        s.ogi_until, s.kn_until = -1.0, snap + OGI_S
    elif name == "Kaeshi: Namikiri": s.kn_until = -1.0
    elif name == "Enpi": s.ee_until = -1.0; gain(s, 10)
    s.t, s.gcd = max(free, snap), nxt
    s.near = away_soon(s, fight, s.t)
    s.log(start, name, gauge(s, f"{cast:.2f}s cast" if cast else ""))
    return s


def gauge(s, how):
    t = s.t
    on = [n for n, u in (("Fugetsu", s.fug_until), ("Fuka", s.fuka_until), ("Tsubame", s.tsubame_until),
                         ("Ogi", s.ogi_until), ("Namikiri", s.kn_until)) if u > t]
    if meikyo(s, t): on.append(f"Meikyo {s.meikyo}")
    sen = "".join(c for c, k in (("S", "setsu"), ("G", "getsu"), ("K", "ka")) if k in s.sen)
    return f"{how:<9} combo {step(s, t) or '-'}  sen {sen or '-':<3} kenki {s.kenki:>3}  med {s.med}  " + " ".join(on)


def ogcd_legal(s, name, at, fight, policy=True):
    if name in CDS:
        n, _ = charges(s, cd_name(name), at)
        if n < 1: return False
    if name in KENKI_COST: return s.kenki >= KENKI_COST[name] and (
        name != "Hissatsu: Yaten" or not policy or (s.ee_until <= at and away_soon(s, fight, at)))
    if name == "Shoha": return s.med == 3
    if name == "Meikyo Shisui": return not (policy and meikyo(s, at))
    if name == "Ikishoten": return at >= 0
    if name == "Tengentsu": return not policy or hit_coming(at + 0.2) is not None
    if name == "Hagakure": return bool(s.sen)
    if name == "True North": return not policy or (s.tn_until <= at and (not flank_rear(s, fight, at + 2.5) or
                                                                         not flank_rear(s, fight, at + 5.0)))
    if name == "Tincture": return fight.pot and s.pot_at is None
    return False


HARM_OGCDS = {"Hissatsu: Shinten", "Hissatsu: Senei", "Shoha", "Hissatsu: Gyoten", "Hissatsu: Yaten",
              "Hissatsu: Kyuten", "Hissatsu: Guren"}


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in HARM_OGCDS and not fight.targetable(at): return None
    if name in MELEE_ACTIONS and not reach(s, fight, at): return None
    if name in CDS: use_cd(s, cd_name(name), at)
    if name in HARM_OGCDS: hit(s, fight, at, POTENCY[name], name)
    if name in KENKI_COST: s.kenki -= KENKI_COST[name]
    if name == "Shoha": s.med = 0
    elif name == "Hissatsu: Yaten": s.ee_until = at + EE_S
    elif name == "Meikyo Shisui":
        if meikyo(s, at): wasted(s, 3, s.meikyo)
        s.meikyo, s.ms_until = 3, at + MEIKYO_S
    elif name == "Ikishoten": gain(s, 50); s.ogi_until = at + OGI_S
    elif name == "Tengentsu": s.ten_hit = hit_coming(at)
    elif name == "Hagakure": gain(s, 10 * len(s.sen)); s.sen = frozenset()
    elif name == "True North": s.tn_until = at + TN_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.near = away_soon(s, fight, s.t)
    s.log(at, name, gauge(s, ""))
    return s


def do_meditate(s, fight, ticks, start=None):
    """Meditate for `ticks` ticks (3 s each, five at most): the player stands still and doesn't act, each tick gives a
    Meditation stack and Kenki. It starts the GCD's cooldown and needs it ready; the search only meditates while Athena
    is away, standing between the runs."""
    s = s.copy()
    start = max(s.t, s.gcd) if start is None else start
    advance(s, fight, start)
    settle(s, fight, start)
    if start < 0 or charges(s, "Meditate", start)[0] < 1: return None
    end = start + MEDITATE_TICK * ticks
    if stand(s, fight, start, end) is None: return None
    use_cd(s, "Meditate", start)
    if s.med + ticks > 3: wasted(s, 2, s.med + ticks - 3)
    s.med = min(3, s.med + ticks)
    gain(s, MEDITATE_KENKI * ticks)
    s.t = max(end, start + ANIM_LOCK)
    s.gcd = max(s.t, start + BASE_GCD * SPEED * (FUKA if s.fuka_until > start else 1.0))
    s.log(start, "Meditate", gauge(s, f"stand {end - start:.2f}s"))     # check.py counts it as standing
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next: the Kaeshi that is ready, Midare Setsugekka at three Sen (not over a pending Kaeshi:
    Setsugekka, which it would replace), Higanbana at one when the DoT is nearly out, Ogi Namikiri when ready; under
    Meikyo Shisui the finishers whose Sen is missing (or Gekko and Kasha for their buffs), otherwise the combo's next
    step (Jinpu / Shifu / Yukikaze as their Sen or buffs call for them, any of them when none does); Enpi out of reach
    or with Enhanced Enpi."""
    out = []
    if c.kn_until > now: out.append("Kaeshi: Namikiri")
    if c.tsubame_until > now: out.append("Kaeshi: Setsugekka")
    n = len(c.sen)
    if n == 3 and c.tsubame_until <= now: out.append("Midare Setsugekka")
    if n == 1:
        land = now + CAST["Higanbana"] - RESOLVE + DELAY["Higanbana"]
        if not c.dot or c.dot[0] + DOT_S - land < 6.0: out.append("Higanbana")
    if c.ogi_until > now: out.append("Ogi Namikiri")
    if meikyo(c, now):
        miss = [g for g in ("Gekko", "Kasha", "Yukikaze") if SEN[g] not in c.sen]
        out += miss or ["Gekko", "Kasha"]
    else:
        st = step(c, now)
        if st == "1":
            nxt = [g for g, buff, u in (("Jinpu", "getsu", c.fug_until), ("Shifu", "ka", c.fuka_until))
                   if buff not in c.sen or u - now < 12]
            if "setsu" not in c.sen: nxt.append("Yukikaze")
            out += nxt or ["Jinpu", "Shifu", "Yukikaze"]
        elif st == "j": out.append("Gekko")
        elif st == "s": out.append("Kasha")
        else: out.append("Hakaze")
    if c.ee_until > now or not reach(c, fight, now, commit=False): out.append("Enpi")
    return out


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD."""
    slots = int((s.gcd - s.t + WEAVE_SLACK) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready, k):
            if "Meikyo Shisui" in combo and "True North" in combo: continue
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, fight, now):
                # True North and Yaten only right before the GCD they are for: anything else only multiplies the states
                if "True North" in combo and g not in POSITIONALS: continue
                if "Hissatsu: Yaten" in combo and g != "Enpi": continue
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and down: out += downtime(c, fight, now)
            elif not combo and not any_gcd:
                w = c.copy(); w.t = w.gcd = now + 0.5
                w.log(c.t, "(wait)"); out.append(w)
    return out


def downtime(c, fight, now):
    """While Athena is away, in one step: Tengentsu on the hits it can catch, then Meditate for 0-5 ticks ending as
    she comes back (standing, between the runs). Every child ends when she is back, so the ranking's time cost doesn't
    favour shorter meditations."""
    back = fight.back_up(now)
    out = []
    for k in range(0, 6):
        med_from = back - MEDITATE_TICK * k
        w = c.copy()
        w.log(now, "(boss away)")
        for h in (LOG_HITS if LOG_HITS is not None else HITS):
            at = h - 2.0
            if not now <= at or h > med_from - ANIM_LOCK: continue
            w.t = max(w.t, at)
            n = do_ogcd(w, fight, "Tengentsu")
            if n is not None: w = n
        if k:
            w = do_meditate(w, fight, k, max(med_from, w.t))
            if w is None: continue
        w.t = w.gcd = max(w.t, back)
        out.append(w)
    return out


# what holding a resource is worth: what it converts into (sure crits at SURE_W), less RATE times the GCD time it takes,
# so spending it leaves the rank where it was (jobs/vpr.py: inflated values make the beam hoard). With a 2.09 s GCD at
# 250 a second a GCD costs ~520: Tsubame-gaeshi and Kaeshi: Namikiri Ready their sure crit (862, 1,196) less that; Ogi
# Namikiri Ready its hit, its Kaeshi and a Meditation stack; a Sen a third of Midare, its Kaeshi and Meditation stack; a
# Meditation stack a third of Shoha; a Kenki point a tenth of Shinten; a combo step what its remaining steps (with Kenki
# and Sen) add over their GCDs; a Meikyo stack a finisher's worth over its GCD; a second of Fugetsu or Fuka 13% of the
# rotation's rate (damage, or GCDs); Enhanced Enpi its +160; a Tengentsu under way its 10 Kenki.
VALUE = dict(kenki=10, sen=290, med=185, tsubame=340, ogi=1530, kn=675, combo_1=60, combo_j=290, combo_s=290,
             meikyo=280, fug=35, fuka=30, ee=160, ten=100)
RATE = 250                                            # potency per second, to compare states at slightly different times:
                                                      # the filler's own (a combo with its Kenki and autos) is ~245
# the search: at width 3,000 these land within ~0.15% of each other over the phase; values at 0.5 lose 1.5% (a Kaeshi
# and the DoT's timing before Palladion), at 1.2-1.5 1-3% (the beam holds Sen and Kenki)
HEURISTICS = [(r, v, 0.0) for r in (210, 230, 250) for v in (0.8, 1.0)]
WIDTH = 3000
SWEEP_WIDTH = 7500                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: +0.30%
MOVE_WEIGHT = 0.0
END_TAPER = 15.0                                      # held resources fade over the window's last seconds


def held(s):
    t = s.t
    v = VALUE.get(f"combo_{step(s, t)}", 0) + VALUE["kenki"] * s.kenki + VALUE["sen"] * len(s.sen)
    v += VALUE["med"] * s.med + VALUE["meikyo"] * (s.meikyo if meikyo(s, t) else 0)
    v += VALUE["tsubame"] * (s.tsubame_until > t) + VALUE["ogi"] * (s.ogi_until > t) + VALUE["kn"] * (s.kn_until > t)
    v += VALUE["ee"] * (s.ee_until > t) + VALUE["ten"] * (s.ten_hit is not None)
    v += VALUE["fug"] * min(max(s.fug_until - t, 0), 30) + VALUE["fuka"] * min(max(s.fuka_until - t, 0), 30)
    return v


def score(s):
    """Damage with the sure crits at their expected gain over an average hit."""
    return s.dmg + (SURE_W - 1) * s.critp


def rank(s, fight):
    return score(s) + held(s) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the swings still to come before the window ends
    return score(s) + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Samurai", "2024-11-12"      # 7.1 set Gyoten's 5 s; no level-90 value has changed since 7.05
OGCDS = set(OGCD_ORDER) | set(REPLAY_OGCDS)
REFERENCE = ("Hissatsu: Shinten", 250)              # no trait or patch touches it
HASTED = {"Fuka": FUKA}                             # calibrate.gcd_of divides gaps that start under it by this


def prepare(p):
    """A replay takes from the log Tengentsu's Kenki (when Tengentsu's Foresight came on: the player was hit) and the
    pre-pull Meikyo Shisui, which the casts don't show: its status coming off before the first Meikyo cast marks one
    (players press it 12-13 s ahead: the log only shows its stacks were all spent, so it lasts until then); without
    that, there was none and both charges are there."""
    global LOG_HITS, LOG_OPENER, LOG_MEDITATE
    n = p["names"]
    name = lambda x: n[str(x["abilityGameID"])]
    LOG_HITS = sorted(x["t"] for x in p["buffs"] if name(x) == "Tengentsu's Foresight" and x["type"] == "applybuff")
    first = min((x["t"] for x in p["casts"] if x["type"] == "cast" and name(x) == "Meikyo Shisui"), default=math.inf)
    off = [x["t"] for x in p["buffs"] if name(x) == "Meikyo Shisui" and x["type"] == "removebuff" and x["t"] < first]
    LOG_OPENER = ((3, max(off[0] + 0.05, MEIKYO_PREPULL + MEIKYO_S), (1, MEIKYO_PREPULL + CDS["Meikyo Shisui"][0]))
                  if off else (0, -1.0, (2, None)))
    med = sorted((x["t"], x["type"]) for x in p["buffs"] if name(x) == "Meditate")
    LOG_MEDITATE = {}
    for x in p["casts"]:
        if x["type"] != "cast" or name(x) != "Meditate": continue
        on = next((t for t, k in med if k == "applybuff" and 0 <= t - x["t"] < 1.5), None)
        off = next((t for t, k in med if k == "removebuff" and on is not None and t > on), None)
        LOG_MEDITATE[round(x["t"], 1)] = min(5, int((off - on + 0.3) // MEDITATE_TICK)) if off is not None else 0


def cast_time(s, name, at):
    return CAST.get(name, 0.0), None


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(combo=step(s, t), sen=sorted(s.sen), kenki=s.kenki, med=s.med, meikyo=s.meikyo if meikyo(s, t) else 0,
                tsubame=s.tsubame_until > t, ogi=s.ogi_until > t, namikiri=s.kn_until > t)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name in IAI.values():
        k = next(k for k, v in IAI.items() if v == name)
        s.sen = frozenset(("setsu", "getsu", "ka")[:k])
    if name in ("Kaeshi: Setsugekka", "Kaeshi: Goken"): s.tsubame_until = start + 1
    if name == "Ogi Namikiri": s.ogi_until = start + 1
    if name == "Kaeshi: Namikiri": s.kn_until = start + 1
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if name in KENKI_COST: s.kenki = max(s.kenki, KENKI_COST[name])
    if name == "Shoha": s.med = 3
    if name in CDS: s.cds[cd_name(name)] = (CDS[cd_name(name)][1], None)     # full: using one starts the recharge
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Positionals are grouped by True North,
    the one way the log shows one was surely taken; without it the model's potency is the miss."""
    if name not in POTENCY: return None
    if name in AUTO_CRIT: return "sure crit", POTENCY[name]
    p = POTENCY[name]
    if name == "Enpi": return ("enhanced" if s.ee_until > t else ""), p[s.ee_until > t]
    if isinstance(p, tuple):
        combo = in_combo(s, name, t)
        g, v = ("combo" if combo else "no combo"), p[combo]
        if name in POSITIONALS:
            tn = s.tn_until > t; g += " TN" if tn else ""; v += POSITIONAL * tn
        return g, v
    return "", p


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Fugetsu; status id from the scorecard's
    cached auras): FFLogs counts every damage-up on the hit, so dividing it out takes it away too."""
    return FUGETSU if "1001298." in (h.get("buffs") or "") else 1.0
