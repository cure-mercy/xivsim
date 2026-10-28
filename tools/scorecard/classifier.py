"""P12S P1 mistake classifier.

Finds every Damage Down and lethal hit in a pull, then attributes it using the party strategy
from xivsim's briefs.html (Paradeigma I light-party baits, Paradeigma II quadrant sweep,
Superchain I laser groups / pairs / towers, Paradeigma III platforms) and the tank swap and shares
the logs show (Glaukopis, Dialogos). Which rules judge a mechanic depends on the raid day (RULEBOOK).
Anything the rules cannot explain falls back to "avoidable AoE -> victim" or stays unattributed.
"""
import collections, itertools, json, math

TANK_JOBS = {"Paladin", "Warrior", "DarkKnight", "Gunbreaker"}
HEALER_JOBS = {"WhiteMage", "Scholar", "Astrologian", "Sage"}
SUPPORT_JOBS = TANK_JOBS | HEALER_JOBS
AVOIDABLE = {  # standing in it is the victim's own mistake
    "Trinity of Souls": "stood on the cleaved side (Trinity of Souls)",
    "Ray of Light": "stood in a Ray of Light column",
    "Superchain Burst": "stood in a green orb point-blank",
    "Superchain Coil": "stood in a donut",
    "Clear Cut": "stood in a Clear Cut cone",
    "Unnatural Enchainment": "stood on a destroyed tile",
    "Sample": "stood on a destroyed tile as its platform fell (Sample)",
    "Palladian Ray": "stood in a Palladion puddle",
}
STUNG_S = 1.0   # a death this soon after an avoidable hit on them is the victim's own, whatever the HP (one mechanic's
                # step: across the caches these gaps run 0-1.0 s; the next step's hits come 1.3 s or more later)
MECH = [(15, 50, "Paradeigma I"), (50, 92, "Paradeigma II"), (92, 110, "Glaukopis"), (110, 160, "Superchain I"),
        (160, 190, "Dialogos"), (190, 236, "Paradeigma III"), (236, 280, "Glaukopis / Ultima Blade"),
        (280, 345, "Palladion"), (345, 395, "Superchain IIA"), (395, 470, "Superchain IIB")]
mech_at = lambda t: next((m for lo, hi, m in MECH if lo <= t < hi), "other")
OPP = {"Astral": "Umbral", "Umbral": "Astral"}
JUMP_S = 20   # a death without a hit this close to the pull's end is a jump off the arena (a wipe call)


# ---------- how sure a reading of the log is ----------
# Confidence is the log's uncertainty, not the rule's (the user's call, 2026-10-28). Positions are logged with events, not
# continuously: one read between samples is interpolated, and even one at a hit is the player's spot as it was logged,
# not as the game snapshotted it (an AoE's edge looks soft by that much). POS_ERR: 90% of positions read g s from the
# nearest sample are within this many y of where the player was (leave one out of 450,000 samples, interpolated from
# their neighbours: scratch/review/pos_error.py); past its end it grows as a run would.
POS_ERR = ((0.0, 0.38), (0.05, 0.38), (0.1, 0.47), (0.2, 0.63), (0.3, 0.90), (0.5, 1.36), (0.75, 2.01), (1.0, 2.78), (1.5, 3.85), (2.5, 5.90))
TIME_ERR = 0.1    # s: a cast's logged time against the boss's snapshot (provokes back by +1.1 s took the hit, from +1.2 s not)


def pos_err(g):
    """How far (y) a position read g s from its nearest sample may be off, 9 times in 10."""
    g = max(g or 0, 0)
    for (g0, e0), (g1, e1) in zip(POS_ERR, POS_ERR[1:]):
        if g <= g1: return e0 + (e1 - e0) * (g - g0) / (g1 - g0)
    return POS_ERR[-1][1] + (g - POS_ERR[-1][0]) * (POS_ERR[-1][1] - POS_ERR[-2][1]) / (POS_ERR[-1][0] - POS_ERR[-2][0])


def unc(*gaps):
    """The uncertainty (y) of a distance read from positions g s from their samples: their errors combined."""
    return math.sqrt(sum(pos_err(g) ** 2 for g in gaps)) if gaps else pos_err(0)


def certainty(margin, u):
    """How sure a verdict is that holds by `margin` against an uncertainty `u` (both in the same unit): high from twice
    it, medium from once, low under it (the log cannot tell which way it went: where another player could equally be
    the culprit, the rule says undecided)."""
    return "high" if margin >= 2 * u else "medium" if margin >= u else "low"


def quad(p):
    x, y = p
    return ("N" if y < 0 else "S") + ("E" if x > 0 else "W")


class Pull:
    def __init__(self, code, fight, rep, ev, acts=None):
        """acts: the pull's entry in the acts cache (acts.py), for the players' casts; without it the rules that read
        casts (the Glaukopis swap) say less about why."""
        self.code, self.fid = code, fight["id"]
        self.s, self.e = fight["startTime"], fight["endTime"]
        self.ab = {int(k): v for k, v in ev["abilities"].items()}
        act = {a["id"]: a for a in rep["masterData"]["actors"] if a["subType"] != "LimitBreak"}   # FFLogs lists the Limit Break as a player
        self.players = {pid: act[pid]["name"] for pid in fight["friendlyPlayers"] if pid in act}
        self.job = {act[pid]["name"]: act[pid]["subType"] for pid in fight["friendlyPlayers"] if pid in act}
        self.casts = None if acts is None else [(t, acts["players"][str(pid)][0], acts["names"].get(str(ab))) for t, pid, ab in acts["casts"]]
        inf = lambda e: e.get("fight") == self.fid and self.s - 30000 <= e["timestamp"] <= self.e + 3000
        self.dmg = [e for e in ev["dmg"] if inf(e) and e["type"] == "damage" and e.get("targetID") in self.players]
        # the game's damage calculation, ~0.7 s before each hit: it names every target, also one killed by another hit first
        self.calc = [e for e in ev["dmg"] if inf(e) and e["type"] == "calculateddamage" and e.get("targetID") in self.players]
        self.deb = [e for e in ev["debuffs"] if inf(e) and e.get("targetID") in self.players]
        self.deaths = [e for e in rep["deaths"] if inf(e) and e.get("targetID") in self.players]
        for e in self.dmg + self.calc + self.deb + self.deaths:
            e["t"] = (e["timestamp"] - self.s) / 1000
            e["who"] = self.players[e["targetID"]]
            e["name"] = self.ab.get(e.get("abilityGameID"), "?")
            tr = e.get("targetResources")
            e["pos"] = ((tr["x"] - 10000) / 100, (tr["y"] - 10000) / 100) if tr and "x" in tr else None
        # where enemy abilities came from: their calculateddamage events carry the caster's position (Athena's lasers)
        self.src = [((e["timestamp"] - self.s) / 1000, self.ab.get(e.get("abilityGameID"), "?"), ((sr["x"] - 10000) / 100, (sr["y"] - 10000) / 100))
                    for e in ev["dmg"] if inf(e) and e["type"] == "calculateddamage" and e.get("sourceID") not in self.players
                    and (sr := e.get("sourceResources")) and "x" in sr]
        self.wf = (ev.get("wf") or {}).get(str(self.fid))   # White Flame's lasers and positions around them (scorecard.wf_compact)
        self.p3 = (ev.get("p3") or {}).get(str(self.fid))   # Paradeigma III's add tethers (scorecard.p3_compact)
        self.sc1 = (ev.get("sc1") or {}).get(str(self.fid))   # Superchain I's towers, last cluster and positions (scorecard.sc1_compact)
        self.p2 = (ev.get("p2") or {}).get(str(self.fid))   # Paradeigma II's tethers, casts and positions (scorecard.p2_compact)

    # helpers
    def white_flame(self, lo, hi):
        """The White Flame laser cast between lo and hi, when each add picks its two nearest players: (its time,
        {add position: its laser instances}, where, unsure), where(player) giving (position, seconds to the nearest
        sample it is read from) or None, and unsure the lasers that could be either add's. In half the waves the lasers
        log Athena's spot (stale): the adds' positions then come from their own White Flame cast just before, and each
        laser goes to the add it fits (wf_pair: 93% right, 0.4% wrong, the rest unsure and counted for both). None
        without the positions (scorecard.fetch_wf)."""
        if not self.wf: return None
        ls = [l for l in self.wf["lasers"] if lo <= l[0] <= hi]
        if not ls: return None
        t1, adds, samples, unsure = min(l[0] for l in ls), collections.defaultdict(set), collections.defaultdict(list), set()
        stale = not all(abs(x) >= WF_WALL for _, _, x, _ in ls)
        if not stale:
            for _, inst, x, y in ls: adds[(x, y)].add(inst)
        else:
            adds = {(x, y): set() for t, _, x, y in self.wf.get("adds", ()) if t1 - 2 <= t <= t1 and abs(x) >= WF_WALL}
        for t, pid, x, y in self.wf["pos"]:
            if pid in self.players: samples[self.players[pid]].append((t, (x, y)))

        def where(w):
            s = samples.get(w)
            if not s: return None
            before, after = [v for v in s if v[0] <= t1], [v for v in s if v[0] > t1]
            if not before: return after[0][1], after[0][0] - t1
            if not after: return before[-1][1], t1 - before[-1][0]
            (ta, pa), (tb, pb) = before[-1], after[0]   # linear between the samples either side
            k = (t1 - ta) / (tb - ta) if tb > ta else 0
            return (pa[0] + k * (pb[0] - pa[0]), pa[1] + k * (pb[1] - pa[1])), min(t1 - ta, tb - t1)
        if stale and adds:
            for inst, ok in wf_pair(self, lo, hi, t1, adds, where).items():
                for a in ok or adds: adds[a].add(inst)
                if len(ok) != 1: unsure.add(inst)
        return t1, dict(adds), where, unsure


    def source_at(self, names, lo, hi):
        """Where the first of these enemy abilities between lo and hi came from, or None."""
        return next((pos for t, n, pos in self.src if n in names and lo <= t <= hi), None)

    def hits(self, names, lo, hi):
        names = {names} if isinstance(names, str) else set(names)
        return [e for e in self.dmg if e["name"] in names and lo <= e["t"] <= hi]

    def holders(self, debuff, lo, hi):
        return [e["who"] for e in self.deb if e["name"] == debuff and e["type"] == "applydebuff" and lo <= e["t"] <= hi]

    def cast_at(self, who, action, lo, hi):
        """Times `who` cast `action` between lo and hi."""
        return [t for t, w, n in self.casts or [] if w == who and n == action and lo <= t <= hi]

    def has_debuff_at(self, debuff, t):
        st = {}
        for e in sorted((e for e in self.deb if e["name"] == debuff and e["t"] <= t), key=lambda e: e["t"]):
            st[e["who"]] = e["type"] in ("applydebuff", "refreshdebuff")
        return {w for w, v in st.items() if v}

    def dead_by(self, t):
        """Players dead at time t: a death (its lethal hit lands ~2 s before the death event) and no sign of a raise
        since: no hit taken with HP left over after it, and no Weakness or Brink of Death (a raise's debuff)."""
        out = set()
        for w in self.job:
            ds = [d["t"] - 2 for d in self.deaths if d["who"] == w and d["t"] - 2 < t]
            if not ds: continue
            last = max(ds)
            if not any(e["who"] == w and last + 2.5 < e["t"] < t and (e.get("targetResources") or {}).get("hitPoints", 0) > 0 for e in self.dmg) \
               and not any(e["who"] == w and e["name"] in ("Weakness", "Brink of Death") and e["type"] == "applydebuff" and last < e["t"] < t for e in self.deb):
                out.add(w)
        return out

    def incidents(self):
        inc = []
        for d in self.deaths:   # the death event is the truth; the lethal hit lands ~2 s earlier
            lethal = [e for e in self.dmg if e["who"] == d["who"] and d["t"] - 4 <= e["t"] <= d["t"] and (e.get("targetResources") or {}).get("hitPoints") == 0]
            if lethal: e = lethal[-1]; inc.append(dict(t=e["t"], kind="death", victim=d["who"], ability=e["name"], pos=e["pos"]))
            else:
                ab = self.ab.get(d.get("killingAbilityGameID"), "?")
                # no lethal hit, above half HP after the last hit in the 5 s before (if any) and the pull over within
                # JUMP_S: a player jumping off the arena once a wipe is called (419 of 427 such deaths end that close).
                # Lower HP, the lethal hit is more likely missing from the log; earlier, the pull went on without them.
                last = next((e for e in reversed(self.dmg) if e["who"] == d["who"] and d["t"] - 5 <= e["t"] <= d["t"]), None)
                tr = (last or {}).get("targetResources") or {}
                jump = ab == "?" and (last is None or tr.get("hitPoints", 0) > tr.get("maxHitPoints", 0) / 2) and (self.e - self.s) / 1000 - d["t"] <= JUMP_S
                inc.append(dict(t=d["t"] - 2, kind="death", victim=d["who"], ability=ab, pos=None, jump=jump))
        for d in self.deb:
            if d["name"] == "Damage Down" and d["type"] in ("applydebuff", "refreshdebuff"):
                # the hit that gave it: an avoidable one (an orb, a donut) when another landed at the same moment
                src = sorted((e for e in self.dmg if e["who"] == d["who"] and abs(e["t"] - d["t"]) <= 0.2), key=lambda e: e["name"] not in AVOIDABLE)
                inc.append(dict(t=d["t"], kind="DD", victim=d["who"], ability=src[0]["name"] if src else "?", pos=src[0]["pos"] if src else None))
        return sorted(inc, key=lambda i: i["t"])


def fault(t, mech, culprits, victims, rule, conf, chain=None, ability=None, fallout=False, hit=False, after=None, *, tag, share="own"):
    """tag: which rule this is, a stable id (scorecard.LABELS names it on the site): the code decides by it, never by the
    rule's text, which is free to change.
    chain: players whose earlier death caused this; their death's culprits are blamed instead when there is one.
    ability: the hit the fault is about; a death to it goes to this fault before an earlier one that hit the victim, and
    faults about the same hit are one cause. fallout: its deaths are fallout of a mistake its culprits made earlier.
    hit: a mistake even when no death or Damage Down follows (a "hit" entry then stands for it). after: the fault whose
    mistake this one is the consequence of; it is counted once, at whichever of their incidents comes first. A rule that blames
    someone besides its own victims without naming them is told with their names first ("X: did not soak ..."), as it is
    read on the victims' deaths too.
    share: how much of the mistake each culprit's is, apart from how sure the rule is (confidence). "own": each made a
    mistake of their own, all of it theirs (also "both off their spots"). "one_of": one mistake, the model cannot tell whose,
    so each of n candidates 1/n (an undecided rule, whose tag ends ".undecided", is that unless said otherwise).
    "together": one shortfall spread over the party, each of the culprits and of the dead players in `chain` (passed to
    whoever caused their deaths) 1/n. A number: each culprit, and each dead player's slot, that share."""
    culprits, victims = list(dict.fromkeys(culprits)), set(victims)
    if culprits and not chain and victims != set(culprits) and any(w not in rule for w in culprits):
        rule = f"{', '.join(culprits)}: {rule}"
    if share == "own" and tag.endswith(".undecided") and len(culprits) > 1: share = "one_of"
    n = len(culprits) + (len(chain or ()) if share == "together" else 0)
    each = share if isinstance(share, (int, float)) else 1 / n if share in ("one_of", "together") and n else 1.0
    return dict(t=t, mechanic=mech, culprits=culprits, victims=victims, rule=rule, confidence=conf, tag=tag,
                chain=chain or [], ability=ability, fallout=fallout, hit=hit, after=after,
                shares={c: each for c in culprits}, chain_share=each if share != "one_of" else 1.0)


# ---------- Paradeigma I: White Flame light-party baits ----------
# Each add fires White Flame at its two nearest living players at the laser cast (positions then fit 916 of 924 adds,
# scratch/whiteflame); a baiter in the line-up can lose their laser to a non-baiter who stands, or runs past, closer.
WF_WALL = 20          # an add's logged x when out at the wall (25); nearer the centre its position is stale
WF_BAIT_MAX = 27.3    # y from their add at the laser cast: as far as a fitting add's second target stood (99th percentile)
WF_WAVES = ((1, (37, 41.5)), (2, (42, 46.5)))
WF_FLAME = 3.0        # y a White Flame line reaches from its centre, as the tether lasers' (scratch/para3tether/width.py)
# the line-up's spots, y from Athena toward the adds' half at the laser cast: tank, melee, healer, ranged by the wall
# (medians of 527 clean waves' baiters ranked by it, scratch/whiteflame/seatspots.py; players keep their rank: 182 of 184)
SEAT_ALONG = (1.3, 6.7, 12.5, 17.9)
SEAT_OFF = 2.5        # y from their spot, off the line through Athena too: past 95% of clean waves' baiters (2.3 y;
                      # scratch/whiteflame/seats2d.py). The add nearer the centre takes the two spots nearer Athena (519 of 527)


class LightParties(tuple):
    """(light party 1, light party 2), with `seats`: {(wave, player): their rank in the line-up, 0-3 from Athena}, and
    `by_side` for a group whose parties bait by the adds' side, not by wave: {"E" / "W": the party baiting the adds
    there}, else None. The parties keep their names (Superchain I's and Paradeigma III's seats); which one baits each
    wave of a pull is `wave_parties`'."""
    seats, by_side = {}, None


def wf_side(p, lo, hi):
    """Which side ("E" / "W") the White Flame adds stood on between lo and hi, or None without their positions."""
    wf = p.white_flame(lo, hi)
    return ("E" if next(iter(wf[1]))[0] > 0 else "W") if wf and wf[1] else None


def wave_parties(p, lp):
    """(wave 1's baiters, wave 2's) in pull p: the light parties, or for a group baiting by side the party on wave 1's
    adds' side first."""
    side = lp.by_side and wf_side(p, *WF_WAVES[0][1])
    if not side: return lp
    out = LightParties((lp.by_side[side], lp.by_side["W" if side == "E" else "E"]))
    out.seats = lp.seats
    return out


def along(wf, x):
    """Player x's distance from Athena toward the adds' half at the laser cast (the line-up's axis), or None."""
    q = wf[2](x)
    return q and q[0][1] * math.copysign(1, next(iter(wf[1]))[1])


def seat_off(wf, seats, w, b):
    """How far baiter b stood from their line-up spot as the lasers fired (along the line and off it), or None."""
    if (w, b) not in seats or not (q := wf[2](b)): return None
    return math.hypot(q[0][0], along(wf, b) - SEAT_ALONG[seats[(w, b)]])


def seat_add(wf, seats, w, b):
    """The add whose laser baiter b's spot draws: the one nearer the centre for the two spots nearer Athena."""
    adds = sorted(wf[1], key=lambda a: abs(a[1]))
    return adds[0 if seats[(w, b)] < 2 else -1] if (w, b) in seats and adds else None


def wf_pair(p, lo, hi, t1, adds, where):
    """{laser instance: the adds it fits}: a laser starts at its add and runs through its target, one of the add's two
    nearest living players, with everyone else in it within WF_FLAME of that line (scratch/whiteflame/pairing.py)."""
    alive = [x for x in p.job if x not in p.dead_by(t1) and where(x)]
    near2 = {a: {x for _, x in sorted((math.dist(where(x)[0], a), x) for x in alive)[:2]} for a in adds}
    out = {}
    for inst, ys in wf_aimed(p, lo, hi, p.hits("White Flame", lo, hi)).items():
        pos = {y: q[0] for y in ys if (q := where(y))}
        out[inst] = [a for a in adds if any(all(line_off(a, pos[tg], q) <= WF_FLAME for q in pos.values()) for tg in pos if tg in near2[a])]
    return out


def wf_aimed(p, lo, hi, hs):
    """{laser instance: the players in its line}: the calculated hits, which also name a player another laser killed
    first, else the hits."""
    out = collections.defaultdict(set)
    for e in [e for e in p.calc if e["name"] == "White Flame" and lo <= e["t"] <= hi] or hs: out[e.get("sourceInstance")].add(e["who"])
    return out


def line_up_seats(pulls, lp):
    """{(wave, player): rank} from the clean waves (every baiter alive and hit once, no one else): the baiters ranked by
    `along`, each player's most common rank."""
    c = collections.defaultdict(collections.Counter)
    for p in pulls:
        for w, (lo, hi) in WF_WAVES:
            hs, wf = p.hits("White Flame", lo, hi), p.white_flame(lo, hi)
            if not hs or not wf or not wf[1]: continue
            exp, cnt = {x for x in wave_parties(p, lp)[w - 1] if x in p.job}, collections.Counter(e["who"] for e in hs)
            if len(exp) != 4 or set(cnt) != exp or any(n != 1 for n in cnt.values()): continue
            al = sorted((a, x) for x in exp if (a := along(wf, x)) is not None)
            if len(al) == 4:
                for r, (_, x) in enumerate(al): c[(w, x)][r] += 1
    return {k: v.most_common(1)[0][0] for k, v in c.items()}


def wf_lined(p, lo, hi, w, t, xs, exp, hs, seats):
    """Faults for xs, who stood in a laser line: each their own, except a baiter in two or more lasers, sharing them
    with others (in line with another target), when someone in them stood over SEAT_OFF from their line-up spot as they
    fired and another did not: those off it. A baiter in two lasers that hit only them was each add's pick: their own."""
    out, done, wf = [], set(), p.white_flame(lo, hi)
    aimed = wf_aimed(p, lo, hi, hs)
    by_far = collections.defaultdict(list)
    for x in (xs if wf and wf[1] and seats else ()):
        mine = [s for s in aimed.values() if x in s]
        if x not in exp or len(mine) < 2 or not any(len(s) > 1 for s in mine): continue
        off = {b: d for b in set().union(*mine) if b in exp and (d := seat_off(wf, seats, w, b)) is not None}
        far = tuple(sorted(b for b, d in off.items() if d > SEAT_OFF))
        if far and len(far) < len(off) and x in off: by_far[far].append(x)
    for far, vs in by_far.items():
        offs = {b: seat_off(wf, seats, w, b) for b in far}
        out.append(fault(t, "Paradeigma I", list(far), vs, f"{', '.join(far)}: off their spot in the White Flame line as wave {w} fired "
                         f"({', '.join(f'{b} {offs[b]:.1f} y from it' for b in far)}): {', '.join(vs)} took two or more lasers in line with them", "medium", tag="p1.wf.off_spot"))
        done |= set(vs)
    return out + [fault(t, "Paradeigma I", [x], [x], f"took a White Flame meant for wave {w} baiters (stood in a laser line)", "medium", tag="p1.wf.line") for x in xs if x not in done]


def wf_closer(p, lo, hi, missing, exp, hs, seats=None, w=None):
    """{missing baiter: ([(interloper, their distance, sure)], the baiter's distance, the players their add's lasers hit,
    whether one of those lasers could be the other add's, (their distance from their spot, seconds from the cast it was
    read) when it is past SEAT_OFF by less than the log can tell (unc), else
    None: who drew the laser cannot be decided)} for the missing baiters within WF_BAIT_MAX of their add at
    the laser cast (the one their seat draws, else the nearest), whose add's lasers also went through a baiter (the
    line-up was there; a whole light party missing is theirs) and an interloper closer to it than they were: a
    non-baiter, or a baiter of the other add over SEAT_OFF from their spot. The nearest such took the laser (the others
    it hit stood behind them in its line), with whoever stood as near as the log can tell (unc: either could have), its
    confidence the margin by which it was nearer (certainty). An interloper no nearer than the positions can tell is a
    tie, the last field: "out" when every such interloper stood off their spot by more than that
    too (a non-baiter past WF_STACK_R from the stack, the other add's baiter past SEAT_OFF), else "at"; None when one stood
    clearly nearer."""
    wf, seats = p.white_flame(lo, hi), seats or {}
    if not wf or not wf[1]: return {}
    t1, adds, where, unsure = wf
    aimed = wf_aimed(p, lo, hi, hs)
    out = {}
    for x in missing:
        if not (px := where(x)): continue
        add = seat_add(wf, seats, w, x) or min(adds, key=lambda a: math.dist(px[0], a))
        dx = math.dist(px[0], add)
        off = seat_off(wf, seats, w, x)
        thin = (off, px[1]) if off is not None and SEAT_OFF < off <= SEAT_OFF + unc(px[1]) else None   # past it by less than the log can tell
        if dx > WF_BAIT_MAX or (off or 0) > SEAT_OFF and not thin: continue   # not in the line-up: theirs
        hit = {y for i, ys in aimed.items() if i in adds[add] for y in ys}
        if off is None and not hit & exp: continue   # no spot to check them against: the line-up must have drawn a laser
        stray = lambda y: y not in exp or (seat_add(wf, seats, w, y) not in (add, None) and (seat_off(wf, seats, w, y) or 0) > SEAT_OFF)
        margin = lambda g: unc(px[1], g)   # what the two positions, read g and px[1] s from their samples, can tell apart
        near = sorted((dy, y, py[1]) for y in hit if y != x and stray(y) and (py := where(y)) and (dy := math.dist(py[0], add)) < dx + margin(py[1]))
        if not near: continue
        near = [v for v in near if v[0] - near[0][0] <= unc(near[0][2], v[2])]   # as near as the log can tell: either drew it
        sure = certainty(dx - near[0][0], margin(near[0][2])) if len(near) == 1 else "low"
        tie = None
        if all(dx - dy <= margin(g) for dy, _, g in near):   # no interloper clearly nearer: who stood off their spot decides
            a0 = next(iter(adds)); stack = (WF_STACK[0] * math.copysign(1, a0[0]), WF_STACK[1] * math.copysign(1, a0[1]))
            # off their spot by more than the positions can tell (as for a baiter barely off theirs: rVkK pull 22)
            away = lambda y: ((math.dist(where(y)[0], stack) - WF_STACK_R) if y not in exp else ((seat_off(wf, seats, w, y) or 0) - SEAT_OFF)) > unc(where(y)[1])
            tie = "out" if all(away(y) for _, y, _ in near) else "at"
        out[x] = [(y, dy, sure) for dy, y, _ in near], dx, sorted(hit), bool(adds[add] & unsure), thin, tie
    return out


# The replay (user's rule, 2026-10-27): each add's two nearest living players at the laser cast, each laser from its add
# through them and on, hitting everyone within WF_LINE of its line, reproduces 90% of waves exactly (1,595 of 1,778;
# scratch/whiteflame/audit_model.py). In those, a player hit more than they should be (a baiter once, anyone else never) is
# blamed on whoever's move to their spot alone would have spared them, else the fewest players who together would have.
WF_LINE = 2.0              # y either side of a White Flame's line it hits (the replay's best fit)
WF_STACK = (-0.2, -10.2)   # the other light party's stack: y toward the adds' wall and along from Athena (medians of 5,136
WF_STACK_R = 3.6           # non-baiters in clean waves, 95% of them within this; scratch/whiteflame/audit.py)
SIDE_FIT = 1.2             # how much better the single hits must fit the adds' sides than the waves (infer_light_parties)
WF_FIX_MAX = 4             # the most players a correction is searched over


def wf_lasers(adds, pos):
    """The replay: [(add, target, players hit)] for positions {player: (x, y)}."""
    out = []
    for a in adds:
        for tg in sorted(pos, key=lambda x: math.dist(pos[x], a))[:2]:
            d = (pos[tg][0] - a[0], pos[tg][1] - a[1]); n = math.hypot(*d) or 1e-9
            out.append((a, tg, {x for x, q in pos.items() if ((q[0] - a[0]) * d[0] + (q[1] - a[1]) * d[1]) / n > 0
                                and abs((q[0] - a[0]) * d[1] - (q[1] - a[1]) * d[0]) / n <= WF_LINE}))
    return out


def wf_replay(p, lo, hi, w, t, lp):
    """Wave w by the replay: (faults, the victims they judge, the victims left to para1's other rules), or None where
    it does not hold: positions missing, a baiter without a learned spot or already dead (para1's chain), or the
    replay not picking the adds' targets (each replayed laser paired with a logged line holding its target). Each picked
    laser hits whom the log says it did (a player at its edge either way) until a correction moves its target; a victim
    no correction of up to WF_FIX_MAX players spares is left to the other rules. Spots: a baiter's line-up seat, everyone else the stack; players within the log's error of
    theirs at the moment itself (unc(0); a stale reading is no proof they were there) are not moved (they stood there). Of the corrections, those with fewest players within their spot's
    tolerance (SEAT_OFF, WF_STACK_R) are blamed, all of them: with everyone in them out of place, each correction's
    players made a mistake either way (the user's rule, 2026-10-27, as for Superchain I's lasers and towers; it was the
    victim's own, else the farthest off); when every one has someone within it and there are several, all of them as
    undecided (low: the user's ruling, said as such). Confidence: the least sure of its margins against the log's error
    (certainty): each culprit past their spot's tolerance, an interloper nearer the add than the baiters it out-stood; at
    most medium where the replay gets a line of the wave wrong or the correction moved players inside their tolerance."""
    seats, wf = getattr(lp, "seats", {}), p.white_flame(lo, hi)
    if not wf or len(wf[1]) != 2: return None
    t1, adds, where, _ = wf
    alive = [x for x in p.job if x not in p.dead_by(t1)]
    bait = {x for x in lp[w - 1] if x in p.job}
    q = {x: where(x) for x in alive}
    if bait - set(alive) or not all(q.values()) or any((w, x) not in seats for x in bait): return None
    pos = {x: v[0] for x, v in q.items()}
    real = wf_lasers(adds, pos)
    aimed = wf_aimed(p, lo, hi, p.hits("White Flame", lo, hi))
    pred, act = collections.Counter(frozenset(h) for *_, h in real), collections.Counter(frozenset(s) for s in aimed.values())
    # the replay must pick the adds' targets (every laser paired with a logged line holding its target); a player at a
    # line's edge can still change who else it hit: those the pairs disagree on are left to the other rules
    lines = [set(s) for s in act.elements()]
    if len(lines) != len(real): return None
    fits = [list(zip(real, ls)) for ls in itertools.permutations(lines) if all(tg in l for (_, tg, _), l in zip(real, ls))]
    if not fits: return None
    # who the log says each picked laser hit (a player at a line's edge either way), until a correction moves its target
    edge = {(a, tg): (l - h, h - l) for (a, tg, h), l in min(fits, key=lambda f: sum(len(h ^ l) for (_, _, h), l in f))}
    logged = collections.Counter(x for h in act.elements() for x in h)
    a0 = next(iter(adds)); sx, sy = math.copysign(1, a0[0]), math.copysign(1, a0[1])
    spot = {x: (0.0, SEAT_ALONG[seats[(w, x)]] * sy) if x in bait else (WF_STACK[0] * sx, WF_STACK[1] * sy) for x in alive}
    off = {x: math.dist(pos[x], spot[x]) for x in alive}
    tol = {x: SEAT_OFF if x in bait else WF_STACK_R for x in alive}
    out_of_place = {x: off[x] > tol[x] for x in alive}
    stack = (WF_STACK[0] * sx, WF_STACK[1] * sy)
    def counts(movers):
        out = collections.Counter()
        for a, tg, h in wf_lasers(adds, {**pos, **{x: spot[x] for x in movers}}):
            if (a, tg) in edge and tg not in movers:
                plus, minus = edge[(a, tg)]
                h = (h | {x for x in plus if x not in movers}) - {x for x in minus if x not in movers}
            out.update(h)
        return out
    n = counts(())
    victims = [x for x in alive if n[x] > (x in bait)]
    movable, tried, blame, alone, undecided, trimmed = [x for x in alive if off[x] > unc(0)], {}, {}, {}, set(), set()   # a stale reading keeps them a candidate
    for v in victims:
        score = lambda c: sum(not out_of_place[x] for x in c)   # players inside their spot's tolerance
        for k in range(1, WF_FIX_MAX + 1):
            ok = [c for c in itertools.combinations(movable, k) if (tried[c] if c in tried else tried.setdefault(c, counts(c)))[v] <= (v in bait)]
            if ok: break
        else: continue
        best = min(map(score, ok))   # options all within tolerance: no telling them apart, so all of them, undecided
        opts = [c for c in ok if score(c) == best]
        blame[v] = tuple(sorted({x for c in opts for x in c}))
        outs = [{x for x in c if out_of_place[x]} for c in opts]
        if best and all(outs):   # every correction moves someone out of place: those, not the ones inside their tolerance
            blame[v] = tuple(sorted(set().union(*outs))); trimmed.add(blame[v])
        alone[blame[v]] = k == 1
        if best and len(opts) > 1 and not all(outs): undecided.add(blame[v])
    targets = {tg for _, tg, _ in real}

    def role(x):
        if x in bait:   # not in the line-up (at the stack, or unhit and over two spots' tolerance away) / off their spot
            return 0 if math.dist(pos[x], stack) < off[x] or not n[x] and off[x] > 2 * SEAT_OFF else 2
        return 1 if x in targets else 3             # nearer an add than its baiters / in a laser line
    words = ("not in the line-up", "nearer an add than its baiters", "off their spot", "in a laser line")
    out = []
    for cul, vs in itertools.groupby(sorted(blame, key=lambda v: (blame[v], v)), key=lambda v: blame[v]):
        vs = list(vs)
        mine = {a for a, tg, _ in real if tg in cul}
        outstood = sorted(b for b in bait if seat_add(wf, seats, w, b) in mine and b not in targets)
        # how sure: the margins it rests on against the log's error, each culprit past their spot's tolerance and an
        # interloper nearer the add than the baiters it out-stood; at most medium where the replay misses a logged line or
        # the correction also moved players inside their tolerance
        conf = least_sure([certainty(off[x] - tol[x], unc(q[x][1])) for x in cul] + [
            certainty(math.dist(pos[b], a) - math.dist(pos[x], a), unc(q[x][1], q[b][1]))
            for a, x, _ in real if x in cul and role(x) == 1 for b in outstood])
        if conf == "high" and (pred != act or cul in trimmed): conf = "medium"
        top = min(map(role, cul))
        how = "; ".join(f"{x} {off[x]:.1f} y from their spot" + (f", {words[role(x)]}" if role(x) != top else "") for x in cul)
        if top == 0: rule = f"not in the White Flame line-up as wave {w} fired ({how})"
        elif top == 1:
            rule = (f"closer to the White Flame add than its baiter{'s' if len(outstood) != 1 else ''} {', '.join(outstood)} as wave {w} fired ("
                    + ", ".join(f"{x} {math.dist(pos[x], a):.1f} y" for x in [x for x in cul if role(x) == 1] + outstood for a in [min(mine, key=lambda a: math.dist(pos[x], a))]) + f"; {how})")
        elif top == 2: rule = f"off their spot in the White Flame line as wave {w} fired ({how})"
        else: rule = f"stood in a White Flame line meant for wave {w} baiters ({how})"
        if cul in undecided:   # the model cannot tell these apart: said so, not passed off as one player's mistake
            how = "; ".join(f"{x} {off[x]:.1f} y from their spot" for x in cul)
            rule = (f"could not be decided who drew the White Flame laser as wave {w} fired ({how}; every correction moves someone within their spot's tolerance): "
                    + ("any one of them at their spot" if alone[cul] else "more than one correction") + f" would have spared {', '.join(vs)}")
        elif cul in trimmed:   # the correction also nudged players inside their tolerance: not their mistake
            rule += f"; {'at their spot' if len(cul) == 1 else 'at their spots'}, with others nudged inside their tolerance, {', '.join(vs)} would not have been hit"
        elif set(vs) != set(cul) or len(cul) > 1:
            rule += f"; {'at their spot' if len(cul) == 1 else 'with any one of them at their spot' if alone[cul] else 'at their spots'}, {', '.join(vs)} would not have been hit"
        out.append(fault(t, "Paradeigma I", list(cul), vs, rule, conf, tag="p1.wf.undecided" if cul in undecided else ("p1.wf.not_in_line_up", "p1.wf.too_close", "p1.wf.off_spot", "p1.wf.line")[top]))
    return out, set(blame), {x for x in logged if logged[x] > (x in bait)} - set(blame)


def infer_light_parties(pulls):
    """LP1 baits the first White Flame wave, LP2 the second; learn who is who from clean single hits, then their seats.
    Some groups bait by the adds' side instead (rVkK, 2026-09-30: one party took the west adds in 12 of 12 pulls, the
    other the east in 22 of 22, whichever wave): when the single hits fit the sides over SIDE_FIT times better than the
    waves, the parties are the side split (BY6A and WtD9 too, 2026-09-23: their wave split mixed the parties), light
    party 1 the one baiting wave 1 more often, with `by_side`."""
    c = {k: collections.Counter() for k in (1, 2, "E", "W")}
    for p in pulls:
        for w, (lo, hi) in WF_WAVES:
            by = collections.defaultdict(list)
            for e in p.hits("White Flame", lo, hi): by[e.get("sourceInstance")].append(e["who"])
            side = wf_side(p, lo, hi)
            for ws in by.values():
                if len(ws) == 1:
                    c[w][ws[0]] += 1
                    if side: c[side][ws[0]] += 1

    def split(a, b):
        one = {w for w, _ in c[a].most_common(4)}
        return one, set([w for w, n in c[b].most_common() if w not in one][:4])   # count order, not set order, before cutting to four
    lp = LightParties(split(1, 2))
    east, west = split("E", "W")
    fit = lambda k, party: sum(c[k][x] for x in party)
    if fit("E", east) + fit("W", west) > SIDE_FIT * (fit(1, lp[0]) + fit(2, lp[1])):   # the side split is the parties then:
        lp = LightParties(sorted((east, west), key=lambda party: -fit(1, party)))       # light party 1 the one baiting wave 1 more
        lp.by_side = {"E": east, "W": west}
    lp.seats = line_up_seats(pulls, lp)
    return lp


def para1(p, lp):
    lp = wave_parties(p, lp)
    out, seats = [], getattr(lp, "seats", {})
    for w, (lo, hi) in WF_WAVES:
        hs = p.hits("White Flame", lo, hi)
        if not hs: continue
        t = min(e["t"] for e in hs); dead = p.dead_by(t - 0.5)
        judged = set()
        if (r := wf_replay(p, lo, hi, w, t, lp)) is not None:
            faults, judged, rest = r
            out += faults
            if not rest: continue
        k = len(out)   # the other rules for the victims the replay left: theirs, not those it judged
        cnt = collections.Counter(e["who"] for e in hs)
        exp = {x for x in lp[w - 1] if x in p.job and x not in dead}
        gone = sorted(x for x in lp[w - 1] if x in p.job and x in dead)
        missing = [x for x in sorted(exp) if x not in cnt]
        extra = [x for x in cnt if x not in exp] + [x for x, n in cnt.items() if n >= 2 and x in exp]
        # an extra player hit only by lasers that also hit their own baiter stood in that baiter's line: their own mistake
        by = collections.defaultdict(set)
        for e in hs: by[e.get("sourceInstance")].add(e["who"])
        lined = [x for x in extra if x not in exp and all(ws & exp for ws in by.values() if x in ws)]
        aimed = wf_aimed(p, lo, hi, hs)
        if missing:
            took = [x for x in extra if x not in lined]
            # a baiter in the line-up whose add found someone out of place closer: theirs, not the baiter's
            by_cul = collections.defaultdict(list)   # both of an add's baiters out-stood by the same players: one fault
            for x, v in wf_closer(p, lo, hi, missing, exp, hs, seats, w).items():
                missing.remove(x)
                by_cul[tuple(y for y, *_ in v[0])].append((x, *v))
            for cul, xs in by_cul.items():
                ys, hit, unsure = xs[0][1], {v for x in xs for v in x[3]}, any(x[4] for x in xs)
                # the add's lasers' victims are theirs; with a laser that could be the other add's, only the non-baiters
                # in a laser with them (a baiter in two goes to wf_lined below, by the seats)
                lost = [v for v in took if v in hit and (not unsure or v not in exp and any(v in s and set(cul) & s for s in aimed.values()))]
                took = [v for v in took if v not in lost]
                dists = (f"{', '.join(f'{y} {dy:.1f} y' for y, dy, _ in ys)}, {', '.join(f'{x} {dx:.1f} y' for x, _, dx, *_ in xs)}")
                if any(x_[6] == "at" for x_ in xs):   # as near as the baiter at their spot, and at their own: no telling
                    out.append(fault(t, "Paradeigma I", list(cul) + [x for x, *_ in xs], lost, f"could not be decided who drew the White Flame laser as wave {w} "
                                     f"fired: {', '.join(cul)} at their spot as near the add as the baiter{'s' if len(xs) > 1 else ''} {', '.join(x for x, *_ in xs)} "
                                     f"at theirs ({dists})" + (f"; the laser went to {', '.join(lost)}" if lost else ""), "low", tag="p1.wf.undecided"))
                    continue
                if thin := [(x, x_[5]) for x_ in xs for x in [x_[0]] if x_[5]]:   # the baiter barely off their spot: no telling
                    out.append(fault(t, "Paradeigma I", list(cul) + [x for x, _ in thin], lost, f"could not be decided who drew the White Flame laser as wave {w} "
                                     f"fired: {', '.join(f'{x} {o:.1f} y from their spot (read {g:.2f} s from the cast)' for x, (o, g) in thin)}, "
                                     f"{', '.join(cul)} nearer the add ({dists})" + (f"; the laser went to {', '.join(lost)}" if lost else ""), "low", tag="p1.wf.undecided"))
                    continue
                out.append(fault(t, "Paradeigma I", list(cul), lost, f"{', '.join(cul)}: closer to the White Flame add than its baiter{'s' if len(xs) > 1 else ''} "
                                 f"{', '.join(x for x, *_ in xs)} as wave {w} fired ({dists})" + (f"; the laser went to {', '.join(lost)}" if lost else ""),
                                 "medium" if all(x_[6] == "out" for x_ in xs) else least_sure([s for x in xs for *_, s in x[1]]), tag="p1.wf.too_close",
                                 share="one_of" if len(cul) > 1 else "own"))   # several as near: one of them drew it
            if missing:
                out.append(fault(t, "Paradeigma I", missing, took, f"not in the White Flame line-up (wave {w}); the laser went to {', '.join(took) or 'someone else'}", "high" if took else "medium", tag="p1.wf.not_in_line_up"))
            else:   # every missing baiter's laser explained: anyone else it hit (a baiter twice) stood in a laser line
                lined += took
            out += wf_lined(p, lo, hi, w, t, lined, exp, hs, seats)
        elif extra and len(extra) <= len(gone):   # a baiter was already dead, so their laser found someone else
            out.append(fault(t, "Paradeigma I", gone, extra, f"White Flame (wave {w}) went to {', '.join(extra)} because {'its baiter' if len(gone) == 1 else 'its baiters'} {', '.join(gone)} {'was' if len(gone) == 1 else 'were'} already dead", "consequence", chain=gone, tag="p1.wf.baiter_dead"))
        elif extra:
            out += wf_lined(p, lo, hi, w, t, extra, exp, hs, seats)
        if judged:
            out[k:] = [f for f in out[k:] if not (f["victims"] and f["victims"] <= judged)]
            for f in out[k:]: f["victims"] -= judged
    return out


def para1_auto(p, lp):
    """Athena's auto-attacks are magical, and a White Flame leaves Magic Vulnerability Up for 6 s. The light party 1 tank
    baits wave 1 next to her and keeps her; wave 2's baiters, the light party 2 tank among them, carry the vulnerability
    into her auto-attack at ~50.5 s, so whoever holds her then must not have been hit by wave 2 (in 708 pulls the
    light party 1 tank took it, in none a wave 2 baiter who lived). A death to that auto-attack is blamed on what put
    the vulnerable player there: the living tanks' provokes, or a tank already dead."""
    lp, out = wave_parties(p, lp), []
    au = next((e for e in p.dmg if e["name"] == "attack" and 48 <= e["t"] <= 53), None)
    if not au or (au.get("targetResources") or {}).get("hitPoints") != 0: return out
    v, t = au["who"], au["t"]
    if v not in {e["who"] for e in p.hits("White Flame", 42, 46.5)}: return out     # no wave 2 vulnerability: other rules
    dead = p.dead_by(t - 0.3)
    tanks = [w for w, j in p.job.items() if j in TANK_JOBS]
    gone, others = [w for w in tanks if w in dead], [w for w in tanks if w != v and w not in dead]
    why = f"Athena's auto-attack after Paradeigma I (magical) killed {v} through wave 2's White Flame vulnerability"
    if not others:
        if gone: out.append(fault(t, "Paradeigma I", gone, [v], f"{why}: {', '.join(gone)} {'was' if len(gone) == 1 else 'were'} already dead, so {v} had to hold her", "consequence", chain=gone, tag="p1.auto"))
        return out
    if v not in tanks: return out
    provoked = p.cast_at(v, "Provoke", 40, t)
    shirk = [w for w in others if p.cast_at(w, "Shirk", 40, t)]
    if provoked:
        out.append(fault(t, "Paradeigma I", [v], [v], f"{why}: they provoked her at {provoked[-1]:.1f} s while carrying it", "high", tag="p1.auto"))
    elif v in lp[0]:   # light party 1's tank keeps Athena, and baits wave 1, not 2
        out.append(fault(t, "Paradeigma I", [v], [v], f"{why}: tanking her, they took a wave 2 White Flame", "high", tag="p1.auto"))
    elif shirk:
        out.append(fault(t, "Paradeigma I", shirk, [v], f"{why}: {', '.join(shirk)} shirked aggro to them", "high", tag="p1.auto"))
    else:
        out.append(fault(t, "Paradeigma I", [v] + others, [v], f"{why}: {v} held her aggro ({', '.join(others)} did not keep it)", "medium", tag="p1.auto", share="one_of"))
    return out


# Paradeigma III's DPS tether seats (the simulator's dpsSpots, in yalms): each DPS stretches to the middle platform
# across from their add's wall: the straight tether (its add, 3 y off the horizontal centre line, on the platform's
# side) level with it, 3 y out, on the line of waymark B / D (the groups' preset: 10 y from the centre line, 35 y from
# the add, half a yalm past the lethal 34.5); the crossed one 10 y out at the platform's outer edge, 8.5 y out. From
# 2026-10-25 half the DPS stand within 0.9 (crossed) / 1.2 y (straight) of theirs, 90% within 1.9 / 3.1 (the 10 y seats).
TETHER_SEAT = 10, 3, 8.5, 10   # straight x, straight y, crossed y, crossed x
TETHER_HALF = 3.0     # a tether laser hits up to ~3 y from its line, past its holder too (scratch/para3tether/width.py)
# how sure a seat-based verdict is: the deciding seat's clearance past the laser's reach against the log's error for the
# one logged position it rests on (the laser's, at its calculated hit; the seats are the plan's)
sure = lambda gap: certainty(gap - TETHER_HALF, unc(0))


def line_off(a, b, q):
    """How far q stands from the line through a and b."""
    return abs((q[0] - a[0]) * (b[1] - a[1]) - (q[1] - a[1]) * (b[0] - a[0])) / max(math.dist(a, b), 1e-9)


def tether_lasers(p, supports):
    """Paradeigma III's DPS tether lasers from their calculated hits, which name every target even when another laser
    killed one first and their own left no damage event: {instance: (ability, its add's position, holder, {target:
    position})}. The holder is the add's last tether before the laser (Pull.p3); without it, a laser calculated on one
    DPS is theirs, one through two belongs to the one holding no other, and of two on one DPS (a dead holder's laser
    goes to someone) theirs is the one whose add is farther: a DPS stretches away."""
    by, add = collections.defaultdict(dict), {}
    for e in p.calc:
        if e["name"] in ("Searing Radiance", "Shadowsear") and 214.5 <= e["t"] <= 217.5:
            by[(e.get("sourceInstance"), e["name"])][e["who"]] = e["pos"]
            if (sr := e.get("sourceResources")) and "x" in sr: add[e.get("sourceInstance")] = ((sr["x"] - 10000) / 100, (sr["y"] - 10000) / 100)

    def first(kv):
        (inst, _), ws = kv
        dps = [w for w in ws if w not in supports]
        far = math.dist(add[inst], ws[dps[0]]) if len(dps) == 1 and inst in add and ws[dps[0]] else 0
        return len(dps), -far
    owner = {}
    for (inst, nm), ws in sorted(by.items(), key=first):
        if len(free := {w for w in ws if w not in supports} - set(owner.values())) == 1: owner[inst] = free.pop()
    # the add's last tether before its laser names the holder outright (a laser through two DPS, a holder dying as it fired)
    t0 = min((e["t"] for e in p.calc if e["name"] in ("Searing Radiance", "Shadowsear") and 214.5 <= e["t"] <= 217.5), default=None)
    for t, inst, pid in (p.p3 or {}).get("tethers", ()):
        if t0 is not None and t < t0 and pid in p.players: owner[inst] = p.players[pid]
    return {inst: (nm, add.get(inst), owner.get(inst), ws) for (inst, nm), ws in by.items()}


def tether_seats(lasers):
    """{holder: (seat, straight)}. The two middle platforms lie in different rows: the west one's is the row its pair
    stood further into than the east pair (one player off their tile does not flip it)."""
    ys = collections.defaultdict(list)
    for nm, a, o, ws in lasers.values():
        if o and a and ws.get(o): ys[-math.copysign(1, a[0])].append(ws[o][1])
    row_w = math.copysign(1, sum(ys[-1]) - sum(ys[1]))
    out = {}
    for nm, a, o, ws in lasers.values():
        if not (o and a): continue
        col = -math.copysign(1, a[0]); row = row_w if col < 0 else -row_w
        straight = math.copysign(1, a[1]) == row
        out[o] = ((col * TETHER_SEAT[0 if straight else 3], row * TETHER_SEAT[1 if straight else 2]), straight)
    return out


def gone_before(p, t, o, laser):
    """Whether holder o was dead before their laser landed at t: not when it was their own laser that killed them (alive
    as it fired; it ran on through whoever stood in its line)."""
    own = any(e["who"] == o and e["name"] == laser[0] and (e.get("targetResources") or {}).get("hitPoints") == 0 and 214.5 <= e["t"] <= 217.5 for e in p.dmg)
    return o in p.dead_by(t) and not own


def tether_cross(p, t, v, o, laser, seat):
    """v hit by o's tether laser. A holder dead before it lands aimed it where they died (off a falling tile, say): their
    death's. Otherwise whichever of them alone at their seat would have cleared it (the victim from the laser as it
    fired, the holder by aiming it from theirs); either way, whoever's seat clears it by more (the lasers are angled: a
    step of the holder's moves the line less near the add), both within 0.5 y of each other (low)."""
    nm, a, _, ws = laser
    if gone_before(p, t, o, laser):
        return fault(t, "Paradeigma III", [o], [v], f"{o} died before their tether laser landed; aimed where they died, it hit {v}", "consequence", chain=[o], tag="p3.tether.dead_holder")
    pv, po = ws.get(v), ws.get(o)
    if not (a and pv and po and v in seat and o in seat):
        return fault(t, "Paradeigma III", [v], [v], f"stood in {o}'s tether laser", "medium", tag="p3.tether.stood_in")
    dv, do = math.dist(pv, seat[v][0]), math.dist(po, seat[o][0])
    how = f"({v} {dv:.1f} y off their seat, {o} {do:.1f})"
    vgap, ogap = line_off(a, po, seat[v][0]), line_off(a, seat[o][0], pv)   # the victim's distance from the line, either seated
    vfix, ofix = vgap > TETHER_HALF, ogap > TETHER_HALF
    if vfix and ofix and abs(vgap - ogap) > unc(0, 0): vfix, ofix = vgap > ogap, ogap > vgap   # clearer by more than the log can tell
    if vfix and not ofix: return fault(t, "Paradeigma III", [v], [v], f"stood in {o}'s tether laser, off their seat {how}", sure(vgap), tag="p3.tether.stood_in")
    if ofix and not vfix: return fault(t, "Paradeigma III", [o], [v], f"{o}: off their seat, their tether laser hit {v} {how}", sure(ogap), tag="p3.tether.holder_off")
    return fault(t, "Paradeigma III", [v, o], [v], f"{v} and {o}: both off their seats, {o}'s tether laser hit {v} {how}", "low", tag="p3.tether.holder_off",
                 share="one_of" if vfix and ofix else "own")   # either alone would have cleared it: one mistake, whose cannot be told


def tether_clip(p, e, laser, seat):
    """A support clipped by a DPS tether laser: theirs (the outer gap the seated lasers leave on the tower), unless the
    laser, its holder at their seat, would have missed them where they stood: the holder's then; within the log's error
    of its reach either way, undecided (both, low)."""
    t, v = e["t"], e["who"]
    nm, a, o, ws = laser or (None,) * 4
    if o and a and o in seat and ws.get(o) and (pv := ws.get(v) or e["pos"]):
        if gone_before(p, t, o, laser):
            return fault(t, "Paradeigma III", [o], [v], f"{o} died before their tether laser landed; aimed where they died, it clipped {v}", "consequence", chain=[o], tag="p3.tether.dead_holder")
        if abs((gap := line_off(a, seat[o][0], pv)) - TETHER_HALF) < unc(0):   # the seat clears them by less than the log can tell, or misses by less
            return fault(t, "Paradeigma III", [v, o], [v], f"could not be decided whose: {o}'s tether laser from their seat would have passed {gap:.1f} y from {v}, "
                         f"at its reach ({TETHER_HALF:g} y) within what the log can tell ({o} {math.dist(ws[o], seat[o][0]):.1f} y off their seat)", "low", tag="p3.tether.undecided")
        if gap > TETHER_HALF:
            return fault(t, "Paradeigma III", [o], [v], f"{o}: off their seat, their tether laser hit {v} at the tower ({o} {math.dist(ws[o], seat[o][0]):.1f} y off their seat)", sure(gap), tag="p3.tether.holder_off")
        # the holder's seat would not have cleared them: theirs, as sure as that laser would still have reached them
        return fault(t, "Paradeigma III", [v], [v], "a DPS tether laser clipped them (soak from the tower's outer side)", certainty(TETHER_HALF - gap, unc(0)), tag="p3.tether.clipped")
    return fault(t, "Paradeigma III", [v], [v], "a DPS tether laser clipped them (soak from the tower's outer side)", "high", tag="p3.tether.clipped")


def dead_soul(p, souls, glow, t):
    """A Glow that hits no living holder of its Soul is a dead holder's tower dropped on someone else: in every cached
    pull, such a Glow came after a holder of its colour died and hit one player. The dead holders of its colour."""
    asp = glow.split()[0]
    return sorted(w for w, a in souls.items() if a == asp and w in p.dead_by(t - 0.2))


# ---------- Paradeigma II: tethers, quadrant sweep, towers ----------
# Replayed from Pull.p2 (scorecard.fetch_p2; scratch/para2audit, 2026-10-28). A tether laser's holder is its cast's
# target, else its add's last tether (a laser through two players logs no target); the classifier's guess (the one
# hit furthest out) was wrong 7 times and found none 31. The adds stand 3 y off each cardinal at the wall and their
# holders stretch straight across: off that line past P2_LINE_TOL (90% of clean pulls within), and their own laser is
# lethal nearer than P2_STRETCH y to the add's wall (no holder lived nearer, 2,689 lasers; the five who died further
# out were low on HP). A laser hits within TETHER_HALF of the line from its add through its holder (2,650 of 2,711
# reproduced from the positions at the calculated hits), past the holder too; its edge looks soft by the logged positions' error (half of
# those 2.5-3 y from it were hit: unc). A Soul stands P2_SOUL_R out on their sweep quadrant's diagonal (the median), off
# it past P2_SOUL_TOL as the lasers land (90%). Their tower drops there: off its spot past P2_OFF (90% of soaked towers
# within), and soakers came from within P2_REACH of it as the lasers landed (99%). With the party short, the game gives
# a Soul holder a tether too (never with all 8 alive, 764 pulls).
P2_LINE_TOL, P2_STRETCH, P2_SOUL_R, P2_SOUL_TOL, P2_OFF, P2_REACH = 1.75, 34.5, 13.24, 2.5, 2.6, 10.7
P2_DIAG = {"NE": (1, -1), "SE": (1, 1), "SW": (-1, 1), "NW": (-1, -1)}


def p2_spot(q):
    """Where a Soul sent to quadrant q stands and drops their tower."""
    return P2_DIAG[q][0] * P2_SOUL_R / 2 ** .5, P2_DIAG[q][1] * P2_SOUL_R / 2 ** .5


def p2_frame(add, pos):
    """(across, side) of pos from a tether add: y across the arena from its wall, and y off its straight line."""
    ax, ay = add
    if abs(ax) > abs(ay): return (pos[0] - ax) * -math.copysign(1, ax), pos[1] - ay
    return (pos[1] - ay) * -math.copysign(1, ay), pos[0] - ax


def p2_straight(add, across):
    """The point straight across from an add, `across` y from its wall."""
    ax, ay = add
    return (ax - math.copysign(across, ax), ay) if abs(ax) > abs(ay) else (ax, ay - math.copysign(across, ay))


def p2_ray(a, b, q):
    """Distance from q to the laser from a through b (from a on, past b)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1
    if (q[0] - a[0]) * dx + (q[1] - a[1]) * dy < 0: return math.dist(a, q)
    return abs((q[0] - a[0]) * dy - (q[1] - a[1]) * dx) / n


def p2_lasers(p):
    """{(laser name, add instance): (add (x, y), holder or None, cast time)} from Pull.p2, or {} without it."""
    out = {}
    for t, nm, inst, tgt, x, y in (p.p2 or {}).get("casts", ()):
        if nm not in ("Searing Radiance", "Shadowsear") or t < 74: continue
        last = [pid for tt, i, pid in p.p2["tethers"] if i == inst and tt <= t]
        out[(nm, inst)] = ((x, y), p.players.get(tgt) or (p.players.get(last[-1]) if last else None), t)
    return out


def p2_tether_fix(add, h, hq, v, vq, spot, tol, gh=0, gv=0):
    """Whose move alone to their spot would have taken `v` (at vq) out of `h`'s tether laser: h's to their add's
    straight line (as far across as they stood), or v's to `spot` (off it past `tol`). (culprits, confidence, why, tag)
    as for Superchain I's lasers: both would, the one off their spot; both when both are; when neither is, or the
    deciding move leaves them nearer the laser's edge than the log can tell (unc of the two positions, read gh and gv s
    from their samples), it cannot be decided (both, low). Neither alone: both. Confidence: the deciding margin against
    the log's error (certainty)."""
    u = unc(gh, gv)
    across, side = p2_frame(add, hq)
    d = {h: p2_ray(add, p2_straight(add, across), vq), v: p2_ray(add, hq, spot) if spot else 0}
    off = {h: abs(side), v: math.dist(vq, spot) if spot else 0}
    lim = lambda x: P2_LINE_TOL if x == h else tol
    far = lambda x: off[x] > lim(x)
    at = lambda x: f"{x} {off[x]:.1f} y off {'their line' if x == h else 'their spot'}"
    facts = f"{at(v)}, {at(h)}"
    opts = [x for x in (v, h) if d[x] > TETHER_HALF]
    if len(opts) == 2:
        out = [x for x in opts if far(x)]
        if not out: return [v, h], "low", f"could not be decided who stood in whose tether laser: either at their spot would have cleared it ({facts})", "p2.tether.undecided"
        if len(out) == 2:
            return [v, h], least_sure([certainty(off[x] - lim(x), unc(gh if x == h else gv)) for x in out]),                 f"stood in {h}'s tether laser, both away from their spots: either back would have cleared it ({facts})", "p2.tether.stood_in"
        opts = out
    if len(opts) == 1:
        x = opts[0]
        if d[x] - TETHER_HALF < u: return [v, h], "low", f"could not be decided who stood in whose tether laser: at its edge ({facts})", "p2.tether.undecided"
        conf = certainty(d[x] - TETHER_HALF, u)
        return ([v], conf, f"stood in {h}'s tether laser ({facts})", "p2.tether.stood_in") if x == v else ([h], conf, f"{h}: off their line, their tether laser hit {v} ({facts})", "p2.tether.holder_off")
    return [v, h], least_sure([certainty(TETHER_HALF - d[x], u) for x in (v, h)]),         f"stood in {h}'s tether laser, and neither alone at their spot would have cleared it ({facts})", "p2.tether.stood_in"


def para2_tethers(p, souls, by, P2, teth):
    """Paradeigma II's tether lasers with their holders known (p2_lasers): each holder's Tilt and place into `teth` for
    the sweep; the faults. A holder killed by their own laser nearer than P2_STRETCH did not stretch it (further out,
    their HP did not hold: no fault); one holding a Soul too was given both by the game, the party short (the deaths
    that left it short are blamed for what their laser hit). Anyone else it hit: a holder dead by then is that death's;
    otherwise p2_tether_fix (a Soul's spot by the sweep, a holder's
    their own add's straight line)."""
    out = []
    t_l = min(t for _, _, t in P2.values())
    dead = p.dead_by(t_l)
    hq = {h: q for add, h, t in P2.values() if (q := track_at(p, p.p2["pos"], h, t))}   # (position, s from its sample)
    at = {h: q[0] for h, q in hq.items()}
    own = {h: add for add, h, _ in P2.values()}
    for (nm, inst), (add, h, t) in P2.items():
        if h not in dead and h in at: teth[h] = ("Umbral" if nm == "Searing Radiance" else "Astral", at[h])
    tq = {quad(pos): tilt for w, (tilt, pos) in teth.items()}

    def spot_of(v, vq):
        if v in souls:
            order = ["NE", "SE", "SW", "NW"] if p.job.get(v) in SUPPORT_JOBS else ["NW", "SW", "SE", "NE"]
            q = next((q for q in order if tq.get(q) == OPP[souls[v]]), None)
            return (p2_spot(q) if q else None), P2_SOUL_TOL
        return (p2_straight(own[v], p2_frame(own[v], vq)[0]) if v in own else None), P2_LINE_TOL
    # a Soul holder holds a tether only with the party short: dead as the game handed out four Souls and four tethers
    # (raised by the lasers or not), or a tether's holder dead since (it goes to someone else: only Soul holders are left)
    first = min((tt for tt, *_ in p.p2["tethers"]), default=t_l)
    short = sorted(p.dead_by(first) | dead)
    for (nm, inst), (add, h, t) in P2.items():
        es = [e for e in by.get((nm, inst), ()) if e["pos"]]
        if h in souls and short:   # the game gave a Soul holder a tether too: the party was short
            out.append(fault(t, "Paradeigma II", short, [h], f"{h} held a Soul and a tether both: the party was short ({', '.join(short)} already dead)", "consequence", chain=short, ability=nm, tag="p2.soul_and_tether"))
        mine = next((e for e in es if e["who"] == h), None)
        if mine and not (h in souls and short) and (mine.get("targetResources") or {}).get("hitPoints") == 0 and (h not in at or p2_frame(add, at[h])[0] < P2_STRETCH):
            how = f" ({p2_frame(add, at[h])[0]:.1f} y across, lethal under {P2_STRETCH:g})" if h in at else ""
            out.append(fault(mine["t"], "Paradeigma II", [h], [h], f"died to their own tether laser (not stretched far enough){how}", "high", tag="p2.tether.not_stretched"))
        for e in es:
            v = e["who"]
            if v == h: continue
            if h in dead:
                out.append(fault(e["t"], "Paradeigma II", [h], [v], f"a tether laser hit {v} because its holder was already dead ({h})", "consequence", chain=[h], tag="p2.tether.dead_holder"))
                continue
            if h in souls and short:   # a holder with a Soul to drop too cannot be on both spots
                out.append(fault(e["t"], "Paradeigma II", short, [v], f"{h} held a Soul and a tether both, the party short ({', '.join(short)} already dead); their laser hit {v}",
                                 "consequence", chain=short, ability=nm, tag="p2.soul_and_tether"))
                continue
            vq = track_at(p, p.p2["pos"], v, t)
            spot, tol = spot_of(v, vq[0]) if vq else (None, 0)
            r = p2_tether_fix(add, h, at[h], v, vq[0], spot, tol, hq[h][1], vq[1]) if h in at and vq and spot else None
            out.append(fault(e["t"], "Paradeigma II", r[0], [v], r[2], r[1], tag=r[3]) if r else fault(e["t"], "Paradeigma II", [v], [v], f"stood in {h}'s tether laser", "medium", tag="p2.tether.stood_in"))
    return out


def p2_unsoaked(p, w, asp, sk, q, drop):
    """Whose an unsoaked tower in its sweep quadrant was, by where it dropped (its Advance cast, Pull.p2) and where its
    soaker stood as the lasers landed, as for Superchain I's: on its spot (within P2_OFF) the soaker's; off it but
    within the soaker's reach (P2_REACH), it cannot be pinned on either alone (both, low); out of their reach with its
    spot in it, the dropper's; neither in reach, both. Confidence: the margins past P2_OFF and P2_REACH against the log's
    error for the soaker's position (certainty). (culprits, confidence, why, tag), or None without positions."""
    tws = [(x, y) for t, nm, inst, tgt, x, y in (p.p2 or {}).get("casts", ()) if nm == f"{asp} Advance" and t >= 78]
    L = p2_lasers(p)
    sq = track_at(p, p.p2["pos"], sk, min(t for *_, t in L.values())) if tws and L else None
    if not sq: return None
    tw = min(tws, key=lambda z: math.dist(z, drop))
    want = p2_spot(q)
    off, d, dp = math.dist(tw, want), math.dist(sq[0], tw), math.dist(sq[0], want)
    facts = f"it dropped {off:.1f} y from its spot, {sk} {d:.1f} y from it and {dp:.1f} from the spot as the lasers landed"
    us = unc(sq[1])   # the soaker's position; the tower's and its spot's are the game's own
    if off <= P2_OFF: return [sk], certainty(P2_OFF - off, unc(0)), f"did not soak {w}'s tower in {q} ({facts})", "p2.tower.unsoaked"
    if d <= P2_REACH: return [sk, w], "low", f"{w}'s tower unsoaked, undecided: {w} dropped it off its spot, but {sk} could still reach it ({facts})", "p2.tower.undecided"
    if dp <= P2_REACH: return [w], least_sure([certainty(d - P2_REACH, us), certainty(P2_REACH - dp, us)]), f"{w}'s tower unsoaked: {w} dropped it out of {sk}'s reach ({facts})", "p2.tower.out_of_reach"
    return [sk, w], least_sure([certainty(d - P2_REACH, us), certainty(dp - P2_REACH, us)]), f"{w}'s tower unsoaked, both away from it ({facts})", "p2.tower.unsoaked"


def para2(p):
    out = []
    souls = {}
    for asp in ("Astral", "Umbral"):
        for w in p.holders(f"{asp}bright Soul", 60, 72): souls[w] = asp
    if not souls: return out
    # tether lasers: Searing Radiance -> Umbral Tilt, Shadowsear -> Astral Tilt
    # the four players without a Soul hold the tethers, so a laser that hit only Soul holders lost its holder: dead
    # (the tether went to someone else) or not where the line ran (the Soul holder stood in it, or took the tether)
    teth, by = {}, collections.defaultdict(list)
    las = p.hits(("Searing Radiance", "Shadowsear"), 74, 78.5)
    for e in las: by[(e["name"], e.get("sourceInstance"))].append(e)
    tethered = [w for w in p.job if w not in souls]
    gone = sorted(w for w in tethered if w in p.dead_by(las[0]["t"] - 0.3)) if las else []
    unhit = [w for w in tethered if w not in gone and w not in {e["who"] for e in las}]
    P2 = p2_lasers(p)
    # a Soul holder also holding a tether (the party short) cannot drop their Soul where the sweep says and stretch their
    # tether too: their tower's failure is the deaths' that left the party short, as their laser's is (para2_tethers)
    forced = {h for _, h, _ in P2.values() if h in souls} if P2 and all(h for _, h, _ in P2.values()) else set()
    short = sorted(p.dead_by(min((tt for tt, *_ in p.p2["tethers"]), default=74)) | p.dead_by(min(t for *_, t in P2.values()))) if forced else []
    forced = forced if short else set()
    if P2 and all(h for _, h, _ in P2.values()):   # the holders known: the lasers replayed
        out += para2_tethers(p, souls, by, P2, teth)
        by = {}
    for (nm, inst), es in by.items():
        es = [e for e in es if e["pos"]]
        if not es: continue
        held = [e for e in es if e["who"] not in souls]
        holder = max(held, key=lambda e: math.hypot(*e["pos"])) if held else None   # the stretched player is furthest out
        # the sweep reads the laser's quadrant and colour, and whoever it hit took its Tilt, holder or not
        far = holder or max(es, key=lambda e: math.hypot(*e["pos"]))
        teth[far["who"]] = ("Umbral" if nm == "Searing Radiance" else "Astral", far["pos"])
        if holder:
            if (holder.get("targetResources") or {}).get("hitPoints") == 0:
                out.append(fault(holder["t"], "Paradeigma II", [holder["who"]], [holder["who"]], "died to their own tether laser (not stretched far enough)", "high", tag="p2.tether.not_stretched"))
        for e in es:
            if e is holder: continue
            if holder:
                out.append(fault(e["t"], "Paradeigma II", [e["who"]], [e["who"]], f"stood in {holder['who']}'s tether laser", "medium", tag="p2.tether.stood_in"))
            elif gone and not unhit:
                out.append(fault(e["t"], "Paradeigma II", gone, [e["who"]], f"a tether laser hit {e['who']} because its holder was already dead ({', '.join(gone)})", "consequence", chain=gone, tag="p2.tether.dead_holder"))
            else:
                out.append(fault(e["t"], "Paradeigma II", [e["who"]], [e["who"]], "holding a Soul, stood in a tether laser's line (or took the tether)" +
                                 (f"; {', '.join(unhit)}'s laser hit no one else" if unhit else ""), "medium", tag="p2.tether.stood_in"))
    tq = {quad(pos): (w, tilt) for w, (tilt, pos) in teth.items()}
    # where each Soul dropped (own Glow hit) and where it should have dropped
    glow = p.hits(("Astral Glow", "Umbral Glow"), 76, 79)
    sp, expq, wrong = {}, {}, set()
    for w, asp in souls.items():
        own = [e for e in glow if e["who"] == w and e["pos"]]
        if not own: continue
        sp[w] = own[0]["pos"]
        order = ["NE", "SE", "SW", "NW"] if p.job.get(w) in SUPPORT_JOBS else ["NW", "SW", "SE", "NE"]
        expq[w] = next((q for q in order if q in tq and tq[q][1] == OPP[asp]), None)
        if expq[w] and quad(sp[w]) != expq[w]: wrong.add(w)
    # Glow AoEs hitting other players
    gi = collections.defaultdict(list)
    for e in glow: gi[(e["name"], e.get("sourceInstance"))].append(e["who"])
    for (nm, inst), ws in gi.items():
        owner = next((w for w in ws if w in souls), None)
        if owner is None and (gone := dead_soul(p, souls, nm, min(e["t"] for e in glow))):
            for v in ws: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", gone, [v], f"{' and '.join(gone)} died holding a Soul; its tower dropped on {v}", "consequence", chain=gone, tag="p2.tower.soul_dead"))
            continue
        for v in ws:
            if v == owner: continue
            if owner in wrong: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [owner], [v, owner], f"dropped their Soul in {quad(sp[owner])} instead of {expq[owner]}; its AoE hit {v}", "high", tag="p2.soul.wrong_quadrant"))
            elif v in wrong: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [v], [v], f"dropped their Soul in {quad(sp[v])} instead of {expq[v]} (inside {owner}'s AoE)", "high", tag="p2.soul.wrong_quadrant"))
            else: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [v], [v], f"stood in {owner + chr(39) + 's' if owner else 'a'} Soul AoE", "medium", tag="p2.soul_aoe"))
    # towers: Astral/Umbral Advance = soak of the Astral/Umbral-bright tower
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 79, 82)
    expl = p.hits("Unmitigated Explosion", 81, 86)
    used = set()
    boom = dict(ability="Unmitigated Explosion")
    # whose tower each soak was in: the nearest Soul of its colour that dropped within a tower's radius
    owner_of = {id(e): min(ws, key=lambda w: math.dist(e["pos"], sp[w])) for e in soaks if e["pos"]
                for ws in [[w for w in sp if e["name"].startswith(souls[w]) and math.dist(e["pos"], sp[w]) < 3.6]] if ws}
    for w, asp in souls.items():
        if w not in sp:   # died holding the Soul: its tower dropped on someone else (see dead_soul), and nobody soaks it
            if expl and w in p.dead_by(77):
                out.append(fault(soaks[0]["t"] if soaks else 80.2, "Paradeigma II", [w], {e["who"] for e in expl},
                                 f"{w} died holding a Soul; its tower went unsoaked", "consequence", chain=[w], **boom, tag="p2.tower.soul_dead"))
            continue
        cand = [e for e in soaks if e["name"].startswith(asp) and e["pos"] and id(e) not in used and math.dist(e["pos"], sp[w]) < 3.6]   # tower radius ~3.5 y (max 3.46 in clean soaks)
        if cand:
            s = min(cand, key=lambda e: math.dist(e["pos"], sp[w])); used.add(id(s))
            if s["who"] in souls:
                out.append(fault(s["t"], "Paradeigma II", ([w] if w in wrong else []) + [s["who"]], [s["who"]],
                                 f"soaked {w}'s tower while holding a Soul" + (f" ({w} dropped it in the wrong quadrant)" if w in wrong else ""), "high", tag="p2.tower.wrong_quadrant" if w in wrong else "p2.tower.wrong_player"))
            elif teth.get(s["who"], (None,))[0] == asp:   # it explodes (15 of 15): the explosion is theirs, and a misplaced dropper's
                out.append(fault(s["t"], "Paradeigma II", ([w] if w in wrong else []) + [s["who"]], {s["who"]} | {e["who"] for e in expl},
                                 f"soaked {w}'s {asp} tower with the same-colour Tilt" + (f" ({w} dropped it in {quad(sp[w])}, sweep says {expq[w]})" if w in wrong else ""),
                                 "high", **(boom if expl else {}), tag="p2.tower.wrong_quadrant" if w in wrong else "p2.tower.wrong_player"))
            continue
        # unsoaked tower (timed at the soak moment so the soakers' own deaths link to it too)
        t = soaks[0]["t"] if soaks else 80.2
        if w in forced:
            out.append(fault(t, "Paradeigma II", short, {e["who"] for e in expl}, f"{w}'s tower unsoaked: {w} held a Soul and a tether both, the party short "
                             f"({', '.join(short)} already dead)", "consequence", chain=short, **boom, tag="p2.soul_and_tether"))
        elif w in wrong:
            out.append(fault(t, "Paradeigma II", [w], {e["who"] for e in expl} | {w}, f"{w}'s tower unsoaked: dropped in {quad(sp[w])}, sweep says {expq[w]}", "high", **boom, tag="p2.tower.wrong_quadrant"))
        elif expq.get(w) in tq:
            sk = tq[expq[w]][0]
            # its soaker soaked a tower of the same colour that another Soul dropped in this quadrant, off the sweep: theirs
            elsewhere = sorted({owner_of[id(e)] for e in soaks if e["who"] == sk and e["name"].startswith(asp) and owner_of.get(id(e)) in wrong and owner_of[id(e)] != w})
            if sk in p.dead_by(80): out.append(fault(t, "Paradeigma II", [sk], {e["who"] for e in expl}, f"tower unsoaked because {sk} was already dead", "consequence", chain=[sk], **boom, tag="p2.tower.unsoaked"))
            elif elsewhere:
                out.append(fault(t, "Paradeigma II", elsewhere, {e["who"] for e in expl} | set(elsewhere), f"{w}'s tower unsoaked: {' and '.join(elsewhere)} dropped "
                                 f"{'theirs' if len(elsewhere) == 1 else 'their towers'} in {expq[w]} off the sweep (sweep says {', '.join(expq[x] for x in elsewhere)}), "
                                 f"and {sk} soaked that one", "high", **boom, tag="p2.tower.wrong_quadrant"))
            else:
                cul, conf, why, tg = p2_unsoaked(p, w, asp, sk, expq[w], sp[w]) or ([sk], "high", f"did not soak {w}'s tower in {expq[w]}", "p2.tower.unsoaked")
                out.append(fault(t, "Paradeigma II", cul, {e["who"] for e in expl} | set(cul), why, conf, **boom, tag=tg))
        else:
            out.append(fault(t, "Paradeigma II", [], {e["who"] for e in expl}, f"{w}'s tower unsoaked; soaker could not be determined", "low", **boom, tag="p2.tower.unsoaked"))
    # one player soaking two towers: the towers were dropped on top of each other
    for who, n in collections.Counter(s["who"] for s in soaks).items():
        if n < 2: continue
        sp_ = [s["pos"] for s in soaks if s["who"] == who and s["pos"]][0]
        stacked = [w for w in sp if math.dist(sp[w], sp_) < 9]
        bad = [w for w in stacked if w in wrong]
        out.append(fault(soaks[0]["t"], "Paradeigma II", bad or [who], {who},
                         f"two towers dropped in one quadrant ({', '.join(stacked)}); {who} soaked both" + (f"; sweep puts {bad[0]} in {expq[bad[0]]}" if bad else ""), "high" if bad else "medium", tag="p2.tower.wrong_quadrant"))
    # explosion with no tower explained: blame Souls that broke the sweep
    if expl and not any(f["tag"].startswith("p2.tower.") for f in out):
        out.append(fault(soaks[0]["t"] if soaks else 80.2, "Paradeigma II", sorted(wrong), {e["who"] for e in expl},
                         "tower exploded; " + (f"Soul dropped off-sweep: {', '.join(f'{w} in {quad(sp[w])} (sweep {expq[w]})' for w in sorted(wrong))}" if wrong else "cause unclear"), "medium" if wrong else "low", **boom, tag="p2.tower.wrong_quadrant" if wrong else "p2.tower.unclear"))
    # soaks that matched no tower: extra player in a tower, a Soul holder, or the same-colour Tilt
    for s in soaks:
        if id(s) in used: continue
        asp = s["name"].split()[0]
        near = min((w for w in souls if souls[w] == asp and w in sp), key=lambda w: math.dist(sp[w], s["pos"]) if s["pos"] else 99, default=None)
        why = "while holding a Soul" if s["who"] in souls else ("with the same-colour Tilt" if teth.get(s["who"], (None,))[0] == asp else "as an extra soaker")
        out.append(fault(s["t"], "Paradeigma II", ([near] if near in wrong else []) + [s["who"]], [s["who"]],
                         f"stepped into {near or 'a'}'s {asp} tower {why}" + (f" ({near} dropped it in the wrong quadrant)" if near in wrong else ""), "high", tag="p2.tower.wrong_quadrant" if near in wrong else "p2.tower.wrong_player"))
    return out


# ---------- Paradeigma III: platforms, support towers, DPS tethers, bright towers, + / X, White Flame ----------
# ---------- Glaukopis: the tank swap ----------
SNAPSHOT = 1.2   # the boss picks its next target this long after a hit: the provoke has to land by then
def glaukopis(p, lo, hi):
    """Glaukopis hits the tank holding aggro when its cast begins and gives them Magic Vulnerability Up; 3.1 s later
    it hits whoever holds aggro SNAPSHOT s after the first hit, and 3.2 s after that a heavy auto-attack (~290k
    unmitigated) lands on whoever holds aggro SNAPSHOT s after the second. Our groups' swap: the second tank provokes
    during the cast, the first provokes back as the second hit lands. Measured on our pulls: a provoke back up to 1.1 s
    after the first hit put the second hit on the same tank, from 1.2 s it did not; after the second hit, 494 provokes
    back by 1.2 s took the auto-attack, in every death to it the provoke came from 1.3 s or never. A tank who takes both
    hits and lives meant to (invulnerability), so only a death is a mistake.
    Each hit is a line from Athena through its target, 5 y wide (the game's data, Action 33532-33533): a non-tank hit
    with a tank stood in it (3 of 575 casts: one between Athena and the tank, one on top of Athena), their own mistake.
    A non-tank hit with no tank beside them, every tank dead, took it because no one was left to hold Athena: whoever
    caused the tanks' deaths."""
    out = []
    g = p.hits("Glaukopis", lo, hi)
    if not g: return out
    mech, is_tank = mech_at(g[0]["t"]), lambda w: p.job.get(w) in TANK_JOBS
    th = [e for e in g if is_tank(e["who"])]
    tanks = [w for w in p.job if is_tank(w)]
    gone = sorted(w for w in tanks if w in p.dead_by(g[0]["t"] - 0.3))
    for e in g:
        if is_tank(e["who"]): continue
        if any(abs(x["t"] - e["t"]) <= 0.3 for x in th):
            out.append(fault(e["t"], mech, [e["who"]], [e["who"]], "stood in the Glaukopis line (a tankbuster from Athena through the tank)", "high", ability="Glaukopis", tag="glauk.line"))
        elif gone and len(gone) == len(tanks):
            out.append(fault(e["t"], mech, gone, [e["who"]], f"Glaukopis hit {e['who']} because no tank was left to hold Athena ({', '.join(gone)} already dead)",
                             "consequence", chain=gone, ability="Glaukopis", tag="glauk.tanks_dead"))
    h1 = th[0] if th else None
    h2 = next((e for e in th if e["t"] > h1["t"] + 1.5), None) if th else None
    if not h2: return out
    a = h1["who"]
    b = next((w for w, j in p.job.items() if j in TANK_JOBS and w != a), None)
    if b is None: return out
    lethal = lambda e: (e.get("targetResources") or {}).get("hitPoints") == 0
    if h2["who"] == a:
        if not lethal(h2): return out
        t, snap = h2["t"], h1["t"] + SNAPSHOT
        if b in p.dead_by(t - 0.3):
            out.append(fault(t, mech, [b], [a], f"{a} took both Glaukopis hits because {b} was already dead", "consequence", chain=[b], tag="glauk.swap"))
        elif p.casts is None:
            out.append(fault(t, mech, [a, b], [a], "no tank swap between the Glaukopis hits: the second hit the vulnerable tank", "medium", tag="glauk.swap", share="one_of"))
        elif back := p.cast_at(a, "Provoke", h1["t"] - 1, snap):
            out.append(fault(t, mech, [a], [a], f"provoked back {back[-1] - h1['t']:+.1f} s from the first Glaukopis, before the second "
                             f"(from +{SNAPSHOT} s): it hit them again with the vulnerability", certainty(snap - back[-1], TIME_ERR), tag="glauk.swap"))
        elif not (pb := p.cast_at(b, "Provoke", h1["t"] - 10, snap)):
            out.append(fault(t, mech, [b], [a], f"did not provoke for the Glaukopis swap; {a} took the second hit with the vulnerability", "high", tag="glauk.swap"))
        else:
            out.append(fault(t, mech, [a, b], [a], f"{b} provoked {pb[-1] - h1['t']:+.1f} s from the first Glaukopis, but {a} held aggro "
                             "for the second (the provoke too early, or a Shirk missing)", "medium", tag="glauk.swap", share="one_of"))
        return out
    # the swap worked: the heavy auto-attack after the second hit has to go back to the first tank
    auto = next((e for e in p.dmg if e["name"] == "attack" and h2["t"] + 2 < e["t"] < h2["t"] + 4.5), None)
    if not auto or auto["who"] != h2["who"] or not lethal(auto) or p.job.get(h2["who"]) not in TANK_JOBS: return out
    t, v = auto["t"], h2["who"]
    if a in p.dead_by(t - 0.3):
        out.append(fault(t, mech, [a], [v], f"the auto-attack after the second Glaukopis killed {v} because {a} was already dead", "consequence", chain=[a], tag="glauk.swap"))
    elif p.casts is None:
        out.append(fault(t, mech, [a], [v], f"did not take the boss back after the second Glaukopis; its auto-attack killed {v} through the vulnerability", "medium", tag="glauk.swap"))
    else:
        back = p.cast_at(a, "Provoke", h2["t"] - 1, t)
        when = f"provoked back {back[0] - h2['t']:+.1f} s from the second Glaukopis, too late (by +{SNAPSHOT} s)" if back else "did not provoke back after the second Glaukopis"
        out.append(fault(t, mech, [a], [v], f"{when}: the auto-attack after it killed {v} through the vulnerability",
                         certainty(back[0] - h2["t"] - SNAPSHOT, TIME_ERR) if back else "high", tag="glauk.swap"))
    return out


BRIGHT_PRIORITY = ("H1", "T1", "T2", "H2")   # bright Souls' middle platforms, east to west (from 2026-10-26)


def bright_seat_lp(s1, s2):
    """The 2026-10-25 rule for the bright Souls' middle platforms (the raidplan then, briefs b238cf0): LP1 the northern,
    LP2 the southern; both in one light party, the healer keeps theirs and the tank takes the other. s1, s2: their seats
    ("H1", "T2", ...). Whether each belongs on the northern one: (s1's, s2's)."""
    if s1[1] != s2[1]: return s1[1] == "1", s2[1] == "1"
    keeps = s1[0] == "H"   # same party: the healer keeps their party's side
    return (s1[1] == "1") == keeps, (s1[1] == "1") != keeps


def seats(p, lp):
    """{"T1": name, "H1": ..., "T2": ..., "H2": ...} from the light parties (light party 1 baits Paradeigma I's first wave)."""
    out = {}
    for n, party in ((1, lp[0]), (2, lp[1])):
        for w in sorted(party):
            role = "T" if p.job.get(w) in TANK_JOBS else "H" if p.job.get(w) in HEALER_JOBS else None
            if role: out.setdefault(f"{role}{n}", w)
    return out


# Paradeigma III's spots by the plan (briefs.html#para3). The platforms alternate columns, so the north platform's column
# (its x sign, p3_column) places the rest: the yellow adds between the tiles at (c * 10, -10.5) and (-c * 10, 10.5), the
# + at the north platform's outer corner, the X at the south wall's middle. Since 2026-10-25 every + and X landed within
# 1.6 y of its spot or 5.7-16 y off it (scratch/review/p3_crossx.py): past P3_CROSS_OFF it was dropped off its spot.
P3_ADD, P3_CROSS_OFF = (10.0, 10.5), 3.0
# A bright tower takes whoever stands within P3_TOWER_R of it (the game's data, Action 33550-33551; a player is a point).
# The centre tower is soaked from the other middle platform, which meets its own only at the arena centre: it has to
# reach P3_ACROSS[0] y past the centre to be humanly reachable from there, and reaching less than P3_ACROSS[1] it is not
# (the user's ruling, 2026-10-28; every soak from the other platform was of a tower within 2.0 y of the centre); between
# the two it cannot be decided whether its soaker could have.
P3_TOWER_R, P3_ACROSS = 3.0, (1.0, 0.5)


def p3_column(seat, spos, quartered):
    """The north platform's column (+1 east, -1 west): the DPS seats' north middle platform lies in the other one; else
    where the + support soaked their tower. None when neither tells."""
    xs = [-math.copysign(1, s[0][0]) for s in seat.values() if s[0][1] < 0]
    if xs: return xs[0]
    q = next((spos[w] for w in quartered if w in spos and spos[w][1] < -8), None)
    return math.copysign(1, q[0]) if q else None


P3_WF_TIE = 2.0   # y: a split of the lasers between the adds that fits within this of the best one cannot be told from it


def p3_split(calc, col):
    """Which add fired each of Paradeigma III's White Flame lasers (calc: their calculated hits): (best split's cost, the
    runner-up's that gives some laser the other add, or None, [the lasers' hits], [each laser's add by the best split],
    [by the runner-up]). A laser fits an add by its logged source when that is the add's (in some pulls it is, in others
    a stale spot), else by its target's distance from the add (the player in it nearest the add), with everyone else it
    hit on the ray from the add through them (a laser runs on past its target: awWM pull 20's went through two). Each add
    fires two, so with four lasers the splits are two and two (a player halfway between the adds cannot be placed by
    distance alone)."""
    adds = {"northern": (col * P3_ADD[0], -P3_ADD[1]), "southern": (-col * P3_ADD[0], P3_ADD[1])}
    lasers = collections.defaultdict(list)
    for e in calc: lasers[e.get("sourceInstance")].append(e)
    ls = list(lasers.values())

    def cost(es, k):
        src = next(((sr["x"] / 100 - 100, sr["y"] / 100 - 100) for e in es if (sr := e.get("sourceResources")) and "x" in sr), None)
        at = next((a for a, q in adds.items() if src and math.dist(src, q) < 1.5), None)
        if at: return 0 if at == k else 1e6
        tg = min(es, key=lambda e: math.dist(adds[k], e["pos"]))
        off = max((p2_ray(adds[k], tg["pos"], e["pos"]) for e in es), default=0)
        return math.dist(adds[k], tg["pos"]) + (1e3 if off > WF_FLAME + 1 else 0)
    if len(ls) == 4: splits = [["northern" if i in c else "southern" for i in range(4)] for c in itertools.combinations(range(4), 2)]
    else: splits = [list(ks) for ks in itertools.product(adds, repeat=len(ls))]
    scored = sorted((sum(cost(es, k) for es, k in zip(ls, ks)), ks) for ks in splits)
    best = scored[0]
    second = next(((c, ks) for c, ks in scored[1:] if ks != best[1]), (None, None))
    return best[0], second[0], ls, best[1], second[1]


def p3_white_flame(p, t, sup, match, seat, col, spos):
    """Paradeigma III's White Flame per add: the + and X supports each bait the add on their platform's edge with the
    middle (the northern add from the north platform; chained to their tile, a support on the other one's platform can
    only bait that one's add, a separate mistake), and of the matching DPS pair the straight tether the add in its own
    column, the crossed one the add across (16 of 16 clean baits, scratch/review/p3_wfseats.py). Which add fired each
    laser: p3_split; where another split fits within P3_WF_TIE, a laser the two give different adds counts for both, and
    whoever it blames is undecided (low). An add's laser through anyone else is its missing baiter's, or a dead baiter's
    death's; with neither, those it hit stood in its line. None when the adds or the DPS seats are unknown."""
    calc = [e for e in p.calc if e["name"] == "White Flame" and 222.5 <= e["t"] <= 225 and e["pos"]]
    if col is None or not calc or any(w not in seat for w in match): return None
    adds = ("northern", "southern")
    plat = lambda w, default: "northern" if w in spos and spos[w][1] < -8 else "southern" if w in spos and spos[w][1] > 8 else default
    of = {**{w: plat(w, "northern") for w in sup["Quartered"]}, **{w: plat(w, "southern") for w in sup["X-Marked"]}}
    for w in match:   # straight: the add in their own column; crossed: the one across
        own = "northern" if (seat[w][0][0] > 0) == (col > 0) else "southern"
        of[w] = own if seat[w][1] else next(k for k in adds if k != own)
    best, second, ls, ks, ks2 = p3_split(calc, col)
    tie = second is not None and second - best < P3_WF_TIE
    hit, unsure = collections.defaultdict(set), set()
    for i, es in enumerate(ls):
        who = {e["who"] for e in es}
        hit[ks[i]] |= who
        if tie and ks2[i] != ks[i]: hit[ks2[i]] |= who; unsure |= who
    dead, out = p.dead_by(t - 0.3), []
    for k in adds:
        exp = {w for w, a in of.items() if a == k}
        missing, gone, extra = sorted(exp - hit[k] - dead), sorted(exp & dead), sorted(hit[k] - exp)
        if not extra and not missing: continue
        low = bool(set(extra) & unsure)
        how = " (which add fired which laser cannot be decided: undecided)" if low else ""
        if missing:
            out.append(fault(t, "Paradeigma III", missing, extra, f"did not bait their White Flame (the {k} add); it hit {', '.join(extra) or 'no one else'}{how}",
                             "low" if low else "high" if extra else "medium", ability="White Flame", tag="p3.wf.missed", share=0.5 if low else "own"))
        if gone and extra:   # a dead baiter's laser found someone else
            f = fault(t, "Paradeigma III", gone, extra, f"White Flame (the {k} add) went to {', '.join(extra)} because {', '.join(gone)} (a baiter) was already dead{how}",
                      "consequence", chain=gone, ability="White Flame", tag="p3.wf.baiter_dead", share=0.5 if low else "own")
            if low: f["cap"] = "low"
            out.append(f)
        if extra and not missing and not gone:
            out += [fault(t, "Paradeigma III", [w], [w], f"stood in a White Flame line (the {k} add's){how}", "low" if w in unsure else "medium",
                          ability="White Flame", tag="p3.wf.line") for w in extra]
    return out


def para3(p, lp, bright_by=None):
    """bright_by: how the bright Souls take the middle platforms, so when both soak one tower the one who belongs on the
    other side is wrong: "light_party" (bright_seat_lp, the 2026-10-25 raid's), "priority" (BRIGHT_PRIORITY east to
    west, from 2026-10-26); None, both share the blame."""
    out = []
    sup = {k: p.holders(f"{k} Soul", 200, 210) for k in ("Quartered", "X-Marked", "Astralbright", "Umbralbright")}
    bright = [(w, a) for a in ("Astral", "Umbral") for w in sup[f"{a}bright"]]
    if not bright: return out
    asp = bright[0][1]
    supports = set(sup["Quartered"]) | set(sup["X-Marked"]) | {w for w, _ in bright}
    supports_all = supports | {w for w, j in p.job.items() if j in SUPPORT_JOBS}   # a support dead before the debuffs gets none
    # support towers (Shock): every support soaks the one on their platform; a tower left unsoaked is Electrify, a wipe
    sh = p.hits("Shock", 213, 215.5)
    wipe = {e["who"] for e in p.hits("Electrify", 215.5, 218.5)}
    spos = {e["who"]: e["pos"] for e in sh if e["pos"]}
    if sh or wipe:
        t = sh[0]["t"] if sh else 214.4; dead = p.dead_by(t - 0.3); got = {e["who"] for e in sh}
        zap = dict(ability="Electrify")   # one Electrify, however many towers stood empty
        missed = [w for w in sorted(supports_all - got) if w not in dead]
        if missed: out.append(fault(t, "Paradeigma III", missed, wipe | set(missed), "did not soak their platform tower (Electrify)", "high", **zap, tag="p3.support_tower.empty"))
        for w in sorted((supports_all - got) & dead):
            out.append(fault(t, "Paradeigma III", [w], wipe, f"{w} was already dead, so their platform tower went unsoaked (Electrify)", "consequence", chain=[w], **zap, tag="p3.support_tower.empty"))
        for w in sorted(got - supports): out.append(fault(t, "Paradeigma III", [w], [w], "a DPS soaked a support tower", "medium", tag="p3.support_tower.dps"))
        # two supports in one tower leave another empty: blame whoever does not belong on that platform
        role = {**{w: "+" for w in sup["Quartered"]}, **{w: "X" for w in sup["X-Marked"]}, **{w: "bright" for w, _ in bright}}
        by_tower = collections.defaultdict(list)
        for e in sh: by_tower[e.get("sourceInstance")].append(e)
        for es in by_tower.values():
            if len(es) < 2 or not es[0]["pos"]: continue
            row = min(3, max(0, int((es[0]["pos"][1] + 20) // 10)))
            want = "+" if row == 0 else ("X" if row == 3 else "bright")
            who = [e["who"] for e in es]
            bad = [w for w in who if role.get(w) != want] or who
            place = {"+": "the north platform (Quartered)", "X": "the south platform (X-Marked)", "bright": "a middle platform (bright Souls)"}[want]
            rule = f"{' and '.join(who)} soaked the same tower on {place}, leaving another tower empty (Electrify)"
            # two bright Souls on one middle tower: the day's rule says which of them belongs on the other side; without
            # one, both share the blame
            seat = {w: s for s, w in seats(p, lp).items() if s in BRIGHT_PRIORITY}
            if bright_by and len(who) == 2 and set(bad) == set(who) and all(role.get(w) == "bright" and w in seat for w in who):
                if bright_by == "priority":
                    first, second = sorted(who, key=lambda w: BRIGHT_PRIORITY.index(seat[w]))
                    west = es[0]["pos"][0] < 0
                    bad = [first if west else second]
                    rule += f"; {bad[0]} belongs on the {'eastern' if west else 'western'} one (priority H1 > T1 > T2 > H2, east to west)"
                else:   # the northern middle platform's tower lies north of the centre line
                    north = es[0]["pos"][1] < 0
                    bad = [w for w, n in zip(who, bright_seat_lp(seat[who[0]], seat[who[1]])) if n != north]
                    rule += (f"; {bad[0]} belongs on the {'southern' if north else 'northern'} one (light parties: LP1 the northern, LP2 the "
                             "southern; the healer keeps theirs when both are in one)")
            out.append(fault(t, "Paradeigma III", bad, wipe | set(who), rule, "high" if len(bad) < len(who) else "medium", **zap, tag="p3.support_tower.empty",
                             share="own" if len(bad) < len(who) else "one_of"))   # which of them belonged elsewhere untold
    # platforms: Quartered takes the north-most, X-Marked the south-most
    wrong_plat = {}
    for w in sup["Quartered"]:
        if w in spos and spos[w][1] > -8: wrong_plat[w] = "Quartered (+) belongs on the north platform"
    for w in sup["X-Marked"]:
        if w in spos and spos[w][1] < 8: wrong_plat[w] = "X-Marked belongs on the south platform"
    # DPS tethers: Searing Radiance -> Umbral Tilt, Shadowsear -> Astral Tilt
    tl = p.hits(("Searing Radiance", "Shadowsear"), 215, 217.5)
    per_inst = collections.Counter(e.get("sourceInstance") for e in tl)
    lasers = tether_lasers(p, supports)
    seat = tether_seats(lasers)
    tilt = {o: "Umbral" if nm == "Searing Radiance" else "Astral" for nm, _, o, _ in lasers.values() if o}
    mine = set()
    # a DPS's own tether is the laser that hit only them; a second laser through them is someone else's
    for e in sorted(tl, key=lambda e: per_inst[e.get("sourceInstance")]):
        if e["who"] in supports:
            out.append(tether_clip(p, e, lasers.get(e.get("sourceInstance")), seat))
        else:
            o = lasers.get(e.get("sourceInstance"), (None,) * 4)[2]
            if o and o != e["who"]:
                out.append(tether_cross(p, e["t"], e["who"], o, lasers[e.get("sourceInstance")], seat)); continue
            if e["who"] in mine: out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "hit by two DPS tether lasers", "medium", tag="p3.tether.stood_in")); continue
            mine.add(e["who"]); tilt.setdefault(e["who"], "Umbral" if e["name"] == "Searing Radiance" else "Astral")
            if (e.get("targetResources") or {}).get("hitPoints") == 0:
                out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "died to their own tether laser (not stretched far enough)", "high", tag="p3.tether.not_stretched"))
    match = [w for w, a in tilt.items() if a == asp]; opp = [w for w, a in tilt.items() if a != asp]
    col = p3_column(seat, spos, sup["Quartered"])
    # + and X: both locked to true north; the owner steps out of their own arms. Each has its spot (+ the north platform's
    # outer corner, X the south wall's middle): one dropped well off it is its owner's, whoever its arms hit
    own = {"Theos's Cross": (sup["Quartered"], "+"), "Theos's Saltire": (sup["X-Marked"], "X")}
    for e in p.hits(("Theos's Cross", "Theos's Saltire"), 221.5, 223.8):
        owners, shape = own[e["name"]]; o = owners[0] if owners else None
        at = p.source_at({e["name"]}, 221.5, 223.8)
        c = col or (math.copysign(1, at[0]) if at else None)
        spot = ((c * 19.0, -19.0) if c else None) if shape == "+" else (0.0, 19.2)
        off = math.dist(at, spot) if at and spot else 0
        if e["who"] == o:
            out.append(fault(e["t"], "Paradeigma III", [o], [o], f"did not step out of their own {shape}", "high", tag="p3.cross"))
        elif o and off > P3_CROSS_OFF:
            where = "the north platform's outer corner" if shape == "+" else "the south wall's middle"
            out.append(fault(e["t"], "Paradeigma III", [o], [e["who"]], f"dropped the {shape} {off:.1f} y from its spot ({where}); its arms hit {e['who']}", certainty(off - P3_CROSS_OFF, unc(0)), tag="p3.cross.off_spot"))
        elif o in wrong_plat:
            out.append(fault(e["t"], "Paradeigma III", [o], [e["who"]], f"dropped the {shape} from the wrong platform ({wrong_plat[o]}); it hit {e['who']}", "high", tag="p3.cross"))
        else:
            out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], f"stood in the arms of {o or 'a'}'s {shape}", "medium", tag="p3.cross"))
    # where the bright towers went: same-colour pair on the Soul's side -> centre corner, otherwise its own tile
    glow = {e["who"]: e for e in p.hits(("Astral Glow", "Umbral Glow"), 222, 224.5) if e["who"] in dict(bright) and e["pos"]}
    pairx = lambda ws: [p_ for p_ in (seat[w][0] if w in seat else next((e["pos"] for e in tl if e["who"] == w and e["pos"]), None) for w in ws) if p_]
    mx = pairx(match); mside = (1 if sum(x for x, _ in mx) > 0 else -1) if mx else None
    misplaced = {}
    want_centre = lambda pos: mside is not None and (pos[0] > 0) == (mside > 0)
    for w, e in glow.items():
        x, y = e["pos"]; centre = math.hypot(x, y) < 6.5
        if mside is not None and centre != want_centre(e["pos"]):
            misplaced[w] = "on its own tile instead of the centre corner" if want_centre(e["pos"]) else "at the centre instead of on its own tile"
    gi = collections.defaultdict(list)
    for e in p.hits(("Astral Glow", "Umbral Glow"), 222, 224.5): gi[(e["name"], e.get("sourceInstance"))].append(e)
    for (nm, inst), es in gi.items():
        gone = [] if any(e["who"] in dict(bright) for e in es) else dead_soul(p, dict(bright), nm, es[0]["t"])
        for e in es:
            if e["who"] in dict(bright): continue
            if gone: out.append(fault(e["t"], "Paradeigma III", gone, [e["who"]], f"{' and '.join(gone)} died holding a bright Soul; its tower dropped on {e['who']}", "consequence", chain=gone, tag="p3.tower.soul_dead"))
            else: out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "stood in a bright Soul's AoE", "medium", tag="p3.bright_aoe"))
    # White Flame: baited by the + and X supports and the matching DPS pair
    wf = p.hits("White Flame", 222.5, 225)
    missing, extra = [], []
    if wf:
        t = wf[0]["t"]; dead = p.dead_by(t - 0.3); hit = collections.Counter(e["who"] for e in wf)
        exp_all = set(sup["Quartered"]) | set(sup["X-Marked"]) | set(match); exp = exp_all - dead
        missing = [w for w in sorted(exp) if w not in hit]; extra = [w for w in hit if w not in exp]
        gone = sorted(exp_all & dead)
        if (per_add := p3_white_flame(p, t, sup, match, seat, col, spos)) is not None: out += per_add   # each add's baiters
        elif extra and gone and not missing:   # a baiter was already dead, so their laser found someone else
            out.append(fault(t, "Paradeigma III", gone, extra, f"White Flame went to {', '.join(extra)} because {', '.join(gone)} (a baiter) was already dead", "consequence", chain=gone, tag="p3.wf.baiter_dead"))
        elif missing: out.append(fault(t, "Paradeigma III", missing, extra, f"did not bait their White Flame; it hit {', '.join(extra) or 'someone else'}", "high" if extra else "medium", tag="p3.wf.missed"))
        elif extra:
            for w in extra: out.append(fault(t, "Paradeigma III", [w], [w], "stood in a White Flame line", "medium", tag="p3.wf.line"))
        for e in wf:
            if e["who"] in exp and hit[e["who"]] == 1 and (e.get("targetResources") or {}).get("hitPoints") == 0:
                out.append(fault(t, "Paradeigma III", [], [e["who"]], "died taking their own assigned White Flame (healing / mitigation)", "unattributed", tag="p3.wf.own"))
    # bright towers: soaked by the opposite pair (Astral Advance = Astral tower)
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 224.5, 227.5)
    expl = p.hits("Unmitigated Explosion", 227, 231)
    blown = {x["who"] for x in expl}
    ts = soaks[0]["t"] if soaks else 226
    for s in soaks:
        if s["who"] not in opp: out.append(fault(s["t"], "Paradeigma III", [s["who"]], [s["who"]], "soaked a bright tower without the opposite Tilt", "high", tag="p3.tower.wrong_player"))
    boom = dict(ability="Unmitigated Explosion")
    for w, a in bright:   # a bright Soul who died before dropping leaves their tower where they fell, and nobody soaks it
        if w not in glow and w in p.dead_by(222.5) and expl:
            out.append(fault(ts, "Paradeigma III", [w], blown, f"{w} died before dropping their bright tower; it went unsoaked", "consequence", chain=[w], **boom, tag="p3.tower.soul_dead"))
    # a tower holds when someone with the opposite Tilt soaks it; soaked only by the wrong Tilt, it explodes all the same
    soaked_near = lambda pos: any(s["pos"] and s["who"] in opp and math.dist(s["pos"], pos) < 6 for s in soaks)
    dead = p.dead_by(ts - 0.3)
    alive, gone = [x for x in opp if x not in dead], [x for x in opp if x in dead]
    idle = [x for x in alive if x not in {s["who"] for s in soaks}]
    # whose tower it is: of the opposite pair, the straight tether soaks the centre tower and the crossed one the tower on
    # their own platform (briefs.html#para3)
    soaker = lambda pos: next((x for x in opp if x in seat and seat[x][1] == want_centre(pos)), None) if mside is not None else None
    unsoaked = collections.defaultdict(list)   # why -> the bright Souls whose towers went unsoaked for it
    for w, e in glow.items():
        if soaked_near(e["pos"]): continue
        sk, across = soaker(e["pos"]), P3_TOWER_R - math.hypot(*e["pos"])
        if opp and not alive: why = "soakers dead"          # no one left to soak it, wherever it stood
        elif sk and sk in dead: why = ("its soaker dead", sk)   # its own soaker dead: whoever else stepped in, theirs
        elif not sk and gone and not idle: why = "soaker dead"   # a soaker short and the living ones at the other tower: likewise
        elif want_centre(e["pos"]) and across < P3_ACROSS[1]:   # out of reach from the other platform
            why = ("misplaced", w) if w in misplaced else ("out of reach", w)
        elif want_centre(e["pos"]) and across < P3_ACROSS[0] and sk: why = ("undecided", w, sk)
        elif w in misplaced: why = ("misplaced", w)
        elif sk: why = ("its soaker", sk)
        elif idle: why = "idle"
        elif alive: why = "other tower"                       # every living soaker took the other tower
        else: why = "unknown"
        unsoaked[why].append(w)
    for why, ws in unsoaked.items():
        towers = " and ".join(f"{w}'s" for w in ws) + (" towers" if len(ws) > 1 else " tower")
        if why in ("soakers dead", "soaker dead"):
            out.append(fault(ts, "Paradeigma III", gone, blown, f"{towers} unsoaked because {'its soakers were' if len(gone) > 1 else 'its soaker was'} already dead", "consequence", chain=gone, **boom, tag="p3.tower.unsoaked"))
        elif why[0] == "its soaker dead":
            out.append(fault(ts, "Paradeigma III", [why[1]], blown, f"{towers} unsoaked because its soaker was already dead ({why[1]})", "consequence", chain=[why[1]], **boom, tag="p3.tower.unsoaked"))
        elif why[0] == "out of reach":
            w = why[1]; h = math.hypot(*glow[w]["pos"])
            reach = f"its {P3_TOWER_R:g} y reach stopped {h - P3_TOWER_R:.1f} y short of it" if h >= P3_TOWER_R else f"it reached only {P3_TOWER_R - h:.1f} y across it"
            out.append(fault(ts, "Paradeigma III", [w], blown | {w}, f"{w}'s tower unsoaked: dropped {h:.1f} y from the arena centre, {reach}, out of reach from the "
                             f"other platform", certainty(h - (P3_TOWER_R - P3_ACROSS[1]), unc(0)), **boom, tag="p3.tower.out_of_reach"))
        elif why[0] == "undecided":
            w, sk = why[1:]; h = math.hypot(*glow[w]["pos"])
            out.append(fault(ts, "Paradeigma III", [w, sk], blown | {w, sk}, f"{w}'s tower unsoaked, undecided: dropped {h:.1f} y from the arena centre, it reached only "
                             f"{P3_TOWER_R - h:.1f} y across it for {sk} on the other platform", "low", **boom, tag="p3.tower.undecided"))
        elif why[0] == "its soaker":
            sk = why[1]
            where = f"soaked {next((f'{x}' for x, ex in glow.items() if x not in ws and any(s['who'] == sk and s['pos'] and math.dist(s['pos'], ex['pos']) < 6 for s in soaks)), 'another')}'s instead" \
                if any(s["who"] == sk for s in soaks) else "soaked none"
            out.append(fault(ts, "Paradeigma III", [sk], blown | {sk}, f"did not soak {towers}, theirs as the {'straight' if seat[sk][1] else 'crossed'} tether ({where})", "high", **boom, tag="p3.tower.unsoaked"))
        elif why == "idle":
            out.append(fault(ts, "Paradeigma III", idle, blown | set(idle), f"did not soak {towers}", "high", **boom, tag="p3.tower.unsoaked"))
        elif why == "other tower":
            out.append(fault(ts, "Paradeigma III", alive, blown, f"{' and '.join(alive)} both soaked the other bright tower; one of them belonged on {towers}", "medium", **boom, tag="p3.tower.unsoaked", share="one_of"))
        elif why == "unknown":
            out.append(fault(ts, "Paradeigma III", [], blown, f"did not soak {towers}", "low", **boom, tag="p3.tower.unsoaked"))
        else:
            out.append(fault(ts, "Paradeigma III", [why[1]], blown | {why[1]}, f"tower unsoaked: placed {misplaced[why[1]]}", "high", **boom, tag="p3.tower.misplaced"))
    return out


# ---------- Superchain I ----------
# The first resolution: the cluster with two short chains sits on an intercardinal, CLUSTER y out on each axis (fitted
# to clean orange spreads: 8.2, 8.3), and the party stands in a ring around it (7.9 y), evenly spaced, seat by seat:
# facing Athena from the cluster, the tanks either side of the line to her, then melee, healers, and ranged at the
# back; the 1s on the right, the 2s on the left. Orange fires one cone from the cluster at each player, so two players
# at the same angle share one; purple fires at all DPS or all supports, each shared with the partner beside them (M1
# with T1, M2 with T2, R1 with H1, R2 with H2). There are always 8 orange cones and 4 purple ones: a dead player's goes
# to someone else (orange: a player hit twice; purple: one at random). SPOT_ANGLE is each row's angle off the line to
# Athena in clean spreads (median, degrees; quartiles within 7-15 of it, except ranged, who stand wider).
MELEE_JOBS = {"Monk", "Dragoon", "Ninja", "Samurai", "Reaper", "Viper"}
CLUSTER, SPOT_ANGLE, SPOT_MARGIN, SPOT_RING = 8.25, {"T": 17, "M": 50, "H": 98, "R": 146}, 20, 7.9
CONE_HALF = 15      # degrees either side of an orange or purple cone's aim
# how far off their seat's angle each row stands in clean orange spreads, 9 times in 10 (2026-10-06 on): past it, off
# their spot (healers and ranged stand much wider than tanks: a flat 20 called a healer at 24 off it)
SPOT_TOL = {"T": 14, "M": 25, "H": 36, "R": 78}
PARTNER = {"T": "M", "M": "T", "H": "R", "R": "H"}


def seats_all(p, lp):
    """{player: (row letter, 1 or 2)} for the whole party, from the light parties and the jobs."""
    row = lambda j: "T" if j in TANK_JOBS else "H" if j in HEALER_JOBS else "M" if j in MELEE_JOBS else "R"
    return {w: (row(p.job[w]), n) for n, party in ((1, lp[0]), (2, lp[1])) for w in party if w in p.job}


def spot_frame(p, lp, hs):
    """(seat, angle, want) for the first resolution: each player's seat, their angle around the cluster off the line to
    Athena (degrees, + = right of someone facing her from the cluster) and their seat's angle. When the whole party
    fits its seats better mirrored (1s left), they are read mirrored: light parties learned the other way round, or a
    group that spread mirrored, where the spots relative to each other still say who moved. None when unknown."""
    seat, pos = seats_all(p, lp), {e["who"]: e["pos"] for e in hs if e["pos"]}
    if len(pos) < 4: return None
    mx, my = sum(x for x, _ in pos.values()) / len(pos), sum(y for _, y in pos.values()) / len(pos)
    cx, cy = math.copysign(CLUSTER, mx), math.copysign(CLUSTER, my)
    to_athena = math.atan2(-cy, -cx)
    ang = {w: (math.degrees(math.atan2(y - cy, x - cx) - to_athena) + 180) % 360 - 180 for w, (x, y) in pos.items()}  # y points south
    diff = lambda a, b: abs((a - b + 180) % 360 - 180)
    want = lambda flip: {w: SPOT_ANGLE[r] * (1 if (n == 1) != flip else -1) for w, (r, n) in seat.items()}
    cost = lambda flip: sum(diff(ang[w], a) for w, a in want(flip).items() if w in ang)
    return seat, ang, want(cost(True) < 0.75 * cost(False))


def cone_blame(p, lp, hs, group):
    """Who of a group in one orange cone made it so: (culprits, confidence, why). Whoever's move alone to their seat's
    angle around the cluster puts them over CONE_HALF degrees from the others (the cones are 30 degrees wide: pairs one
    hit stood a median 11 apart, pairs none did over 15; scratch/sc1audit/cones.py). Several would: those off their
    spot (past their row's SPOT_TOL); all when they all are; none, it cannot be decided (all, low). None alone: all of
    them. Confidence: their move's margin past the cone's edge and how far past their tolerance they stood, against the
    log's error as an angle at the ring (SPOT_RING). The user's rule as for the other mechanics, 2026-10-27 (it was the one
    further off by SPOT_MARGIN, else a share). The tag last."""
    fr = spot_frame(p, lp, hs)
    if not fr or not all(w in fr[0] and w in fr[1] for w in group): return sorted(group), "low", "", "sc1.orange"
    seat, ang, want = fr
    gap = lambda a, b: abs((a - b + 180) % 360 - 180)
    off = {w: gap(ang[w], want[w]) for w in group}
    name = lambda w: "".join(map(str, seat[w]))
    told = ", ".join(f"{w} ({name(w)}) {off[w]:.0f}" for w in sorted(group, key=off.get, reverse=True)) + " degrees off their spots"
    fixes = [w for w in group if all(gap(want[w], ang[o]) > CONE_HALF for o in group if o != w)]
    past = lambda w: off[w] - SPOT_TOL[seat[w][0]]     # degrees past their row's tolerance
    out = [w for w in fixes if past(w) > 0]
    # how sure: the log's error for a hit's position, as an angle at the ring's radius; their move clearing the others'
    # cones and their being off their spot, each against it
    u = math.degrees(math.atan2(unc(0), SPOT_RING))
    sure = lambda w: least_sure([certainty(min(gap(want[w], ang[o]) for o in group if o != w) - CONE_HALF, u)] + ([certainty(past(w), u)] if past(w) > 0 else []))
    if len(fixes) == 1 or len(out) == 1:
        w = fixes[0] if len(fixes) == 1 else out[0]
        return [w], sure(w), f"; {w} ({name(w)}) stood {off[w]:.0f} degrees off their spot around the cluster ({told})", "sc1.orange"
    if out: return sorted(out), least_sure([certainty(past(w), u) for w in out]), f"; each of them back at their spot would have done ({told})", "sc1.orange"
    if fixes: return sorted(group), "low", f"; could not be decided who stood in whose orange cone ({told})", "sc1.orange.undecided"
    return sorted(group), "medium" if any(past(w) > 0 for w in group) else "low", f"; no one of them alone back at their spot would have done ({told})", "sc1.orange"


def pair_blame(p, lp, hs, crowd):
    """Three or more in one purple pair: the pair whose spot (midway between its two seats) the crowd stands at keeps
    it, the others joined it. (culprits, confidence, why); no culprits when it cannot tell."""
    seat = seats_all(p, lp)
    extra = [w for w in crowd if w in seat and (PARTNER[seat[w][0]], seat[w][1]) not in {seat.get(x) for x in crowd}]
    if extra and len(extra) < len(crowd): return extra, "medium", f"; {', '.join(extra)} joined a pair not theirs"
    fr = spot_frame(p, lp, hs)
    if not fr or not all(w in fr[0] and w in fr[1] for w in crowd): return [], "low", ""
    seat, ang, want = fr
    a = math.degrees(math.atan2(sum(math.sin(math.radians(ang[w])) for w in crowd), sum(math.cos(math.radians(ang[w])) for w in crowd)))
    spot = lambda w: (want[w] + want[w] * SPOT_ANGLE[PARTNER[seat[w][0]]] / SPOT_ANGLE[seat[w][0]]) / 2    # midway to the partner
    home = [w for w in crowd if abs((spot(w) - a + 180) % 360 - 180) < SPOT_MARGIN]
    if home and len(home) < len(crowd):
        out = sorted(set(crowd) - set(home))
        return out, "medium", f"; the pair stood at {', '.join(home)}'s spot, {', '.join(out)} joined it"
    return [], "low", ""


# Superchain I's lasers run from Athena, each aimed at its Strong Soul, 6 y wide (the game's data). Seen from Athena the two laser
# groups stand a median 17 degrees apart in pulls where no one took both; where someone did, a median 5 (2026-10-26)
LASER_STRONG = {"Astral Impact": "Astralstrong", "Umbral Impact": "Umbralstrong"}
LASER_SHARERS = 4   # each laser is shared by 4 (the user's rule): a Soul pair and two Tilts
LASER_OF_SOUL = {"Astralstrong": "Astral Impact", "Umbralbright": "Astral Impact", "Umbralstrong": "Umbral Impact", "Astralbright": "Umbral Impact"}
SHARE_ROLL = 0.05   # a hit's damage rolls +-5%: a full share sparing them by less than that cannot be told from not


def sc1_laser_of(p, S, w, t):
    """The laser a player shares: by their Soul, else by the Tilt they held (Umbral Tilt shares the Astral laser), at
    their death if they died before t; None when neither tells (1 of 207 players dead by the lasers in the caches)."""
    nm = next((nm for s, nm in LASER_OF_SOUL.items() if w in S[s]), None)
    if nm: return nm
    at = max((d["t"] - 2.05 for d in p.deaths if d["who"] == w and d["t"] - 2 < t), default=t - 0.2)
    return "Astral Impact" if w in p.has_debuff_at("Umbral Tilt", at) else "Umbral Impact" if w in p.has_debuff_at("Astral Tilt", at) else None


def share_short(t, mech, e, n, m, gone, what, base=None, *, tags):
    """A lethal hit `e` of a share that n players took and m should have, the rest of them (gone) already dead: when the
    hit split m ways would have spared its target, a fault chained to the dead (their death's culprits are blamed);
    within SHARE_ROLL of it, the same but undecided (low). None when they would have died all the same, or when the
    living who should have shared it (base, with them) would have been enough: then it is their fault alone. tags: the
    fault's tag, (sharer dead, undecided)."""
    hp, ab = e["amount"] - e.get("overkill", 0), e.get("absorbed", 0)
    at = lambda k: (e["amount"] + ab) * n / k - ab
    full = at(m)
    if hp <= full or base and base > n and hp > at(base): return None
    thin = hp - full <= SHARE_ROLL * full
    who, was = " and ".join(gone), "was" if len(gone) == 1 else "were"
    lead = f"could not be decided whether a full {what} would have spared {e['who']}" if thin else f"{what} a sharer short"
    f = fault(t, mech, gone, [e["who"]], f"{lead}: {who}, who shared it, {was} already dead (shared by {m}, {e['who']} "
              f"would have kept {hp - full:,.0f} HP)", "consequence", chain=gone, ability=e["name"], tag=tags[thin])
    if thin: f["cap"] = "low"
    elif hp - full <= 2 * SHARE_ROLL * full: f["cap"] = "medium"   # spared by less than twice the roll
    return f
CAMPS_APART = 10    # degrees: groups closer than this stood on top of each other, and the Strong Souls aim the lines
ON_ONE_SPOT = 5     # this many players in both lasers: the groups stood on one spot, each in both is their own


def clip_blame(p, lt, exp, S, w, clip, both):
    """A player in their own laser group also hit by the other laser (clip): whose mistake, as (culprits, rule,
    confidence, chain). With the groups apart, the clipping laser's Strong Soul when they stood nearer the victim's
    group than their own (in the middle), else the victim (stood toward the other group); with the groups together,
    both Strong Souls'; with everyone in both, each victim's own; with its Strong Soul dead, whoever killed them."""
    if len(both) >= ON_ONE_SPOT: return [w], f"took both lasers ({clip} too): the laser groups stood on one spot", "high", None
    gone = [x for x in S[LASER_STRONG[clip]] if x in p.dead_by(lt[0]["t"] - 0.3)]
    if gone:
        return [], f"took both lasers ({clip} too): {', '.join(gone)}, who aims it, was already dead (a dead target's laser goes to someone else)", "consequence", gone
    return clip_geometry(p, lt, exp, S, w, clip) + (None,)


def clip_geometry(p, lt, exp, S, w, clip):
    """clip_blame's verdict from where the groups and the clipping laser's Strong Soul stood, seen from Athena."""
    mine = next(nm for nm in exp if nm != clip)
    athena, pos = p.source_at(set(LASER_STRONG), lt[0]["t"] - 3, lt[-1]["t"] + 0.5), {e["who"]: e["pos"] for e in lt if e["pos"]}
    s = next((x for x in S[LASER_STRONG[clip]] if x in pos), None)
    bearing = lambda q: math.atan2(q[1] - athena[1], q[0] - athena[0])
    mean = lambda ws: math.degrees(math.atan2(sum(math.sin(bearing(pos[x])) for x in ws), sum(math.cos(bearing(pos[x])) for x in ws)))
    diff = lambda a, b: abs((a - b + 180) % 360 - 180)
    theirs, ours = [x for x in exp[clip] - {s} if x in pos], [x for x in exp[mine] - {w} if x in pos]
    if not (athena and s and ours): return [w], f"took both lasers ({clip} too)", "medium"
    if not theirs:   # no one else took the clipping laser: did its Strong Soul stand in the victim's group?
        if diff(math.degrees(bearing(pos[s])), mean(ours)) < CAMPS_APART:
            return [s], f"took both lasers ({clip} too): {s}, who aims it, stood in {w}'s laser group", "medium"
        return [w], f"took both lasers ({clip} too)", "medium"
    gap = diff(mean(theirs), mean(ours))
    if gap < CAMPS_APART:
        aim = [x for k in LASER_STRONG.values() for x in S[k]]
        return aim, f"took both lasers ({clip} too): the laser groups stood {gap:.0f} degrees apart as seen from Athena, so the lines overlapped " \
                    f"(the Strong Souls {', '.join(aim)} aim them)", "medium"
    a = math.degrees(bearing(pos[s]))
    if diff(a, mean(ours)) < diff(a, mean(theirs)):
        return [s], f"took both lasers ({clip} too): {s}, who aims it, stood nearer {w}'s laser group than their own", "medium"
    return [w], f"took both lasers ({clip} too): stood toward the {clip} group", "medium"


# The lasers replayed (scratch/sc1audit/lasers.py, 2026-10-27; the user's rule the same day): each runs from Athena at
# the centre through its Strong Soul as its hits are calculated, hitting everyone within SC1_LASER_HALF of the line (the
# game's data; the cast's logged source is stale), which reproduces 88% of lasers exactly. Each laser group stands
# SC1_GROUP_R out, SC1_GROUP_ANG degrees either side of the laser cluster's bearing (the donut-only cluster; the Astral
# laser's group clockwise of it): clean pulls' sharers stand a median 1.0 y from that spot, 95% within SC1_GROUP_TOL, in
# every group. How sure a verdict is comes from its margins against the logged positions' error (certainty).
SC1_LASER_HALF, SC1_GROUP_R, SC1_GROUP_ANG, SC1_GROUP_TOL = 3.0, 11.3, 15, 2.6


def sc1_laser_replay(p, exp, S):
    """The lasers from positions (Pull.sc1), or None without them: dict(hits(laser, movers) -> who it hits with the
    movers at their group's spot, fits {laser: the replay reproduces its calculated hits}, off {player: y from their
    group's spot}, gap {player: s to their nearest position sample}, strong {laser: its Strong Soul})."""
    sc = p.sc1 or {}
    calc = [e for e in p.calc if e["name"] in LASER_STRONG and 134 <= e["t"] <= 140]
    if not calc: return None
    t, shapes = min(e["t"] for e in calc), collections.defaultdict(set)
    for c in sc.get("cluster", ()):
        if 134 <= c[0] <= 139: shapes[(round(c[2]), round(c[3]))].add(c[1])
    lc = [k for k, v in shapes.items() if v == {"Coil"}]
    if len(lc) != 1: return None
    b = math.atan2(lc[0][1], lc[0][0])
    spot = {nm: (SC1_GROUP_R * math.cos(b + math.radians(a)), SC1_GROUP_R * math.sin(b + math.radians(a)))
            for nm, a in (("Astral Impact", SC1_GROUP_ANG), ("Umbral Impact", -SC1_GROUP_ANG))}
    group = {w: nm for nm, ws in exp.items() for w in ws}
    dead = p.dead_by(t - 2)     # death events before the calculation (dead_by dates a death 2 s back)
    pos = {w: q for w in p.job if w not in dead and (q := sc1_where(p, w, t))}
    strong = {nm: next((x for x in S[k] if x in pos), None) for nm, k in LASER_STRONG.items()}

    def dists(nm, movers=()):
        """{player: y from laser nm's line} with the movers at their group's spot (behind Athena: out of it), or None."""
        pp = {w: spot[group[w]] if w in movers and w in group else q[0] for w, q in pos.items()}
        s = pp.get(strong[nm])
        if not s: return None
        n = math.hypot(*s) or 1e-9
        return {w: abs(q[0] * s[1] - q[1] * s[0]) / n if (q[0] * s[0] + q[1] * s[1]) / n > 0 else 99 for w, q in pp.items()}

    def hits(nm, movers=()):
        d = dists(nm, movers)
        return None if d is None else {w for w, x in d.items() if x <= SC1_LASER_HALF}
    got = {nm: {e["who"] for e in calc if e["name"] == nm} for nm in LASER_STRONG}
    def fits(nm):
        """The replay reproduces laser nm: everyone inside it by more than the log can tell (unc of their position and its
        Strong Soul's) was hit, everyone outside it by more not; nearer its edge, as the log has it."""
        d = dists(nm)
        if d is None: return False
        for w, x in d.items():
            e = unc(pos[w][1], pos[strong[nm]][1])
            if x <= SC1_LASER_HALF - e and w not in got[nm] or x > SC1_LASER_HALF + e and w in got[nm]: return False
        return True
    return dict(hits=hits, dists=dists, fits={nm: fits(nm) for nm in LASER_STRONG},
                off={w: math.dist(q[0], spot[group[w]]) for w, q in pos.items() if w in group}, gap={w: q[1] for w, q in pos.items()}, strong=strong)


def sc1_misaim(R, nm, w):
    """A laser the replay does not reproduce that hit w, who stood at their group's spot (inside SC1_GROUP_TOL by more than
    the log can tell): it was aimed where they were not, so not their mistake. (culprits, confidence, why): the laser's
    Strong Soul when they stood off their spot (as sure as they were off it), else both, undecided (low). None when w was
    not surely at their spot. The last field: undecided."""
    s = R["strong"][nm] if R else None
    if not (s and s != w and SC1_GROUP_TOL - R["off"].get(w, 99) >= unc(R["gap"].get(w, 9))): return None
    at = lambda x: f"{x} {R['off'].get(x, 0):.1f} y from their group's spot"
    if R["off"].get(s, 0) > SC1_GROUP_TOL:
        return [s], certainty(R["off"][s] - SC1_GROUP_TOL, unc(R["gap"].get(s, 9))), f"{s}, who aims it, stood {R['off'][s]:.1f} y from their group's spot ({at(w)}; the laser aimed where the positions do not put it)", False
    return [w, s], "low", f"the laser aimed where the positions do not put it, both at their spots ({at(w)}, {at(s)})", True


def sc1_laser_fix(R, nm, w, want):
    """Whose move alone to their laser group's spot would have put `w` where they belong for laser nm (in it when
    `want`, else out of it): w, or the laser's Strong Soul, who aims it. (culprits, confidence, why, undecided) or None. Both
    would: the one off their spot (past SC1_GROUP_TOL); both when both are (two mistakes, medium); when neither is, it
    cannot be decided (both, low). Neither alone: both together (medium)."""
    s = R["strong"][nm]
    ok = lambda movers: (w in (R["hits"](nm, movers) or set())) == want
    opts = list(dict.fromkeys(x for x in (w, s) if x and ok((x,))))
    far = lambda x: R["off"].get(x, 0) > SC1_GROUP_TOL
    at = lambda x: f"{x} {R['off'].get(x, 0):.1f} y from their group's spot"
    g = lambda x: R["gap"].get(x, 9)
    offc = lambda x: certainty(R["off"].get(x, 0) - SC1_GROUP_TOL, unc(g(x)))   # how sure they were off their spot
    # how sure x's move decides it: w's distance from the laser's edge with x at their spot, against the error of the
    # position left as logged (the other one's)
    edge = lambda x: certainty(abs((R["dists"](nm, (x,)) or {}).get(w, 99) - SC1_LASER_HALF), unc(g(s if x == w else w)))
    if len(opts) == 2:
        out = [x for x in opts if far(x)]
        if not out: return [w, s], "low", f"either at their spot would have done ({at(w)}, {at(s)})", True
        if len(out) == 2: return [w, s], least_sure([offc(w), offc(s)]), f"both away from their spots, either back would have done ({at(w)}, {at(s)})", False
        opts = out
    if len(opts) == 1:
        x = opts[0]
        if edge(x) == "low" and s and s != w:   # the move decides it by less than the log can tell: either could be the culprit
            return [w, s], "low", f"at the laser's edge within what the log can tell ({at(w)}, read {g(w):.2f} s from a sample; {at(s)})", True
        return [x], least_sure([edge(x)] + ([offc(x)] if far(x) else [])), at(x) if x == w else f"{s}, who aims it, stood {R['off'].get(s, 0):.1f} y from their group's spot", False
    if s and s != w and ok((w, s)): return [w, s], least_sure([offc(x) for x in (w, s) if far(x)] or ["medium"]), f"both away from their spots ({at(w)}, {at(s)})", False
    return None


# The bright Souls' towers (scratch/sc1audit, 2026-10-27): each drops on the cardinal beside the last cluster on its
# side, Astral on the right and Umbral on the left as you face Athena from the cluster, SC1_TOWER_R out (the median).
# Soaked towers landed within SC1_OFF of that spot nine times in ten, and their soakers came from within SC1_REACH as it
# dropped (99%; the tower resolves 3 s after it drops).
# A tower, and the bright Soul's AoE as it drops, takes whoever stands within SC1_ON of it (the game's data, Action
# 33550-33551, 33548-33549). A Strong Soul SC1_STEP y nearer their tower than a second before was stepping in.
SC1_TOWER_R, SC1_OFF, SC1_REACH, SC1_ON, SC1_STEP = 10.9, 6.9, 15.2, 3.0, 1.0
# Heavensflame (Theos's Holy) reaches SC1_FLAME y (the game's data, Action 33542); who walked in is read over the last
# SC1_FLAME_WINDOW s, and nearer its edge than the logged positions' error (unc) it cannot be told.
SC1_FLAME, SC1_FLAME_WINDOW = 6.0, 1.5


def sc1_where(p, w, at):
    """(position, seconds to the nearest sample it is read from) of player `w` at `at` (Pull.sc1), or None."""
    return track_at(p, (p.sc1 or {}).get("pos", ()), w, at)


def track_at(p, samples, w, at):
    """(position, seconds to the nearest sample it is read from) of player `w` at `at` from position samples [[t, player
    id, x, y]] (Pull.sc1's or Pull.p2's), between the samples either side, or None."""
    s = sorted((t, (x, y)) for t, pid, x, y in samples if p.players.get(pid) == w)
    if not s: return None
    before, after = [v for v in s if v[0] <= at], [v for v in s if v[0] > at]
    if not before: return after[0][1], after[0][0] - at
    if not after: return before[-1][1], at - before[-1][0]
    (ta, pa), (tb, pb) = before[-1], after[0]
    k = (at - ta) / (tb - ta) if tb > ta else 0
    return (pa[0] + k * (pb[0] - pa[0]), pa[1] + k * (pb[1] - pa[1])), min(at - ta, tb - at)


def sc1_spot(p, asp):
    """(the tower [t, x, y] where it dropped, its planned spot (x, y)) for one bright tower (Pull.sc1), or None."""
    sc = p.sc1 or {}
    tw = next(([t, x, y] for t, a, x, y in sc.get("towers", ()) if a == asp), None)
    cl = [c for c in sc.get("cluster", ()) if c[0] >= 139]   # the last cluster's orb and donut
    if not tw or not cl: return None
    cx, cy = sum(c[2] for c in cl) / len(cl), sum(c[3] for c in cl) / len(cl)
    # the cardinal beside the cluster on the tower's side: facing Athena (-cx, -cy), right is clockwise (y points south)
    card = [(0, math.copysign(1, cy)), (math.copysign(1, cx), 0)]
    want = next(((v[0] * SC1_TOWER_R, v[1] * SC1_TOWER_R) for v in card if (-cx * v[1] + cy * v[0] > 0) == (asp == "Astral")), None)
    return (tw, want) if want else None


def sc1_dropped_on(p, asp, v, at):
    """A Strong Soul hit by a bright Soul's AoE (at `at`): (why, confidence) when its owner dropped the tower on them,
    well off its spot (past SC1_OFF), while they stood clear of the spot (past its SC1_ON) and were not stepping in
    (under SC1_STEP y nearer it over the second before), else None: they stepped in early. Clean pulls' soakers wait
    clear of their tower's spot (all over 3 y from the tower as it drops), so a tower on its spot never lands on them."""
    sp, q, q1 = sc1_spot(p, asp), sc1_where(p, v, at), sc1_where(p, v, at - 1)
    if not sp or not q or not q1: return None
    (tw, want), here = sp, (sp[0][1], sp[0][2])
    off, clear, step = math.dist(here, want), math.dist(q[0], want), math.dist(q1[0], here) - math.dist(q[0], here)
    if off <= SC1_OFF or clear <= SC1_ON or step >= SC1_STEP: return None
    # as sure as its margins against the log's error: the tower off its spot (the game's own position), they clear of it
    # and not stepping in (their positions, read q[1] and q1[1] s from their samples)
    return (f"{off:.1f} y from its spot; {v} {math.dist(q[0], here):.1f} y from it, {clear:.1f} from the spot, {max(step, 0):.1f} y nearer than a second before",
            least_sure([certainty(off - SC1_OFF, unc(0)), certainty(clear - SC1_ON, unc(q[1])), certainty(SC1_STEP - step, unc(q[1], q1[1]))]))


def sc1_tower(p, asp, soaker, owner):
    """Whose move alone to their spot would have saved an unsoaked bright tower, from where it dropped and where its
    soaker stood as it did: (culprits, confidence, why, off plan, tag) or None without the positions. The soaker's when it
    dropped on its spot (could they reach it or not: they were not where they should be); its dropper's when it dropped
    out of the soaker's reach and its spot was in it, or off its spot right on them (its AoE gave them the wrong Tilt);
    when it dropped off its spot but within reach, undecided (either could have saved it, the user's call, 2026-10-27);
    when neither its spot nor where it dropped was in reach, both."""
    sp = sc1_spot(p, asp)
    if not sp: return None
    tw, want = sp
    glow = [e["t"] for e in p.calc if e["name"] == f"{asp} Glow" and tw[0] - 5 <= e["t"] <= tw[0]]
    q = sc1_where(p, soaker, min(glow) if glow else tw[0] - 3)
    if not q: return None
    at = (tw[1], tw[2])
    d, dp, off = math.dist(q[0], at), math.dist(q[0], want), math.dist(at, want)
    us = unc(q[1])   # the soaker's position; the tower's and its spot's are the game's own
    facts = f"it dropped {off:.1f} y from its spot, {soaker} {d:.1f} y from it and {dp:.1f} from the spot"
    if off <= SC1_OFF:
        return [soaker], certainty(SC1_OFF - off, unc(0)), f"{soaker} could reach it ({facts})" if d <= SC1_REACH else f"{soaker} was not near it ({facts})", off, "sc1.tower.unsoaked"
    if d <= SC1_ON:   # off its spot right on them: its AoE gave them the wrong Tilt
        return [owner], least_sure([certainty(SC1_ON - d, us), certainty(off - SC1_OFF, unc(0))]), f"{owner} dropped it on {soaker}, off its spot ({facts})", off, "sc1.tower.dropped_on"
    if d <= SC1_REACH:
        return [soaker, owner], "low", f"undecided: {owner} dropped it off its spot, but {soaker} could still reach it ({facts})", off, "sc1.tower.undecided"
    if dp <= SC1_REACH:
        return [owner], least_sure([certainty(d - SC1_REACH, us), certainty(SC1_REACH - dp, us)]), f"{owner} dropped it out of {soaker}'s reach ({facts})", off, "sc1.tower.out_of_reach"
    return [soaker, owner], least_sure([certainty(d - SC1_REACH, us), certainty(dp - SC1_REACH, us)]), f"both away from it ({facts})", off, "sc1.tower.unsoaked"


def sc1_together(p, S):
    """Whose tower was off its spot when the two bright Souls dropped theirs on one spot: (culprits, confidence, facts,
    tag) or None without the positions (or with both towers on their spots). The spots are opposite cardinals ~15 y apart,
    so one tower at least is off its own: the Soul's whose tower dropped past SC1_OFF from its spot, both when both did.
    A tower nearer SC1_OFF than the log's error either way may have been either: its Soul is blamed too (low), and with
    no tower surely off, it cannot be decided (both, low; as the user's rule for the towers, 2026-10-27). In all 7 cached
    pulls that dropped together (2026-10-28), one tower landed on its spot and only one off it."""
    offs = {}
    for asp in ("Astral", "Umbral"):
        sp = sc1_spot(p, asp)
        if not sp or not S[f"{asp}bright"]: return None
        offs[S[f"{asp}bright"][0]] = (asp, math.dist((sp[0][1], sp[0][2]), sp[1]))
    u = unc(0)   # the towers' positions and their spots are the game's own
    sure = {w: certainty(abs(d - SC1_OFF), u) for w, (_, d) in offs.items()}
    off = [w for w, (_, d) in offs.items() if d > SC1_OFF and sure[w] != "low"]
    edge = [w for w in offs if sure[w] == "low"]
    facts = "; ".join(f"{w}'s {asp} tower {d:.1f} y from its spot" for w, (asp, d) in offs.items())
    if not off: return (list(offs), "low", f"could not be decided whose was off its spot ({facts})", "sc1.bright_together.undecided") if edge else None
    return off + edge, least_sure(list(sure.values())), f"{' and '.join(w + chr(39) + 's' for w in off)} off {'its spot' if len(off) == 1 else 'their spots'} ({facts})", "sc1.bright_together"


def superchain1(p, lp):
    out = []
    S = {k: p.holders(f"{k} Soul", 120, 130) for k in ("Astralstrong", "Umbralstrong", "Astralbright", "Umbralbright", "Heavensflame")}
    if not any(S.values()): return out
    # first resolution: purple pairs (Emission, 2 per instance) / orange cones (Radiation, 1 per instance)
    for nm, want in (("Superchain Emission", 2), ("Superchain Radiation", 1)):
        hs = p.hits(nm, 128.5, 132)
        if not hs: continue
        t = hs[0]["t"]; dead = p.dead_by(t - 0.3)
        by = collections.defaultdict(list)
        for e in hs: by[e.get("sourceInstance")].append(e["who"])
        hit = collections.Counter(e["who"] for e in hs)
        alive = [w for w in p.job if w not in dead]
        gone = sorted(w for w in dead if w not in hit)    # their cone went to someone else
        if nm == "Superchain Emission":
            missing = [w for w in alive if w not in hit]
            lone = [ws[0] for ws in by.values() if len(ws) == 1]
            crowd = [ws for ws in by.values() if len(ws) > 2]
            if gone and (lone or crowd):   # a dead target's cone picked someone at random
                out.append(fault(t, "Superchain I", gone, {w for ws in by.values() for w in ws}, f"purple jacks out of their pairs because {', '.join(gone)} "
                                 f"{'was' if len(gone) == 1 else 'were'} already dead (a dead target's goes to someone at random)", "consequence", chain=gone, tag="sc1.purple"))
                continue
            # a lone target's seat partner left them (missing, or in another pair), when every player has a seat of their
            # own; otherwise every missing player
            seat = seats_all(p, lp); by_seat = {s: w for w, s in seat.items()}
            for v in lone:
                mate = by_seat.get((PARTNER[seat[v][0]], seat[v][1])) if v in seat and len(by_seat) == len(seat) == len(p.job) else None
                if mate in missing or mate in hit:
                    out.append(fault(t, "Superchain I", [mate], [v], f"not in their pair for the purple jack ({'missing' if mate in missing else 'in another pair'}); "
                                     f"{v} took it alone", "high", tag="sc1.purple"))
                elif missing:
                    out.append(fault(t, "Superchain I", missing, [v], f"not in their pair for the purple jack; {v} took it alone", "high", tag="sc1.purple"))
            for ws in crowd:   # three or more: whoever's seat partner is not in it, or who stood away from it, joined
                cul, conf, why = pair_blame(p, lp, hs, ws)
                out.append(fault(t, "Superchain I", cul or ws, ws, "three or more in one purple-jack pair" + why, conf, tag="sc1.purple",
                                 share="own" if cul else (len(ws) - 2) / len(ws)))   # who joined untold: all but two of them did
        else:   # every cone from the cluster hits whoever stands in line with it
            groups = {frozenset(ws) for ws in by.values() if len(ws) > 1}
            doubled = [w for w, n in hit.items() if n >= 2 and not any(w in g for g in groups)]
            if gone and sum(n - 1 for n in hit.values()) <= len(gone):   # all the extra hits are the dead players' cones
                if groups or doubled:
                    out.append(fault(t, "Superchain I", gone, set(doubled) | {w for g in groups for w in g}, f"orange cones doubled up because {', '.join(gone)} "
                                     f"{'was' if len(gone) == 1 else 'were'} already dead (a dead player's cone goes to someone else)", "consequence", chain=gone, tag="sc1.orange"))
                continue
            for g in groups:
                cul, conf, why, ctag = cone_blame(p, lp, hs, g)
                out.append(fault(t, "Superchain I", cul, g, f"orange cone overlap ({', '.join(sorted(g))}){why}", conf, tag=ctag))
            for w in doubled:   # two cones that hit only them, nobody dead
                out.append(fault(t, "Superchain I", [w], [w], "hit by two orange cones (not in their spread spot)", "medium", tag="sc1.orange"))
    # lasers: Astral laser shared by Astralstrong + Umbralbright + Umbral Tilts, Umbral laser the mirror
    lt = p.hits(("Astral Impact", "Umbral Impact"), 136, 139.5)
    wrong_group = set()
    if lt:
        t = lt[0]["t"]; tilt = {a: p.has_debuff_at(f"{a} Tilt", t - 0.2) for a in ("Astral", "Umbral")}
        exp = {"Astral Impact": set(S["Astralstrong"]) | set(S["Umbralbright"]) | tilt["Umbral"],
               "Umbral Impact": set(S["Umbralstrong"]) | set(S["Astralbright"]) | tilt["Astral"]}
        wrong = [(e["who"], e["name"]) for e in lt if e["who"] not in exp[e["name"]]]
        wrong_group = {w for w, _ in wrong}
        both = {e["who"] for e in lt if e["name"] == "Astral Impact"} & {e["who"] for e in lt if e["name"] == "Umbral Impact"}
        # a laser not theirs, with its own colour's Tilt, is their own death (it kills through six sharers); it only
        # helps the others in it. Listed first: a wrong-group player's death is theirs before the short laser's. Both
        # lasers on one player is a mistake even when they live (it leaves them low for what comes next)
        # where the replay reproduces a laser, whose move alone to their group's spot would have set it right (the
        # user's rule, 2026-10-27); the rules below are the fallback
        R = sc1_laser_replay(p, exp, S)
        fix = lambda nm, w, want: sc1_laser_fix(R, nm, w, want) if R and R["fits"][nm] and not any(x in p.dead_by(t - 0.3) for x in S[LASER_STRONG[nm]]) else None
        undecided = lambda w, nm: f"could not be decided whose spot put {w} in the {nm}"
        for w, nm in wrong:
            clip = w in both and any(w in ws for ws in exp.values())
            if rf := fix(nm, w, False):
                cul, conf, why, und = rf
                lead = f"took both lasers ({nm} too)" if clip else f"took {nm}, not their laser group's"
                rule = f"{undecided(w, nm)} ({'both lasers' if clip else 'not their laser'}): {why}" if und else f"{lead}: {why}"
                out.append(fault(t, "Superchain I", cul, [w], rule, conf, ability=nm, hit=clip, tag="sc1.laser.undecided" if und else "sc1.laser.both" if clip else "sc1.laser.group"))
            elif clip:
                cul, why, conf, chain = clip_blame(p, lt, exp, S, w, nm, both)
                und = False
                if chain is None and len(both) < ON_ONE_SPOT and (ma := sc1_misaim(R, nm, w)):   # at their spot: the laser's aim
                    cul, conf, why, und = ma[0], ma[1], (f"{undecided(w, nm)} (both lasers): " if ma[3] else f"took both lasers ({nm} too): ") + ma[2], ma[3]
                out.append(fault(t, "Superchain I", cul, [w], why, conf, chain=chain, ability=nm, hit=True, tag="sc1.laser.undecided" if und else "sc1.laser.both"))
            elif ma := sc1_misaim(R, nm, w):
                out.append(fault(t, "Superchain I", ma[0], [w], (f"{undecided(w, nm)} (not their laser): " if ma[3] else f"took {nm}, not their laser group's: ") + ma[2],
                                 ma[1], ability=nm, tag="sc1.laser.undecided" if ma[3] else "sc1.laser.group"))
            else: out.append(fault(t, "Superchain I", [w], [w], f"in the wrong laser group (took {nm})", "high", tag="sc1.laser.group"))
        # a laser a sharer short: whoever belonged in it and lived, but took the other or neither
        dead = p.dead_by(t - 0.3)
        missing = {}   # laser -> (its living sharers not in it, the fault blaming them)
        for nm, ws in exp.items():
            got = {e["who"] for e in lt if e["name"] == nm}
            away = sorted(ws - got - dead)
            if not got or not away: continue
            missing[nm] = (away, len(out))
            if all(fix(nm, w, True) for w in away):   # one fault for the sharers it left out, each with its reason
                rs = [fix(nm, w, True) for w in away]
                cul, conf, und = list(dict.fromkeys(x for r in rs for x in r[0])), least_sure([r[1] for r in rs]), any(r[3] for r in rs)
                miss = ", ".join(away)
                rule = (f"could not be decided whose spot left {miss} out of the {nm}; it was a sharer short: " if und
                        else f"{nm} a sharer short ({miss} not in it): ") + "; ".join(r[2] for r in rs)
                out.append(fault(t, "Superchain I", cul, got, rule, conf, tag="sc1.laser.undecided" if und else "sc1.laser.short"))
                continue
            other = [w for w in away if w in wrong_group]
            out.append(fault(t, "Superchain I", away, got, f"not in the {nm} group ({', '.join(other) + ' took the other laser' if other else 'missed it'}); it was a sharer short",
                             "high" if other else "medium", tag="sc1.laser.short"))
        # a laser short of its LASER_SHARERS because sharers of it were already dead: a death a full share would have
        # spared follows from theirs, unless its living sharers joining would have been enough (a wrong-group player's
        # death, both lasers included, stays their own). With living ones missing too, both are the one hit's causes
        for nm in exp:
            es = [e for e in lt if e["name"] == nm]
            n, gone = len({e["who"] for e in es}), sorted(w for w in dead if sc1_laser_of(p, S, w, t) == nm)
            away, k = missing.get(nm, ([], None))
            base = min(LASER_SHARERS, n + len(away))
            if not gone or not es or base >= LASER_SHARERS: continue
            for e in es:
                if e["who"] not in wrong_group and (e.get("targetResources") or {}).get("hitPoints") == 0:
                    if f := share_short(t, "Superchain I", e, n, min(LASER_SHARERS, base + len(gone)), gone, nm, base, tags=("sc1.laser.short_dead", "sc1.laser.short_undecided")):
                        out.append(f)
                        if k is not None: out[k]["ability"] = nm   # one cause with the living sharers' fault
    # Heavensflame spread: each AoE lands on its owner and hits whoever is within SC1_FLAME of them (an owner standing
    # clear never hit anyone else in 1,478 AoEs). A Strong Soul at or stepping into their tower is where they must be:
    # the Heavensflame player's, who keeps clear of the towers. Anyone else (a bright Soul stepping back, another
    # Heavensflame player; their spots vary by 10-30 y between groups): whoever closed the distance over the last
    # SC1_FLAME_WINDOW s, both when both did; within the log's error of its edge either way, or together all along, it
    # cannot be decided (both, low). The user's rule, 2026-10-27 (scratch/sc1audit/flame_moves.py)
    hh = p.hits("Theos's Holy", 145.5, 149)
    by = collections.defaultdict(list)
    for e in hh: by[e.get("sourceInstance")].append(e["who"])
    hf, told = set(S["Heavensflame"]), set()
    tc = min((e["t"] for e in p.calc if e["name"] == "Theos's Holy" and 144 <= e["t"] <= 149), default=hh[0]["t"] - 0.7 if hh else None)
    tower_of = {w: next((x[2:] for x in (p.sc1 or {}).get("towers", ()) if x[1] == OPP[k[:6]]), None)
                for k in ("Astralstrong", "Umbralstrong") for w in S[k]}

    def flame(o, v):
        """(culprits, confidence, why, tag) for owner o's Heavensflame on v, or None without positions."""
        q = [sc1_where(p, w, at) for w in (o, v) for at in (tc, tc - SC1_FLAME_WINDOW)]
        if not all(q): return None
        (qo, qo0, qv, qv0) = q
        tw = tower_of.get(v)
        # the log's error for each distance read: now, and with o's or v's move of the last SC1_FLAME_WINDOW s undone
        e, eo, ev = unc(qo[1], qv[1]), unc(qo0[1], qv[1]), unc(qo[1], qv0[1])
        at_tower, step = tw and math.dist(qv[0], tw) <= SC1_ON + unc(qv[1]), tw and math.dist(qv0[0], tw) - math.dist(qv[0], tw)
        if tw and (at_tower or step >= SC1_STEP):
            conf = certainty(SC1_ON + unc(qv[1]) - math.dist(qv[0], tw), unc(qv[1])) if at_tower else certainty(step - SC1_STEP, unc(qv[1], qv0[1]))
            return [o], conf, f"Heavensflame did not keep clear of the towers; hit {v} at their tower", "sc1.flame.spread"
        d, o_stayed, v_stayed = math.dist(qo[0], qv[0]), math.dist(qo0[0], qv[0]), math.dist(qo[0], qv0[0])
        facts = f"{d:.1f} y apart; {o_stayed:.1f} had {o} stayed, {v_stayed:.1f} had {v}"
        if d > SC1_FLAME + e:   # the positions do not even put them within reach: they cannot tell who walked in
            return [o, v], "low", f"could not be decided who walked into whose Heavensflame ({facts}: the positions miss the hit)", "sc1.flame.undecided"
        o_in, v_in = o_stayed > SC1_FLAME + eo, v_stayed > SC1_FLAME + ev
        o_out, v_out = o_stayed <= SC1_FLAME - eo, v_stayed <= SC1_FLAME - ev   # still within reach with that move undone
        c_in = lambda stayed, u: certainty(stayed - SC1_FLAME, u)     # how sure the move brought them within reach
        c_out = lambda stayed, u: certainty(SC1_FLAME - stayed, u)    # how sure they were within reach without it
        if o_in and v_in: return [o, v], least_sure([c_in(o_stayed, eo), c_in(v_stayed, ev)]), f"Heavensflame did not spread far enough: {o} and {v} both moved within reach ({facts})", "sc1.flame.spread"
        if o_in and v_out: return [o], least_sure([c_in(o_stayed, eo), c_out(v_stayed, ev)]), f"Heavensflame did not spread far enough: {o} moved within reach of {v} ({facts})", "sc1.flame.spread"
        if v_in and o_out: return [v], least_sure([c_in(v_stayed, ev), c_out(o_stayed, eo)]), f"{v} walked into {o}'s Heavensflame ({facts})", "sc1.flame.walked_in"
        return [o, v], "low", f"could not be decided who walked into whose Heavensflame ({facts})", "sc1.flame.undecided"
    for ws in by.values():
        owner = next((w for w in ws if w in hf), None)
        for v in ws:
            if v == owner or frozenset((owner, v)) in told: continue
            told.add(frozenset((owner, v)))
            r = flame(owner, v) if owner and tc is not None else None
            if v in hf:
                cul, conf, why, ftag = r or ([owner, v], "medium", "pair did not split", "sc1.flame.spread")
                out.append(fault(hh[0]["t"], "Superchain I", cul, [owner, v], f"two Heavensflame players overlapped: {why}", conf, ability="Theos's Holy", tag=ftag,
                                 share="own" if r else "one_of"))   # without positions: one of them did not spread
            else:
                cul, conf, why, ftag = r or ([owner], "medium", f"Heavensflame did not spread far enough; hit {v}", "sc1.flame.spread")
                out.append(fault(hh[0]["t"], "Superchain I", cul, [v], why, conf, ability="Theos's Holy", tag=ftag))
    # the bright Souls' small AoE as they drop their towers: only the owner belongs in it. Strong Souls wait beside it
    # before stepping in, the two bright Souls drop on opposite cardinals, and Heavensflame spreads well away from
    # everyone (a Heavensflame player in it, left low, often dies to their own Theos's Holy next, matched to this too)
    bright, strong = set(S["Astralbright"]) | set(S["Umbralbright"]), set(S["Astralstrong"]) | set(S["Umbralstrong"])
    glow = p.hits(("Astral Glow", "Umbral Glow"), 144, 147.5)
    gi = collections.defaultdict(list)
    for e in glow: gi[(e["name"], e.get("sourceInstance"))].append(e["who"])
    together, tblame = set(), None   # the bright Souls who dropped their towers on one spot; (culprits, confidence, tag) for it
    for e in glow:
        v, owner = e["who"], next((w for w in gi[(e["name"], e.get("sourceInstance"))] if w in bright), None)
        if v == owner: continue
        if owner is None and (gone := dead_soul(p, {w: a for a in ("Astral", "Umbral") for w in S[f"{a}bright"]}, e["name"], e["t"])):
            out.append(fault(e["t"], "Superchain I", gone, [v], f"{' and '.join(gone)} died holding a bright Soul; its tower dropped on {v}", "consequence", chain=gone, tag="sc1.tower.soul_dead"))
            continue
        if v in strong and owner and (dr := sc1_dropped_on(p, e["name"].split()[0], v, e["t"])):   # dropped on them, off its spot
            out.append(fault(e["t"], "Superchain I", [owner], [v], f"{owner} dropped their tower on {v}, off its spot ({dr[0]})", dr[1], tag="sc1.glow.dropped_on"))
        elif v in strong:
            out.append(fault(e["t"], "Superchain I", [v], [v], "stepped into the tower before the bright Soul's AoE went off", "high", tag="sc1.glow.early"))
        elif owner in wrong_group:   # the laser side decides the tower side
            out.append(fault(e["t"], "Superchain I", [owner], [v], f"took the wrong laser, so their tower dropped on the wrong side; its AoE hit {v}", "high", tag="sc1.tower.wrong_side"))
        elif v in bright:   # the owner is in it too: two bright Souls' AoEs together can kill either
            cul, conf, facts, ttag = ([v], "high", None, "sc1.bright_together") if v in wrong_group else \
                sc1_together(p, S) or ([owner, v] if owner else [v], "medium", None, "sc1.bright_together")   # whose tower was off its spot
            if v not in wrong_group and owner: together, tblame = {owner, v}, (cul, conf, ttag)
            out.append(fault(e["t"], "Superchain I", cul, [v] + ([owner] if owner else []),
                             f"the bright Souls dropped their towers together ({owner or 'a bright Soul'}'s AoE hit {v}); they go on opposite cardinals"
                             + (f": {facts}" if facts else ""), conf, tag=ttag))
        elif v in hf:
            out.append(fault(e["t"], "Superchain I", [v], [v], f"Heavensflame not spread away: stood in {owner + chr(39) + 's' if owner else 'a'} bright Soul's AoE as the tower dropped", "high", tag="sc1.flame.bright_aoe"))
        else:
            out.append(fault(e["t"], "Superchain I", [v], [v], f"stood in {owner + chr(39) + 's' if owner else 'a'} bright Soul's AoE as the tower dropped", "medium", tag="sc1.bright_aoe"))
    # final towers: Astralbright tower soaked by Umbralstrong (Astral Advance), Umbralbright by Astralstrong
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 147, 150.5)
    expl = p.hits("Unmitigated Explosion", 149, 156)
    for asp, soaker in (("Astral", S["Umbralstrong"]), ("Umbral", S["Astralstrong"])):
        got = [e for e in soaks if e["name"] == f"{asp} Advance"]
        # anyone in it holding its Tilt (the opposite of its colour) holds it, not only its Strong Soul: 47 of 47 towers held
        # by others with that Tilt did not explode, nor 31 with players of the wrong Tilt in them too (2026-10-27,
        # scratch/sc1audit/tower_fates.py); with a dead Strong Soul that is a save, not a mistake
        held = {e["who"] for e in got} & (p.has_debuff_at(f"{OPP[asp]} Tilt", got[0]["t"] - 0.1) if got else set())
        holder, cover = [w for w in soaker if w in held], sorted(held - set(soaker))
        for e in got:
            if e["who"] in soaker or e["who"] in cover and not holder: continue   # covering for its Strong Soul: judged below
            if together and e["who"] not in together:   # both towers on one spot: soaking one meant soaking both
                out.append(fault(e["t"], "Superchain I", tblame[0], [e["who"]], f"in the {asp} tower too, as the bright Souls dropped their towers together",
                                 tblame[1], fallout=True, tag=tblame[2]))
            else: out.append(fault(e["t"], "Superchain I", [e["who"]], [e["who"]], f"soaked the {asp} tower (meant for {', '.join(soaker)})", "high", tag="sc1.tower.wrong_player"))
        # unsoaked, or soaked only by others with the wrong Tilt: it explodes. Held by others in its Strong Soul's place,
        # it does not, but it kills them (39 of 39 Heavensflame players, 23 of 32 others; its Strong Soul lives 9 times in
        # 10): their deaths are whoever's the explosion would have been
        left = S[f"{asp}bright"] and not any(e["who"] in soaker for e in got)   # its Strong Soul not in it (in it with the wrong Tilt: below)
        sub = {e["who"] for e in got if e["who"] in cover and (e.get("targetResources") or {}).get("hitPoints", 1) == 0} if left and cover else set()
        if left and (not held or sub):
            t = expl[0]["t"] if expl else 150
            # dead before it went off, but not in the explosion itself: its deaths can come within dead_by's 2 s of the
            # towers resolving (2026-10-27: soakers alive at the resolve counted already dead)
            bt = min((e["t"] for e in p.calc if e["name"] == "Unmitigated Explosion" and e["t"] >= 147), default=t)
            dead = ({w for w in p.dead_by(t - 2) if not any(d["who"] == w and d["t"] >= bt - 0.3 for d in p.deaths)} if not sub
                    else p.dead_by(got[0]["t"]))   # held, with no explosion: dead as it resolved
            b = S[f"{asp}bright"][0]
            sk = [w for w in soaker if w not in dead]
            if sub:   # no explosion: the substitutes it killed are the victims, the absent soaker not hurt
                t, blown, mine_too = got[0]["t"], sub, False
                how, boom = f"; {', '.join(cover)} held it in their place and died to it", dict(ability=f"{asp} Advance")
            else: blown, mine_too, how, boom = {e["who"] for e in expl}, True, "", dict(ability="Unmitigated Explosion")
            hurt = lambda cul: blown | set(cul) if mine_too else blown
            # those who held it in its Strong Soul's place and died to it saved the pull: the site says so on their deaths
            put = lambda f: out.append(dict(f, saved=sorted(sub)) if sub else f)
            said = lambda r: r.replace("tower unsoaked", "tower not soaked by its Strong Soul") + how if sub else r   # it held: not "unsoaked"
            if b in p.dead_by(144):
                put(fault(t, "Superchain I", [b], blown, f"{b} died before dropping the {asp}bright tower" + (how if sub else "; it went unsoaked"),
                                 "consequence", chain=[b], **boom, tag="sc1.tower.substitute" if sub else "sc1.tower.soul_dead"))
            elif not sk:   # wherever it dropped, no one was left to soak it
                put(fault(t, "Superchain I", list(soaker), blown, f"{asp}bright tower's soaker was already dead{how}" if sub else
                                 f"{asp}bright tower unsoaked because its soaker was already dead", "consequence", chain=list(soaker), **boom, tag="sc1.tower.substitute" if sub else "sc1.tower.unsoaked"))
            elif rp := sc1_tower(p, asp, sk[0], b):   # where it dropped, and where its soaker stood
                cul, conf, why, off, ttag = rp
                lsr = f"{b} took the wrong laser, so it dropped on the wrong side; " if b in wrong_group and b in cul else ""
                und = ttag == "sc1.tower.undecided"
                rtag = ttag if und else "sc1.tower.wrong_side" if lsr and cul != [sk[0]] else ttag
                rule = (f"did not soak the {asp}bright tower: {why}" if cul == [sk[0]] else f"{asp}bright tower unsoaked, {why}" if und
                        else f"{asp}bright tower unsoaked: {lsr}{why}")
                put(fault(t, "Superchain I", cul, hurt(cul), said(rule), conf, **boom, tag="sc1.tower.substitute" if sub else rtag))
            elif b in wrong_group:   # the laser side decides the tower side, so this tower landed away from its soaker
                put(fault(t, "Superchain I", [b], hurt([b]), said(f"{asp}bright tower unsoaked: {b} took the wrong laser, so it dropped on the wrong side"), "high", **boom, tag="sc1.tower.substitute" if sub else "sc1.tower.wrong_side"))
            else: put(fault(t, "Superchain I", sk, hurt(sk), said(f"did not soak the {asp}bright tower"), "high", **boom, tag="sc1.tower.substitute" if sub else "sc1.tower.unsoaked"))
        # soaked by its Strong Soul, but with the wrong Tilt (the tower takes the opposite one): it explodes all the same,
        # whether they live or not (2026-10-26: 81 such towers exploded, 7 did not, in pulls that had already ended).
        # The Tilt came from the bright Soul's AoE when they stepped in early, or from the other laser
        mine = [e["who"] for e in got if e["who"] in soaker]
        if mine and S[f"{asp}bright"] and not held:
            w, t, blown, boom = mine[0], expl[0]["t"] if expl else 150, {e["who"] for e in expl}, dict(ability="Unmitigated Explosion")
            src = next((f for f in out if f["victims"] == {w} and (f["tag"] in ("sc1.glow.early", "sc1.glow.dropped_on", "sc1.laser.group")
                                                                    or f.get("ability") in LASER_STRONG)), None)
            why = ("the bright Soul's AoE gave it as they stepped in early" if src and src["tag"] == "sc1.glow.early"
                   else "the bright Soul's AoE gave it, dropped on them" if src and src["tag"] == "sc1.glow.dropped_on"
                   else "from the laser they took" if src else "cause unclear")
            rule = f"the {asp} tower failed: {w} soaked it with the wrong Tilt ({why})"
            if src:   # the mistake that gave them the Tilt, with its culprits' shares (one of two undecided stays one of two)
                f = fault(t, "Superchain I", src["culprits"], blown, rule, src["confidence"], chain=src["chain"], after=src, **boom, tag="sc1.tower.wrong_tilt")
                out.append(dict(f, shares=dict(src["shares"]), chain_share=src["chain_share"]))
            else: out.append(fault(t, "Superchain I", [w], blown | {w}, rule, "medium", **boom, tag="sc1.tower.wrong_tilt_unclear"))
    return out


# ---------- Dialogos: the tanks' shared hit and the party stack ----------
# Athena stands at the arena centre. Peridialogos aims the tanks' hit at the closest player and the stack at the
# farthest; Apodialogos the other way round. So the tanks belong at the centre for Peridialogos and out for Apodialogos,
# the party the opposite. Measured at the hits (r from the centre, clean resolutions): Peridialogos tanks r <= 5.6,
# party >= 7.7; Apodialogos party <= 8.4, tanks >= 9.8. CENTRE_R splits the two bands.
CENTRE_R = {"Peridialogos": 6.6, "Apodialogos": 9.1}


def dialogos(p):
    """Apodialogos or Peridialogos is one hit the two tanks share (alone, one takes twice the damage: 265k unmitigated
    for Apodialogos, 490k for Peridialogos, against 135k each for two), aimed at one player and hitting those in line
    with them; Dialogos, about 0.6 s later, is a stack the rest of the party shares (78k each for six, 448k alone).
    Concussion, the tank hit's damage over time, follows. A player's place is read from their position at either hit;
    one hit by neither has no position, and is only blamed as missing from a hit that needed them."""
    out = []
    tb = p.hits(("Apodialogos", "Peridialogos"), 165, 180)
    if not tb: return out
    t, nm = tb[0]["t"], tb[0]["name"]
    st = p.hits("Dialogos", t - 1, t + 2.5)
    in_tb, in_st = {e["who"] for e in tb}, {e["who"] for e in st}
    dead = p.dead_by(t - 0.3) - in_tb - in_st
    is_tank = lambda w: p.job.get(w) in TANK_JOBS
    tanks = {w for w in p.job if is_tank(w)} - dead
    party = set(p.job) - tanks - dead
    peri = nm == "Peridialogos"
    where = lambda centre: "at the centre" if centre else "out"
    r = {}
    for e in tb + st:
        if e["pos"] and e["who"] not in r: r[e["who"]] = math.hypot(*e["pos"])
    misplaced = lambda w: w in r and (r[w] < CENTRE_R[nm]) != (is_tank(w) == peri)   # tanks at the centre for Peridialogos
    pick = lambda ws, closest: (min if closest else max)((w for w in ws if w in r), key=r.get, default=None)
    # how sure a verdict resting on where they stood is: their distance from the band's split against the log's error at
    # the hit (one not out of place, or in the hit, is the log's own fact)
    placed = lambda w: certainty(abs(r[w] - CENTRE_R[nm]), unc(0)) if misplaced(w) else "high"
    target = pick(in_tb, peri)                     # the player the tanks' hit was aimed at
    blamed = set()
    # the tanks' hit: a non-tank in it took it (from the tanks' place, or in line with them), unless it was aimed at a
    # non-tank standing where the party belongs: then the tanks were not where they belong
    out_t, extra = sorted(tanks - in_tb), sorted(in_tb - tanks)
    if extra and target and not is_tank(target) and not misplaced(target):
        cul = sorted(w for w in tanks if w not in in_tb or misplaced(w))
        if cul:
            out.append(fault(t, "Dialogos", cul, in_tb, f"not {where(peri)} for {nm} (the tanks' hit goes to the {'closest' if peri else 'farthest'} "
                             f"player); it went to {target} and hit {', '.join(extra)}", least_sure([placed(w) for w in cul]), ability=nm, tag="dlg.tank_share"))
            blamed |= set(cul)
    else:
        for x in extra:
            how = f"stood {where(peri)} with the tanks" if misplaced(x) else "stood in line with the tanks"
            out.append(fault(t, "Dialogos", [x], [x], f"{how} for {nm} (a hit the two tanks share)", placed(x), ability=nm, tag="dlg.tank_share"))
            blamed.add(x)
        if out_t and target and is_tank(target):
            out.append(fault(t, "Dialogos", out_t, in_tb, f"left {nm} to {', '.join(sorted(in_tb & tanks))} (the two tanks share it)", "high", ability=nm, tag="dlg.tank_share"))
            blamed |= set(out_t)
    gone = sorted({w for w in p.job if is_tank(w)} & dead)
    if gone and not out_t and not extra and in_tb:
        out.append(fault(t, "Dialogos", gone, in_tb, f"{', '.join(sorted(in_tb))} took {nm} alone because {', '.join(gone)} was already dead (the two tanks share it)", "consequence", chain=gone, ability=nm, tag="dlg.tank_share"))
    # the stack: aimed at a tank, that tank stood where the party belongs; aimed at the party, whoever of the party
    # is not in it left it (one in the tanks' hit counts once: a culprit's faults within 2 s are one mistake)
    s_target = pick(in_st, not peri)
    if s_target and is_tank(s_target):
        cul = sorted(w for w in in_st if is_tank(w) and w not in blamed)
        if cul: out.append(fault(st[0]["t"], "Dialogos", cul, in_st, f"stood {where(not peri)} where the party stacks for {nm}; the Dialogos stack went to them", "high", ability="Dialogos", tag="dlg.stack"))
    elif s_target:   # one the tanks' hit had just killed could not be in it: the stack's shortfall is that death's
        killed = sorted(w for w in party & in_tb if any(e["who"] == w and (e.get("targetResources") or {}).get("hitPoints") == 0 for e in tb))
        miss = sorted(party - in_st - set(killed))
        if miss: out.append(fault(st[0]["t"], "Dialogos", miss, in_st, f"not in the Dialogos stack: {len(in_st & party)} of the party's {len(party)} shared it", "high", ability="Dialogos", tag="dlg.stack"))
        if killed and not killed[0] in in_st:
            out.append(fault(st[0]["t"], "Dialogos", killed, in_st, f"the Dialogos stack was short: {', '.join(killed)} died to {nm} just before", "consequence",
                             chain=killed, ability="Dialogos", tag="dlg.stack"))
        # the rest of the party already dead: a death a full stack would have spared follows from theirs
        gone = sorted(w for w in dead if not is_tank(w))
        for e in st if gone else []:
            if (e.get("targetResources") or {}).get("hitPoints") == 0:
                base = len(in_st) + len(miss) + len(killed)   # the living who left it, and the tanks' hit's dead, first
                if f := share_short(e["t"], "Dialogos", e, len(in_st), base + len(gone), gone, "Dialogos stack", base, tags=("dlg.stack", "dlg.stack")): out.append(f)
    return out


# ---------- the rule book ----------
# Which rules judge each mechanic, by the raid day they take effect (the report's local date, as the site groups raid
# days). A pull is judged by the latest entry dated on or before its day, so patching a mechanic's strategy is a new
# dated entry and older pulls keep the rules they were played under. GENERIC (also a mechanic not listed, or a day
# before its first entry) leaves only the generic rules: standing in an avoidable AoE is the victim's mistake.
# NOT_YET blames no one for anything in the mechanic: the groups are still learning it or have no settled strategy.
# a mechanic with no rule function: GENERIC blames avoidable hits and their fallout, NOT_YET no one, AVOIDABLE_ONLY
# (before the group had a strategy for it) only avoidable hits and deaths within STUNG_S of one
GENERIC, NOT_YET, AVOIDABLE_ONLY = "generic", "not yet", "avoidable only"
CONF_ORDER = {"high": 0, "medium": 1, "low": 2}   # surest first
least_sure = lambda confs: max(confs, key=lambda c: CONF_ORDER.get(c, 1))


# which of several faults about one hit names it (its tag): tether failures first, then tower failures, in this order;
# any other rule after them, the direct causes first. The order the labels had when they were read from the text
MAIN_ORDER = ("p2.tether.not_stretched", "p3.tether.not_stretched", "p2.tether.undecided", "p2.tether.holder_off", "p3.tether.clipped",
              "p3.tether.holder_off", "p3.tether.dead_holder", "p2.tether.stood_in", "p3.tether.stood_in",
              "p3.support_tower.empty", "sc1.tower.substitute", "sc1.tower.wrong_tilt", "sc1.tower.wrong_tilt_unclear", "p2.tower.undecided",
              "sc1.tower.undecided", "p3.support_tower.dps", "p2.tower.soul_dead", "p3.tower.soul_dead", "sc1.tower.soul_dead",
              "p2.tower.wrong_quadrant", "p2.soul.wrong_quadrant", "sc1.tower.wrong_side", "p2.tower.out_of_reach", "sc1.tower.out_of_reach",
              "sc1.glow.dropped_on", "sc1.tower.dropped_on", "p3.tower.misplaced", "sc1.glow.early", "p2.tower.unsoaked", "p2.tower.unclear",
              "p3.tower.unsoaked", "sc1.tower.unsoaked", "p2.tower.wrong_player", "p3.tower.wrong_player", "sc1.tower.wrong_player")
main_tag = lambda fs: min((f["tag"] for f in fs), key=lambda t: MAIN_ORDER.index(t) if t in MAIN_ORDER else len(MAIN_ORDER))


def merged(fs):
    """Faults about the same hit as one cause (an explosion of two unsoaked towers): their culprits and chains together."""
    if len(fs) == 1: return fs[0]
    direct = [f for f in fs if not f["chain"]]
    culprits = list(dict.fromkeys(c for f in direct for c in f["culprits"]))
    return dict(fs[0], culprits=culprits, chain=list(dict.fromkeys(n for f in fs for n in f["chain"])), direct=culprits, tag=main_tag(direct or fs),
                shares={c: max(f["shares"].get(c, 0) for f in direct if c in f["culprits"]) for c in culprits},
                direct_conf=least_sure([f["confidence"] for f in direct]) if direct else None,
                confidence=least_sure([f["confidence"] for f in direct]) if direct else "consequence",
                # the direct causes first: a cause's label comes from before "; earlier"
                rule="; earlier: ".join(r for r in ("; ".join(dict.fromkeys(f["rule"] for f in direct)), "; ".join(dict.fromkeys(f["rule"] for f in fs if f["chain"]))) if r),
                victims=set().union(*(f["victims"] for f in fs)),
                fallout=bool(direct) and all(f["fallout"] for f in direct), parts=fs, saved=sorted({w for f in fs for w in f.get("saved", ())}))
RULEBOOK = {
    "Paradeigma I": [(None, AVOIDABLE_ONLY),   # before the group's strategy: only avoidable hits (Trinity of Souls)
                     ("2026-09-29", lambda p, lp: para1(p, lp) + para1_auto(p, lp))],   # the strategy took effect
    "Paradeigma II": [(None, AVOIDABLE_ONLY),   # likewise (Ray of Light)
                      ("2026-09-29", lambda p, lp: para2(p))],
    "Glaukopis": [(None, AVOIDABLE_ONLY), ("2026-09-29", lambda p, lp: glaukopis(p, 92, 110))],   # the tank swap, with Paradeigma I and II's
    "Superchain I": [(None, AVOIDABLE_ONLY),   # before the group's strategy: only avoidable hits (orb, donut) are blamed
                     ("2026-10-06", superchain1)],   # the strategy officially introduced
    "Dialogos": [(None, AVOIDABLE_ONLY), ("2026-10-06", lambda p, lp: dialogos(p))],   # with Superchain I's
    "Paradeigma III": [(None, AVOIDABLE_ONLY),
                       ("2026-10-25", lambda p, lp: para3(p, lp, bright_by="light_party")),   # the original strategy arrived: bright Souls by light party
                       ("2026-10-26", lambda p, lp: para3(p, lp, bright_by="priority"))],   # bright Souls by H1 > T1 > T2 > H2
    "Glaukopis / Ultima Blade": [(None, AVOIDABLE_ONLY), ("2026-09-29", lambda p, lp: glaukopis(p, 236, 280))],   # the same swap
    "Palladion": [(None, NOT_YET)],   # to start blaming it: ("YYYY-MM-DD", GENERIC) or a rule
}


def strategy_dates():
    """The rule book's dated entries, for the site's charts: [{day, mechanics, kind}], kind "added" when a mechanic
    starts being blamed by a strategy (after AVOIDABLE_ONLY, NOT_YET or GENERIC), "changed" when its rules change."""
    out = {}
    for mech, versions in RULEBOOK.items():
        for (_, before), (since, rule) in zip(versions, versions[1:]):
            kind = "changed" if callable(before) else "added"
            out.setdefault((since, kind), []).append(mech)
    return [dict(day=d, kind=k, mechanics=ms) for (d, k), ms in sorted(out.items())]


def rules_on(day):
    """{mechanic: rule function, GENERIC or NOT_YET} for a raid day ("YYYY-MM-DD"); None means the latest rules."""
    out = {}
    for mech, versions in RULEBOOK.items():
        on = [rule for since, rule in versions if since is None or day is None or since <= day]
        out[mech] = on[-1] if on else GENERIC
    return out


# deaths no mechanic explains, from what the user recognised in them (2026-10-26)
EARLY_PULL_S = 15     # before the first mechanic: Athena's first auto-attack on a non-tank means she was pulled early,
                      # and the non-tanks her autos kill before one reaches a tank are its fallout
BROKEN_GEAR = 0.5     # max HP under this share of the other non-tanks' median: broken gear (one player, at 5%, in the caches)
RAIDWIDES = {"On the Soul", "Ultima Blade"}   # hit every living player (On the Soul 1,591 of 1,683 casts; Ultima Blade 14
                              # of 14) and are survived with healing and mitigation; Unmitigated Explosion (a tower failure),
                              # Superchain Radiation (a cone at each player) and Theos's Ultima (shared damage) are not
FELL_GAP, FELL_HP, FELL_LEFT = 1.0, 0.25, 6   # a death with no hit, the last at least FELL_GAP s before with FELL_HP of
                                              # their HP left, and the pull going on FELL_LEFT s more: fell off the arena?


def broken_gear(p):
    """{player: (their max HP, the other non-tanks' median)} for players whose max HP is far below the party's."""
    mx = collections.defaultdict(list)
    for e in p.dmg:
        if m := (e.get("targetResources") or {}).get("maxHitPoints"): mx[e["who"]].append(m)
    med = {w: sorted(v)[len(v) // 2] for w, v in mx.items()}
    out = {}
    for w, m in med.items():
        others = sorted(v for x, v in med.items() if x != w and p.job.get(x) not in TANK_JOBS)
        if others and m < BROKEN_GEAR * others[len(others) // 2]: out[w] = (m, others[len(others) // 2])
    return out


def early_puller(p):
    """(the non-tank Athena's first auto-attack hit before EARLY_PULL_S, so she was pulled early, often by a ranged
    click; until when her autos found no tank), or (None, 0)."""
    autos = sorted((e for e in p.dmg if e["name"] == "attack"), key=lambda e: e["t"])
    if not autos or autos[0]["t"] >= EARLY_PULL_S or p.job.get(autos[0]["who"]) in TANK_JOBS: return None, 0
    return autos[0]["who"], next((e["t"] for e in autos if p.job.get(e["who"]) in TANK_JOBS), float("inf"))


def fell_off(p, i, incs):
    """A death with no hit that is not a jump: their last hit at least FELL_GAP s before, at FELL_HP of their HP or more,
    the pull going on more than FELL_LEFT s, and not the first of a wave of jumps (two more deaths with no hit within 3 s,
    the start of a wipe call by players already low)."""
    if i["kind"] != "death" or i["ability"] != "?" or i.get("jump") or (p.e - p.s) / 1000 - i["t"] <= FELL_LEFT: return False
    last = next((e for e in reversed(p.dmg) if e["who"] == i["victim"] and e["t"] <= i["t"] + 2), None)
    tr = (last or {}).get("targetResources") or {}
    if last and (i["t"] - last["t"] < FELL_GAP or tr.get("hitPoints", 0) < FELL_HP * tr.get("maxHitPoints", 1)): return False
    return sum(1 for j in incs if j is not i and j["kind"] == "death" and j["ability"] == "?" and 0 < j["t"] - i["t"] <= 3) < 2


def classify(p, lp, day=None):
    """Every Damage Down and lethal hit in the pull with its mechanic, cause, culprits and confidence, judged by the
    rule book on the pull's raid day. Entries marked derived=True are fallout of an earlier mistake (blame carried over
    from it), not a new mistake of their own; jump=True is a death without a hit (jumping off the arena). A mistake that
    counts though no death or Damage Down followed is an entry of kind "hit"."""
    rules = rules_on(day)
    faults = sorted((f for rule in rules.values() if callable(rule) for f in rule(p, lp)), key=lambda f: f["t"])
    res, used = [], set()       # used: faults already counted at an incident

    def from_chain(i, f):
        """Blame whoever caused the deaths behind a fault (its chain), as sure as the least sure of them, besides the
        fault's own culprits when it merges a direct one; those carried over from the earlier deaths are not counted
        again (carried). Several faults about one hit (two unsoaked towers) are told side by side: the direct ones, then
        "and at once" the chained ones, "(1) ... (2) ..." when several, each with the earlier deaths behind it. The same story as a tree for the site (trace): {rule, deaths:
        [{who, t, by, why: the death's own tree}]}, or for several causes {parts: [their trees]}."""
        direct = f.get("direct", [])
        # the death behind it is the one before the fault, not a later one (raised, they can die again in its fallout: yd7c pull 26)
        why_of = lambda chain, t: [(n, r) for n in chain for r in [next((r for r in reversed(res) if r["victim"] == n and r["kind"] == "death" and r["t"] <= t), None)] if r and r["culprits"]]
        why = why_of(f["chain"], f["t"])
        culprits = list(dict.fromkeys(direct + [c for _, r in why for c in r["culprits"]]))
        follows = list(dict.fromkeys(f["chain"] + [n for g in f.get("parts", []) for n in g["chain"]]))   # whose deaths it follows from
        if not culprits: return dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=[], shares={}, confidence="consequence", derived=True, follows=follows, tag=f["tag"])
        # each one's share: a direct culprit's from the fault, a carried one's that of the dead player's slot (chain_share)
        # times theirs in that death; one culprit named twice keeps the larger
        shares = {}
        give = lambda c, x: shares.__setitem__(c, min(1.0, max(shares.get(c, 0.0), x)))
        for c in direct: give(c, f.get("shares", {}).get(c, 1.0))
        for g in f.get("parts", [f]):
            for n, r in why_of(g["chain"], g["t"]):
                for c in r["culprits"]: give(c, g.get("chain_share", 1.0) * r.get("shares", {}).get(c, 1.0))
        by = lambda n, r: "their own mistake" if r["culprits"] == [n] else "caused by " + ", ".join(r["culprits"])
        trace = lambda rule, ws: rule + ("; earlier: " + "; ".join(f"{n}'s death, {by(n, r)}: {r['cause']}" for n, r in ws) if ws else "")
        cause = trace(f["rule"], why)
        if f.get("parts"):   # the direct causes first, then "and at once" each chained one's trace: causes of the one hit
            # (both towers exploding), not one the background of the other (it read "; earlier:", 2026-10-28)
            chained = list(dict.fromkeys(trace(g["rule"], why_of(g["chain"], g["t"])) for g in f["parts"] if g["chain"]))
            plain = "; ".join(dict.fromkeys(g["rule"] for g in f["parts"] if not g["chain"]))
            told = " ".join(f"({k}) {t}" for k, t in enumerate(chained, 1)) if len(chained) > 1 else "".join(chained)
            cause = plain + ("; and at once: " + told if told else "") if plain else told   # the label comes from before "; and at once"
        tree = lambda rule, ws: dict(rule=rule, **({"deaths": [dict(who=n, t=round(r["t"], 1), by=r["culprits"], why=r.get("trace") or dict(rule=r["cause"])) for n, r in ws]} if ws else {}))
        node = tree(f["rule"], why)
        if f.get("parts"):
            nodes = ([dict(rule=plain)] if plain else []) + list({json.dumps(t, sort_keys=True): t for t in (tree(g["rule"], why_of(g["chain"], g["t"])) for g in f["parts"] if g["chain"])}.values())
            node = dict(parts=nodes) if len(nodes) > 1 else nodes[0]   # several causes of one hit: told side by side
        return dict(i, mechanic=f["mechanic"], cause=cause, trace=node, follows=follows, tag=f["tag"],
                    culprits=culprits, shares={c: shares.get(c, 1.0) for c in culprits}, derived=not direct, carried=[c for c in culprits if c not in direct] if direct else [],
                    confidence=least_sure(([f["direct_conf"]] if direct else []) + [r["confidence"] for _, r in why]
                                          + [g["cap"] for g in f.get("parts", [f]) if g.get("cap")]))   # cap: a chain the rule is unsure of

    def add(r):
        """A mistake in a NOT_YET mechanic keeps its cause but blames no one, as does a death there no rule explains;
        fallout of an earlier one keeps its blame.
        In an AVOIDABLE_ONLY one, only an avoidable hit's blame stays (own_hit); its other deaths are not blamed, not
        left to the rules for deaths no rule explains. Every entry carries its rule's tag."""
        if not r.get("tag"): raise ValueError(f"an entry without a rule tag: {r.get('cause')}")
        gate = rules.get(r["mechanic"])
        if (r["culprits"] and gate == NOT_YET and not r.get("derived") or not r["culprits"] and gate == NOT_YET and not r.get("jump")
                or gate == AVOIDABLE_ONLY and not r.get("own_hit") and not r.get("jump")):
            why = f"no rules for {r['mechanic']} yet" if gate == NOT_YET else f"no strategy for {r['mechanic']} yet on this day"
            r = dict(r, culprits=[], confidence="not blamed", cause=f"{r['cause']} (not blamed: {why})")
        r["shares"] = {c: r.get("shares", {}).get(c, 1.0) for c in r["culprits"]}   # each culprit's share of the mistake
        res.append(r)
    incs, gear, (puller, untanked) = p.incidents(), broken_gear(p), early_puller(p)
    called = min((i["t"] for i in incs if i.get("jump")), default=float("inf"))   # the first jump: the wipe was called
    for i in incs:
        mech = mech_at(i["t"])
        if i.get("jump"):
            add(dict(i, mechanic=mech, cause="left the arena without taking a hit (jumped off: wipe called?)", culprits=[], confidence="unattributed", tag="jump"))
            continue
        # the faults about the very hit that killed them (one cause together), else, unless the hit was an avoidable one,
        # the earliest fault that hit them
        near = [f for f in faults if i["victim"] in f["victims"] and -1.5 <= i["t"] - f["t"] <= 4.5]
        about = [f for f in near if f.get("ability") == i["ability"]]
        f = merged(about) if about else None if i["ability"] in AVOIDABLE else near[0] if near else None
        # an avoidable hit just before a death blamed on others (or no one) makes it the victim's own mistake (fallout
        # of that hit's incident, if it had one)
        stung = i["kind"] == "death" and i["ability"] not in AVOIDABLE and not (f and not f["chain"] and f["culprits"] == [i["victim"]]) and next(
            (e for e in reversed(p.dmg) if e["who"] == i["victim"] and e["name"] in AVOIDABLE and 0 <= i["t"] - e["t"] <= STUNG_S), None)
        if stung:
            hit = next((r for r in reversed(res) if r["victim"] == i["victim"] and r["ability"] == stung["name"] and i["victim"] in r["culprits"]
                        and abs(r["t"] - stung["t"]) <= 0.5), None)
            cause = AVOIDABLE[stung["name"]]
            add(dict(i, mechanic=mech, culprits=[i["victim"]], confidence="high", own_hit=True, tag=f"avoid.{stung['name']}",
                     **(dict(cause=f"after their earlier {hit['kind']}: {cause}", derived=True) if hit else dict(cause=f"{cause}, then {i['ability']} killed them"))))
            continue
        # the faults about the very hit that killed them (one cause together), else, unless the hit was an avoidable one,
        # the earliest fault that hit them
        near =[f for f in faults if i["victim"] in f["victims"] and -1.5 <= i["t"] - f["t"] <= 4.5]
        about = [f for f in near if f.get("ability") == i["ability"]]
        f = merged(about) if about else None if i["ability"] in AVOIDABLE else near[0] if near else None
        if f is None and i["ability"] == "Unmitigated Explosion":   # an explosion that reached someone no tower fault names
            tw = [f for f in faults if f.get("ability") == i["ability"] and abs(i["t"] - f["t"]) <= 4.5] \
                 or [f for f in faults if f["tag"].split(".")[1] in ("tower", "support_tower") and abs(i["t"] - f["t"]) <= 4.5][:1]
            f = merged(tw) if tw else None
        own = None
        if f is None and i["ability"] not in AVOIDABLE:   # later fallout of a mistake that hurt them earlier in the same mechanic
            hurt = [g for g in reversed(faults) if g["mechanic"] == mech and 0 < i["t"] - g["t"] <= 15 and i["victim"] in g["victims"]]
            # their own first, then one about them alone (the laser they took) before one about a group (a laser short)
            own = next((g for g in hurt if i["victim"] in g["culprits"]), next((g for g in hurt if g["victims"] == {i["victim"]}), hurt[0] if hurt else None))
        prev = next((r for r in reversed(res) if r["victim"] == i["victim"] and r["culprits"] and 0 <= i["t"] - r["t"] <= 10), None)
        if f:   # the mistakes these faults follow from (after): counted already, at an earlier incident?
            parts = f.get("parts", [f])
            direct = [g for g in parts if not g["chain"]]
            prior = [g["after"] for g in direct if g.get("after")]
            again = bool(direct) and len(prior) == len(direct) and all(id(g) in used for g in prior)
            used.update(id(g) for g in parts + prior)
        saved = {"saved": True} if f and i["victim"] in f.get("saved", ()) else {}   # died holding what would have lost the pull
        if f and f["chain"]:
            r = from_chain(i, f)
            add(dict(r, derived=True, carried=[], **saved) if again and r["culprits"] else dict(r, **saved))
        elif f:
            add(dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=f["culprits"], shares=f["shares"], confidence=f["confidence"], tag=f["tag"], **saved, **({"derived": True} if f["fallout"] or again else {})))
        elif prev and i["ability"] not in AVOIDABLE:
            add(dict(i, mechanic=mech, cause=f"after their earlier {prev['kind']}: {prev['cause']}", culprits=prev["culprits"], shares=prev["shares"], confidence="medium", derived=True, tag=prev["tag"]))
        elif own and own["chain"]:
            used.add(id(own))
            add(from_chain(i, own))
        elif own and id(own) in used:   # the mistake was already counted at an earlier incident
            add(dict(i, mechanic=mech, cause=f"after their earlier mistake: {own['rule']}", culprits=own["culprits"], shares=own["shares"], confidence="medium", derived=True, tag=own["tag"]))
        elif own:   # the mistake's first incident: it counts here
            used.add(id(own))
            add(dict(i, mechanic=own["mechanic"], cause=own["rule"], culprits=own["culprits"], shares=own["shares"], confidence=own["confidence"], tag=own["tag"]))
        elif i["ability"] in AVOIDABLE:
            add(dict(i, mechanic=mech, cause=AVOIDABLE[i["ability"]], culprits=[i["victim"]], confidence="high", own_hit=True, tag=f"avoid.{i['ability']}"))
        elif (i["kind"] == "death" and puller and i["t"] < untanked and p.job.get(i["victim"]) not in TANK_JOBS   # killed by an auto
              and any(e["who"] == i["victim"] and e["name"] == "attack" and (e.get("targetResources") or {}).get("hitPoints") == 0
                      and i["t"] - 4 <= e["t"] <= i["t"] + 2 for e in p.dmg)):
            add(dict(i, mechanic=mech, cause=f"{puller} pulled Athena early: her first auto-attack went to them, not a tank (an accidental pull?)",
                     culprits=[puller], confidence="medium", own_hit=True, early_pull=True, tag="early_pull", **({"derived": True} if any(r.get("early_pull") for r in res) else {})))
        elif i["kind"] == "death" and i["victim"] in gear:
            m, med = gear[i["victim"]]
            add(dict(i, mechanic=mech, cause=f"had {m:,} max HP against the party's ~{med:,} (broken gear?)", culprits=[i["victim"]], confidence="medium", own_hit=True, tag="broken_gear"))
        elif fell_off(p, i, incs):
            add(dict(i, mechanic=mech, cause="died without taking a hit while the pull went on (fell off the arena?)", culprits=[i["victim"]], confidence="low", own_hit=True, tag="fell_off"))
        elif i["ability"] == "Shockwave":
            add(dict(i, mechanic=mech, cause="stood in Athena's dash line (Palladion Shockwave)", culprits=[i["victim"]], confidence="medium", tag="palladion.dash"))
        elif i["kind"] == "death" and i["ability"] in RAIDWIDES and i["t"] < called:
            # a raidwide no rule explains, before the wipe was called (no one heals after the first jump): healing and
            # mitigation fell short, and in this game's design shields,
            # mitigation and HP restoration come from every role, so no one's part can be told: everyone alive shares
            # it (low), and the dead are passed to whoever caused their deaths (the user's rule, 2026-10-28)
            dead = sorted(p.dead_by(i["t"] - 0.3) - {i["victim"]})
            alive = sorted(w for w in p.job if w not in dead)
            f = dict(fault(i["t"], mech, alive, [i["victim"]], f"{i['ability']}: healing and mitigation fell short, everyone shares it (no one's part can be told)" +
                           (f"; {', '.join(dead)} already dead" if dead else ""), "low", chain=dead, tag="raidwide", share="together"), direct=alive, direct_conf="low")
            add(from_chain(i, f))
        elif i["ability"] == "attack" and p.job.get(i["victim"]) in TANK_JOBS:
            add(dict(i, mechanic=mech, cause="tank died to auto-attacks (mitigation / tank swap)", culprits=[], confidence="unattributed", tag="tank_autos"))
        else:
            earlier = [r for r in res if r["t"] < i["t"] - 0.5 and r["culprits"]]
            add(dict(i, mechanic=mech, cause=f"{i['kind']} to {i['ability']}" + (" after an earlier mistake" if earlier else " (no rule matched: likely HP / mitigation)"),
                            culprits=[], confidence="consequence" if earlier else "unattributed", tag="unexplained"))
    # mistakes that count without a death or Damage Down to carry them (both lasers on a player who lived)
    for f in faults:
        if f["hit"] and id(f) not in used:
            for v in sorted(f["victims"]):
                i = dict(t=f["t"], kind="hit", victim=v, ability=f["ability"], pos=None)
                add(from_chain(i, f) if f["chain"] else dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=f["culprits"], shares=f["shares"], confidence=f["confidence"], tag=f["tag"]))
    # the deaths that left no one alive: the party had wiped, and later deaths (players raised after it) are part of it
    for r in res:
        if r["kind"] == "death" and not r.get("jump") and not set(p.job) - p.dead_by(r["t"] + 0.1): r["party_dead"] = True
    return sorted(res, key=lambda r: r["t"]), faults
