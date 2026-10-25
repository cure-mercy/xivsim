"""Summoner at level 90, Dawntrail patch 7.1 and later, single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/summoner) and the patch notes since 7.0
(patchnotes.py). Both show level-100 values: Arcane Mastery (level 94) raises nearly every potency there, and Necrotize
(92), Ruby's Glimmer / Searing Flash (96) and Solar Bahamut (100) lie above P12S. At level 90 the potencies are
Endwalker's (Ruin Mastery IV, 84, sets Ruin III and the Rites), and the patches since 7.0 touch only the level-94 values.

Level-90 values measured in our logs (2026-10-22, scratch/smn): the scorecard's cached events (our 77 pulls by two
Summoners, Sep-Oct 2026, with the pets' hits under the owner; 11 benchmark clears, Mar-Dec 2025), each player's
plain-hit cluster with others' damage buffs and their own Searing Light divided out, scaled to Fester (340, untouched):
- Ruin III 310, Ruin IV 430, Astral Impulse 440, Fountain of Fire 540, Ruby Rite 510, Topaz Rite 330, Emerald Rite 230,
  Energy Drain 200, Deathflare 500, Mountain Buster 150, Crimson Cyclone and Crimson Strike 430, Slipstream 430 and its
  windstorm 30 a tick;
- the pets' hits stand at 0.79 of their tooltips: Wyrmwave and Scarlet Flame 119, Akh Morn and Revelation 1,030 (1,300),
  Inferno, Earthen Fury and Aerial Blast 600; Searing Light raises them too (+5% on Akh Morn and Wyrmwave as on Fester).

The loop: a demi-summon (Summon Bahamut, then Summon Phoenix, alternating; a 60 s GCD) opens a 15 s trance in which
Ruin III becomes Astral Impulse / Fountain of Fire, the demi hits four times on its own (Wyrmwave / Scarlet Flame), and
Enkindle (Akh Morn / Revelation) and, under Bahamut, Deathflare can be used once. It grants the three Arcanum: after the
trance, Summon Ifrit II / Titan II / Garuda II (instant GCDs, any order) each hit once (their pet's 600) and grant
attunement for the Rites (Gemshine): two Ruby Rites (2.8 s casts on a 3 s recast), four Topaz Rites (each granting
Titan's Favor for an oGCD Mountain Buster) or four Emerald Rites (instant, 1.5 s recast); Ifrit adds Crimson Cyclone
(a dash to the boss) -> Crimson Strike (3 y), Garuda Slipstream (a 3 s cast on a 3.5 s recast, then a windstorm under
the boss for 15 s). Energy Drain (60 s) gives two Aetherflow for Fester and Further Ruin for one instant Ruin IV;
Searing Light (120 s) +5% for 20 s.

From the logs (none of it in the guide):
- Summon Bahamut / Phoenix are GCD spells, their 60 s shortened by spell speed (every log's gaps; 57 s at a 2.31 s
  GCD), the next GCD 2.5 s later, Deathflare and Searing Light woven after them); no Rite,
  favor action or primal comes inside a trance (the first primal 16-22 s after the demi), and a demi-summon or a primal
  removes whatever favor is left (Ifrit's / Garuda's Favor and Crimson Strike Ready otherwise last 50 s and more).
- The demi's four hits come on their own timer, 5.1 / 7.3 / 10.4 / 13.5 s after the summon, whatever is cast (a trance
  with one Fountain of Fire still got four Scarlet Flames); Akh Morn and Revelation land ~1.0 s after Enkindle, but not
  before the demi is out (~3 s after the summon); Inferno and Earthen Fury land 4.06 s after their summon, Aerial
  Blast 3.39 s.
- Emerald Rite's 1.5 s recast doesn't shrink with spell speed (1.47-1.51 s at a 2.32 s GCD); Ruin III, Ruby Rite,
  Slipstream and their recasts do. The windstorm ticks six times, at its landing and every 3 s after.
- MP never binds (lowest logged 1,600 in 15,000 casts): the model leaves it out; Rekindle, Radiant Aegis, Lucid Dreaming
  and Addle only take time in a replay.

Crimson Cyclone rushes to Athena (engine.dash's gap closer). While our plan holds the player to a spot (from a
mechanic's first cue to its last snapshot, as p12s.plan_spans) it may only be a dash along a stretch of the run that goes
straight to her (Paradeigma I's swap in R1): anywhere else it would pull them off the spot. As Red Mage's Corps-a-corps
it can't pull them off a far spot before its snapshot. Crimson Strike reaches 3 y beyond her hitbox, so it needs melee
reach (p12s.FAR).
"""
import itertools
from engine import ANIM_LOCK, BASE_GCD, RESOLVE, SLIDE, SlotState, cd_key, dash, dash_gain, gcd_times, settle, stand

POTENCY = {"Ruin III": 310, "Ruin IV": 430, "Astral Impulse": 440, "Fountain of Fire": 540, "Ruby Rite": 510,
           "Topaz Rite": 330, "Emerald Rite": 230, "Fester": 340, "Energy Drain": 200, "Deathflare": 500,
           "Mountain Buster": 150, "Crimson Cyclone": 430, "Crimson Strike": 430, "Slipstream": 430}
PET = {"Wyrmwave": 119, "Scarlet Flame": 119, "Akh Morn": 1030, "Revelation": 1030, "Inferno": 600, "Earthen Fury": 600,
       "Aerial Blast": 600}
DEMIS = ("Summon Bahamut", "Summon Phoenix")
TRANCE = {"Summon Bahamut": ("Astral Impulse", "Wyrmwave", "Enkindle Bahamut", "Akh Morn"),
          "Summon Phoenix": ("Fountain of Fire", "Scarlet Flame", "Enkindle Phoenix", "Revelation")}
PRIMALS = {"Summon Ifrit II": ("ruby", 2, "Inferno", 4.06), "Summon Titan II": ("topaz", 4, "Earthen Fury", 4.06),
           "Summon Garuda II": ("emerald", 4, "Aerial Blast", 3.39)}
RITE = {"ruby": "Ruby Rite", "topaz": "Topaz Rite", "emerald": "Emerald Rite"}
TRANCE_S, ATT_S, FR_S, SL_S, SL_MULT, SWIFT_S = 15.0, 30.0, 60.0, 20.0, 1.05, 10.0
DEMI_HITS = (5.1, 7.3, 10.4, 13.5)              # the demi's own hits, seconds after the summon
ENK_DELAY, ENK_OUT = 1.0, 3.0                   # Akh Morn / Revelation: after Enkindle, and not before summon + 3 s
SLIP_BASE, SLIP_TICKS = 30.0, (0.0, 1.5, 4.5, 7.5, 10.5, 13.5)   # windstorm ticks after its landing (the 3 s tick's phase averaged)
# Slipstream's tick: plain potency at base speed, its tooltip's 30, as every DoT (measured 30.2: its ground ticks are
# ordinary hits in the logs, crit and direct-hit flags included); dot_tick() puts on the spell speed bonus (2 - SPEED)


def dot_tick():
    return SLIP_BASE * (2 - SPEED)


CAST = {"Ruin III": 1.5, "Ruby Rite": 2.8, "Slipstream": 3.0}  # scaled by spell speed
RECAST = {"Ruby Rite": 3.0, "Slipstream": 3.5}  # scaled; Emerald Rite's 1.5 s is not (FIXED)
FIXED = {"Emerald Rite": 1.5}
# seconds from executing (a spell: resolving) to the damage landing, the logs' medians
DELAY = {"Ruin III": 0.80, "Ruin IV": 0.80, "Astral Impulse": 0.63, "Fountain of Fire": 1.07, "Ruby Rite": 0.63,
         "Topaz Rite": 0.63, "Emerald Rite": 0.63, "Fester": 0.94, "Energy Drain": 1.03, "Deathflare": 0.80,
         "Mountain Buster": 0.76, "Crimson Cyclone": 0.85, "Crimson Strike": 0.76, "Slipstream": 1.02}
CDS = {"Demi": (60, 1), "Energy Drain": (60, 1), "Searing Light": (120, 1), "Swiftcast": (60, 1), "Deathflare": (20, 1),
       "Enkindle": (20, 1), "Fester": (1, 1), "Mountain Buster": (1, 1), "Tincture": (270, 1)}
OGCD_ORDER = ["Tincture", "Searing Light", "Energy Drain", "Enkindle Bahamut", "Enkindle Phoenix", "Deathflare",
              "Mountain Buster", "Fester", "Swiftcast"]
DAMAGE_OGCDS = {"Energy Drain", "Enkindle Bahamut", "Enkindle Phoenix", "Deathflare", "Mountain Buster", "Fester"}
GCDS = ["Ruin III", "Ruin IV", "Astral Impulse", "Fountain of Fire", *DEMIS, *PRIMALS, "Ruby Rite", "Topaz Rite",
        "Emerald Rite", "Crimson Cyclone", "Crimson Strike", "Slipstream"]
MELEE_ACTIONS = {"Crimson Strike"}              # 3 y beyond Athena's hitbox
SPEED = 0.98                                    # spell speed factor: a 2.45 s GCD, the benchmark clears' (2.41-2.45) and
                                                # one of our two Summoners' (the other plays 2.32 s)


class State(SlotState):
    __slots__ = ("t", "gcd", "nxt_demi", "demi", "demi_t", "enk", "arc", "att", "stacks", "att_until", "favor", "csr",
                 "mb", "af", "fr_until", "sl_from", "sl_until", "swift", "cds", "lost", "dmg", "dotp", "pot_at", "first",
                 "hist", "mvi", "acc", "free", "spot", "ai", "mlast", "dashed", "waste")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.nxt_demi, s.demi, s.demi_t, s.enk = DEMIS[0], None, -99.0, False
        s.arc = frozenset()                     # Arcanum left: the primal summons still to make
        s.att, s.stacks, s.att_until = None, 0, -1.0
        s.favor, s.csr, s.mb = None, False, False   # Ifrit's / Garuda's Favor, Crimson Strike Ready, Titan's Favor
        s.af, s.fr_until = 0, -1.0
        s.sl_from = s.sl_until = s.swift = -1.0
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.lost = 0.0
        s.dmg, s.dotp, s.pot_at, s.first, s.hist = 0.0, 0.0, None, True, None
        s.waste = (0, 0, 0, 0, 0)
        s.mvi, s.acc, s.free, s.spot = 0, 0.0, -30.0, 0        # forced movement (engine.stand)
        s.ai, s.mlast = 0, -30.0                                # out of reach (fight.away)
        s.dashed = ()                                           # (move window, segment) dashed (engine.dash)
        return s

    def key(self):
        t = self.t
        return (round(t, 1), round(self.gcd, 1), self.nxt_demi, self.demi if in_trance(self, t) else None,
                round(max((self.demi_t + TRANCE_S) - t, 0), 1), self.enk, self.arc,
                self.att if attuned(self, t) else None, self.stacks if attuned(self, t) else 0, self.favor, self.csr,
                self.mb, self.af, round(max(self.fr_until - t, 0), 1) // 5, round(max(self.sl_until - t, 0), 1),
                self.swift > t, self.pot_at is None, cd_key(self.cds), self.mvi, round(min(self.acc, 4.0) * 2) / 2,
                self.spot, self.ai, tuple(k for i, k in self.dashed if i == self.mvi))



WASTE = ("Arcanum lost to a demi-summon", "attunement stacks lost", "favor lost", "Aetherflow overcapped",
         "Further Ruin lost")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- statuses and cooldowns ----------------------------------------------------------------------------------------

def in_trance(s, t):
    return s.demi is not None and t < s.demi_t + TRANCE_S


def demi_out(s, t):
    return s.demi is not None and s.demi_t <= t < s.demi_t + TRANCE_S


def attuned(s, t):
    return s.att is not None and s.stacks > 0 and s.att_until > t


def further_ruin(s, t):
    return s.fr_until > t


def advance(s, fight, to):
    """Attunement and Further Ruin that lapse by `to`."""
    if s.att is not None and s.att_until <= to:
        if s.stacks: wasted(s, 1, s.stacks)
        s.att, s.stacks = None, 0
    if s.fr_until > -1.0 and s.fr_until <= to:
        wasted(s, 4); s.fr_until = -1.0


def recast_of(name):
    """The demi-summons are GCD spells: spell speed shortens their 60 s (57 s at a 2.31 s GCD)."""
    return CDS[name][0] * (SPEED if name == "Demi" else 1.0)


def charges(s, name, at):
    n, nxt = s.cds[name]
    if nxt is None or nxt > at: return n, nxt         # nothing comes back by `at` (most calls)
    rec, mx = recast_of(name), CDS[name][1]
    while n < mx and nxt is not None and nxt <= at:
        n += 1; nxt = nxt + rec if n < mx else None
    return n, nxt


def full_since(s, name, t):
    """When the cooldown last came back, if it is up at t (else None); up at the pull counts from 0."""
    n, nxt = s.cds[name]
    mx = CDS[name][1]
    if n == mx: return 0.0
    f = nxt + (mx - n - 1) * recast_of(name)
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
    rec, mx = recast_of(name), CDS[name][1]
    if n == mx:
        if name in CAPPED: s.lost += VALUE[CAPPED[name]] * max(at - max(full_since(s, name, at), 0.0), 0)
        nxt = at + rec
    s.cds[name] = (n - 1, nxt)


def cd_name(name):
    return "Demi" if name in DEMIS else "Enkindle" if name.startswith("Enkindle") else name


def ready(s, name, t):
    """When the cooldown next has a charge, from t."""
    n, nxt = charges(s, name, t)
    return t if n else nxt


# --- reach (as jobs/rdm.py) ----------------------------------------------------------------------------------------

def reach(s, fight, t, commit=True):
    """May a melee action land at t: no away window ([lo, hi] somewhere in which the player is out of reach for `need`
    seconds on end) is left without such a stretch."""
    W, i = fight.away, s.ai
    while i < len(W) and W[i].lo < t:
        w = W[i]
        if min(t, w.hi) - max(s.mlast, w.lo) >= w.need - 1e-9: i += 1; continue
        if w.hi - max(t, w.lo) >= w.need - 1e-9: break
        return False
    if commit: s.ai, s.mlast = i, t
    return True


def cyclone_lands(s, fight, t):
    """Crimson Cyclone lands the player beside Athena: not while a far spot holds them (before its snapshot, the middle
    of its stretch out of reach); after the snapshot it ends the stretch early (rdm.corps_lands)."""
    for i in range(s.ai, len(fight.away)):
        w = fight.away[i]
        if w.lo > t: break
        if t < w.hi:
            if t < (w.lo + w.hi) / 2 - 1e-9: return False
            s.ai, s.mlast = i + 1, t
    return True


_spans = {}


def plan_spans(fight):
    """[(lo, hi)] from the first cue to the last snapshot of each mechanic of our plan, as p12s.plan_spans, rebuilt from
    the fight's move windows (a plan run's `why` ends "(.. y; plan, ..)"): the plan holds a ranged player to its spots."""
    k = id(fight.moves)
    if k not in _spans:
        by = {}
        for w in fight.moves:
            if "; plan" in w.why: by.setdefault(w.why.split(":")[0], []).extend((w.lo, w.hi))
        _spans[k] = (fight.moves, sorted((min(v), max(v)) for v in by.values()))
    return _spans[k][1]


def cyclone_spot(s, fight, t):
    """Crimson Cyclone rushes the player to Athena: inside a mechanic of our plan only as a dash along a stretch of its
    run that goes straight to her (engine.dash_gain), which lands them where the plan sends them; anywhere else in it
    the dash would pull them off their spot."""
    return not any(lo <= t <= hi for lo, hi in plan_spans(fight)) or dash_gain(s, fight, t, "in") is not None


# --- actions -------------------------------------------------------------------------------------------------------

def cast_time(s, name, at):
    """Cast time and the instant it spends (Swiftcast)."""
    if name not in CAST: return 0.0, None
    if s.swift > at: return 0.0, "swift"
    return CAST[name] * SPEED, None


def recast(name):
    return FIXED[name] if name in FIXED else RECAST.get(name, BASE_GCD) * SPEED


def gcd_legal(s, name, at):
    if name == "Ruin III": return not in_trance(s, at)
    if name == "Ruin IV": return further_ruin(s, at)
    if name in ("Astral Impulse", "Fountain of Fire"):
        return in_trance(s, at) and TRANCE[s.demi][0] == name
    if name in DEMIS: return at >= 0 and name == s.nxt_demi and charges(s, "Demi", at)[0] >= 1
    if name in PRIMALS: return name in s.arc and not in_trance(s, at)
    if name in ("Ruby Rite", "Topaz Rite", "Emerald Rite"): return attuned(s, at) and RITE[s.att] == name
    if name == "Crimson Cyclone": return s.favor == "ifrit"
    if name == "Crimson Strike": return s.csr
    if name == "Slipstream": return s.favor == "garuda"
    return False


def mult(s, fight, at):
    m = fight.mult(at, s.pot_at)
    if s.sl_from <= at < s.sl_until: m *= SL_MULT
    return m


def hit(s, fight, at, potency, land, dot=False):
    """A hit executed (snapshotting buffs) at `at` and landing at `land`, counted if it lands on Athena in the window."""
    if 0 <= land < fight.until and fight.targetable(land):
        d = potency * mult(s, fight, at)
        s.dmg += d
        if dot: s.dotp += d


def pet(s, fight, land, potency):
    """A pet's hit: it takes the buffs up when it lands."""
    hit(s, fight, land, potency, land)


def end_favors(s):
    """A demi-summon or a primal ends the favors left (and Titan's)."""
    if s.favor or s.csr: wasted(s, 2)
    s.favor, s.csr = None, False
    if s.mb: wasted(s, 2)
    s.mb = False


def do_gcd(s, fight, name):
    """Cast a GCD as soon as possible; returns the new state or None when it cannot be cast."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start) or not fight.targetable(start): return None
    cast, used = cast_time(s, name, start)
    if s.first:
        s.first = False
        if cast: start = RESOLVE - cast             # the opener is pre-cast to resolve at 0:00
    if cast and stand(s, fight, start, start + cast - SLIDE) is None: return None
    if fight.next_down(start) <= start + max(cast - RESOLVE, 0) + DELAY.get(name, 0.0): return None
    if name in MELEE_ACTIONS and not reach(s, fight, start): return None
    if name == "Crimson Cyclone" and not (cyclone_spot(s, fight, start) and cyclone_lands(s, fight, start)): return None
    snap, free, nxt = gcd_times(start, cast, recast(name))
    if used == "swift": s.swift = -1.0
    saved = dash(s, fight, start, "in") if name == "Crimson Cyclone" else 0.0
    if name in POTENCY: hit(s, fight, snap, POTENCY[name], snap + DELAY[name])
    if name in DEMIS:
        use_cd(s, "Demi", start)
        if s.arc: wasted(s, 0, len(s.arc))
        end_favors(s)
        if s.stacks: wasted(s, 1, s.stacks)
        s.att, s.stacks, s.att_until = None, 0, -1.0
        s.demi, s.demi_t, s.enk = name, start, True
        s.nxt_demi = DEMIS[1 - DEMIS.index(name)]
        s.arc = frozenset(PRIMALS)
        for off in DEMI_HITS: pet(s, fight, start + off, PET[TRANCE[name][1]])
    elif name in PRIMALS:
        att, n, pet_hit, d = PRIMALS[name]
        if attuned(s, start): wasted(s, 1, s.stacks)
        end_favors(s)
        s.arc = s.arc - {name}
        s.att, s.stacks, s.att_until = att, n, start + ATT_S
        s.favor = {"ruby": "ifrit", "emerald": "garuda"}.get(att)
        pet(s, fight, start + d, PET[pet_hit])
    elif name in RITE.values():
        s.stacks -= 1
        if name == "Topaz Rite":
            if s.mb: wasted(s, 2)
            s.mb = True
    elif name == "Ruin IV": s.fr_until = -1.0
    elif name == "Crimson Cyclone": s.favor, s.csr = None, True
    elif name == "Crimson Strike": s.csr = False
    elif name == "Slipstream":
        s.favor = None
        land = snap + DELAY[name]
        for off in SLIP_TICKS: hit(s, fight, land + off, dot_tick(), land + off, dot=True)
    s.t, s.gcd = max(free, snap), nxt
    how = f"{cast:.2f}s cast" if cast else ("Swiftcast" if used == "swift" else "instant")
    s.log(start, name, gauge(s, how + (f" dash {saved:.2f}s" if saved else "")))
    return s


def gauge(s, how):
    t = s.t
    on = []
    if in_trance(s, t): on.append(f"{s.demi.split()[1]} {s.demi_t + TRANCE_S - t:.1f}s")
    if s.arc: on.append("arcanum " + "".join(sorted(p.split()[1][0] for p in s.arc)))
    if attuned(s, t): on.append(f"{s.att} {s.stacks}")
    if s.favor: on.append(f"{s.favor} favor")
    if s.csr: on.append("Strike ready")
    if s.mb: on.append("Titan's favor")
    if s.af: on.append(f"AF{s.af}")
    if further_ruin(s, t): on.append("FR")
    if s.sl_from <= t < s.sl_until: on.append("SL")
    if s.swift > t: on.append("Swift")
    return f"{how:<17} " + " ".join(on)


def ogcd_legal(s, name, at, fight, policy=True):
    if cd_name(name) in CDS:
        n, _ = charges(s, cd_name(name), at)
        if n < 1: return False
    if name in DAMAGE_OGCDS and (at < 0 or not fight.targetable(at)): return False
    if name in ("Enkindle Bahamut", "Enkindle Phoenix"):
        return demi_out(s, at) and s.enk and TRANCE[s.demi][2] == name
    if name == "Deathflare": return demi_out(s, at) and s.demi == "Summon Bahamut"
    if name == "Mountain Buster": return s.mb
    if name == "Fester": return s.af > 0
    if name == "Searing Light": return at >= 0
    if name == "Swiftcast": return not (policy and s.swift > at)
    if name == "Tincture": return fight.pot and s.pot_at is None
    return name in CDS


def do_ogcd(s, fight, name, policy=True):
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if cd_name(name) in CDS: use_cd(s, cd_name(name), at)
    if name in POTENCY: hit(s, fight, at, POTENCY[name], at + DELAY[name])
    if name in ("Enkindle Bahamut", "Enkindle Phoenix"):
        s.enk = False
        pet(s, fight, max(at + ENK_DELAY, s.demi_t + ENK_OUT), PET[TRANCE[s.demi][3]])
    elif name == "Mountain Buster": s.mb = False
    elif name == "Fester": s.af -= 1
    elif name == "Energy Drain":
        if s.af: wasted(s, 3, s.af)
        if further_ruin(s, at): wasted(s, 4)
        s.af, s.fr_until = 2, at + FR_S
    elif name == "Searing Light": s.sl_from, s.sl_until = at, at + SL_S
    elif name == "Swiftcast": s.swift = at + SWIFT_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.log(at, name, gauge(s, ""))
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next: in a trance only its Impulse / Fountain (anything else loses one); otherwise every
    legal GCD, but a primal only once the last one's Rites and favors are spent (the logs never summon over them but
    for a few deaths). The opener is a Ruin III pre-cast to land at the pull, as in every clear."""
    if c.first: return ["Ruin III"]
    if in_trance(c, now): return [TRANCE[c.demi][0]]
    busy = attuned(c, now) or c.favor or c.csr
    return [g for g in GCDS if gcd_legal(c, g, now) and not (g in PRIMALS and busy)]


def expand(s, fight):
    """Children: up to two oGCDs that fit before the next GCD, then a GCD; while Athena is away, a wait until she is
    back."""
    now = max(s.t, s.gcd)
    if not s.first and not fight.targetable(now):
        w = s.copy(); w.t = w.gcd = fight.back_up(now)
        w.log(s.t, "(boss away)")
        return [w]
    slots = int((s.gcd - s.t) / ANIM_LOCK + 1e-6) if not s.first else 0
    ready_ = [o for o in OGCD_ORDER if ogcd_legal(s, o, s.t, fight)] if slots else []
    out = []
    for k in range(0, min(slots, 2) + 1):
        for combo in itertools.combinations(ready_, k):
            c = s
            for o in combo:
                c = do_ogcd(c, fight, o)
                if c is None: break
            if c is None: continue
            now = max(c.t, c.gcd)
            any_gcd = False
            for g in candidates(c, fight, now):
                if "Swiftcast" in combo and g not in CAST: continue     # Swiftcast only right before a hard cast
                n = do_gcd(c, fight, g)
                if n is not None: out.append(n); any_gcd = True
            if not combo and not any_gcd:           # nothing lands before Athena leaves: wait for her return
                w = c.copy(); w.t = w.gcd = fight.back_up(fight.next_down(now)) if fight.next_down(now) < now + 5 else now + 0.5
                w.log(c.t, "(wait)"); out.append(w)
    return out


# What holding a resource is worth: what it converts into less RATE times the GCD time it takes, at Ruin III's rate (the
# filler: 310 over a 2.45 s GCD, ~127 a second), so spending it leaves the rank where it was (jobs/vpr.py). An Arcanum
# its primal: the summon's 600 and its Rites and favor actions over their GCDs (Titan ~960 with the Mountain Busters,
# Ifrit ~800, Garuda ~620); an attunement stack its Rite over its GCD (Ruby ~140, Topaz ~170 with its Mountain Buster,
# Emerald ~40 on its 1.5 s); Ifrit's Favor Crimson Cyclone and Strike over two GCDs (~360), Crimson Strike Ready one
# (~120); Garuda's Favor Slipstream and its windstorm over 3.5 s (~175); Titan's Favor a Mountain Buster; an Aetherflow
# stack a Fester; Further Ruin Ruin IV over Ruin III; Enkindle and Deathflare their hits (oGCDs); a second of Searing
# Light 5% of the burst's rate; Swiftcast a hard cast made while moving.
VALUE = dict(arc_titan=960, arc_ifrit=800, arc_garuda=620, ruby=140, topaz=170, emerald=40, ifrit=360, csr=120,
             garuda=175, mb=150, af=340, fr=120, enk=1030, df=500, sl=12, swift=30,
             cap_demi=80, cap_ed=17, cap_sl=3)
ARC = {"Summon Titan II": "arc_titan", "Summon Ifrit II": "arc_ifrit", "Summon Garuda II": "arc_garuda"}
# A cooldown sitting ready loses what its recast would bring (pct.py's CAPPED, at its share a second): a demi-summon
# ~4,800 over 60 s (its trance, pets, Enkindle and three Arcanum over Ruin III), Energy Drain ~1,000, Searing Light ~300
# over 120 s
CAPPED = {"Demi": "cap_demi", "Energy Drain": "cap_ed", "Searing Light": "cap_sl"}
CAP_W = 1.0
RATE = 130                                            # potency per second, to compare states at slightly different times
# tune.py --job smn (2026-10-22, 36 settings, R1 whole phase): values at 0.10-0.15 of these at rates 115-150 all come
# within 0.07%; at 0.5-0.7 the beam holds Arcanum and attunement (-0.3% to -0.6%), at 1.0 it drifts on the filler until
# the next demi-summon wipes them (-5.5%). R2 the same.
HEURISTICS = [(135, 0.15, 0.0), (125, 0.15, 0.0), (125, 0.1, 0.0), (130, 0.15, 0.0)]
WIDTH = 1000                                          # the beam (--layers gcd): 93.2k at 1,000, 94.3k at 3,000 (63 s)
SWEEP_WIDTH = 1000                                    # engine.sweep: 500-4,000 within 0.3% (17 s at 1,000), level with the
                                                      # beam at 3,000
MOVE_WEIGHT = 0.0
END_TAPER = 15.0                                      # held resources fade over the window's last seconds
FAR = True                                            # p12s.fight: out of reach at the plan's far spots (Crimson Strike)


def held(s, fight=None):
    """What the held resources are worth (VALUE); an Arcanum only while no demi-summon would come before it is used."""
    t = s.t
    v = sum(VALUE[ARC[p]] for p in s.arc)
    if attuned(s, t): v += VALUE[s.att] * s.stacks
    if s.favor: v += VALUE[s.favor]
    v += VALUE["csr"] * s.csr + VALUE["mb"] * s.mb + VALUE["af"] * s.af + VALUE["fr"] * further_ruin(s, t)
    if demi_out(s, t) or in_trance(s, t):
        v += VALUE["enk"] * s.enk
        if s.demi == "Summon Bahamut" and charges(s, "Deathflare", t)[0]: v += VALUE["df"]
    v += VALUE["sl"] * max(s.sl_until - max(t, s.sl_from), 0) + VALUE["swift"] * (s.swift > t)
    return v


def score(s):
    return s.dmg


def rank(s, fight):
    return score(s) + held(s, fight) * min(1.0, max(fight.until - s.t, 0) / END_TAPER) - CAP_W * capped(s, s.t) - RATE * s.t


def final(s, fight):
    return score(s) + (held(s, fight) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Summoner", "2024-11-12"      # 7.1: Crimson Strike Ready; nothing at level 90 changed since
OGCDS = set(OGCD_ORDER)
REFERENCE = ("Fester", 340)


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


STATUSES = {"Further Ruin": lambda s, t: s.fr_until > t, "Searing Light": lambda s, t: s.sl_from <= t < s.sl_until,
            "Swiftcast": lambda s, t: s.swift > t, "Aetherflow": lambda s, t: s.af > 0,
            "Ifrit's Favor": lambda s, t: s.favor == "ifrit", "Garuda's Favor": lambda s, t: s.favor == "garuda",
            "Crimson Strike Ready": lambda s, t: bool(s.csr), "Titan's Favor": lambda s, t: bool(s.mb)}


def status(s, t):
    return dict(demi=s.demi if in_trance(s, t) else None, arc=sorted(s.arc), att=s.att if attuned(s, t) else None,
                stacks=s.stacks if attuned(s, t) else 0, favor=s.favor, csr=s.csr, mb=s.mb, af=s.af,
                fr=further_ruin(s, t))


def force(s, fight, name, start):
    """Cast it anyway, with what it needs granted (the replay carries on after an illegal cast)."""
    s = s.copy()
    if name in ("Astral Impulse", "Fountain of Fire"):
        s.demi = DEMIS[0] if name == "Astral Impulse" else DEMIS[1]; s.demi_t = max(s.demi_t, start - TRANCE_S + 0.1)
    if name in DEMIS: s.nxt_demi, s.cds["Demi"] = name, (1, None)
    if name in PRIMALS: s.arc = s.arc | {name}; s.demi_t = min(s.demi_t, start - TRANCE_S)
    if name in RITE.values():
        s.att = next(k for k, v in RITE.items() if v == name); s.stacks, s.att_until = max(s.stacks, 1), max(s.att_until, start + 1)
    if name == "Crimson Cyclone": s.favor = "ifrit"
    if name == "Crimson Strike": s.csr = True
    if name == "Slipstream": s.favor = "garuda"
    if name == "Ruin IV": s.fr_until = start + 1
    if name == "Ruin III": s.demi_t = min(s.demi_t, start - TRANCE_S)
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    if cd_name(name) in CDS: s.cds[cd_name(name)] = (1, None)
    if name in ("Enkindle Bahamut", "Enkindle Phoenix", "Deathflare"):
        s.demi = DEMIS[0] if name != "Enkindle Phoenix" else DEMIS[1]; s.enk = True
        if not demi_out(s, t): s.demi_t = t - 1.0
    if name == "Mountain Buster": s.mb = True
    if name == "Fester": s.af = max(s.af, 1)
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` cast at t from state s."""
    if name not in POTENCY: return None
    return "", POTENCY[name]


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own: Searing Light's 5% (status 1002703 on the
    hit). FFLogs counts every damage-up on the hit, so dividing it out takes this away too."""
    return SL_MULT if "1002703." in (h.get("buffs") or "") else 1.0
