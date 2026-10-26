"""P12S P1 mistake classifier.

Finds every Damage Down and lethal hit in a pull, then attributes it using the party strategy
from xivsim's briefs.html (Paradeigma I light-party baits, Paradeigma II quadrant sweep,
Superchain I laser groups / pairs / towers, Paradeigma III platforms) and the tank swap and shares
the logs show (Glaukopis, Dialogos). Which rules judge a mechanic depends on the raid day (RULEBOOK).
Anything the rules cannot explain falls back to "avoidable AoE -> victim" or stays unattributed.
"""
import collections, math

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
        self.deb = [e for e in ev["debuffs"] if inf(e) and e.get("targetID") in self.players]
        self.deaths = [e for e in rep["deaths"] if inf(e) and e.get("targetID") in self.players]
        for e in self.dmg + self.deb + self.deaths:
            e["t"] = (e["timestamp"] - self.s) / 1000
            e["who"] = self.players[e["targetID"]]
            e["name"] = self.ab.get(e.get("abilityGameID"), "?")
            tr = e.get("targetResources")
            e["pos"] = ((tr["x"] - 10000) / 100, (tr["y"] - 10000) / 100) if tr and "x" in tr else None

    # helpers
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


def fault(t, mech, culprits, victims, rule, conf, chain=None, ability=None, fallout=False):
    """chain: players whose earlier death caused this; their death's culprits are blamed instead when there is one.
    ability: the hit the fault is about; a death to it goes to this fault before an earlier one that hit the victim, and
    faults about the same hit are one cause. fallout: its deaths are fallout of a mistake its culprits made earlier."""
    return dict(t=t, mechanic=mech, culprits=list(dict.fromkeys(culprits)), victims=set(victims), rule=rule, confidence=conf,
                chain=chain or [], ability=ability, fallout=fallout)


# ---------- Paradeigma I: White Flame light-party baits ----------
def infer_light_parties(pulls):
    """LP1 baits the first White Flame wave, LP2 the second; learn who is who from clean single hits."""
    c1, c2 = collections.Counter(), collections.Counter()
    for p in pulls:
        for (lo, hi), c in (((37, 41.5), c1), ((42, 46.5), c2)):
            by = collections.defaultdict(list)
            for e in p.hits("White Flame", lo, hi): by[e.get("sourceInstance")].append(e["who"])
            for ws in by.values():
                if len(ws) == 1: c[ws[0]] += 1
    lp1 = {w for w, _ in c1.most_common(4)}
    lp2 = [w for w, n in c2.most_common() if w not in lp1][:4]   # keep the count order, not set order, before cutting to four
    return lp1, set(lp2)


def para1(p, lp):
    out = []
    for w, (lo, hi) in ((1, (37, 41.5)), (2, (42, 46.5))):
        hs = p.hits("White Flame", lo, hi)
        if not hs: continue
        t = min(e["t"] for e in hs); dead = p.dead_by(t - 0.5)
        cnt = collections.Counter(e["who"] for e in hs)
        exp = {x for x in lp[w - 1] if x in p.job and x not in dead}
        gone = sorted(x for x in lp[w - 1] if x in p.job and x in dead)
        missing = [x for x in sorted(exp) if x not in cnt]
        extra = [x for x in cnt if x not in exp] + [x for x, n in cnt.items() if n >= 2 and x in exp]
        # an extra player hit only by lasers that also hit their own baiter stood in that baiter's line: their own mistake
        by = collections.defaultdict(set)
        for e in hs: by[e.get("sourceInstance")].add(e["who"])
        lined = [x for x in extra if x not in exp and all(ws & exp for ws in by.values() if x in ws)]
        if missing:
            took = [x for x in extra if x not in lined]
            out.append(fault(t, "Paradeigma I", missing, took, f"not in the White Flame line-up (wave {w}); the laser went to {', '.join(took) or 'someone else'}", "high" if took else "medium"))
            for x in lined:
                out.append(fault(t, "Paradeigma I", [x], [x], f"took a White Flame meant for wave {w} baiters (stood in a laser line)", "medium"))
        elif extra and len(extra) <= len(gone):   # a baiter was already dead, so their laser found someone else
            out.append(fault(t, "Paradeigma I", gone, extra, f"White Flame (wave {w}) went to {', '.join(extra)} because {'its baiter' if len(gone) == 1 else 'its baiters'} {', '.join(gone)} {'was' if len(gone) == 1 else 'were'} already dead", "consequence", chain=gone))
        elif extra:
            for x in extra:
                out.append(fault(t, "Paradeigma I", [x], [x], f"took a White Flame meant for wave {w} baiters (stood in a laser line)", "medium"))
    return out


def para1_auto(p, lp):
    """Athena's auto-attacks are magical, and a White Flame leaves Magic Vulnerability Up for 6 s. The light party 1 tank
    baits wave 1 next to her and keeps her; wave 2's baiters, the light party 2 tank among them, carry the vulnerability
    into her auto-attack at ~50.5 s, so whoever holds her then must not have been hit by wave 2 (in 708 pulls the
    light party 1 tank took it, in none a wave 2 baiter who lived). A death to that auto-attack is blamed on what put
    the vulnerable player there: the living tanks' provokes, or a tank already dead."""
    out = []
    au = next((e for e in p.dmg if e["name"] == "attack" and 48 <= e["t"] <= 53), None)
    if not au or (au.get("targetResources") or {}).get("hitPoints") != 0: return out
    v, t = au["who"], au["t"]
    if v not in {e["who"] for e in p.hits("White Flame", 42, 46.5)}: return out     # no wave 2 vulnerability: other rules
    dead = p.dead_by(t - 0.3)
    tanks = [w for w, j in p.job.items() if j in TANK_JOBS]
    gone, others = [w for w in tanks if w in dead], [w for w in tanks if w != v and w not in dead]
    why = f"Athena's auto-attack after Paradeigma I (magical) killed {v} through wave 2's White Flame vulnerability"
    if not others:
        if gone: out.append(fault(t, "Paradeigma I", gone, [v], f"{why}: {', '.join(gone)} {'was' if len(gone) == 1 else 'were'} already dead, so {v} had to hold her", "consequence", chain=gone))
        return out
    if v not in tanks: return out
    provoked = p.cast_at(v, "Provoke", 40, t)
    shirk = [w for w in others if p.cast_at(w, "Shirk", 40, t)]
    if provoked:
        out.append(fault(t, "Paradeigma I", [v], [v], f"{why}: they provoked her at {provoked[-1]:.1f} s while carrying it", "high"))
    elif v in lp[0]:   # light party 1's tank keeps Athena, and baits wave 1, not 2
        out.append(fault(t, "Paradeigma I", [v], [v], f"{why}: tanking her, they took a wave 2 White Flame", "high"))
    elif shirk:
        out.append(fault(t, "Paradeigma I", shirk, [v], f"{why}: {', '.join(shirk)} shirked aggro to them", "high"))
    else:
        out.append(fault(t, "Paradeigma I", [v] + others, [v], f"{why}: {v} held her aggro ({', '.join(others)} did not keep it)", "medium"))
    return out


def dead_soul(p, souls, glow, t):
    """A Glow that hits no living holder of its Soul is a dead holder's tower dropped on someone else: in every cached
    pull, such a Glow came after a holder of its colour died and hit one player. The dead holders of its colour."""
    asp = glow.split()[0]
    return sorted(w for w, a in souls.items() if a == asp and w in p.dead_by(t - 0.2))


# ---------- Paradeigma II: tethers, quadrant sweep, towers ----------
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
                out.append(fault(holder["t"], "Paradeigma II", [holder["who"]], [holder["who"]], "died to their own tether laser (not stretched far enough)", "high"))
        for e in es:
            if e is holder: continue
            if holder:
                out.append(fault(e["t"], "Paradeigma II", [e["who"]], [e["who"]], f"stood in {holder['who']}'s tether laser", "medium"))
            elif gone and not unhit:
                out.append(fault(e["t"], "Paradeigma II", gone, [e["who"]], f"a tether laser hit {e['who']} because its holder was already dead ({', '.join(gone)})", "consequence", chain=gone))
            else:
                out.append(fault(e["t"], "Paradeigma II", [e["who"]], [e["who"]], "holding a Soul, stood in a tether laser's line (or took the tether)" +
                                 (f"; {', '.join(unhit)}'s laser hit no one else" if unhit else ""), "medium"))
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
            for v in ws: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", gone, [v], f"{' and '.join(gone)} died holding a Soul; its tower dropped on {v}", "consequence", chain=gone))
            continue
        for v in ws:
            if v == owner: continue
            if owner in wrong: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [owner], [v, owner], f"dropped their Soul in {quad(sp[owner])} instead of {expq[owner]}; its AoE hit {v}", "high"))
            elif v in wrong: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [v], [v], f"dropped their Soul in {quad(sp[v])} instead of {expq[v]} (inside {owner}'s AoE)", "high"))
            else: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [v], [v], f"stood in {owner + chr(39) + 's' if owner else 'a'} Soul AoE", "medium"))
    # towers: Astral/Umbral Advance = soak of the Astral/Umbral-bright tower
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 79, 82)
    expl = p.hits("Unmitigated Explosion", 81, 86)
    used = set()
    boom = dict(ability="Unmitigated Explosion")
    for w, asp in souls.items():
        if w not in sp:   # died holding the Soul: its tower dropped on someone else (see dead_soul), and nobody soaks it
            if expl and w in p.dead_by(77):
                out.append(fault(soaks[0]["t"] if soaks else 80.2, "Paradeigma II", [w], {e["who"] for e in expl},
                                 f"{w} died holding a Soul; its tower went unsoaked", "consequence", chain=[w], **boom))
            continue
        cand = [e for e in soaks if e["name"].startswith(asp) and e["pos"] and id(e) not in used and math.dist(e["pos"], sp[w]) < 3.6]   # tower radius ~3.5 y (max 3.46 in clean soaks)
        if cand:
            s = min(cand, key=lambda e: math.dist(e["pos"], sp[w])); used.add(id(s))
            if s["who"] in souls:
                out.append(fault(s["t"], "Paradeigma II", ([w] if w in wrong else []) + [s["who"]], [s["who"]],
                                 f"soaked {w}'s tower while holding a Soul" + (f" ({w} dropped it in the wrong quadrant)" if w in wrong else ""), "high"))
            elif teth.get(s["who"], (None,))[0] == asp:
                out.append(fault(s["t"], "Paradeigma II", [s["who"]], [s["who"]], f"soaked {w}'s {asp} tower with the same-colour Tilt", "high"))
            continue
        # unsoaked tower (timed at the soak moment so the soakers' own deaths link to it too)
        t = soaks[0]["t"] if soaks else 80.2
        if w in wrong:
            out.append(fault(t, "Paradeigma II", [w], {e["who"] for e in expl} | {w}, f"tower unsoaked: dropped in {quad(sp[w])}, sweep says {expq[w]}", "high", **boom))
        elif expq.get(w) in tq:
            sk = tq[expq[w]][0]
            if sk in p.dead_by(80): out.append(fault(t, "Paradeigma II", [sk], {e["who"] for e in expl}, f"tower unsoaked because {sk} was already dead", "consequence", chain=[sk], **boom))
            else: out.append(fault(t, "Paradeigma II", [sk], {e["who"] for e in expl} | {sk}, f"did not soak {w}'s tower in {expq[w]}", "high", **boom))
        else:
            out.append(fault(t, "Paradeigma II", [], {e["who"] for e in expl}, f"{w}'s tower unsoaked; soaker could not be determined", "low", **boom))
    # one player soaking two towers: the towers were dropped on top of each other
    for who, n in collections.Counter(s["who"] for s in soaks).items():
        if n < 2: continue
        sp_ = [s["pos"] for s in soaks if s["who"] == who and s["pos"]][0]
        stacked = [w for w in sp if math.dist(sp[w], sp_) < 9]
        bad = [w for w in stacked if w in wrong]
        out.append(fault(soaks[0]["t"], "Paradeigma II", bad or [who], {who},
                         f"two towers dropped in one quadrant ({', '.join(stacked)}); {who} soaked both" + (f"; sweep puts {bad[0]} in {expq[bad[0]]}" if bad else ""), "high" if bad else "medium"))
    # explosion with no tower explained: blame Souls that broke the sweep
    if expl and not any("tower" in f["rule"] for f in out):
        out.append(fault(soaks[0]["t"] if soaks else 80.2, "Paradeigma II", sorted(wrong), {e["who"] for e in expl},
                         "tower exploded; " + (f"Soul dropped off-sweep: {', '.join(f'{w} in {quad(sp[w])} (sweep {expq[w]})' for w in sorted(wrong))}" if wrong else "cause unclear"), "medium" if wrong else "low", **boom))
    # soaks that matched no tower: extra player in a tower, a Soul holder, or the same-colour Tilt
    for s in soaks:
        if id(s) in used: continue
        asp = s["name"].split()[0]
        near = min((w for w in souls if souls[w] == asp and w in sp), key=lambda w: math.dist(sp[w], s["pos"]) if s["pos"] else 99, default=None)
        why = "while holding a Soul" if s["who"] in souls else ("with the same-colour Tilt" if teth.get(s["who"], (None,))[0] == asp else "as an extra soaker")
        out.append(fault(s["t"], "Paradeigma II", ([near] if near in wrong else []) + [s["who"]], [s["who"]],
                         f"stepped into {near or 'a'}'s {asp} tower {why}" + (f" ({near} dropped it in the wrong quadrant)" if near in wrong else ""), "high"))
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
    hits and lives meant to (invulnerability), so only a death is a mistake."""
    out = []
    g = p.hits("Glaukopis", lo, hi)
    h1 = g[0] if g else None
    h2 = next((e for e in g if e["t"] > h1["t"] + 1.5), None) if g else None
    if not h2 or p.job.get(h1["who"]) not in TANK_JOBS: return out   # a tank already dead: the fallout rules cover it
    a, mech = h1["who"], mech_at(h1["t"])
    b = next((w for w, j in p.job.items() if j in TANK_JOBS and w != a), None)
    if b is None: return out
    lethal = lambda e: (e.get("targetResources") or {}).get("hitPoints") == 0
    if h2["who"] == a:
        if not lethal(h2): return out
        t, snap = h2["t"], h1["t"] + SNAPSHOT
        if b in p.dead_by(t - 0.3):
            out.append(fault(t, mech, [b], [a], f"{a} took both Glaukopis hits because {b} was already dead", "consequence", chain=[b]))
        elif p.casts is None:
            out.append(fault(t, mech, [a, b], [a], "no tank swap between the Glaukopis hits: the second hit the vulnerable tank", "medium"))
        elif back := p.cast_at(a, "Provoke", h1["t"] - 1, snap):
            out.append(fault(t, mech, [a], [a], f"provoked back {back[-1] - h1['t']:+.1f} s from the first Glaukopis, before the second "
                             f"(from +{SNAPSHOT} s): it hit them again with the vulnerability", "high"))
        elif not (pb := p.cast_at(b, "Provoke", h1["t"] - 10, snap)):
            out.append(fault(t, mech, [b], [a], f"did not provoke for the Glaukopis swap; {a} took the second hit with the vulnerability", "high"))
        else:
            out.append(fault(t, mech, [a, b], [a], f"{b} provoked {pb[-1] - h1['t']:+.1f} s from the first Glaukopis, but {a} held aggro "
                             "for the second (the provoke too early, or a Shirk missing)", "medium"))
        return out
    # the swap worked: the heavy auto-attack after the second hit has to go back to the first tank
    auto = next((e for e in p.dmg if e["name"] == "attack" and h2["t"] + 2 < e["t"] < h2["t"] + 4.5), None)
    if not auto or auto["who"] != h2["who"] or not lethal(auto) or p.job.get(h2["who"]) not in TANK_JOBS: return out
    t, v = auto["t"], h2["who"]
    if a in p.dead_by(t - 0.3):
        out.append(fault(t, mech, [a], [v], f"the auto-attack after the second Glaukopis killed {v} because {a} was already dead", "consequence", chain=[a]))
    elif p.casts is None:
        out.append(fault(t, mech, [a], [v], f"did not take the boss back after the second Glaukopis; its auto-attack killed {v} through the vulnerability", "medium"))
    else:
        back = p.cast_at(a, "Provoke", h2["t"] - 1, t)
        when = f"provoked back {back[0] - h2['t']:+.1f} s from the second Glaukopis, too late (by +{SNAPSHOT} s)" if back else "did not provoke back after the second Glaukopis"
        out.append(fault(t, mech, [a], [v], f"{when}: the auto-attack after it killed {v} through the vulnerability", "high"))
    return out


BRIGHT_PRIORITY = ("H1", "T1", "T2", "H2")   # bright Souls' middle platforms, west to east


def seats(p, lp):
    """{"T1": name, "H1": ..., "T2": ..., "H2": ...} from the light parties (light party 1 baits Paradeigma I's first wave)."""
    out = {}
    for n, party in ((1, lp[0]), (2, lp[1])):
        for w in sorted(party):
            role = "T" if p.job.get(w) in TANK_JOBS else "H" if p.job.get(w) in HEALER_JOBS else None
            if role: out.setdefault(f"{role}{n}", w)
    return out


def para3(p, lp, priority=False):
    """priority: the bright Souls take the middle platforms by BRIGHT_PRIORITY, so when both soak one tower the one
    who belongs on the other side is wrong; without it (before the groups agreed on it) both share the blame."""
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
        if missed: out.append(fault(t, "Paradeigma III", missed, wipe | set(missed), "did not soak their platform tower (Electrify)", "high", **zap))
        for w in sorted((supports_all - got) & dead):
            out.append(fault(t, "Paradeigma III", [w], wipe, f"{w} was already dead, so their platform tower went unsoaked (Electrify)", "consequence", chain=[w], **zap))
        for w in sorted(got - supports): out.append(fault(t, "Paradeigma III", [w], [w], "a DPS soaked a support tower", "medium"))
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
            # two bright Souls on one middle tower: the priority says which of them belongs on the other side; without
            # it, both share the blame
            rank = {w: BRIGHT_PRIORITY.index(s) for s, w in seats(p, lp).items() if s in BRIGHT_PRIORITY}
            if priority and len(who) == 2 and set(bad) == set(who) and all(role.get(w) == "bright" and w in rank for w in who):
                first, second = sorted(who, key=rank.get)
                west = es[0]["pos"][0] < 0
                bad = [second if west else first]
                rule += f"; {bad[0]} belongs on the {'eastern' if west else 'western'} one (priority H1 > T1 > T2 > H2, west to east)"
            out.append(fault(t, "Paradeigma III", bad, wipe | set(who), rule, "high" if len(bad) < len(who) else "medium", **zap))
    # platforms: Quartered takes the north-most, X-Marked the south-most
    wrong_plat = {}
    for w in sup["Quartered"]:
        if w in spos and spos[w][1] > -8: wrong_plat[w] = "Quartered (+) belongs on the north platform"
    for w in sup["X-Marked"]:
        if w in spos and spos[w][1] < 8: wrong_plat[w] = "X-Marked belongs on the south platform"
    # DPS tethers: Searing Radiance -> Umbral Tilt, Shadowsear -> Astral Tilt
    tl = p.hits(("Searing Radiance", "Shadowsear"), 215, 217.5)
    per_inst = collections.Counter(e.get("sourceInstance") for e in tl)
    tilt = {}
    # a DPS's own tether is the laser that hit only them; a second laser through them is someone else's
    for e in sorted(tl, key=lambda e: per_inst[e.get("sourceInstance")]):
        if e["who"] in supports:
            out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "a DPS tether laser clipped them (soak from the tower's outer side)", "high"))
        else:
            if e["who"] in tilt: out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "hit by two DPS tether lasers", "medium")); continue
            tilt[e["who"]] = "Umbral" if e["name"] == "Searing Radiance" else "Astral"
            if (e.get("targetResources") or {}).get("hitPoints") == 0:
                out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "died to their own tether laser (not stretched far enough)", "high"))
    match = [w for w, a in tilt.items() if a == asp]; opp = [w for w, a in tilt.items() if a != asp]
    # + and X: both locked to true north; the owner steps out of their own arms
    own = {"Theos's Cross": (sup["Quartered"], "+"), "Theos's Saltire": (sup["X-Marked"], "X")}
    for e in p.hits(("Theos's Cross", "Theos's Saltire"), 221.5, 223.8):
        owners, shape = own[e["name"]]; o = owners[0] if owners else None
        if e["who"] == o:
            out.append(fault(e["t"], "Paradeigma III", [o], [o], f"did not step out of their own {shape}", "high"))
        elif o in wrong_plat:
            out.append(fault(e["t"], "Paradeigma III", [o], [e["who"]], f"dropped the {shape} from the wrong platform ({wrong_plat[o]}); it hit {e['who']}", "high"))
        else:
            out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], f"stood in the arms of {o or 'a'}'s {shape}", "medium"))
    # where the bright towers went: same-colour pair on the Soul's side -> centre corner, otherwise its own tile
    glow = {e["who"]: e for e in p.hits(("Astral Glow", "Umbral Glow"), 222, 224.5) if e["who"] in dict(bright) and e["pos"]}
    pairx = lambda ws: [p_ for p_ in (next((e["pos"] for e in tl if e["who"] == w and e["pos"]), None) for w in ws) if p_]
    mx = pairx(match); mside = (1 if sum(x for x, _ in mx) > 0 else -1) if mx else None
    misplaced = {}
    for w, e in glow.items():
        x, y = e["pos"]; centre = math.hypot(x, y) < 6.5
        want_centre = mside is not None and (x > 0) == (mside > 0)
        if mside is not None and centre != want_centre:
            misplaced[w] = "on its own tile instead of the centre corner" if want_centre else "at the centre instead of on its own tile"
    gi = collections.defaultdict(list)
    for e in p.hits(("Astral Glow", "Umbral Glow"), 222, 224.5): gi[(e["name"], e.get("sourceInstance"))].append(e)
    for (nm, inst), es in gi.items():
        gone = [] if any(e["who"] in dict(bright) for e in es) else dead_soul(p, dict(bright), nm, es[0]["t"])
        for e in es:
            if e["who"] in dict(bright): continue
            if gone: out.append(fault(e["t"], "Paradeigma III", gone, [e["who"]], f"{' and '.join(gone)} died holding a bright Soul; its tower dropped on {e['who']}", "consequence", chain=gone))
            else: out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "stood in a bright Soul's AoE", "medium"))
    # White Flame: baited by the + and X supports and the matching DPS pair
    wf = p.hits("White Flame", 222.5, 225)
    missing, extra = [], []
    if wf:
        t = wf[0]["t"]; dead = p.dead_by(t - 0.3); hit = collections.Counter(e["who"] for e in wf)
        exp_all = set(sup["Quartered"]) | set(sup["X-Marked"]) | set(match); exp = exp_all - dead
        missing = [w for w in sorted(exp) if w not in hit]; extra = [w for w in hit if w not in exp]
        gone = sorted(exp_all & dead)
        if extra and gone and not missing:   # a baiter was already dead, so their laser found someone else
            out.append(fault(t, "Paradeigma III", gone, extra, f"White Flame went to {', '.join(extra)} because {', '.join(gone)} (a baiter) was already dead", "consequence", chain=gone))
        elif missing: out.append(fault(t, "Paradeigma III", missing, extra, f"did not bait their White Flame; it hit {', '.join(extra) or 'someone else'}", "high" if extra else "medium"))
        elif extra:
            for w in extra: out.append(fault(t, "Paradeigma III", [w], [w], "stood in a White Flame line", "medium"))
        for e in wf:
            if e["who"] in exp and hit[e["who"]] == 1 and (e.get("targetResources") or {}).get("hitPoints") == 0:
                out.append(fault(t, "Paradeigma III", [], [e["who"]], "died taking their own assigned White Flame (healing / mitigation)", "unattributed"))
    # bright towers: soaked by the opposite pair (Astral Advance = Astral tower)
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 224.5, 227.5)
    expl = p.hits("Unmitigated Explosion", 227, 231)
    blown = {x["who"] for x in expl}
    ts = soaks[0]["t"] if soaks else 226
    for s in soaks:
        if s["who"] not in opp: out.append(fault(s["t"], "Paradeigma III", [s["who"]], [s["who"]], "soaked a bright tower without the opposite Tilt", "high"))
    boom = dict(ability="Unmitigated Explosion")
    for w, a in bright:   # a bright Soul who died before dropping leaves their tower where they fell, and nobody soaks it
        if w not in glow and w in p.dead_by(222.5) and expl:
            out.append(fault(ts, "Paradeigma III", [w], blown, f"{w} died before dropping their bright tower; it went unsoaked", "consequence", chain=[w], **boom))
    soaked_near = lambda pos: any(s["pos"] and math.dist(s["pos"], pos) < 6 for s in soaks)
    dead = p.dead_by(ts - 0.3)
    alive, gone = [x for x in opp if x not in dead], [x for x in opp if x in dead]
    idle = [x for x in alive if x not in {s["who"] for s in soaks}]
    unsoaked = collections.defaultdict(list)   # why -> the bright Souls whose towers went unsoaked for it
    for w, e in glow.items():
        if soaked_near(e["pos"]): continue
        if opp and not alive: why = "soakers dead"          # no one left to soak it, wherever it stood
        elif w in misplaced: why = ("misplaced", w)
        elif idle and missing and set(idle) <= set(extra): why = "swap"   # the soakers took the White Flame, its baiters did not
        elif idle: why = "idle"
        elif gone: why = "soaker dead"
        elif alive: why = "other tower"                       # every living soaker took the other tower
        else: why = "unknown"
        unsoaked[why].append(w)
    for why, ws in unsoaked.items():
        towers = " and ".join(f"{w}'s" for w in ws) + (" towers" if len(ws) > 1 else " tower")
        if why in ("soakers dead", "soaker dead"):
            out.append(fault(ts, "Paradeigma III", gone, blown, f"{towers} unsoaked because {'its soakers were' if len(gone) > 1 else 'its soaker was'} already dead", "consequence", chain=gone, **boom))
        elif why == "swap":
            out.append(fault(ts, "Paradeigma III", idle + missing, blown | set(idle), f"{' and '.join(idle)} took the White Flame meant for "
                             f"{' and '.join(missing)} instead of soaking (the DPS pairs' roles swapped): {towers} went unsoaked", "medium", **boom))
        elif why == "idle":
            out.append(fault(ts, "Paradeigma III", idle, blown | set(idle), f"did not soak {towers}", "high", **boom))
        elif why == "other tower":
            out.append(fault(ts, "Paradeigma III", alive, blown, f"{' and '.join(alive)} both soaked the other bright tower; one of them belonged on {towers}", "medium", **boom))
        elif why == "unknown":
            out.append(fault(ts, "Paradeigma III", [], blown, f"did not soak {towers}", "low", **boom))
        else:
            out.append(fault(ts, "Paradeigma III", [why[1]], blown | {why[1]}, f"tower unsoaked: placed {misplaced[why[1]]}", "high", **boom))
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
CLUSTER, SPOT_ANGLE, SPOT_MARGIN = 8.25, {"T": 17, "M": 50, "H": 98, "R": 146}, 20
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
    """Who of a group sharing an orange cone left their spot around the cluster: (culprits, confidence, why). The one
    further off their seat's angle by at least SPOT_MARGIN degrees; all of them when each is that far off (a swap);
    otherwise they share it."""
    fr = spot_frame(p, lp, hs)
    if not fr or not all(w in fr[0] and w in fr[1] for w in group): return sorted(group), "low", ""
    seat, ang, want = fr
    off = {w: abs((ang[w] - want[w] + 180) % 360 - 180) for w in group}
    far = sorted(group, key=off.get, reverse=True)
    name = lambda w: "".join(map(str, seat[w]))
    if off[far[0]] - off[far[1]] >= SPOT_MARGIN:
        w = far[0]
        return [w], "high" if off[w] - off[far[1]] >= 2 * SPOT_MARGIN else "medium", f"; {w} ({name(w)}) stood {off[w]:.0f} degrees off their spot around the cluster"
    if off[far[-1]] >= SPOT_MARGIN:
        return sorted(group), "medium", "; " + ", ".join(f"{w} ({name(w)}) {off[w]:.0f}" for w in far) + " degrees off their spots"
    return sorted(group), "low", ""


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
                                 f"{'was' if len(gone) == 1 else 'were'} already dead (a dead target's goes to someone at random)", "consequence", chain=gone))
                continue
            # a lone target's seat partner left them (missing, or in another pair), when every player has a seat of their
            # own; otherwise every missing player
            seat = seats_all(p, lp); by_seat = {s: w for w, s in seat.items()}
            for v in lone:
                mate = by_seat.get((PARTNER[seat[v][0]], seat[v][1])) if v in seat and len(by_seat) == len(seat) == len(p.job) else None
                if mate in missing or mate in hit:
                    out.append(fault(t, "Superchain I", [mate], [v], f"not in their pair for the purple jack ({'missing' if mate in missing else 'in another pair'}); "
                                     f"{v} took it alone", "high"))
                elif missing:
                    out.append(fault(t, "Superchain I", missing, [v], f"not in their pair for the purple jack; {v} took it alone", "high"))
            for ws in crowd:   # three or more: whoever's seat partner is not in it, or who stood away from it, joined
                cul, conf, why = pair_blame(p, lp, hs, ws)
                out.append(fault(t, "Superchain I", cul or ws, ws, "three or more in one purple-jack pair" + why, conf))
        else:   # every cone from the cluster hits whoever stands in line with it
            groups = {frozenset(ws) for ws in by.values() if len(ws) > 1}
            doubled = [w for w, n in hit.items() if n >= 2 and not any(w in g for g in groups)]
            if gone and sum(n - 1 for n in hit.values()) <= len(gone):   # all the extra hits are the dead players' cones
                if groups or doubled:
                    out.append(fault(t, "Superchain I", gone, set(doubled) | {w for g in groups for w in g}, f"orange cones doubled up because {', '.join(gone)} "
                                     f"{'was' if len(gone) == 1 else 'were'} already dead (a dead player's cone goes to someone else)", "consequence", chain=gone))
                continue
            for g in groups:
                cul, conf, why = cone_blame(p, lp, hs, g)
                out.append(fault(t, "Superchain I", cul, g, f"orange cone overlap ({', '.join(sorted(g))}){why}", conf))
            for w in doubled:   # two cones that hit only them, nobody dead
                out.append(fault(t, "Superchain I", [w], [w], "hit by two orange cones (not in their spread spot)", "medium"))
    # lasers: Astral laser shared by Astralstrong + Umbralbright + Umbral Tilts, Umbral laser the mirror
    lt = p.hits(("Astral Impact", "Umbral Impact"), 136, 139.5)
    wrong_group = set()
    if lt:
        t = lt[0]["t"]; tilt = {a: p.has_debuff_at(f"{a} Tilt", t - 0.2) for a in ("Astral", "Umbral")}
        exp = {"Astral Impact": set(S["Astralstrong"]) | set(S["Umbralbright"]) | tilt["Umbral"],
               "Umbral Impact": set(S["Umbralstrong"]) | set(S["Astralbright"]) | tilt["Astral"]}
        wrong = [(e["who"], e["name"]) for e in lt if e["who"] not in exp[e["name"]]]
        wrong_group = {w for w, _ in wrong}
        # a laser not theirs, with its own colour's Tilt, is their own death (it kills through six sharers); it only
        # helps the others in it. Listed first: a wrong-group player's death is theirs before the short laser's
        for w, nm in wrong:
            out.append(fault(t, "Superchain I", [w], [w], f"in the wrong laser group (took {nm})", "high"))
        # a laser a sharer short: whoever belonged in it and lived, but took the other or neither
        dead = p.dead_by(t - 0.3)
        for nm, ws in exp.items():
            got = {e["who"] for e in lt if e["name"] == nm}
            away = sorted(ws - got - dead)
            if not got or not away: continue
            other = [w for w in away if w in wrong_group]
            out.append(fault(t, "Superchain I", away, got, f"not in the {nm} group ({', '.join(other) + ' took the other laser' if other else 'missed it'}); it was a sharer short",
                             "high" if other else "medium"))
    # Heavensflame spread
    hh = p.hits("Theos's Holy", 145.5, 149)
    by = collections.defaultdict(list)
    for e in hh: by[e.get("sourceInstance")].append(e["who"])
    hf = set(S["Heavensflame"])
    for ws in by.values():
        owner = next((w for w in ws if w in hf), None)
        for v in ws:
            if v == owner: continue
            if v in hf: out.append(fault(hh[0]["t"], "Superchain I", [owner, v], [owner, v], "two Heavensflame players overlapped (pair did not split)", "medium", ability="Theos's Holy"))
            else: out.append(fault(hh[0]["t"], "Superchain I", [owner], [v], f"Heavensflame did not spread far enough; hit {v}", "medium", ability="Theos's Holy"))
    # the bright Souls' small AoE as they drop their towers: only the owner belongs in it. Strong Souls wait beside it
    # before stepping in, the two bright Souls drop on opposite cardinals, and Heavensflame spreads well away from
    # everyone (a Heavensflame player in it, left low, often dies to their own Theos's Holy next, matched to this too)
    bright, strong = set(S["Astralbright"]) | set(S["Umbralbright"]), set(S["Astralstrong"]) | set(S["Umbralstrong"])
    glow = p.hits(("Astral Glow", "Umbral Glow"), 144, 147.5)
    gi = collections.defaultdict(list)
    for e in glow: gi[(e["name"], e.get("sourceInstance"))].append(e["who"])
    together = set()            # the bright Souls who dropped their towers on one spot
    for e in glow:
        v, owner = e["who"], next((w for w in gi[(e["name"], e.get("sourceInstance"))] if w in bright), None)
        if v == owner: continue
        if owner is None and (gone := dead_soul(p, {w: a for a in ("Astral", "Umbral") for w in S[f"{a}bright"]}, e["name"], e["t"])):
            out.append(fault(e["t"], "Superchain I", gone, [v], f"{' and '.join(gone)} died holding a bright Soul; its tower dropped on {v}", "consequence", chain=gone))
            continue
        if v in strong:
            out.append(fault(e["t"], "Superchain I", [v], [v], "stepped into the tower before the bright Soul's AoE went off", "high"))
        elif owner in wrong_group:   # the laser side decides the tower side
            out.append(fault(e["t"], "Superchain I", [owner], [v], f"took the wrong laser, so their tower dropped on the wrong side; its AoE hit {v}", "high"))
        elif v in bright:   # the owner is in it too: two bright Souls' AoEs together can kill either
            if v not in wrong_group and owner: together = {owner, v}
            out.append(fault(e["t"], "Superchain I", [v] if v in wrong_group else [owner, v] if owner else [v], [v] + ([owner] if owner else []),
                             f"the bright Souls dropped their towers together ({owner or 'a bright Soul'}'s AoE hit {v}); they go on opposite cardinals", "high" if v in wrong_group else "medium"))
        elif v in hf:
            out.append(fault(e["t"], "Superchain I", [v], [v], f"Heavensflame not spread away: stood in {owner + chr(39) + 's' if owner else 'a'} bright Soul's AoE as the tower dropped", "high"))
        else:
            out.append(fault(e["t"], "Superchain I", [v], [v], f"stood in {owner + chr(39) + 's' if owner else 'a'} bright Soul's AoE as the tower dropped", "medium"))
    # final towers: Astralbright tower soaked by Umbralstrong (Astral Advance), Umbralbright by Astralstrong
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 147, 150.5)
    expl = p.hits("Unmitigated Explosion", 149, 156)
    for asp, soaker in (("Astral", S["Umbralstrong"]), ("Umbral", S["Astralstrong"])):
        got = [e for e in soaks if e["name"] == f"{asp} Advance"]
        for e in got:
            if e["who"] in soaker: continue
            if together and e["who"] not in together:   # both towers on one spot: soaking one meant soaking both
                out.append(fault(e["t"], "Superchain I", sorted(together), [e["who"]], f"in the {asp} tower too, as the bright Souls dropped their towers together",
                                 "medium", fallout=True))
            else: out.append(fault(e["t"], "Superchain I", [e["who"]], [e["who"]], f"soaked the {asp} tower (meant for {', '.join(soaker)})", "high"))
        # unsoaked, or soaked only by someone else (which does not hold it): it explodes
        if not any(e["who"] in soaker for e in got) and S[f"{asp}bright"]:
            t = expl[0]["t"] if expl else 150
            dead = p.dead_by(t - 2); blown = {e["who"] for e in expl}
            b = S[f"{asp}bright"][0]
            sk = [w for w in soaker if w not in dead]
            boom = dict(ability="Unmitigated Explosion")
            if b in p.dead_by(144):
                out.append(fault(t, "Superchain I", [b], blown, f"{b} died before dropping the {asp}bright tower; it went unsoaked", "consequence", chain=[b], **boom))
            elif not sk:   # wherever it dropped, no one was left to soak it
                out.append(fault(t, "Superchain I", list(soaker), blown, f"{asp}bright tower unsoaked because its soaker was already dead", "consequence", chain=list(soaker), **boom))
            elif b in wrong_group:   # the laser side decides the tower side, so this tower landed away from its soaker
                out.append(fault(t, "Superchain I", [b], blown | {b}, f"{asp}bright tower unsoaked: {b} took the wrong laser, so it dropped on the wrong side", "high", **boom))
            else: out.append(fault(t, "Superchain I", sk, blown | set(sk), f"did not soak the {asp}bright tower", "high", **boom))
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
    target = pick(in_tb, peri)                     # the player the tanks' hit was aimed at
    blamed = set()
    # the tanks' hit: a non-tank in it took it (from the tanks' place, or in line with them), unless it was aimed at a
    # non-tank standing where the party belongs: then the tanks were not where they belong
    out_t, extra = sorted(tanks - in_tb), sorted(in_tb - tanks)
    if extra and target and not is_tank(target) and not misplaced(target):
        cul = sorted(w for w in tanks if w not in in_tb or misplaced(w))
        if cul:
            out.append(fault(t, "Dialogos", cul, in_tb, f"not {where(peri)} for {nm} (the tanks' hit goes to the {'closest' if peri else 'farthest'} "
                             f"player); it went to {target} and hit {', '.join(extra)}", "high", ability=nm))
            blamed |= set(cul)
    else:
        for x in extra:
            how = f"stood {where(peri)} with the tanks" if misplaced(x) else "stood in line with the tanks"
            out.append(fault(t, "Dialogos", [x], [x], f"{how} for {nm} (a hit the two tanks share)", "high", ability=nm))
            blamed.add(x)
        if out_t and target and is_tank(target):
            out.append(fault(t, "Dialogos", out_t, in_tb, f"left {nm} to {', '.join(sorted(in_tb & tanks))} (the two tanks share it)", "high", ability=nm))
            blamed |= set(out_t)
    gone = sorted({w for w in p.job if is_tank(w)} & dead)
    if gone and not out_t and not extra and in_tb:
        out.append(fault(t, "Dialogos", gone, in_tb, f"{', '.join(sorted(in_tb))} took {nm} alone because {', '.join(gone)} was already dead (the two tanks share it)", "consequence", chain=gone, ability=nm))
    # the stack: aimed at a tank, that tank stood where the party belongs; aimed at the party, whoever of the party
    # is not in it left it (one in the tanks' hit counts once: a culprit's faults within 2 s are one mistake)
    s_target = pick(in_st, not peri)
    if s_target and is_tank(s_target):
        cul = sorted(w for w in in_st if is_tank(w) and w not in blamed)
        if cul: out.append(fault(st[0]["t"], "Dialogos", cul, in_st, f"stood {where(not peri)} where the party stacks for {nm}; the Dialogos stack went to them", "high", ability="Dialogos"))
    elif s_target:   # one the tanks' hit had just killed could not be in it: the stack's shortfall is that death's
        killed = sorted(w for w in party & in_tb if any(e["who"] == w and (e.get("targetResources") or {}).get("hitPoints") == 0 for e in tb))
        miss = sorted(party - in_st - set(killed))
        if miss: out.append(fault(st[0]["t"], "Dialogos", miss, in_st, f"not in the Dialogos stack: {len(in_st & party)} of the party's {len(party)} shared it", "high", ability="Dialogos"))
        if killed and not killed[0] in in_st:
            out.append(fault(st[0]["t"], "Dialogos", killed, in_st, f"the Dialogos stack was short: {', '.join(killed)} died to {nm} just before", "consequence",
                             chain=killed, ability="Dialogos"))
    return out


# ---------- the rule book ----------
# Which rules judge each mechanic, by the raid day they take effect (the report's local date, as the site groups raid
# days). A pull is judged by the latest entry dated on or before its day, so patching a mechanic's strategy is a new
# dated entry and older pulls keep the rules they were played under. GENERIC (also a mechanic not listed, or a day
# before its first entry) leaves only the generic rules: standing in an avoidable AoE is the victim's mistake.
# NOT_YET blames no one for anything in the mechanic: the groups are still learning it or have no settled strategy.
GENERIC, NOT_YET = "generic", "not yet"
CONF_ORDER = {"high": 0, "medium": 1, "low": 2}   # surest first
least_sure = lambda confs: max(confs, key=lambda c: CONF_ORDER.get(c, 1))


def merged(fs):
    """Faults about the same hit as one cause (an explosion of two unsoaked towers): their culprits and chains together."""
    if len(fs) == 1: return fs[0]
    direct = [f for f in fs if not f["chain"]]
    culprits = list(dict.fromkeys(c for f in direct for c in f["culprits"]))
    return dict(fs[0], culprits=culprits, chain=list(dict.fromkeys(n for f in fs for n in f["chain"])), direct=culprits,
                direct_conf=least_sure([f["confidence"] for f in direct]) if direct else None,
                confidence=least_sure([f["confidence"] for f in direct]) if direct else "consequence",
                # the direct causes first: a cause's label comes from before "; earlier"
                rule="; earlier: ".join(r for r in ("; ".join(dict.fromkeys(f["rule"] for f in direct)), "; ".join(dict.fromkeys(f["rule"] for f in fs if f["chain"]))) if r),
                victims=set().union(*(f["victims"] for f in fs)),
                fallout=bool(direct) and all(f["fallout"] for f in direct), parts=fs)
RULEBOOK = {
    "Paradeigma I": [(None, lambda p, lp: para1(p, lp) + para1_auto(p, lp))],
    "Paradeigma II": [(None, lambda p, lp: para2(p))],
    "Glaukopis": [(None, lambda p, lp: glaukopis(p, 92, 110))],
    "Superchain I": [(None, superchain1)],
    "Dialogos": [(None, lambda p, lp: dialogos(p))],
    "Paradeigma III": [(None, para3),
                       ("2026-10-26", lambda p, lp: para3(p, lp, priority=True))],   # bright Souls by H1 > T1 > T2 > H2
    "Glaukopis / Ultima Blade": [(None, lambda p, lp: glaukopis(p, 236, 280))],
    "Palladion": [(None, NOT_YET)],   # to start blaming it: ("YYYY-MM-DD", GENERIC) or a rule
}


def rules_on(day):
    """{mechanic: rule function, GENERIC or NOT_YET} for a raid day ("YYYY-MM-DD"); None means the latest rules."""
    out = {}
    for mech, versions in RULEBOOK.items():
        on = [rule for since, rule in versions if since is None or day is None or since <= day]
        out[mech] = on[-1] if on else GENERIC
    return out


def classify(p, lp, day=None):
    """Every Damage Down and lethal hit in the pull with its mechanic, cause, culprits and confidence, judged by the
    rule book on the pull's raid day. Entries marked derived=True are fallout of an earlier mistake (blame carried over
    from it), not a new mistake of their own; jump=True is a death without a hit (jumping off the arena)."""
    rules = rules_on(day)
    faults = sorted((f for rule in rules.values() if callable(rule) for f in rule(p, lp)), key=lambda f: f["t"])
    res, used = [], set()       # used: faults already counted at an incident

    def from_chain(i, f):
        """Blame whoever caused the deaths behind a fault (its chain), as sure as the least sure of them, besides the
        fault's own culprits when it merges a direct one; those carried over from the earlier deaths are not counted
        again (carried)."""
        direct = f.get("direct", [])
        why = [(n, r) for n in f["chain"] for r in [next((r for r in reversed(res) if r["victim"] == n and r["kind"] == "death"), None)] if r and r["culprits"]]
        culprits = list(dict.fromkeys(direct + [c for _, r in why for c in r["culprits"]]))
        if not culprits: return dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=[], confidence="consequence", derived=True)
        return dict(i, mechanic=f["mechanic"], cause=f["rule"] + ("; earlier: " + "; ".join(f"{n} {r['cause']}" for n, r in why) if why else ""),
                    culprits=culprits, derived=not direct, carried=[c for c in culprits if c not in direct] if direct else [],
                    confidence=least_sure(([f["direct_conf"]] if direct else []) + [r["confidence"] for _, r in why]))

    def add(r):
        """A mistake in a NOT_YET mechanic keeps its cause but blames no one; fallout of an earlier one keeps its blame."""
        if rules.get(r["mechanic"]) == NOT_YET and r["culprits"] and not r.get("derived"):
            r = dict(r, culprits=[], confidence="not blamed", cause=f"{r['cause']} (not blamed: no rules for {r['mechanic']} yet)")
        res.append(r)
    for i in p.incidents():
        mech = mech_at(i["t"])
        if i.get("jump"):
            add(dict(i, mechanic=mech, cause="left the arena without taking a hit (jumped off: wipe called?)", culprits=[], confidence="unattributed"))
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
            add(dict(i, mechanic=mech, culprits=[i["victim"]], confidence="high",
                     **(dict(cause=f"after their earlier {hit['kind']}: {cause}", derived=True) if hit else dict(cause=f"{cause}, then {i['ability']} killed them"))))
            continue
        # the faults about the very hit that killed them (one cause together), else, unless the hit was an avoidable one,
        # the earliest fault that hit them
        near =[f for f in faults if i["victim"] in f["victims"] and -1.5 <= i["t"] - f["t"] <= 4.5]
        about = [f for f in near if f.get("ability") == i["ability"]]
        f = merged(about) if about else None if i["ability"] in AVOIDABLE else near[0] if near else None
        if f is None and i["ability"] == "Unmitigated Explosion":   # an explosion that reached someone no tower fault names
            tw = [f for f in faults if f.get("ability") == i["ability"] and abs(i["t"] - f["t"]) <= 4.5] \
                 or [f for f in faults if "tower" in f["rule"] and abs(i["t"] - f["t"]) <= 4.5][:1]
            f = merged(tw) if tw else None
        own = None
        if f is None and i["ability"] not in AVOIDABLE:   # later fallout of a mistake that hurt them earlier in the same mechanic
            hurt = [g for g in reversed(faults) if g["mechanic"] == mech and 0 < i["t"] - g["t"] <= 15 and i["victim"] in g["victims"]]
            own = next((g for g in hurt if i["victim"] in g["culprits"]), hurt[0] if hurt else None)   # their own first
        prev = next((r for r in reversed(res) if r["victim"] == i["victim"] and r["culprits"] and 0 <= i["t"] - r["t"] <= 10), None)
        if f and f["chain"]:
            add(from_chain(i, f))
        elif f:
            used.update(id(g) for g in f.get("parts", [f]))
            add(dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=f["culprits"], confidence=f["confidence"], **({"derived": True} if f["fallout"] else {})))
        elif prev and i["ability"] not in AVOIDABLE:
            add(dict(i, mechanic=mech, cause=f"after their earlier {prev['kind']}: {prev['cause']}", culprits=prev["culprits"], confidence="medium", derived=True))
        elif own and own["chain"]:
            add(from_chain(i, own))
        elif own and id(own) in used:   # the mistake was already counted at an earlier incident
            add(dict(i, mechanic=mech, cause=f"after their earlier mistake: {own['rule']}", culprits=own["culprits"], confidence="medium", derived=True))
        elif own:   # the mistake's first incident: it counts here
            used.add(id(own))
            add(dict(i, mechanic=own["mechanic"], cause=own["rule"], culprits=own["culprits"], confidence=own["confidence"]))
        elif i["ability"] in AVOIDABLE:
            add(dict(i, mechanic=mech, cause=AVOIDABLE[i["ability"]], culprits=[i["victim"]], confidence="high"))
        elif i["ability"] == "Shockwave":
            add(dict(i, mechanic=mech, cause="stood in Athena's dash line (Palladion Shockwave)", culprits=[i["victim"]], confidence="medium"))
        elif i["ability"] == "attack" and p.job.get(i["victim"]) in TANK_JOBS:
            add(dict(i, mechanic=mech, cause="tank died to auto-attacks (mitigation / tank swap)", culprits=[], confidence="unattributed"))
        else:
            earlier = [r for r in res if r["t"] < i["t"] - 0.5 and r["culprits"]]
            add(dict(i, mechanic=mech, cause=f"{i['kind']} to {i['ability']}" + (" after an earlier mistake" if earlier else " (no rule matched: likely HP / mitigation)"),
                            culprits=[], confidence="consequence" if earlier else "unattributed"))
    return res, faults
