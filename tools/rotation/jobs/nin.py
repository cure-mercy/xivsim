"""Ninja at level 90, Dawntrail patch 7.3 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/ninja) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Melee Mastery III (level 94) raises the combo, Fuma Shuriken, Raiton,
Suiton, Bhavacakra and the Raijus there, and Kunai's Bane (92), Higi with Zesho Meppo / Deathfrog Medium (96) and
Tenri Jindo (100) lie above P12S. So the level-90 kit is the combo, Trick Attack, the mudras and ninjutsu, Kassatsu
(Hyosho Ranryu), Ten Chi Jin, Raiju, Dream Within a Dream, Dokumori, Bhavacakra with Meisui, and Bunshin with Phantom
Kamaitachi; Increase Attack Speed (45) takes 15% off the GCD and auto-attacks.

Level-90 values measured in the benchmark clears (2026-10-22, scratch/nin; our groups have no Ninja): the full FFLogs
logs of the nine clears with one (Feb 2025 - Sep 2026), each player's plain hits over FFLogs' multiplier (which leaves
Kassatsu out), scaled to Dream Within a Dream (180 a hit, set in 7.1):
- Spinning Edge 220, Gust Slash 160 / 320 in combo, Aeolian Edge 140 / 320 in combo +60 from the rear +100 with
  Kazematoi, Armor Crush 140 / 340 in combo +60 from the flank (bonusPercent 50 / 42 / 65 / 58 fit only these), Trick
  Attack 300 / 400 from the rear, Bhavacakra 350 / 500 under Meisui, Fleeting Raiju 560, Raiton 650, Suiton 500, Fuma
  Shuriken 450 (466 on 16 hits), Hyosho Ranryu 1,300 x 1.3 under Kassatsu, Dokumori 400 (7.3; 300 before), auto-attacks
  76 every 2.18 s;
- the shadow's hits are pet hits, only in the scorecard's acts caches (over the owner's multiplier at the time): a
  copied weaponskill 148 (tooltip 160), Phantom Kamaitachi 665 since 7.3 (550 before; tooltips 700 / 600).

Rules from the logs: mudras take a flat 0.5 s and a ninjutsu 1.5 s before the next GCD (Ten Chi Jin's first two
1.0 s), whatever the skill speed; mudras, ninjutsu, Raiju and Phantom Kamaitachi never break the combo; Raiju Ready
goes one stack a Raiju and all of it with a melee weaponskill; Bunshin's stacks go on weaponskills (the Raijus too),
not on ninjutsu or Phantom Kamaitachi; Shadow Walker (Suiton) is spent by Trick Attack or Meisui; the Trick Attack
and Dokumori debuffs reach hits executed from their own hit landing until 15 / 20 s later. Eight of nine clears press
the opener's three mudras before the pull (unlogged) and open with Suiton: the search does too (PREPULL), and a replay
reads it from the log (prepare).

Positionals and reach as for the Viper (jobs/vpr.py): Aeolian Edge (rear), Armor Crush (flank) and Trick Attack
(rear) need True North in the fight's `pinned` spans; the combo, Fleeting Raiju, Trick Attack, Dream Within a Dream,
Bhavacakra and Dokumori (8 y, taken as melee) need reach; ninjutsu, Phantom Kamaitachi and Throwing Dagger reach 20 y.
Forked Raiju (a gap closer) is left to replays: the search doesn't rush in while the plan keeps the player away.
"""
import itertools
from engine import ANIM_LOCK, BASE_GCD, SlotState, cd_key, recast, settle

POTENCY = {"Spinning Edge": 220, "Gust Slash": 160, "Aeolian Edge": 140, "Armor Crush": 140, "Throwing Dagger": 200,
           "Fleeting Raiju": 560, "Forked Raiju": 560, "Phantom Kamaitachi": 665, "Trick Attack": 300,
           "Dream Within a Dream": 180, "Bhavacakra": 350, "Dokumori": 400,
           "Fuma Shuriken": 450, "Raiton": 650, "Suiton": 500, "Hyosho Ranryu": 1300, "Katon": 350,
           "Goka Mekkyaku": 600, "Hyoton": 350, "Huton": 240, "Doton": 0, "Rabbit Medium": 0}
COMBO_POT = {"Gust Slash": 320, "Aeolian Edge": 320, "Armor Crush": 340}
POS, TA_REAR, KAZ, MEISUI_BONUS, KASSATSU = 60, 100, 100, 150, 1.30
SHADOW = 148                                    # a shadow's copy of a weaponskill (pet hit)
DREAM_HITS = 3
AUTO, AUTO_DELAY = 76, 2.18
HASTE = 0.85                                    # Increase Attack Speed: weaponskills and auto-attacks 15% faster
MUDRA_GCD, NINJ_RECAST, TCJ_RECAST = 0.5, 1.5, 1.0
WEAVE_SLACK = 0.05
MELEE_WS = ("Spinning Edge", "Gust Slash", "Aeolian Edge", "Armor Crush")
COMBO = MELEE_WS[:2]
FINISHERS = MELEE_WS[2:]
SHADOWED = set(MELEE_WS) | {"Fleeting Raiju", "Forked Raiju", "Throwing Dagger"}
WEAPONSKILLS = list(MELEE_WS) + ["Throwing Dagger", "Fleeting Raiju", "Forked Raiju", "Phantom Kamaitachi"]
MUDRAS = ("Ten", "Chi", "Jin")
NINJUTSU = ("Fuma Shuriken", "Raiton", "Suiton", "Hyosho Ranryu", "Katon", "Goka Mekkyaku", "Hyoton", "Huton", "Doton",
            "Rabbit Medium")
TCJ_ORDER = ("Fuma Shuriken", "Raiton", "Suiton")
SEQ = {"Fuma Shuriken": ("Ten",), "Raiton": ("Ten", "Chi"), "Suiton": ("Ten", "Chi", "Jin"),
       "Hyosho Ranryu": ("Ten", "Jin")}         # the search's mudras for each ninjutsu
GAIN = {"Spinning Edge": 5, "Gust Slash": 5, "Aeolian Edge": 15, "Armor Crush": 15, "Throwing Dagger": 5,
        "Fleeting Raiju": 5, "Forked Raiju": 5, "Phantom Kamaitachi": 10, "Dokumori": 40, "Meisui": 50}
COMBO_GAIN = {"Gust Slash", "Aeolian Edge", "Armor Crush"}           # their Ninki only in combo
SHADOW_NINKI = 5
# seconds from executing an action to its damage landing, the logs' medians (the shadow's from the acts caches)
DELAY = {"Spinning Edge": 0.40, "Gust Slash": 0.40, "Aeolian Edge": 0.53, "Armor Crush": 0.62, "Throwing Dagger": 0.6,
         "Fleeting Raiju": 0.76, "Forked Raiju": 0.67, "Phantom Kamaitachi": 1.65, "Trick Attack": 0.80,
         "Dream Within a Dream": 0.71, "Bhavacakra": 0.62, "Dokumori": 1.07, "Fuma Shuriken": 0.89, "Raiton": 0.71,
         "Suiton": 0.98, "Hyosho Ranryu": 0.62}
SHADOW_DELAY = {"Spinning Edge": 0.49, "Gust Slash": 0.49, "Aeolian Edge": 0.62, "Armor Crush": 0.72,
                "Fleeting Raiju": 0.85, "Forked Raiju": 0.85, "Throwing Dagger": 0.6}
TRICK, DOKUMORI = 1.10, 1.05                    # own debuffs on Athena: +10% the Ninja's damage, +5% everyone's
TA_S, DK_S = 15.0, 20.0                         # from the debuff's landing (its action's hit)
LAG = 0.6                                       # statuses outlast their tooltip in the logs (a Trick Attack 20.49 s after
                                                # its Suiton spent Shadow Walker; Meisui and Raiju Ready ran out at 30.6-30.7 s)
COMBO_S, SEQ_S, TCJ_S = 30, 6, 6
TN_S = 10.5                                     # True North ends 10.49-10.61 after its cast (calibrate's status check)
KASS_S, SW_S, MEISUI_S, RAIJU_S, BUN_S, PK_S = (d + LAG for d in (15, 20, 30, 30, 30, 45))
PREPULL = -3.5                                  # the search's pre-pull mudras: Ten, Chi, Jin from -3.5 s, Suiton at 0 (the
                                                # clears' charges fit first mudras 1.5-4.5 s before their opening Suiton)
CDS = {"Mudra": (20, 2), "Kassatsu": (60, 1), "Trick Attack": (60, 1), "Dream Within a Dream": (60, 1),
       "Dokumori": (120, 1), "Ten Chi Jin": (120, 1), "Meisui": (120, 1), "Bunshin": (90, 1), "Bhavacakra": (1, 1),
       "True North": (45, 2), "Tincture": (270, 1)}
GCDS = WEAPONSKILLS + list(MUDRAS) + list(NINJUTSU)
OGCD_ORDER = ["Tincture", "Dokumori", "Bunshin", "Kassatsu", "Ten Chi Jin", "Trick Attack", "Meisui",
              "Dream Within a Dream", "Bhavacakra", "True North"]
HARM_OGCDS = ("Trick Attack", "Dream Within a Dream", "Bhavacakra", "Dokumori")
MELEE_ACTIONS = set(MELEE_WS) | {"Fleeting Raiju", "Trick Attack", "Dream Within a Dream", "Bhavacakra", "Dokumori"}
POSITIONALS = {"Aeolian Edge", "Armor Crush"}
SPEED = 0.984                                   # skill speed factor: 2.46 s unhasted, a 2.09 s GCD (the clears'
                                                # median calibrate.gcd_of; 2.41-2.47 s)
MELEE = True                                    # p12s.py gives it a melee's windows (M1 / M2)
LOG_PREPULL = None                              # a replay: when the log's unlogged pre-pull mudras began (prepare)


class State(SlotState):
    __slots__ = ("t", "gcd", "combo", "combo_until", "kaz", "ninki", "seq", "seq_until", "kass_until", "tcj", "tcj_until",
                 "sw_until", "meisui_until", "raiju", "raiju_until", "bun", "bun_until", "pk_until", "ta", "dk",
                 "tn_until", "cds", "auto_next", "dmg", "lost", "waste", "pot_at", "first", "hist", "mvi", "acc", "free",
                 "spot", "ai", "mlast", "near")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.combo, s.combo_until, s.kaz, s.ninki = 0, -1.0, 0, 0
        s.seq, s.seq_until = (), -1.0             # the mudras made so far
        s.kass_until, s.tcj, s.tcj_until = -1.0, 0, -1.0
        s.sw_until = s.meisui_until = s.pk_until = s.tn_until = -1.0
        s.raiju, s.raiju_until, s.bun, s.bun_until = 0, -1.0, 0, -1.0
        s.ta = s.dk = (-1.0, -1.0)                # debuff windows on Athena: (from, to)
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        pre = PREPULL if LOG_PREPULL is None else LOG_PREPULL
        if pre is not False:                      # the pull opens on Suiton from mudras made before it
            s.seq, s.seq_until = MUDRAS, pre + SEQ_S
            s.cds["Mudra"] = (1, pre + CDS["Mudra"][0])
        s.auto_next, s.dmg, s.lost, s.pot_at, s.first, s.hist = 0.0, 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0
        s.ai, s.mlast, s.near = 0, -30.0, False
        return s

    def key(self):
        return (round(self.t, 1), round(self.gcd, 1), self.combo if self.combo_until > self.t else 0, self.kaz,
                self.ninki, self.seq if self.seq_until > self.t else (), round(max(self.kass_until - self.t, 0), 1),
                self.tcj if self.tcj_until > self.t else -1, round(max(self.sw_until - self.t, 0), 1),
                self.meisui_until > self.t, self.raiju if self.raiju_until > self.t else 0,
                self.bun if self.bun_until > self.t else 0, round(max(self.pk_until - self.t, 0), 1),
                round(max(self.ta[1] - self.t, 0), 1), round(max(self.dk[1] - self.t, 0), 1),
                round(max(self.tn_until - self.t, 0), 1), self.pot_at is None, cd_key(self.cds), self.mvi,
                round(min(self.acc, 4.0) * 2) / 2, self.ai,
                round(min(self.t - self.mlast, 4), 1) if self.near else None)



WASTE = ("Ninki overcapped", "Kazematoi overcapped", "Raiju Ready lost", "Bunshin stacks lost")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time passing --------------------------------------------------------------------------------------------------

def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, and the Ninja's own Trick Attack and
    Dokumori on Athena."""
    m = fight.mult(at, s.pot_at)
    if s.ta[0] <= at < s.ta[1]: m *= TRICK
    if s.dk[0] <= at < s.dk[1]: m *= DOKUMORI
    return m


def advance(s, fight, to):
    """Auto-attacks up to `to` (while the boss can be hit and the player is in reach), and statuses that lapse."""
    while s.auto_next <= to:
        a = s.auto_next
        if 0 <= a + 0.5 < fight.until and fight.targetable(a) and not out_of_reach(s, fight, a):
            s.dmg += AUTO * mult(s, fight, a)
        s.auto_next = a + AUTO_DELAY
    if s.raiju and s.raiju_until <= to: wasted(s, 2, s.raiju); s.raiju = 0
    if s.bun and s.bun_until <= to: wasted(s, 3, s.bun); s.bun = 0


def cd_name(name):
    return "Mudra" if name in MUDRAS else name


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
    """Potency the cooldowns have lost sitting full so far (CAPPED: what a second of their recharge is worth)."""
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


def ready(s, name, t):
    """When the cooldown next has a charge, from t."""
    n, nxt = charges(s, name, t)
    return t if n else nxt


def hit(s, fight, at, potency, name, delay=None):
    land = at + (DELAY.get(name, 0.6) if delay is None else delay)
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
    for w in fight.away[s.ai:]:                     # a loop, not any() over a generator: called for every action
        if w.lo <= t + ahead and w.hi > t: return True
    return False


# --- actions -------------------------------------------------------------------------------------------------------

def combo_step(s, at):
    return s.combo if s.combo_until > at else 0


def mudras(s, at):
    return s.seq if s.seq_until > at else ()


def in_tcj(s, at):
    return s.tcj_until > at and s.tcj < 3


def kassatsu(s, at):
    return s.kass_until > at


def ninjutsu_of(seq, kass):
    """The ninjutsu a mudra sequence makes (Rabbit Medium for a broken one)."""
    if not seq or len(set(seq)) < len(seq): return "Rabbit Medium"
    last = seq[-1]
    if len(seq) == 1: return "Fuma Shuriken"
    if len(seq) == 2:
        return {"Chi": "Raiton", "Ten": "Goka Mekkyaku" if kass else "Katon",
                "Jin": "Hyosho Ranryu" if kass else "Hyoton"}[last]
    return {"Jin": "Suiton", "Ten": "Huton", "Chi": "Doton"}[last]


def ninki(s, n):
    if s.ninki + n > 100: wasted(s, 0, s.ninki + n - 100)
    s.ninki = min(100, s.ninki + n)


def gcd_legal(s, name, at):
    if in_tcj(s, at): return name in NINJUTSU                    # only ninjutsu while Ten Chi Jin lasts
    if name in MUDRAS: return bool(mudras(s, at)) or kassatsu(s, at) or charges(s, "Mudra", at)[0] > 0
    if name in NINJUTSU:
        seq = mudras(s, at)
        return bool(seq) and (name == ninjutsu_of(seq, kassatsu(s, at)) or name == "Rabbit Medium")
    if name in ("Fleeting Raiju", "Forked Raiju"): return s.raiju > 0 and s.raiju_until > at
    if name == "Phantom Kamaitachi": return s.pk_until > at
    return True                                 # the combo, Throwing Dagger


def potency(s, fight, name, at):
    p = POTENCY[name]
    st = combo_step(s, at)
    if name == "Gust Slash" and st == 1: p = COMBO_POT[name]
    if name in FINISHERS:
        if st == 2: p = COMBO_POT[name]
        p += POS * flank_rear(s, fight, at)
        if name == "Aeolian Edge" and s.kaz: p += KAZ
    return p


def do_gcd(s, fight, name):
    """Execute a GCD (a weaponskill, a mudra or a ninjutsu) as soon as possible; returns the new state or None."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    if name not in MUDRAS and (not fight.targetable(start) or fight.next_down(start) <= start + DELAY.get(name, 0.6)):
        return None
    if name in MELEE_ACTIONS and not reach(s, fight, start): return None
    s.first = False
    if name in MUDRAS:
        seq = mudras(s, start)
        if not seq:
            if not kassatsu(s, start): use_cd(s, "Mudra", start)
            s.seq_until = start + SEQ_S
        s.seq = seq + (name,)
        s.t = s.gcd = start + MUDRA_GCD
        s.log(start, name, gauge(s))
        return s
    if name in NINJUTSU:
        tcj = in_tcj(s, start)
        p = POTENCY[name] * (KASSATSU if kassatsu(s, start) else 1.0)
        hit(s, fight, start, p, name)
        s.seq, s.seq_until, s.kass_until = (), -1.0, -1.0
        if name == "Raiton":
            if s.raiju == 3: wasted(s, 2)
            s.raiju, s.raiju_until = min(3, (s.raiju if s.raiju_until > start else 0) + 1), start + RAIJU_S
        elif name in ("Suiton", "Huton"): s.sw_until = start + SW_S
        rc = NINJ_RECAST
        if tcj:
            s.tcj += 1
            if s.tcj < 3: rc = TCJ_RECAST
            else: s.tcj_until = -1.0
        s.t, s.gcd = start + min(ANIM_LOCK, rc), start + rc
        s.log(start, name, gauge(s))
        return s
    # a weaponskill
    st = combo_step(s, start)
    hit(s, fight, start, potency(s, fight, name, start), name)
    if name in SHADOWED and s.bun and s.bun_until > start:
        hit(s, fight, start, SHADOW, name, SHADOW_DELAY.get(name, 0.6))
        s.bun -= 1; ninki(s, SHADOW_NINKI)
    if name in GAIN and (name not in COMBO_GAIN or st == MELEE_WS.index(name) or name in FINISHERS and st == 2):
        ninki(s, GAIN[name])
    if name in MELEE_WS:
        if s.raiju and s.raiju_until > start: wasted(s, 2, s.raiju)
        s.raiju = 0
        if name == "Spinning Edge": s.combo, s.combo_until = 1, start + COMBO_S
        elif name == "Gust Slash" and st == 1: s.combo, s.combo_until = 2, start + COMBO_S
        else:
            if name == "Aeolian Edge" and s.kaz: s.kaz -= 1
            if name == "Armor Crush" and st == 2:
                if s.kaz > 3: wasted(s, 1, s.kaz - 3)
                s.kaz = min(5, s.kaz + 2)
            s.combo, s.combo_until = 0, -1.0
    elif name in ("Fleeting Raiju", "Forked Raiju"):
        s.raiju -= 1
    elif name == "Phantom Kamaitachi":
        s.pk_until = -1.0
    s.t, s.gcd = start + ANIM_LOCK, start + recast(BASE_GCD, SPEED, HASTE)
    s.near = away_soon(s, fight, s.t)
    s.log(start, name, gauge(s))
    return s


def gauge(s):
    t = s.t
    on = [n for n, u in (("SW", s.sw_until), ("kassatsu", s.kass_until), ("meisui", s.meisui_until),
                         ("PK", s.pk_until)) if u > t]
    if s.raiju and s.raiju_until > t: on.append(f"raiju {s.raiju}")
    if s.bun and s.bun_until > t: on.append(f"bunshin {s.bun}")
    if s.ta[0] <= t < s.ta[1]: on.append("TA")
    if s.dk[0] <= t < s.dk[1]: on.append("doku")
    return f"ninki {s.ninki:3d}  kaz {s.kaz}  mudra {charges(s, 'Mudra', t)[0]}  " + " ".join(on)


def ogcd_legal(s, name, at, fight, policy=True):
    if name not in CDS or charges(s, name, at)[0] < 1: return False
    if in_tcj(s, at) or mudras(s, at) and name != "Tincture": return False     # it would break the mudras / Ten Chi Jin
    if name in ("Trick Attack", "Meisui"):
        if s.sw_until <= at: return False
        if name == "Meisui": return at >= 0 and not (policy and ready(s, "Trick Attack", at) < s.sw_until - 1.0)
        return True
    if name in ("Bhavacakra", "Bunshin"): return s.ninki >= 50
    if name == "Ten Chi Jin": return not kassatsu(s, at)
    if name == "Kassatsu": return not (policy and kassatsu(s, at))
    if name == "True North": return not policy or (s.tn_until <= at and (not flank_rear(s, fight, at + 2.5) or
                                                                         not flank_rear(s, fight, at + 5.0)))
    if name == "Tincture": return fight.pot and s.pot_at is None
    return not (policy and s.first)


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in HARM_OGCDS and not fight.targetable(at): return None
    if name in MELEE_ACTIONS and not reach(s, fight, at): return None
    use_cd(s, name, at)
    if name == "Trick Attack":
        hit(s, fight, at, POTENCY[name] + TA_REAR * flank_rear(s, fight, at), name)
        land = at + DELAY[name]
        s.ta, s.sw_until = (land, land + TA_S), -1.0
    elif name == "Dokumori":
        hit(s, fight, at, POTENCY[name], name)
        land = at + DELAY[name]
        s.dk = (land, land + DK_S)
        ninki(s, GAIN[name])
    elif name == "Dream Within a Dream": hit(s, fight, at, POTENCY[name] * DREAM_HITS, name)
    elif name == "Bhavacakra":
        bonus = s.meisui_until > at
        hit(s, fight, at, POTENCY[name] + MEISUI_BONUS * bonus, name)
        s.ninki -= 50
        if bonus: s.meisui_until = -1.0
    elif name == "Bunshin":
        s.ninki -= 50
        if s.bun and s.bun_until > at: wasted(s, 3, s.bun)
        s.bun, s.bun_until, s.pk_until = 5, at + BUN_S, at + PK_S
    elif name == "Meisui":
        s.sw_until, s.meisui_until = -1.0, at + MEISUI_S
        ninki(s, GAIN[name])
    elif name == "Kassatsu": s.kass_until = at + KASS_S
    elif name == "Ten Chi Jin": s.tcj, s.tcj_until = 0, at + TCJ_S
    elif name == "True North": s.tn_until = at + TN_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.near = away_soon(s, fight, s.t)
    s.log(at, name, gauge(s))
    return s


# --- the search ----------------------------------------------------------------------------------------------------

def chain(s, fight, names):
    """Several GCDs back to back (the mudras and their ninjutsu, Ten Chi Jin's three), or None if one can't be."""
    for g in names:
        s = do_gcd(s, fight, g)
        if s is None: return None
    return s


def candidates(c, fight, now):
    """The GCD steps worth trying next, each a tuple of GCDs. Ten Chi Jin's three ninjutsu while it lasts; otherwise the
    combo's next step (the finisher: Aeolian Edge with Kazematoi, Armor Crush below four), a Raiju, Phantom Kamaitachi,
    Raiton on a mudra charge, Suiton when Shadow Walker would be there for Trick Attack, and Throwing Dagger out of
    reach. Under Kassatsu only Hyosho Ranryu."""
    if in_tcj(c, now): return [TCJ_ORDER[c.tcj:]]
    if kassatsu(c, now): return [SEQ["Hyosho Ranryu"] + ("Hyosho Ranryu",)]
    st = combo_step(c, now)
    if st < 2: out = [(MELEE_WS[st],)]
    else: out = [(f,) for f, ok in (("Aeolian Edge", c.kaz > 0), ("Armor Crush", c.kaz <= 3)) if ok]
    if c.raiju and c.raiju_until > now: out.append(("Fleeting Raiju",))
    if c.pk_until > now: out.append(("Phantom Kamaitachi",))
    if charges(c, "Mudra", now)[0] > 0:
        out.append(SEQ["Raiton"] + ("Raiton",))
        if c.sw_until <= now + 2 and ready(c, "Trick Attack", now) < now + 2 + SW_S - 3:
            out.append(SEQ["Suiton"] + ("Suiton",))
    if not reach(c, fight, now, commit=False): out.append(("Throwing Dagger",))
    return out


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD step, then the step. Kassatsu goes only right before
    Hyosho Ranryu, Ten Chi Jin before its three ninjutsu, True North before a positional. While Athena is away, waits
    until she is back, or 1-1.5 s before, so the mudras can be ready for her."""
    now = max(s.t, s.gcd)
    if s.first and mudras(s, now):                     # the pre-pull mudras: Suiton first
        n = do_gcd(s, fight, "Suiton")
        return [n] if n else []
    back = fight.back_up(now)
    if back - 1.5 > now + 1e-9:                         # Athena away: every wait gains time (a child that doesn't
        out = []                                        # would keep its rank and hang the beam)
        for lead in (1.5, 1.0, 0.0):
            w = s.copy(); w.gcd = back - lead; w.t = max(s.t, w.gcd - 2 * ANIM_LOCK)
            name = f"(boss away, until {lead:.1f} s before)" if lead else "(boss away)"     # polish picks by name
            w.log(s.t, name); out.append(w)
        return out
    slots = min(2, int((s.gcd - s.t + WEAVE_SLACK) / ANIM_LOCK + 1e-6)) if not s.first else 0
    ready_ = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, slots + 1):
        for combo in itertools.combinations(ready_, k):
            if "Kassatsu" in combo and "Ten Chi Jin" in combo: continue
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, fight, now):
                if "Kassatsu" in combo and g[-1] != "Hyosho Ranryu": continue
                if "Ten Chi Jin" in combo and g[0] not in TCJ_ORDER: continue
                if "True North" in combo and g[-1] not in POSITIONALS: continue
                n = chain(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            if not combo and not any_gcd:
                w = c.copy(); w.t = w.gcd = now + 0.5
                w.log(c.t, "(wait)"); out.append(w)
    return out


# what holding a resource is worth (flat potency; engine.configure scales them): what it converts into less RATE times
# the GCD time it takes. A combo step what the rest of the combo brings over Spinning Edges; Kazematoi an Aeolian Edge's
# +100; Ninki a fiftieth of a Bhavacakra; a Raiju Ready stack Fleeting Raiju (and its shadow, Ninki) over a filler GCD;
# Phantom Kamaitachi Ready likewise; a Bunshin stack its shadow hit; Shadow Walker its Trick Attack or Meisui's Ninki;
# Meisui a Bhavacakra's +150.
VALUE = dict(combo1=110, combo2=220, kaz=90, ninki=7, raiju=250, pk=400, bun=180, sw=150, meisui=150, cap_mudra=20)
# A cooldown sitting at full charges loses what its recharge would bring (pct.py's CAPPED, at its share a second)
CAPPED = {"Mudra": "cap_mudra"}
CAP_W = 1.0
RATE = 300                                            # potency per second, to compare states at slightly different times
# tune.py --job nin (2026-10-22, 36 settings, M2 whole phase): rates 300-340 at scale 1.0 all find 131,102 (M1 the same),
# scale 0.8 131,056, 0.5 -0.4%; those ties make a portfolio of them redundant, so it keeps scale 0.8 and 1.5 (the best
# standing still over 0:00-365 s) beside two of them
HEURISTICS = [(300, 1.0, 0.0), (340, 1.0, 0.0), (315, 0.8, 0.0), (300, 1.5, 0.0)]
WIDTH = 2000                                          # the beam (--layers gcd): 1,000-4,000 within 1.5%, 48 s at 2,000
SWEEP_WIDTH = 2000                                    # engine.sweep: 1,000-8,000 within 0.5% and 1.5-3% over the beam
                                                      # (39 s at 2,000, one setting)
MOVE_WEIGHT = 0.0
END_TAPER = 15.0                                      # held resources fade over the window's last seconds


def held(s):
    t = s.t
    st = combo_step(s, t)
    v = VALUE["combo1"] * (st == 1) + VALUE["combo2"] * (st == 2) + VALUE["kaz"] * s.kaz + VALUE["ninki"] * s.ninki
    v += VALUE["raiju"] * (s.raiju if s.raiju_until > t else 0) + VALUE["bun"] * (s.bun if s.bun_until > t else 0)
    v += VALUE["pk"] * (s.pk_until > t) + VALUE["sw"] * (s.sw_until > t) + VALUE["meisui"] * (s.meisui_until > t)
    return v


def rank(s, fight):
    return s.dmg + held(s) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - CAP_W * capped(s, s.t) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the swings still to come before the window ends
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Ninja", "2024-11-12"        # 7.1 set Dream Within a Dream; 7.3 Dokumori and Phantom Kamaitachi
CONVERT_SINCE = "2025-08-05"                        # none of our players is a Ninja: dps.py --site converts at the clears'
                                                    # Ninjas since 7.3 (four players), at the current values and gear
OGCDS = set(OGCD_ORDER)
REFERENCE = ("Dream Within a Dream", 180)           # a hit; untouched since 7.1
CAST = {}


def cast_time(s, name, at):
    return 0.0, None


def prepare(p):
    """A replay of log p opens with mudras made before the pull when its first ninjutsu comes before any logged mudra
    (their casts aren't logged), made as early as the 6 s Mudra status allows: its charge comes back soonest."""
    global LOG_PREPULL
    n = p["names"]
    cs = [(x["t"], n[str(x["abilityGameID"])]) for x in p["casts"] if x["type"] == "cast"]
    first_n = next((t for t, a in cs if a in NINJUTSU), None)
    first_m = next((t for t, a in cs if a in MUDRAS), None)
    LOG_PREPULL = first_n - SEQ_S if first_n is not None and (first_m is None or first_n < first_m) else False


def unprepare():
    global LOG_PREPULL
    LOG_PREPULL = None


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


STATUSES = {"Mudra": lambda s, t: bool(s.seq) and s.seq_until > t, "Kassatsu": lambda s, t: s.kass_until > t,
            "Ten Chi Jin": lambda s, t: s.tcj_until > t, "Shadow Walker": lambda s, t: s.sw_until > t,
            "Meisui": lambda s, t: s.meisui_until > t, "Raiju Ready": lambda s, t: s.raiju > 0 and s.raiju_until > t,
            "Bunshin": lambda s, t: s.bun > 0 and s.bun_until > t, "Phantom Kamaitachi Ready": lambda s, t: s.pk_until > t,
            "True North": lambda s, t: s.tn_until > t}


def status(s, t):
    return dict(combo=combo_step(s, t), kaz=s.kaz, ninki=s.ninki, mudras=mudras(s, t), mudra=charges(s, "Mudra", t),
                kassatsu=kassatsu(s, t), tcj=s.tcj if s.tcj_until > t else None, sw=s.sw_until > t,
                raiju=s.raiju if s.raiju_until > t else 0, bunshin=s.bun if s.bun_until > t else 0, pk=s.pk_until > t)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    s.tcj_until = s.tcj_until if name in NINJUTSU else -1.0
    if name in MUDRAS and not mudras(s, start):
        s.cds["Mudra"] = (1, charges(s, "Mudra", start)[1] or start + CDS["Mudra"][0])
    if name in NINJUTSU and not in_tcj(s, start):
        seq = next((q for q in (("Ten",), ("Ten", "Chi"), ("Chi", "Ten"), ("Ten", "Jin"), ("Ten", "Chi", "Jin"),
                                ("Chi", "Jin", "Ten"), ("Ten", "Jin", "Chi"))
                    if ninjutsu_of(q, name in ("Hyosho Ranryu", "Goka Mekkyaku")) == name), ("Ten", "Ten"))
        s.seq, s.seq_until = seq, start + 1
        if name in ("Hyosho Ranryu", "Goka Mekkyaku"): s.kass_until = start + 1
    if name in ("Fleeting Raiju", "Forked Raiju"): s.raiju, s.raiju_until = max(s.raiju, 1), max(s.raiju_until, start + 1)
    if name == "Phantom Kamaitachi": s.pk_until = start + 1
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    s.seq, s.seq_until, s.tcj_until = (), -1.0, -1.0
    if name in CDS:                                 # one charge, the recharge still running (True North has two)
        rec, mx = CDS[name]
        s.cds[name] = (1, charges(s, name, t)[1] or (None if mx == 1 else t + rec))
    if name in ("Trick Attack", "Meisui"): s.sw_until = t + 1
    if name in ("Bhavacakra", "Bunshin"): s.ninki = max(s.ninki, 50)
    if name == "Ten Chi Jin": s.kass_until = -1.0
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Positionals are grouped by True North,
    the one way the log shows one was surely taken; without it the model's potency is the miss."""
    if name not in POTENCY: return None
    if name in NINJUTSU: return ("kassatsu" if kassatsu(s, t) else ""), POTENCY[name] * (KASSATSU if kassatsu(s, t) else 1)
    if name == "Bhavacakra": return ("meisui", POTENCY[name] + MEISUI_BONUS) if s.meisui_until > t else ("", POTENCY[name])
    if name == "Trick Attack": return ("TN", 400) if s.tn_until > t else ("", 300)
    if name in FINISHERS or name == "Gust Slash":
        st = combo_step(s, t)
        p = COMBO_POT[name] if st == (2 if name in FINISHERS else 1) else POTENCY[name]
        if name in FINISHERS:
            tn = s.tn_until > t
            p += POS * tn + (KAZ if name == "Aeolian Edge" and s.kaz else 0)
            return ("combo" if p >= COMBO_POT[name] else "") + (" kaz" if name == "Aeolian Edge" and s.kaz else "") + (" TN" if tn else ""), p
        return ("combo" if p == COMBO_POT[name] else ""), p
    return "", POTENCY[name]


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own: their Trick Attack and Dokumori on Athena
    (status ids on the hits): FFLogs counts every damage-up on the hit, so dividing it out takes it away too."""
    b = h.get("buffs") or ""
    return (TRICK if "1003254." in b else 1.0) * (DOKUMORI if "1003849." in b else 1.0)
