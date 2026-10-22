"""Bard at level 90, Dawntrail patch 7.0 and later (no single-target change at level 90 since), single target.

Rules follow the official job guide (na.finalfantasyxiv.com/jobguide/bard) and the patch notes since 7.0
(patchnotes.py): 7.2-7.3 only touched AoE potencies and actions above level 90 (Resonant Arrow 96, Radiant Encore 100).
Both show level-100 values. Ranged Mastery (level 94) raises Empyreal Arrow to 260, Sidewinder to 400, Refulgent Arrow
to 280, Burst Shot to 220 and Apex Arrow to 140-700, so those five are lower at level 90 by an amount the guide doesn't
give; Heartbreak Shot (92) is still Bloodletter. Those, the DoT ticks, auto-attacks and hit delays were measured in
the logs (2026-10-22, scratch/brd): no benchmark clear has a Bard, so our groups' 62 clean pulls by four Bards.

Every action is instant and reaches 25 y, so the strategy's running costs a Bard nothing: only the boss's downtime.

Songs (45 s each, 120 s recast, singing one ends the one before; only in combat): while one plays, every server tick
(3 s) on which Caustic Bite or Stormbite is on the boss grants Repertoire with an 80% chance, and Empyreal Arrow grants
one surely. The search counts the expected 0.8 per tick (as Monk's chakra counts the expected crits):
  - the Wanderer's Minuet: stacks (up to 3) for Pitch Perfect, 100 / 220 / 360; lost when the song ends;
  - Mage's Ballad: each takes 7.5 s off Bloodletter's recast (three charges of 15 s);
  - Army's Paeon: stacks (up to 4), each 4% off the GCD and the auto-attack delay. Singing the Minuet or the Ballad
    over it (or within 30 s of it running out: Army's Ethos) grants Army's Muse for 10 s, 1 / 2 / 4 / 12% by stacks.
Each Repertoire also adds 5 Soul Voice: Apex Arrow spends it all (20 at least), and at 80 or more grants Blast Arrow.
Each song sung adds its Coda; Radiant Finale spends them for 20 s of +2% damage a Coda.

Hawk's Eye: Burst Shot, Caustic Bite, Stormbite and Iron Jaws grant it with a 35% chance, for a Refulgent Arrow. Also
random, so the search adds its expected worth to those four (a proc turns the next Burst Shot into a Refulgent Arrow,
which can't proc itself: HAWK_EV) and only fires Refulgent Arrow under Barrage (three hits); a replay of a log fires it
whenever the log does.

Self-buffs: Raging Strikes +15%, Radiant Finale, Mage's Ballad +1%; Battle Voice (+20% direct hit), the Minuet (+2%
crit) and the Paeon (+3% direct hit) at their expected worth for typical rates. dps.py's crit/direct-hit gain is
measured on hits under none of those, so they aren't counted twice in a ceiling. A replay against logged damage
(dps.py's check) does count them twice, about 2%.

DoTs snapshot buffs when they land and tick on the server's 3 s tick (TICK_PHASE); their damage is counted when applied,
and a refresh (Iron Jaws, or the bite again) loses the ticks the old one still had.
"""
import itertools, math
from engine import ANIM_LOCK, BASE_GCD, settle

# Burst Shot, Refulgent Arrow, Empyreal Arrow, Sidewinder and Apex Arrow from the logs (plain hits scaled to Bloodletter:
# 199 / 260 / 241 / 318 / 5 a Soul Voice), below Ranged Mastery's level-94 values (220 / 280 / 260 / 400 / 140-700);
# the others are the guide's, untouched by traits (the logs agree within 1%).
POTENCY = {"Burst Shot": 200, "Refulgent Arrow": 260, "Caustic Bite": 150, "Stormbite": 100, "Iron Jaws": 100,
           "Blast Arrow": 700, "Empyreal Arrow": 240, "Sidewinder": 320, "Bloodletter": 130,
           "Shadowbite": 200, "Ladonsbite": 140, "Rain of Death": 100}       # AoE: only in replays
APEX = 5.0                                      # Apex Arrow potency per Soul Voice (logs: ~400 at 80, ~500 at 100)
BARRAGE_HITS = 3
PP = (0, 100, 220, 360)                         # Pitch Perfect by Repertoire stacks (in between: interpolated)
DOT = {"Caustic Bite": 25, "Stormbite": 31}     # tick potency in the logs: 1.25x the tooltip's 20 / 25, as BLM's Thunder III
DOT_S = 45.0
HAWK, REPERTOIRE = 0.35, 0.80                   # chances: Hawk's Eye per proc-granting GCD, Repertoire per server tick
HAWK_GCDS = {"Burst Shot", "Caustic Bite", "Stormbite", "Iron Jaws"}
HAWK_EV = HAWK * (POTENCY["Refulgent Arrow"] - POTENCY["Burst Shot"]) / (1 + HAWK)
# auto-attacks: 68 potency (logs, scaled to Bloodletter) every 3.07 s; Army's Paeon / Muse shorten the delay
AUTO, AUTO_DELAY = 68, 3.07
# seconds from executing an action to its damage landing, the logs' medians; buffs snapshot on execution
DELAY = {"Burst Shot": 1.47, "Refulgent Arrow": 1.47, "Caustic Bite": 1.29, "Stormbite": 1.29, "Iron Jaws": 0.62,
         "Apex Arrow": 1.07, "Blast Arrow": 1.65, "Empyreal Arrow": 1.03, "Sidewinder": 0.53, "Bloodletter": 1.60,
         "Rain of Death": 1.65, "Pitch Perfect": 0.80}
TICK_PHASE = 1.5                                # server ticks land at TICK_PHASE + 3k seconds
SONG_S, ETHOS_S, MUSE_S, BUFF_S, BARRAGE_S, BLAST_S = 45, 30, 10, 20, 10, 10
SV_PER = 5
AP_HASTE = 0.04
MUSE = (0.0, 0.01, 0.02, 0.04, 0.12)            # Army's Muse by the Paeon's stacks
RAGING, BALLAD = 1.15, 1.01
# typical rates at this gear level (as in solve.py) for the worth of the Bard's own crit and direct-hit buffs
CRIT_RATE, CRIT_DMG, DH_RATE = 0.25, 1.60, 0.36
MINUET = 1 + 0.02 * (CRIT_DMG - 1) / (1 + CRIT_RATE * (CRIT_DMG - 1))
PAEON = 1 + 0.03 * 0.25 / (1 + DH_RATE * 0.25)
VOICE = 1 + 0.20 * 0.25 / (1 + DH_RATE * 0.25)
SONGS = {"The Wanderer's Minuet": "WM", "Mage's Ballad": "MB", "Army's Paeon": "AP"}
ALIAS = {"the Wanderer's Minuet": "The Wanderer's Minuet"}      # the logs spell it with a capital T
CODA = {"WM": 1, "MB": 2, "AP": 4}
SWITCH = 15.0                                   # the search may sing over a song with less than this left
CDS = {"The Wanderer's Minuet": (120, 1), "Mage's Ballad": (120, 1), "Army's Paeon": (120, 1),
       "Raging Strikes": (120, 1), "Battle Voice": (120, 1), "Radiant Finale": (110, 1), "Barrage": (120, 1),
       "Empyreal Arrow": (15, 1), "Sidewinder": (60, 1), "Bloodletter": (15, 3), "Pitch Perfect": (1, 1),
       "Tincture": (270, 1)}
GCDS = ["Burst Shot", "Refulgent Arrow", "Caustic Bite", "Stormbite", "Iron Jaws", "Apex Arrow", "Blast Arrow",
        "Shadowbite", "Ladonsbite"]
OGCD_ORDER = ["Tincture", "The Wanderer's Minuet", "Mage's Ballad", "Army's Paeon", "Raging Strikes", "Battle Voice",
              "Radiant Finale", "Barrage", "Empyreal Arrow", "Sidewinder", "Pitch Perfect", "Bloodletter"]
SPEED = 0.996                                   # skill speed factor: a 2.49 s GCD (our Bards: 2.45-2.50)
HASTE_STATUSES = ("Army's Paeon", "Army's Muse")    # calibrate.gcd_of leaves GCDs under these out
LOG = False                                     # a replay of a log: Refulgent Arrow whenever the log fires it


class State:
    __slots__ = ("t", "gcd", "song", "song_until", "rep", "sv", "coda", "ethos", "ethos_until", "muse", "muse_until",
                 "rs_until", "bv_until", "rf_until", "rf", "barrage_until", "blast_until", "caustic", "storm", "cds",
                 "auto_next", "tick_next", "dmg", "dotp", "waste", "pot_at", "first", "hist", "mvi", "acc", "free", "spot")

    @classmethod
    def initial(cls, fight):
        s = cls()
        s.t = s.gcd = 0.0
        s.song, s.song_until, s.rep, s.sv, s.coda = None, -1.0, 0.0, 0.0, 0
        s.ethos, s.ethos_until, s.muse, s.muse_until = 0.0, -1.0, 0.0, -1.0
        s.rs_until = s.bv_until = s.rf_until = s.barrage_until = s.blast_until = -1.0
        s.rf = 1.0
        s.caustic = s.storm = None                  # (when it landed, the multiplier it snapshot)
        s.cds = {k: (n, None) for k, (_, n) in CDS.items()}
        s.auto_next, s.tick_next = 0.0, TICK_PHASE
        s.dmg, s.dotp, s.pot_at, s.first, s.hist = 0.0, 0.0, None, True, None
        s.waste = (0.0, 0.0, 0.0)
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
        dot = lambda d: round(max(d[0] + DOT_S - self.t, 0)) if d else None
        return (r(self.t), r(self.gcd), self.song if self.song_until > self.t else None, left(self.song_until),
                round(self.rep * 5) / 5, round(self.sv / 5), self.coda, round(self.ethos * 5) / 5 if self.ethos_until > self.t else 0,
                left(self.muse_until), left(self.rs_until), left(self.bv_until), left(self.rf_until),
                left(self.barrage_until), left(self.blast_until), dot(self.caustic), dot(self.storm), self.pot_at is None,
                tuple((n, r(x) if x is not None else None) for n, x in self.cds.values()))

    def log(self, t, action, note=""):
        self.hist = (self.hist, (round(t, 2), action, note))

    def history(self):
        out, h = [], self.hist
        while h: h, e = h; out.append(e)
        return out[::-1]


WASTE = ("Repertoire overcapped", "Soul Voice overcapped", "Pitch Perfect stacks dropped")


def wasted(s, i, n=1):
    w = list(s.waste); w[i] += n; s.waste = tuple(w)


# --- time passing --------------------------------------------------------------------------------------------------

def singing(s, t, song=None):
    return s.song is not None and s.song_until > t and (song is None or s.song == song)


def mult(s, fight, at):
    """Damage multiplier on a hit executed at `at`: raid buffs, tincture, own Raging Strikes, Radiant Finale, songs and
    Battle Voice (the last three at their expected worth)."""
    m = fight.mult(at, s.pot_at) * (RAGING if s.rs_until > at else 1) * (s.rf if s.rf_until > at else 1)
    m *= VOICE if s.bv_until > at else 1
    if singing(s, at): m *= {"WM": MINUET, "MB": BALLAD, "AP": PAEON}[s.song]
    return m


def haste(s, t):
    if singing(s, t, "AP"): return AP_HASTE * min(s.rep, 4)
    if s.muse_until > t: return s.muse
    return 0.0


def dot_on(d, t):
    return d is not None and d[0] < t <= d[0] + DOT_S


def end_song(s, at):
    """The song runs out: the Paeon's stacks become Army's Ethos, the Minuet's are lost."""
    if s.song == "AP" and s.rep > 0: s.ethos, s.ethos_until = s.rep, at + ETHOS_S
    if s.song == "WM" and s.rep > 0: wasted(s, 2, s.rep)
    s.song, s.song_until, s.rep = None, -1.0, 0.0


def repertoire(s, at, n):
    """n Repertoire (an expected 0.8 from a tick, 1 from Empyreal Arrow) under the current song."""
    v = s.sv + SV_PER * n
    if v > 100: wasted(s, 1, v - 100)
    s.sv = min(100.0, v)
    if s.song == "MB":
        k, nxt = charges(s, "Bloodletter", at)
        if nxt is None: wasted(s, 0, n); return     # all three charges up: the cut is lost
        s.cds["Bloodletter"] = (k, nxt - 7.5 * n)
        s.cds["Bloodletter"] = charges(s, "Bloodletter", at)
    else:
        cap = 3 if s.song == "WM" else 4
        if s.rep + n > cap: wasted(s, 0, s.rep + n - cap)
        s.rep = min(cap, s.rep + n)


def advance(s, fight, to):
    """Up to `to`, in time order: songs running out, auto-attacks, and the server ticks on which the DoTs grant
    Repertoire."""
    while True:
        e = s.song_until if s.song is not None else math.inf
        a, k = s.auto_next, s.tick_next
        nxt = min(e, a, k)
        if nxt > to: break
        if e == nxt: end_song(s, e)
        elif k == nxt:
            if singing(s, k) and fight.targetable(k) and k < fight.until and (dot_on(s.caustic, k) or dot_on(s.storm, k)):
                repertoire(s, k, REPERTOIRE)
            s.tick_next = k + 3.0
        else:
            if 0 <= a + 0.5 < fight.until and fight.targetable(a): s.dmg += AUTO * mult(s, fight, a)
            s.auto_next = a + AUTO_DELAY * (1 - haste(s, a))


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
    """The recast an action runs on (Rain of Death shares Bloodletter's)."""
    name = ALIAS.get(name, name)
    return "Bloodletter" if name == "Rain of Death" else name


def hit(s, fight, at, potency, name):
    land = at + DELAY.get(name, 0.6)
    if 0 <= land < fight.until and fight.targetable(land): s.dmg += potency * mult(s, fight, at)


def ticks(fight, a, b):
    """Server ticks in (a, b] inside the window while the boss can be hit."""
    k = math.floor((a - TICK_PHASE) / 3) + 1
    n = 0
    while TICK_PHASE + 3 * k <= b:
        t = TICK_PHASE + 3 * k
        if 0 <= t < fight.until and fight.targetable(t): n += 1
        k += 1
    return n


def apply_dot(s, fight, name, land, m):
    """Put the DoT on the boss at `land` with multiplier m, replacing the old one (its remaining ticks are lost)."""
    attr = "caustic" if name == "Caustic Bite" else "storm"
    cur = getattr(s, attr)
    if cur and cur[0] + DOT_S > land:
        lost = ticks(fight, land, cur[0] + DOT_S) * DOT[name] * cur[1]
        s.dmg -= lost; s.dotp -= lost
    gain = ticks(fight, land, land + DOT_S) * DOT[name] * m
    s.dmg += gain; s.dotp += gain
    setattr(s, attr, (land, m))


def pitch(rep):
    i = min(int(rep), 2)
    return PP[i] + (PP[i + 1] - PP[i]) * (min(rep, 3) - i)


# --- actions -------------------------------------------------------------------------------------------------------

def gcd_legal(s, name, at):
    if name in ("Refulgent Arrow", "Shadowbite"): return LOG or s.barrage_until > at
    if name == "Apex Arrow": return s.sv >= 20 - 1e-6
    if name == "Blast Arrow": return s.blast_until > at
    return True


def potency(s, fight, name, at):
    if name == "Refulgent Arrow": return POTENCY[name] * (BARRAGE_HITS if s.barrage_until > at else 1)
    if name == "Shadowbite" and s.barrage_until > at: return 300
    if name == "Apex Arrow": return APEX * s.sv
    return POTENCY[name] + (HAWK_EV if name in HAWK_GCDS and not LOG else 0)


def do_gcd(s, fight, name):
    """Execute a GCD as soon as possible; returns the new state or None when it cannot be."""
    s = s.copy()
    start = max(s.t, s.gcd)
    advance(s, fight, start)
    settle(s, fight, start)
    if not gcd_legal(s, name, start): return None
    if not fight.targetable(start): return None
    s.first = False
    recast = BASE_GCD * SPEED * (1 - haste(s, start))
    snap = start
    m = mult(s, fight, snap)
    hit(s, fight, snap, potency(s, fight, name, snap), name)
    land = snap + DELAY.get(name, 0.6)
    if name in ("Refulgent Arrow", "Shadowbite"):
        if s.barrage_until > snap: s.barrage_until = -1.0
    elif name in DOT: apply_dot(s, fight, name, land, m)
    elif name == "Iron Jaws":
        for d, attr in (("Caustic Bite", "caustic"), ("Stormbite", "storm")):
            cur = getattr(s, attr)
            if cur and cur[0] + DOT_S > land: apply_dot(s, fight, d, land, m)
    elif name == "Apex Arrow":
        if s.sv >= 80 - 1e-6: s.blast_until = snap + BLAST_S
        s.sv = 0.0
    elif name == "Blast Arrow": s.blast_until = -1.0
    s.t, s.gcd = start + ANIM_LOCK, start + recast
    s.log(start, name, gauge(s, ""))
    return s


def gauge(s, how):
    left = lambda d: f"{max(d[0] + DOT_S - s.t, 0):4.1f}" if d else "  - "
    song = f"{s.song} {max(s.song_until - s.t, 0):4.1f}s rep {s.rep:3.1f}" if singing(s, s.t) else "-" + " " * 18
    return (f"{how:<4}{song}  SV {s.sv:5.1f}  coda {bin(s.coda).count('1')}  dots {left(s.caustic)} {left(s.storm)}"
            + (f"  haste {haste(s, s.t):.0%}" if haste(s, s.t) else ""))


def sing(s, name, at):
    """A new song over the old one: the Paeon's stacks (or Army's Ethos) give Army's Muse to the Minuet or Ballad."""
    new = SONGS[name]
    stacks = 0.0
    if singing(s, at, "AP"): stacks = s.rep
    elif s.ethos_until > at: stacks = s.ethos
    if singing(s, at, "WM") and s.rep > 0: wasted(s, 2, s.rep)
    if new != "AP" and stacks > 0:
        i = min(int(stacks), 3)
        s.muse, s.muse_until = MUSE[i] + (MUSE[i + 1] - MUSE[i]) * (min(stacks, 4) - i), at + MUSE_S
    s.ethos, s.ethos_until = 0.0, -1.0
    s.song, s.song_until, s.rep = new, at + SONG_S, 0.0
    s.coda |= CODA[new]


def ogcd_legal(s, name, at, fight, policy=True):
    name = ALIAS.get(name, name)
    if cd_name(name) not in CDS: return False
    if charges(s, cd_name(name), at)[0] < 1: return False
    if name in SONGS:
        if at < 0 or s.first: return False
        return not policy or not singing(s, at) or (s.song_until - at < SWITCH and s.song != SONGS[name])
    if name == "Pitch Perfect":
        if not singing(s, at, "WM") or s.rep < 1e-6: return False
        # the search: at three stacks, or the last stacks before the song (or the window) ends or the boss goes away
        return not policy or s.rep >= 3 - 1e-6 or min(s.song_until, fight.next_down(at), fight.until) - at < 4
    if name == "Radiant Finale": return s.coda > 0 and not (policy and s.first)
    if name == "Tincture": return fight.pot and s.pot_at is None
    return not (policy and s.first)               # the search opens with a GCD


def do_ogcd(s, fight, name, policy=True):
    name = ALIAS.get(name, name)
    s = s.copy()
    at = s.t
    advance(s, fight, at)
    settle(s, fight, at)
    if not ogcd_legal(s, name, at, fight, policy): return None
    if name in POTENCY or name == "Pitch Perfect":
        if not fight.targetable(at): return None
    use_cd(s, cd_name(name), at)
    if name in SONGS: sing(s, name, at)
    elif name == "Pitch Perfect": hit(s, fight, at, pitch(s.rep), name); s.rep = 0.0
    elif name == "Empyreal Arrow":
        hit(s, fight, at, POTENCY[name], name)
        if singing(s, at): repertoire(s, at, 1.0)
    elif name in ("Sidewinder", "Bloodletter", "Rain of Death"): hit(s, fight, at, POTENCY[name], name)
    elif name == "Raging Strikes": s.rs_until = at + BUFF_S
    elif name == "Battle Voice": s.bv_until = at + BUFF_S
    elif name == "Radiant Finale":
        s.rf, s.rf_until, s.coda = 1 + 0.02 * bin(s.coda).count("1"), at + BUFF_S, 0
    elif name == "Barrage": s.barrage_until = at + BARRAGE_S
    elif name == "Tincture": s.pot_at = at
    s.t = at + ANIM_LOCK
    s.log(at, name, gauge(s, ""))
    return s


def candidates(c, fight, now):
    """The GCDs worth trying next: Burst Shot; Refulgent Arrow under Barrage; a bite that is off or about to fall off;
    Iron Jaws when one is about to, or when the buffs on now beat the ones the DoTs snapshot; Apex Arrow at 80 Soul
    Voice (or before the boss goes away or the window ends); Blast Arrow."""
    out = ["Burst Shot"]
    if c.barrage_until > now: out.append("Refulgent Arrow")
    left = {d: (x[0] + DOT_S - now if x else -1) for d, x in (("Caustic Bite", c.caustic), ("Stormbite", c.storm))}
    out += [d for d, v in left.items() if v < 3]
    up = [x for x in (c.caustic, c.storm) if x and x[0] + DOT_S > now + 0.6]
    if up and (min(left[d] for d in left if left[d] > 0) < 6 or mult(c, fight, now) > 1.05 * min(x[1] for x in up)):
        out.append("Iron Jaws")
    if c.sv >= 80 - 1e-6 or (c.sv >= 20 and min(fight.next_down(now), fight.until) - now < 10): out.append("Apex Arrow")
    if c.blast_until > now: out.append("Blast Arrow")
    return out


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
            any_gcd = False
            for g in candidates(c, fight, now):
                if "Barrage" in combo and g != "Refulgent Arrow": continue      # Barrage only right before its arrow
                n = do_gcd(c, fight, g)
                if n is None: continue
                any_gcd = True
                out.append(n)
            down = not fight.targetable(now)
            if not combo and (not any_gcd or down):
                # boss away: to when it is back, or a GCD's length at a time (a song may want singing meanwhile)
                back = fight.back_up(now)
                for to in ({back} | ({now + 2.5} if now + 2.5 < back - 0.5 else set())) if down else {now + 0.5}:
                    w = c.copy(); w.t = w.gcd = to
                    w.log(c.t, "(boss away)" if down else "(wait)"); out.append(w)
    return out


# what holding a resource is worth over the GCDs it displaces: a Minuet stack a third of a Pitch Perfect; a Ballad
# stack 7.5 s of Bloodletter; a Paeon stack (or Ethos) its haste; Soul Voice its share of Apex and Blast Arrow over two
# Burst Shots; a Coda 2% of 20 s; Barrage two more Refulgent Arrows; Blast Arrow Ready its arrow over a Burst Shot.
VALUE = dict(wm=120, mb=65, ap=30, sv=6, coda=80, barrage=520, blast=480)
RATE = 200                                            # potency per second, to compare states at slightly different times
# tune.py (2026-10-22, sweep): (200, 1.0) stays the best over the phase; values at 0.8-0.95 come close
HEURISTICS = [(200, 1.0, 0.0), (220, 0.9, 0.0), (265, 0.95, 0.0), (225, 0.8, 0.0)]
WIDTH = 3000
SWEEP_WIDTH = 6000                                    # engine.sweep (layers by time), against the beam at WIDTH, taking no longer: +0.42%
MOVE_WEIGHT = 0.0


def held(s):
    t = s.t
    v = VALUE["sv"] * s.sv + VALUE["coda"] * bin(s.coda).count("1")
    if singing(s, t): v += VALUE[s.song.lower()] * s.rep
    if s.ethos_until > t: v += VALUE["ap"] * s.ethos
    v += VALUE["barrage"] * (s.barrage_until > t) + VALUE["blast"] * (s.blast_until > t)
    return v


def rank(s, fight):
    return s.dmg + held(s) - RATE * s.t


def final(s, fight):
    s = s.copy(); advance(s, fight, fight.until)          # the shots still to come before the window ends
    return s.dmg + (held(s) if fight.carry else 0)


# --- calibration hooks (calibrate.py) -------------------------------------------------------------------------------
LOG_NAME, LOGS_SINCE = "Bard", "2024-07-02"         # Dawntrail: no single-target change at level 90 since 7.0
OGCDS = set(OGCD_ORDER) | set(ALIAS) | {"Rain of Death"}
REFERENCE = ("Bloodletter", 130)                    # no trait touches it (Heartbreak Shot replaces it at 92)
CAST = {}


def cast_time(s, name, at):
    return 0.0, None


def prepare(p):
    """A replay of log p fires Refulgent Arrow whenever the log does (its own Hawk's Eye procs) and so counts no
    expected procs."""
    global LOG
    LOG = True


def at(s, fight, t):
    c = s.copy(); advance(c, fight, t)
    return c


def status(s, t):
    return dict(song=s.song if singing(s, t) else None, rep=round(s.rep, 2), sv=round(s.sv), coda=bin(s.coda).count("1"),
                barrage=s.barrage_until > t, blast=s.blast_until > t)


def force(s, fight, name, start):
    """Use it anyway, with what it needs granted (the replay carries on after an illegal action)."""
    s = s.copy()
    if name == "Apex Arrow": s.sv = max(s.sv, 20)
    if name == "Blast Arrow": s.blast_until = start + 1
    return do_gcd(s, fight, name) or s


def force_ogcd(s, fight, name, t):
    s = s.copy()
    name = ALIAS.get(name, name)
    if name == "Pitch Perfect" and singing(s, t, "WM"): s.rep = max(s.rep, 1)
    if name == "Radiant Finale": s.coda = s.coda or 1
    if cd_name(name) in CDS:                        # one charge, the recharge still running (Bloodletter has three)
        rec, mx = CDS[cd_name(name)]
        s.cds[cd_name(name)] = (1, charges(s, cd_name(name), t)[1] or (None if mx == 1 else t + rec))
    return do_ogcd(s, fight, name, policy=False) or s


def label(s, fight, name, t):
    """(group, model potency) for a logged hit of `name` used at t from state s. Barrage's Refulgent Arrow logs three
    hits of the plain potency."""
    if name == "Refulgent Arrow": return ("barrage" if s.barrage_until > t else ""), POTENCY[name]
    if name == "Pitch Perfect": return f"{s.rep:.0f} stacks", pitch(s.rep)
    if name == "Apex Arrow": return f"{round(s.sv, -1):.0f} SV", APEX * s.sv
    if name in ("Raging Strikes", "Battle Voice", "Radiant Finale", "Barrage", "Tincture") or name in SONGS: return None
    if name in POTENCY: return "", POTENCY[name]
    return None


def cast_label(s, name, t):
    return ""


def own_factor(p, h):
    """The part of a logged hit's FFLogs multiplier that is the player's own (Raging Strikes, their Radiant Finale and
    Mage's Ballad): FFLogs counts every damage-up on the hit, so dividing it out takes these away too. Status ids from
    the logs: Raging Strikes 125, Mage's Ballad 2217, Radiant Finale 2964 (its other status, 2722, is never on a hit)."""
    b = h.get("buffs") or ""
    m = RAGING if "1000125." in b else 1.0
    n = p["names"]
    own = [(x["t"], ALIAS.get(n[str(x["abilityGameID"])], n[str(x["abilityGameID"])])) for x in p["casts"] if x["type"] == "cast"]
    if "1002217." in b and any(a == "Mage's Ballad" and 0 <= h["t"] - t < SONG_S + 1 for t, a in own): m *= BALLAD
    if "1002964." in b:
        rf = [t for t, a in own if a == "Radiant Finale" and 0 <= h["t"] - t < BUFF_S + 1]
        if rf:                                      # the Coda: distinct songs sung since the Radiant Finale before
            before = max((t for t, a in own if a == "Radiant Finale" and t < rf[-1]), default=-math.inf)
            m *= 1 + 0.02 * len({a for t, a in own if a in SONGS and before < t < rf[-1]})
    return m
