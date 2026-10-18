"""P12S P1 mistake classifier.

Finds every Damage Down and lethal hit in a pull, then attributes it using the party strategy
from xivsim's briefs.html (Paradeigma I light-party baits, Paradeigma II quadrant sweep,
Superchain I laser groups / pairs / towers). Anything the rules cannot explain falls back to
"avoidable AoE -> victim" or stays unattributed.
"""
import collections, math

SUPPORT_JOBS = {"Paladin", "Warrior", "DarkKnight", "Gunbreaker", "WhiteMage", "Scholar", "Astrologian", "Sage"}
AVOIDABLE = {  # standing in it is the victim's own mistake
    "Trinity of Souls": "stood on the cleaved side (Trinity of Souls)",
    "Ray of Light": "stood in a Ray of Light column",
    "Superchain Burst": "stood in a green orb point-blank",
    "Superchain Coil": "stood in a donut",
    "Clear Cut": "stood in a Clear Cut cone",
    "Unnatural Enchainment": "stood on a destroyed tile",
    "Palladian Ray": "stood in a Palladion puddle",
}
MECH = [(15, 50, "Paradeigma I"), (50, 92, "Paradeigma II"), (92, 110, "Glaukopis"), (110, 160, "Superchain I"),
        (160, 190, "Dialogos"), (190, 236, "Paradeigma III"), (236, 280, "Glaukopis / Ultima Blade"),
        (280, 345, "Palladion"), (345, 395, "Superchain IIA"), (395, 470, "Superchain IIB")]
mech_at = lambda t: next((m for lo, hi, m in MECH if lo <= t < hi), "other")
OPP = {"Astral": "Umbral", "Umbral": "Astral"}


def quad(p):
    x, y = p
    return ("N" if y < 0 else "S") + ("E" if x > 0 else "W")


class Pull:
    def __init__(self, code, fight, rep, ev):
        self.code, self.fid = code, fight["id"]
        self.s, self.e = fight["startTime"], fight["endTime"]
        self.ab = {int(k): v for k, v in ev["abilities"].items()}
        act = {a["id"]: a for a in rep["masterData"]["actors"]}
        self.players = {pid: act[pid]["name"] for pid in fight["friendlyPlayers"] if pid in act}
        self.job = {act[pid]["name"]: act[pid]["subType"] for pid in fight["friendlyPlayers"] if pid in act}
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

    def has_debuff_at(self, debuff, t):
        st = {}
        for e in sorted((e for e in self.deb if e["name"] == debuff and e["t"] <= t), key=lambda e: e["t"]):
            st[e["who"]] = e["type"] in ("applydebuff", "refreshdebuff")
        return {w for w, v in st.items() if v}

    def dead_by(self, t):
        """Players dead at time t: a death (its lethal hit lands ~2 s before the death event) and no sign of a raise
        since, i.e. no hit taken with HP left over after it."""
        out = set()
        for w in self.job:
            ds = [d["t"] - 2 for d in self.deaths if d["who"] == w and d["t"] - 2 < t]
            if not ds: continue
            last = max(ds)
            if not any(e["who"] == w and last + 2.5 < e["t"] < t and (e.get("targetResources") or {}).get("hitPoints", 0) > 0 for e in self.dmg):
                out.add(w)
        return out

    def incidents(self):
        inc = []
        for d in self.deaths:   # the death event is the truth; the lethal hit lands ~2 s earlier
            lethal = [e for e in self.dmg if e["who"] == d["who"] and d["t"] - 4 <= e["t"] <= d["t"] and (e.get("targetResources") or {}).get("hitPoints") == 0]
            if lethal: e = lethal[-1]; inc.append(dict(t=e["t"], kind="death", victim=d["who"], ability=e["name"], pos=e["pos"]))
            else: inc.append(dict(t=d["t"] - 2, kind="death", victim=d["who"], ability=self.ab.get(d.get("killingAbilityGameID"), "?"), pos=None))
        for d in self.deb:
            if d["name"] == "Damage Down" and d["type"] in ("applydebuff", "refreshdebuff"):
                src = [e for e in self.dmg if e["who"] == d["who"] and abs(e["t"] - d["t"]) <= 0.2]
                inc.append(dict(t=d["t"], kind="DD", victim=d["who"], ability=src[0]["name"] if src else "?", pos=src[0]["pos"] if src else None))
        return sorted(inc, key=lambda i: i["t"])


def fault(t, mech, culprits, victims, rule, conf, chain=None):
    """chain: players whose earlier death caused this; their death's culprits are blamed instead when there is one."""
    return dict(t=t, mechanic=mech, culprits=list(dict.fromkeys(culprits)), victims=set(victims), rule=rule, confidence=conf, chain=chain or [])


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
        missing = [x for x in sorted(exp) if x not in cnt]
        extra = [x for x in cnt if x not in exp] + [x for x, n in cnt.items() if n >= 2 and x in exp]
        if missing:
            out.append(fault(t, "Paradeigma I", missing, extra, f"not in the White Flame line-up (wave {w}); the laser went to {', '.join(extra) or 'someone else'}", "high" if extra else "medium"))
        elif extra:
            for x in extra:
                out.append(fault(t, "Paradeigma I", [x], [x], f"took a White Flame meant for wave {w} baiters (stood in a laser line)", "medium"))
    return out


# ---------- Paradeigma II: tethers, quadrant sweep, towers ----------
def para2(p):
    out = []
    souls = {}
    for asp in ("Astral", "Umbral"):
        for w in p.holders(f"{asp}bright Soul", 60, 72): souls[w] = asp
    if not souls: return out
    # tether lasers: Searing Radiance -> Umbral Tilt, Shadowsear -> Astral Tilt
    teth, by = {}, collections.defaultdict(list)
    for e in p.hits(("Searing Radiance", "Shadowsear"), 74, 78.5): by[(e["name"], e.get("sourceInstance"))].append(e)
    for (nm, inst), es in by.items():
        es = [e for e in es if e["pos"]]
        if not es: continue
        holder = max(es, key=lambda e: math.hypot(*e["pos"]))           # the stretched player is furthest out
        teth[holder["who"]] = ("Umbral" if nm == "Searing Radiance" else "Astral", holder["pos"])
        if (holder.get("targetResources") or {}).get("hitPoints") == 0:
            out.append(fault(holder["t"], "Paradeigma II", [holder["who"]], [holder["who"]], "died to their own tether laser (not stretched far enough)", "high"))
        for e in es:
            if e is not holder:
                out.append(fault(e["t"], "Paradeigma II", [e["who"]], [e["who"]], f"stood in {holder['who']}'s tether laser", "medium"))
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
    for e in glow: gi[e.get("sourceInstance")].append(e["who"])
    for inst, ws in gi.items():
        owner = next((w for w in ws if w in souls), None)
        for v in ws:
            if v == owner: continue
            if owner in wrong: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [owner], [v, owner], f"dropped their Soul in {quad(sp[owner])} instead of {expq[owner]}; its AoE hit {v}", "high"))
            elif v in wrong: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [v], [v], f"dropped their Soul in {quad(sp[v])} instead of {expq[v]} (inside {owner}'s AoE)", "high"))
            else: out.append(fault(min(e["t"] for e in glow), "Paradeigma II", [v], [v], f"stood in {owner + chr(39) + 's' if owner else 'a'} Soul AoE", "medium"))
    # towers: Astral/Umbral Advance = soak of the Astral/Umbral-bright tower
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 79, 82)
    expl = p.hits("Unmitigated Explosion", 81, 86)
    used = set()
    for w, asp in souls.items():
        if w not in sp: continue
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
            out.append(fault(t, "Paradeigma II", [w], {e["who"] for e in expl} | {w}, f"tower unsoaked: dropped in {quad(sp[w])}, sweep says {expq[w]}", "high"))
        elif expq.get(w) in tq:
            sk = tq[expq[w]][0]
            if sk in p.dead_by(80): out.append(fault(t, "Paradeigma II", [], {e["who"] for e in expl}, f"tower unsoaked because {sk} was already dead", "consequence"))
            else: out.append(fault(t, "Paradeigma II", [sk], {e["who"] for e in expl} | {sk}, f"did not soak {w}'s tower in {expq[w]}", "high"))
        else:
            out.append(fault(t, "Paradeigma II", [], {e["who"] for e in expl}, f"{w}'s tower unsoaked; soaker could not be determined", "low"))
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
                         "tower exploded; " + (f"Soul dropped off-sweep: {', '.join(f'{w} in {quad(sp[w])} (sweep {expq[w]})' for w in sorted(wrong))}" if wrong else "cause unclear"), "medium" if wrong else "low"))
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
def para3(p):
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
        for w in sorted(supports_all - got):
            if w in dead: out.append(fault(t, "Paradeigma III", [w], wipe, f"{w} was already dead, so their platform tower went unsoaked (Electrify)", "consequence", chain=[w]))
            else: out.append(fault(t, "Paradeigma III", [w], wipe | {w}, "did not soak their platform tower (Electrify)", "high"))
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
            # two bright Souls on one middle tower: which of them was wrong depends on the group's priority, so both share it
            out.append(fault(t, "Paradeigma III", bad, wipe | set(who), f"{' and '.join(who)} soaked the same tower on {place}, leaving another tower empty (Electrify)",
                             "high" if len(bad) < len(who) else "medium"))
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
    for e in p.hits(("Astral Glow", "Umbral Glow"), 222, 224.5):
        if e["who"] not in dict(bright): out.append(fault(e["t"], "Paradeigma III", [e["who"]], [e["who"]], "stood in a bright Soul's AoE", "medium"))
    # White Flame: baited by the + and X supports and the matching DPS pair
    wf = p.hits("White Flame", 222.5, 225)
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
    for w, a in bright:   # a bright Soul who died before dropping leaves their tower where they fell, and nobody soaks it
        if w not in glow and w in p.dead_by(222.5) and expl:
            out.append(fault(ts, "Paradeigma III", [w], blown, f"{w} died before dropping their bright tower; it went unsoaked", "consequence", chain=[w]))
    soaked_near = lambda pos: any(s["pos"] and math.dist(s["pos"], pos) < 6 for s in soaks)
    for w, e in glow.items():
        if soaked_near(e["pos"]): continue
        if w in misplaced:
            out.append(fault(ts, "Paradeigma III", [w], blown | {w}, f"tower unsoaked: placed {misplaced[w]}", "high"))
        else:
            dead = p.dead_by(ts - 0.3); idle = [x for x in opp if x not in {s["who"] for s in soaks}]
            if idle and all(x in dead for x in idle):
                out.append(fault(ts, "Paradeigma III", idle, blown, f"{w}'s tower unsoaked because its soaker was already dead", "consequence", chain=idle))
            else:
                out.append(fault(ts, "Paradeigma III", [x for x in idle if x not in dead], blown | set(idle), f"did not soak {w}'s tower", "high" if idle else "low"))
    return out


# ---------- Superchain I ----------
def superchain1(p):
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
        if nm == "Superchain Emission":
            missing = [w for w in alive if w not in hit]
            lone = [ws[0] for ws in by.values() if len(ws) == 1]
            if lone and missing: out.append(fault(t, "Superchain I", missing, lone, f"not in their pair for the purple jack; {', '.join(lone)} took it alone", "high"))
            for ws in by.values():
                if len(ws) > 2: out.append(fault(t, "Superchain I", ws, ws, "three or more in one purple-jack pair", "low"))
        else:
            for ws in by.values():
                if len(ws) > 1: out.append(fault(t, "Superchain I", ws[1:], ws, f"orange cone overlap ({', '.join(ws)})", "low"))
            for w, n in hit.items():
                if n >= 2: out.append(fault(t, "Superchain I", [w], [w], "hit by two orange cones (not in their spread spot)", "medium"))
    # lasers: Astral laser shared by Astralstrong + Umbralbright + Umbral Tilts, Umbral laser the mirror
    lt = p.hits(("Astral Impact", "Umbral Impact"), 136, 139.5)
    wrong_group = set()
    if lt:
        t = lt[0]["t"]; tilt = {a: p.has_debuff_at(f"{a} Tilt", t - 0.2) for a in ("Astral", "Umbral")}
        exp = {"Astral Impact": set(S["Astralstrong"]) | set(S["Umbralbright"]) | tilt["Umbral"],
               "Umbral Impact": set(S["Umbralstrong"]) | set(S["Astralbright"]) | tilt["Astral"]}
        wrong = [(e["who"], e["name"]) for e in lt if e["who"] not in exp[e["name"]]]
        wrong_group = {w for w, _ in wrong}
        for w, nm in wrong:   # the other laser is now a sharer short, so its group are victims too
            out.append(fault(t, "Superchain I", [w], {e["who"] for e in lt}, f"in the wrong laser group (took {nm}); the other laser was a sharer short", "high"))
        if not wrong:
            dead = p.dead_by(t - 0.3)
            for nm, ws in exp.items():
                got = {e["who"] for e in lt if e["name"] == nm}
                for w in sorted(ws - got - dead): out.append(fault(t, "Superchain I", [w], got, f"missed their {nm} share (fewer players split it)", "medium"))
    # Heavensflame spread
    hh = p.hits("Theos's Holy", 145.5, 149)
    by = collections.defaultdict(list)
    for e in hh: by[e.get("sourceInstance")].append(e["who"])
    hf = set(S["Heavensflame"])
    for ws in by.values():
        owner = next((w for w in ws if w in hf), None)
        for v in ws:
            if v == owner: continue
            if v in hf: out.append(fault(hh[0]["t"], "Superchain I", [owner, v], [v], "two Heavensflame players overlapped (pair did not split)", "medium"))
            else: out.append(fault(hh[0]["t"], "Superchain I", [owner], [v], f"Heavensflame did not spread far enough; hit {v}", "medium"))
    # bright Soul AoE vs strong Souls waiting to soak
    for e in p.hits(("Astral Glow", "Umbral Glow"), 144, 147):
        if e["who"] in set(S["Astralstrong"]) | set(S["Umbralstrong"]):
            out.append(fault(e["t"], "Superchain I", [e["who"]], [e["who"]], "stepped into the tower before the bright Soul's AoE went off", "high"))
    # final towers: Astralbright tower soaked by Umbralstrong (Astral Advance), Umbralbright by Astralstrong
    soaks = p.hits(("Astral Advance", "Umbral Advance"), 147, 150.5)
    expl = p.hits("Unmitigated Explosion", 149, 156)
    for asp, soaker in (("Astral", S["Umbralstrong"]), ("Umbral", S["Astralstrong"])):
        got = [e for e in soaks if e["name"] == f"{asp} Advance"]
        for e in got:
            if e["who"] not in soaker: out.append(fault(e["t"], "Superchain I", [e["who"]], [e["who"]], f"soaked the {asp} tower (meant for {', '.join(soaker)})", "high"))
        if not got and S[f"{asp}bright"]:
            t = expl[0]["t"] if expl else 150
            dead = p.dead_by(t - 2); blown = {e["who"] for e in expl}
            b = S[f"{asp}bright"][0]
            sk = [w for w in soaker if w not in dead]
            if b in wrong_group:   # the laser side decides the tower side, so this tower landed away from its soaker
                out.append(fault(t, "Superchain I", [b], blown | {b}, f"{asp}bright tower unsoaked: {b} took the wrong laser, so it dropped on the wrong side", "high"))
            elif b in p.dead_by(144):
                out.append(fault(t, "Superchain I", [b], blown, f"{b} died before dropping the {asp}bright tower; it went unsoaked", "consequence", chain=[b]))
            elif sk: out.append(fault(t, "Superchain I", sk, blown | set(sk), f"did not soak the {asp}bright tower", "high"))
            else: out.append(fault(t, "Superchain I", list(soaker), blown, f"{asp}bright tower unsoaked because its soaker was already dead", "consequence", chain=list(soaker)))
    return out


def classify(p, lp):
    """Every Damage Down and lethal hit in the pull with its mechanic, cause, culprits and confidence. Entries marked
    derived=True are fallout of an earlier mistake (blame carried over from it), not a new mistake of their own."""
    faults = sorted(para1(p, lp) + para2(p) + superchain1(p) + para3(p), key=lambda f: f["t"])
    res = []
    for i in p.incidents():
        mech = mech_at(i["t"])
        f = next((f for f in faults if i["victim"] in f["victims"] and -1.5 <= i["t"] - f["t"] <= 4.5), None)
        if f is None and i["ability"] == "Unmitigated Explosion":
            f = next((f for f in faults if "tower" in f["rule"] and abs(i["t"] - f["t"]) <= 4.5), None)
        own = None
        if f is None and i["ability"] not in AVOIDABLE:   # later fallout of the victim's own earlier mistake in the same mechanic
            own = next((f for f in reversed(faults) if f["mechanic"] == mech and 0 < i["t"] - f["t"] <= 15 and (i["victim"] in f["victims"] or i["victim"] in f["culprits"])), None)
        prev = next((r for r in reversed(res) if r["victim"] == i["victim"] and r["culprits"] and 0 <= i["t"] - r["t"] <= 10), None)
        if f and f["chain"]:   # blame whoever caused the earlier death behind this fault
            why = [(n, r) for n in f["chain"] for r in [next((r for r in reversed(res) if r["victim"] == n and r["culprits"]), None)] if r]
            if why:
                res.append(dict(i, mechanic=f["mechanic"], cause=f["rule"] + "; earlier: " + "; ".join(f"{n} {r['cause']}" for n, r in why),
                                culprits=list(dict.fromkeys(c for _, r in why for c in r["culprits"])), confidence="medium", derived=True))
            else:
                res.append(dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=[], confidence="consequence", derived=True))
        elif f:
            res.append(dict(i, mechanic=f["mechanic"], cause=f["rule"], culprits=f["culprits"], confidence=f["confidence"]))
        elif prev and i["ability"] not in AVOIDABLE:
            res.append(dict(i, mechanic=mech, cause=f"after their earlier {prev['kind']}: {prev['cause']}", culprits=prev["culprits"], confidence="medium", derived=True))
        elif own:
            res.append(dict(i, mechanic=mech, cause=f"after their earlier mistake: {own['rule']}", culprits=own["culprits"], confidence="medium", derived=True))
        elif i["ability"] in AVOIDABLE:
            res.append(dict(i, mechanic=mech, cause=AVOIDABLE[i["ability"]], culprits=[i["victim"]], confidence="high"))
        elif i["ability"] == "Shockwave":
            res.append(dict(i, mechanic=mech, cause="stood in Athena's dash line (Palladion Shockwave)", culprits=[i["victim"]], confidence="medium"))
        elif i["ability"] == "attack" and p.job.get(i["victim"]) in SUPPORT_JOBS - {"WhiteMage", "Scholar", "Astrologian", "Sage"}:
            res.append(dict(i, mechanic=mech, cause="tank died to auto-attacks (mitigation / tank swap)", culprits=[], confidence="unattributed"))
        else:
            earlier = [r for r in res if r["t"] < i["t"] - 0.5 and r["culprits"]]
            res.append(dict(i, mechanic=mech, cause=f"{i['kind']} to {i['ability']}" + (" after an earlier mistake" if earlier else " (no rule matched: likely HP / mitigation)"),
                            culprits=[], confidence="consequence" if earlier else "unattributed"))
    return res, faults
