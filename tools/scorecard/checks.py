"""Rotation checks: simple, nameable mistakes per pull, costed in DPS and set against the clears.

  Cooldown held    an oGCD the clears use on cooldown sat ready at full charges while the player was alive
  GCD gaps         time between GCD starts beyond the player's usual GCD (+0.3 s), while alive, split by what filled
                   it: an interrupted cast, an oGCD weave that pushed the GCD back, or nothing at all
  Casts interrupted  a begun cast that never went off
  Healing GCDs     healers: GCDs that deal no damage (Eukrasia, raises and Esuna aside)
  Combo / positional  a hit with less bonus (FFLogs' bonusPercent) than the clears usually get on that skill; the
                   damage lost follows from the bonus share: hit x ((1 - got) / (1 - usual) - 1)
  Burst windows    GCDs started inside the player's own damage buff (20 s; Wildfire 10 s), per window
  Procs            short self-buffs the clears spend with a cast (85%+): expired unspent, or refreshed while still up
  Maintained buffs self-buffs the clears keep up (85%+ of the fight): seconds down while alive, after the opener
  DoT gaps         damage-over-time ticks missing after the first one, while alive (jobs whose clears keep a DoT up)
  Gauge            gauge wasted at the cap, replayed from casts (gauges.py; only gauges whose tables replay the clears
                   with under 6% unaffordable spends); Black Mage: Polyglot overcapped

Every check runs from 0:00 until the player died or the pull was lost (as in the scorecard; dead time is skipped).
The clears are measured over the same stretch of fight, 0:00 to the same time, so mechanics that cost everyone uptime
(movement, untargetable moments) cancel out; what is left is what our player does differently.
Level-90 cooldowns and charges are read off the clears, since the game data's base values are before traits.
"""
import collections, functools, json, statistics as st, sys
from pathlib import Path

import build_benchmark as B
import gamedata, gauges
from scorecard import ROLE, WINDOWS as PHASES

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "rotation"))
# oGCDs worth holding to a cooldown although they deal no damage themselves: raid and self damage buffs and resource
# generators at level 90. oGCDs that deal damage qualify on their own; defensives and utility never do (the clears time
# those to mechanics and strategy, e.g. tank invulnerabilities in Paradeigma I).
BUFFS = {"Manafont", "Ley Lines", "Amplifier", "Divination", "Devilment", "Flourish", "Delirium", "Living Shadow",
         "Lance Charge", "Battle Litany", "Life Surge", "No Mercy", "Bloodfest", "Wildfire", "Barrel Stabilizer", "Reassemble",
         "Riddle of Fire", "Brotherhood", "Perfect Balance", "Riddle of Wind", "Kassatsu", "Ten Chi Jin", "Meisui", "Bunshin",
         "Dokumori", "Mug", "Fight or Flight", "Requiescat", "Starry Muse", "Arcane Circle", "Embolden", "Manafication",
         "Acceleration", "Ikishoten", "Meikyo Shisui", "Chain Stratagem", "Aetherflow", "Searing Light", "Serpent's Ire",
         "Inner Release", "Presence of Mind", "Raging Strikes", "Battle Voice", "Radiant Finale", "Barrage", "Technical Finish"}
DOT_COVER = 0.65             # share of 3 s server ticks with a tick, over a clear, for a job to count as keeping a DoT up
MAX_SHARE = 1.15
GAUGE_SHORT = 0.06           # a gauge table is trusted when under this share of the clears' spends were unaffordable
ANIM = 0.65                  # an oGCD's animation lock
# non-damaging GCDs that cost no damage: Eukrasia, raises and Esuna, and White Mage's lily heals (three lilies make the
# Blood Lily that Afflatus Misery spends, so they pay their GCD back)
NEUTRAL = {"Eukrasia", "Raise", "Resurrection", "Ascend", "Egeiro", "Esuna", "Afflatus Solace", "Afflatus Rapture"}
# statuses on oneself that are not rotation: stances, food, dance partner, Kardia, card and Soulsow states
NOT_ROTATION = {"Defiance", "Grit", "Royal Guard", "Iron Will", "Well Fed", "Medicated", "Closed Position", "Kardia", "Kardion",
                "The Balance", "Soulsow", "Esprit", "Sprint", "Swiftcast", "Lucid Dreaming"}
PROC_USED, KEPT_UP, KEPT_FROM = 0.85, 0.85, 15.0
SPENT = 0.05                 # a proc spent by a cast is removed at the cast's own timestamp; buffs that run out are not
KEPT_SKIP = {"Aetherflow"}   # stack resources: being out of stacks means they were spent, not dropped   # proc: share spent by a cast; maintained: uptime; counted from this time
# damage gained from maintained self-buffs (haste buffs such as Fuka and Swiftscaled get no cost)
BUFF_VALUE = {"Surging Tempest": 0.10, "Power Surge": 0.10, "Hunter's Instinct": 0.10, "Fugetsu": 0.13, "Standard Finish": 0.05}
# damage buffs whose window the player fills with GCDs: seconds of window after the buff lands (~0.6 s after the cast)
WINDOWS = {"No Mercy": 20, "Fight or Flight": 20, "Riddle of Fire": 20, "Lance Charge": 20, "Raging Strikes": 20,
           "Devilment": 20, "Wildfire": 10, "Searing Light": 20, "Starry Muse": 20, "Embolden": 20, "Arcane Circle": 20,
           "Divination": 20, "Chain Stratagem": 20, "Battle Litany": 20, "Brotherhood": 20, "Dokumori": 20}             # clears using an oGCD more often than its recast allows: the rotation shortens it, skip
GAP_TOL = 0.3                # seconds beyond the usual GCD before a gap counts (weaving and latency)
ON_CD = 0.75                 # an oGCD is checked when the clears get at least this share of its possible uses
MIN_RECAST = 30
SLIDE = 0.46                 # FFLogs logs a hard cast this long before its cast bar ends
SPLIT = PHASES[1][1]        # end of Opener & Paradeigma I: before it, compare with clears that move through it like we do


def starts(p, src, busy=False):
    """GCD start times of a player in a pull: the begun cast for hard casts, the cast itself for instants. With `busy`,
    [(start, seconds the cast kept them busy (0 for instants), the action's own GCD recast relative to 2.5 s)] instead,
    e.g. 1.32 for Pictomancer's 3.3 s subtractive spells (recasts over 5 s are cooldowns, not the GCD lock)."""
    acts = gamedata.actions({a for _, s, a in p["casts"] if s == src})
    begun = collections.defaultdict(list)
    for t, s, a in p.get("begins", []):
        if s == src: begun[a].append(t)
    out, last = [], -1e9              # last: the player's previous cast; a begin before it belongs to an earlier cast
    for t, s, a in sorted(x for x in p["casts"] if x[1] == src):
        prev, last = last, t
        if not (acts.get(a) or {}).get("gcd"): continue
        b = [x for x in begun[a] if 0 <= t - x < 6 and x > prev]    # instant casts (Swiftcast, Dualcast, procs) have none
        rec = acts[a]["recast"] / 2.5 if acts[a]["recast"] <= 5 else 1.0
        out.append((b[-1], t - b[-1] + SLIDE + 0.1, rec) if b else (t, 0.0, rec))
    out.sort()
    return out if busy else [x[0] for x in out]


def usual_gcd(intervals):
    """The player's usual GCD: the most common start-to-start interval (0.05 s bins) between 1.5 and 3.5 s."""
    c = collections.Counter(round(x * 20) / 20 for x in intervals if 1.5 <= x <= 3.5)
    return c.most_common(1)[0][0] if c else None


def aura_spans(p, sid, status, end):
    """[(applied, removed)] of a status on the player (open spans run to `end`)."""
    out, on = [], None
    for t, s, a, c in p.get("auras", []):
        if s != sid or a != status: continue
        if c in (1, 3) and on is None: on = t
        elif c == 0 and on is not None: out.append((on, t)); on = None
    if on is not None: out.append((on, end))
    return out


def overlap(spans, alive):
    return sum(max(0.0, min(b, d) - max(a, c)) for a, b in spans for c, d in alive)


def capped(uses, recast, charges, alive, until):
    """Seconds an action sat at full charges inside the alive windows up to `until`. Charges start full 30 s before
    the pull; a use while (by our numbers) empty is taken as-is."""
    c, nxt, since, spans = charges, None, -30.0, []
    for u in sorted(t for t in uses if t <= until) + [None]:
        to = until if u is None else u
        while c < charges and nxt is not None and nxt <= to:
            c += 1
            if c == charges: since, nxt = nxt, None
            else: nxt += recast
        if c == charges: spans.append((since, to))
        if u is None: break
        if c == charges: nxt = u + recast
        c = max(0, c - 1)
    return overlap(spans, [(max(a, 0), min(b, until)) for a, b in alive])


def dot_missing(ticks, alive, until):
    """Ticks missing after the first one: every gap over 3.5 s between ticks (or to the end) that lies in the alive
    windows counts its missing 3 s ticks."""
    ts = sorted(t for t in ticks if 0 <= t <= until and any(a <= t <= b for a, b in alive))
    if not ts: return 0
    miss = 0
    for a, b in zip(ts, ts[1:] + [min(until, next(e for s, e in alive if s <= ts[-1] <= e))]):
        if b - a > 3.5 and any(s <= a and b <= e for s, e in alive): miss += round((b - a) / 3) - 1
    return miss


# --- what the clears do, per job --------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def clear_logs(job):
    """[(acts pull, player id, death time or None, kill length, moved through Paradeigma I)] for each clear player."""
    kills = json.loads((HERE / "benchmark.json").read_text())["kills"]
    out = []
    for k in kills:
        p = B.kill_acts(k)
        deaths, pf = {}, B.CACHE / f"phases_{k['code']}_{k['fight']}.json"
        for x in (json.loads(pf.read_text())["deaths"] if pf.exists() else []):
            deaths[x["name"]] = min(deaths.get(x["name"], 1e9), x["t"])
        for sid, (name, j) in p["players"].items():
            if j == job: out.append((p, int(sid), deaths.get(name), p["end"], not B.invuln_strategy(k)))
    return out


def trusted_gauges(job, logs):
    """The job's gauges whose tables replay the clears with few unaffordable spends."""
    out = []
    for spec in gauges.GAUGES.get(job, []):
        short = spends = 0
        for p, sid, death, end, _ in logs:
            _, sh, sp = gauge_waste(p, sid, spec, [(0.0, death or end)], end)
            short += sh; spends += sp
        if spends and short <= GAUGE_SHORT * spends: out.append(spec)
    return out


@functools.lru_cache(maxsize=None)
def profile(job):
    """The job's checks at level 90, from the clears: oGCDs used on cooldown (recast and charges as played) and
    whether the job keeps a DoT up."""
    logs = clear_logs(job)
    if not logs: return dict(cooldowns={}, dot=False, bonus={}, damaging=set(), windows={}, procs={}, kept={}, spenders={}, gcd=None, gauges=[])
    ids = {a for p, sid, *_ in logs for _, s, a in p["casts"] if s == sid}
    damaging = {x[2] for p, sid, *_ in logs for x in p["dmg"] if x[1] == sid and not x[4]}
    acts = gamedata.actions(ids)
    cds = {}
    for a, info in acts.items():
        if info["gcd"] or info["category"] != "Ability" or info["recast"] < MIN_RECAST: continue
        if info["name"] not in BUFFS and a not in damaging: continue
        uses = [sorted(t for t, s, x in p["casts"] if s == sid and x == a) for p, sid, *_ in logs]
        if sum(map(len, uses)) < len(logs): continue
        gaps = [b - a2 for u in uses for a2, b in zip(u, u[1:])]
        if info["charges"] > 1:
            recast = info["recast"]
            charges = max(1, min(info["charges"], max((sum(1 for y in u if x <= y < x + recast - 1) for u in uses for x in u), default=1)))
        else:
            charges = 1
            seen = [g for g in gaps if g >= 0.5 * info["recast"]]
            recast = min([info["recast"]] + seen)
        share = st.mean(len(u) / (charges + max(0.0, end - 2) // recast) for u, (_, _, _, end, _) in zip(uses, logs))
        if ON_CD <= share <= MAX_SHARE: cds[a] = dict(name=info["name"], recast=round(recast, 1), charges=charges, share=round(share, 2))
    ticks = [len({round(x[0] / 3) for x in p["dmg"] if x[1] == sid and x[4]}) / end * 3 for p, sid, _, end, _ in logs]
    bonus = collections.defaultdict(collections.Counter)
    for p, sid, *_ in logs:
        for x in p["dmg"]:
            if x[1] == sid and not x[4]: bonus[x[2]][x[5]] += 1
    usual = {}
    for a, c in bonus.items():
        b, n = c.most_common(1)[0]
        if b > 0 and n >= 0.5 * sum(c.values()) and sum(c.values()) >= 10: usual[a] = b
    wins = {a: WINDOWS[i["name"]] for a, i in acts.items() if i["name"] in WINDOWS}
    procs, kept, spenders = {}, {}, {}
    names = {}
    for p, sid, *_ in logs: names.update({int(k): v for k, v in p["names"].items()})
    stats = collections.defaultdict(lambda: dict(n=0, used=0, dur=[], up=[], by=collections.Counter()))
    for p, sid, death, end, _ in logs:
        casts = [t for t, s2, a in p["casts"] if s2 == sid]
        for status in {x[2] for x in p.get("auras", []) if x[1] == sid}:
            sp = aura_spans(p, sid, status, end)
            if not sp or names.get(status) in NOT_ROTATION: continue
            S = stats[status]
            S["n"] += len(sp); S["dur"] += [b - a for a, b in sp]
            S["used"] += sum(1 for a, b in sp if b < end - 1 and any(abs(b - c) <= SPENT for c in casts))
            for a, b in sp:
                S["by"].update(x for t, s2, x in p["casts"] if s2 == sid and abs(b - t) <= SPENT)
            S["up"].append(sum(b - a for a, b in sp) / max(1.0, end - KEPT_FROM))
    for status, S in stats.items():
        if S["n"] >= 2 * len(logs) and st.median(S["dur"]) <= 30 and S["used"] >= PROC_USED * S["n"]:
            procs[status] = names.get(status, str(status))
            spenders[status] = S["by"].most_common(1)[0][0] if S["by"] else None
        elif names.get(status) not in KEPT_SKIP and st.median(S["up"]) >= KEPT_UP and sum(S["up"]) / len(logs) >= KEPT_UP * 0.8: kept[status] = names.get(status, str(status))
    return dict(cooldowns=cds, dot=st.median(ticks) >= DOT_COVER, bonus=usual, damaging=damaging | {x[2] for p, sid, *_ in logs
                for x in p["dmg"] if x[1] == sid}, windows=wins, procs=procs, kept=kept, spenders=spenders, gauges=trusted_gauges(job, logs),
                gcd=st.median(g for g in (usual_gcd([b - a for a, b in zip(ss, ss[1:])]) for ss in (starts(p, sid) for p, sid, *_ in logs)) if g))


# --- one player in one pull ----------------------------------------------------------------------------------------

def pull(p, sid, job, alive, until, gcd=None, start=0.0):
    """Raw counts for one player in one pull over the alive windows between `start` and `until`."""
    prof = profile(job)
    alive = [(max(start, a), min(b, until)) for a, b in alive if min(b, until) > max(start, a)]
    out = dict(alive=sum(b - a for a, b in alive), alive_early=sum(max(0.0, min(b, SPLIT) - a) for a, b in alive),
               held={}, gap_idle=0.0, gap_clip=0.0, gap_interrupt=0.0, interrupted=0, healgcd=0, dot=0, gauge={},
               bonus=collections.Counter(), bonus_loss=collections.Counter(), windows={},
               expired=collections.Counter(), overwritten=collections.Counter(), down={},
               casts=collections.Counter(), admg=collections.Counter())
    inside = lambda t: t <= until and any(a <= t <= b for a, b in alive)
    acts = gamedata.actions({x[2] for x in p["casts"] if x[1] == sid} | {x[2] for x in p.get("begins", []) if x[1] == sid})
    mine = [(t, a) for t, s2, a in p["casts"] if s2 == sid]
    ogcd = sorted(t for t, a in mine if a in acts and not acts[a]["gcd"])
    cut = sorted(t for t, s2, a in p.get("begins", []) if s2 == sid and not any(x == a and 0 <= tc - t < 6 for tc, x in mine))
    out["interrupted"] = sum(1 for t in cut if inside(t))
    for a, cd in prof["cooldowns"].items():
        uses = [t for t, s, x in p["casts"] if s == sid and x == a]
        out["held"][a] = capped(uses, cd["recast"], cd["charges"], alive, until)
    ss = starts(p, sid, busy=True)
    if gcd:
        for (a, busy, rec), (b, _, _) in zip(ss, ss[1:]):
            if b > until or not any(s <= a and b <= e for s, e in alive): continue
            extra = b - a - max(gcd * rec, busy) - GAP_TOL
            if extra <= 0: continue
            woven = [t for t in ogcd if a < t < b]
            if any(a < t < b for t in cut): out["gap_interrupt"] += extra
            elif woven and b - (woven[-1] + ANIM) <= GAP_TOL: out["gap_clip"] += extra
            else: out["gap_idle"] += extra
    if ROLE.get(job) == "Healer":
        dmg_here = prof["damaging"] | {x[2] for x in p["dmg"] if x[1] == sid}
        out["healgcd"] = sum(1 for t, a in mine if a in acts and acts[a]["gcd"] and a not in dmg_here
                             and acts[a]["name"] not in NEUTRAL and inside(t))
    for t, s2, a, amt, tick, bonus in p["dmg"]:
        if s2 != sid or tick or a not in prof["bonus"] or not inside(t) or bonus >= prof["bonus"][a]: continue
        info = gamedata.actions({a}).get(a) or {}
        cast = max((tc for tc, x in mine if x == a and tc <= t), default=None)            # the cast this hit came from
        prev = max(((tc, x) for tc, x in mine if cast is not None and tc < cast and x in acts and acts[x]["gcd"]), default=None)
        # a broken combo leaves no bonus at all; level-90 replacements (Raiden Thrust for True Thrust) are not predecessors
        # in the game data, so only a bonus-less hit after the wrong GCD counts as one
        broken = bonus == 0 and info.get("combo") and (prev is None or prev[1] != info["combo"])
        kind = "Combo broken" if broken else "Positional missed"
        out["bonus"][kind] += 1
        out["bonus_loss"][kind] += amt * ((1 - bonus / 100) / (1 - prof["bonus"][a] / 100) - 1)
    hitting = prof["damaging"] | {x[2] for x in p["dmg"] if x[1] == sid}
    for t, a in mine:
        if a in hitting and a in acts and inside(t): out["casts"][a] += 1
    for t, s2, a, amt, *_ in p["dmg"]:
        if s2 == sid and inside(t): out["admg"][a] += amt
    end = p["end"]
    for status in prof["procs"]:
        for a, b in aura_spans(p, sid, status, end):
            # dying or the pull ending strips every status: only removals well inside an alive stretch count
            if any(lo <= b < hi - 1 for lo, hi in alive) and not any(abs(b - t) <= SPENT for t, _ in mine): out["expired"][status] += 1
        out["overwritten"][status] += sum(1 for t, s2, x, c in p.get("auras", []) if s2 == sid and x == status and c == 2 and inside(t))
    for status in prof["kept"]:
        win = [(max(a, KEPT_FROM), b) for a, b in alive if b > max(a, KEPT_FROM)]
        out["down"][status] = sum(b - a for a, b in win) - overlap(aura_spans(p, sid, status, end), win)
    gstarts = [x[0] for x in ss]
    for a, dur in prof["windows"].items():
        n = g = 0
        for t, x in mine:
            if x != a: continue
            w0, w1 = t + 0.6, t + 0.6 + dur
            if w1 > until or not any(s <= w0 and w1 <= e for s, e in alive): continue
            n += 1; g += sum(1 for y in gstarts if w0 <= y < w1)
        if n: out["windows"][a] = [n, g]
    if prof["dot"]:
        out["dot"] = dot_missing([x[0] for x in p["dmg"] if x[1] == sid and x[4]], alive, until)
    if job == "BlackMage": out["gauge"] = blm_gauge(p, sid, until)
    for spec in prof["gauges"]:
        out["gauge"][f"{spec['label']} overcapped"] = gauge_waste(p, sid, spec, alive, until)[0]
    return out


def gauge_waste(p, sid, spec, alive, until):
    """(units wasted at the cap, unaffordable spends, spends) for one gauge of one player in one pull."""
    names, end = p["names"], p["end"]
    casts = [(t, names.get(str(a), "")) for t, s, a in p["casts"] if s == sid]
    acts = gamedata.actions({a for t, s, a in p["casts"] if s == sid})
    ws = {v["name"] for v in acts.values() if v["category"] == "Weaponskill"}
    applied = [(t, names.get(str(a), "")) for t, s, a, c in p.get("auras", []) if s == sid and c == 1]
    ids = collections.defaultdict(list)
    for k, n in names.items(): ids[n].append(int(k))
    spans = {}
    def on(status, t):
        if status not in spans: spans[status] = [x for i in ids.get(status, []) for x in aura_spans(p, sid, i, end)]
        return any(a <= t <= b for a, b in spans[status])
    return gauges.replay(spec, casts, on, alive, until, applied, ws)


def blm_gauge(p, sid, until):
    """Black Mage resources lost, from replaying the casts through the job model (tools/rotation)."""
    import calibrate
    from engine import Fight
    from jobs import blm as J
    casts = [dict(type="begincast", t=t, abilityGameID=a) for t, s, a in p.get("begins", [])
             if s == sid and str(a) in p["names"]]          # a begun cast that never went off has no name: skip it
    casts += [dict(type="cast", t=t, abilityGameID=a) for t, s, a in p["casts"] if s == sid]
    casts.sort(key=lambda x: (x["t"], x["type"] != "begincast"))
    log = dict(names=p["names"], casts=casts, buffs=[], hits=[], name="", id=sid)
    s = calibrate.replay_fight(log, Fight(until=until))
    return {"Polyglot overcapped": s.waste[0]}


# --- costs ---------------------------------------------------------------------------------------------------------

def unit_costs(p, sid):
    """Damage per unit of each check, from the player's own hits in this pull: an idle GCD second at their damage per
    active second, a missing tick at their median tick, a use of a damaging oGCD at its average hit."""
    by, ticks = collections.defaultdict(list), []
    for t, s, a, amt, tick, *_ in p["dmg"]:
        if s != sid: continue
        (ticks if tick else by[a]).append(amt)
    acts = gamedata.actions(set(by))
    gcds = [a for a in by if (acts.get(a) or {}).get("gcd")]
    main = max(gcds, key=lambda a: len(by[a])) if gcds else None       # their filler: what a healing GCD replaced
    return dict(ability={a: st.mean(v) for a, v in by.items()}, tick=st.median(ticks) if ticks else 0.0,
                gcd_hit=st.mean(by[main]) if main else None)


# --- the clears over the same stretch, and the summary per player --------------------------------------------------

@functools.lru_cache(maxsize=None)
def clear_rates(job, T):
    """Each check per alive second for the clears, as (rates before SPLIT, rates from SPLIT to T). Before SPLIT only
    clears that moved through Paradeigma I count, when the job has at least two such players."""
    logs = clear_logs(job)
    moving = [x for x in logs if x[4]]
    parts = []
    for a, b, pool in ((0.0, min(T, SPLIT), moving if len(moving) >= 2 else logs), (SPLIT, T, logs)):
        tot, alive = collections.Counter(), 0.0
        if b > a:
            for p, sid, death, end, _ in pool:
                ss = starts(p, sid)
                r = pull(p, sid, job, [(0.0, death or end)], min(b, end), usual_gcd([y - x for x, y in zip(ss, ss[1:])]), start=a)
                alive += r["alive"]
                for k, v in flat(r).items(): tot[k] += v
        parts.append({k: v / alive for k, v in tot.items()} if alive else {})
    return tuple(parts)


def flat(r):
    """The per-second checks of a pull (burst windows are per window and kept apart)."""
    out = {k: r[k] for k in ("gap_idle", "gap_clip", "gap_interrupt", "interrupted", "healgcd", "dot")}
    out.update({("held", a): v for a, v in r["held"].items()})
    out.update({("gauge", k): v for k, v in r["gauge"].items()})
    out.update({("bonus", k): v for k, v in r["bonus"].items()})
    out.update({("bonus_loss", k): v for k, v in r["bonus_loss"].items()})
    out.update({("expired", k): v for k, v in r["expired"].items()})
    out.update({("overwritten", k): v for k, v in r["overwritten"].items()})
    out.update({("down", k): v for k, v in r["down"].items()})
    out.update({("casts", k): v for k, v in r["casts"].items()})
    return out


@functools.lru_cache(maxsize=None)
def clear_windows(job):
    """{buff action: GCDs per window} over the clears' whole kills."""
    tot = collections.defaultdict(lambda: [0, 0])
    for p, sid, death, end, _ in clear_logs(job):
        ss = starts(p, sid)
        r = pull(p, sid, job, [(0.0, death or end)], end, usual_gcd([y - x for x, y in zip(ss, ss[1:])]))
        for a, (n, g) in r["windows"].items(): tot[a][0] += n; tot[a][1] += g
    return {a: g / n for a, (n, g) in tot.items() if n}


def summary(job, pulls, gcd=None):
    """pulls: [(raw counts from pull(), the pull's `until`, unit costs, damage dealt while alive)] for one player on one
    job. Returns the checks with our rate, the clears' rate over the same stretches and the cost of the difference."""
    prof = profile(job)
    alive = sum(r["alive"] for r, _, _, _ in pulls)
    if alive < 60 or not clear_logs(job): return None
    ours, exp = collections.Counter(), collections.Counter()
    for r, until, _, _ in pulls:
        early, late = clear_rates(job, int(round(until / 10) * 10))
        for k, v in flat(r).items(): ours[k] += v
        for k, v in early.items(): exp[k] += v * r["alive_early"]
        for k, v in late.items(): exp[k] += v * (r["alive"] - r["alive_early"])
    ability = collections.defaultdict(list)
    for _, _, u, _ in pulls:
        for a, v in u["ability"].items(): ability[a].append(v)
    ticks = [u["tick"] for _, _, u, _ in pulls if u["tick"]]
    dps = sum(d for _, _, _, d in pulls) / alive
    gcd_hit = [u["gcd_hit"] for _, _, u, _ in pulls if u.get("gcd_hit")]
    labels = {"gap_idle": "GCD gaps: nothing cast", "gap_clip": "GCD gaps: weaving delayed the GCD",
              "gap_interrupt": "GCD gaps: after an interrupted cast"}
    rows, units, names = [], {}, {}
    for k in sorted(set(ours) | set(exp), key=str):
        if isinstance(k, tuple) and k[0] in ("bonus_loss", "casts"): continue
        excess = ours[k] - exp[k]
        if k in labels: label, unit, each = labels[k], "s", dps
        elif k == "interrupted": label, unit, each = "Casts interrupted", "times", None     # their time is in the gap above
        elif k == "healgcd": label, unit, each = "Healing GCDs", "gcds", st.mean(gcd_hit) if gcd_hit else None
        elif k[0] == "bonus":
            lost = ours[("bonus_loss", k[1])] - exp[("bonus_loss", k[1])]
            rows.append(dict(key=str(k), label=k[1], unit="times", ours=ours[k] / alive * 60, clears=exp[k] / alive * 60,
                             cost=max(0.0, lost) / alive if excess > 0 else None))
            names[k] = k[1]
            continue
        elif k == "dot": label, unit, each = "DoT ticks missed", "ticks", st.median(ticks) if ticks else None
        elif k[0] in ("expired", "overwritten"):
            if not ours[k] and not exp[k]: continue
            label, unit, each = f"{prof['procs'].get(k[1], k[1])} {k[0]}", "times", None
            # a lost proc is worth the cast that spends it, less the filler a GCD spender would have replaced
            sp = prof["spenders"].get(k[1])
            if sp and ability.get(sp):
                info = gamedata.actions({sp}).get(sp) or {}
                each = st.mean(ability[sp]) - (st.mean(gcd_hit) if info.get("gcd") and gcd_hit else 0)
                each = each if each > 0 else None
        elif k[0] == "down":
            name = prof["kept"].get(k[1], str(k[1]))
            label, unit, each = f"{name} down", "s", BUFF_VALUE[name] * dps if name in BUFF_VALUE else None
        elif k[0] == "held":
            cd = prof["cooldowns"][k[1]]
            label, unit = f"{cd['name']} held", "s"
            each = st.mean(ability[k[1]]) / cd["recast"] if ability.get(k[1]) else None    # per second held
        else:
            label, unit = k[1], "times"
            each = st.mean(ability[16507]) if k[1] == "Polyglot overcapped" and ability.get(16507) else None
            spec = next((g for g in prof["gauges"] if f"{g['label']} overcapped" == k[1]), None)
            if spec:      # a wasted gauge unit is worth its share of the spender, less the filler a GCD spender replaces
                unit, each = "gauge", None
                byname = {v["name"]: a for a, v in gamedata.actions(set(ability)).items()}
                sp = byname.get(spec["spender"])
                if sp is not None and ability.get(sp):
                    info = gamedata.actions({sp}).get(sp) or {}
                    v = st.mean(ability[sp]) - (st.mean(gcd_hit) if info.get("gcd") and gcd_hit else 0)
                    each = v / spec["spend"][spec["spender"]] if v > 0 else None
        rows.append(dict(key=str(k), label=label, unit=unit, ours=ours[k] / alive * 60, clears=exp[k] / alive * 60,
                         cost=max(0.0, excess) * each / alive if each else None))
        if each: units[k], names[k] = each, label
    win, ref = collections.defaultdict(lambda: [0, 0]), clear_windows(job)
    for r, _, _, _ in pulls:
        for a, (n, g) in r["windows"].items(): win[a][0] += n; win[a][1] += g
    for a, (n, g) in win.items():
        if a in ref: rows.append(dict(key=str(("window", a)), label=f"GCDs in {prof['cooldowns'].get(a, {}).get('name') or gamedata.actions({a})[a]['name']}",
                                      unit="per window", ours=g / n, clears=ref[a], windows=n, cost=None))
    rows.sort(key=lambda x: -(x["cost"] or 0))
    # abilities: casts per minute against the clears over the same stretches, worth the player's own damage per cast
    admg, casts = collections.Counter(), collections.Counter()
    for r, _, _, _ in pulls:
        admg.update(r["admg"]); casts.update(r["casts"])
    # GCD skills are compared at the player's own GCD speed: a slower GCD from gear fits fewer casts, which is no mistake
    speed = prof["gcd"] / gcd if prof.get("gcd") and gcd else 1.0
    skills = []
    for k in {k for k in set(ours) | set(exp) if isinstance(k, tuple) and k[0] == "casts"}:
        a = k[1]
        info = gamedata.actions({a}).get(a)
        if not info or (ours[k] + exp[k]) / alive * 60 < 0.05: continue
        ref = exp[k] * (speed if info["gcd"] else 1.0)
        per_cast = admg[a] / casts[a] if casts[a] else None
        skills.append(dict(name=info["name"], gcd=info["gcd"], ours=ours[k] / alive * 60, clears=ref / alive * 60,
                           worth=(ref - ours[k]) * per_cast / alive if per_cast else None))
    skills.sort(key=lambda x: -abs(x["worth"] or 0))
    return dict(alive_min=alive / 60, pulls=len(pulls), dps=dps, clears=len(clear_logs(job)), checks=rows, abilities=skills,
                clear_gcd=prof.get("gcd"),
                per_pull=per_pull(job, pulls, units, names))


def per_pull(job, pulls, units, names):
    """Each pull's rotation loss against the clears over the same stretch, in DPS (negative: better than the clears),
    priced with the player's units from the summary, and the check that cost the most in it."""
    out = []
    for r, until, _, dealt in pulls:
        if r["alive"] < 20: continue
        early, late = clear_rates(job, int(round(until / 10) * 10))
        mine = flat(r)
        exp = lambda k: early.get(k, 0) * r["alive_early"] + late.get(k, 0) * (r["alive"] - r["alive_early"])
        parts = {k: (mine.get(k, 0) - exp(k)) * u for k, u in units.items()}
        parts.update({k: mine.get(("bonus_loss", k[1]), 0) - exp(("bonus_loss", k[1])) for k in names if k[0] == "bonus"})
        top = max(parts, key=parts.get) if parts else None
        out.append(dict(n=r.get("n"), alive=round(r["alive"]), loss=round(sum(parts.values()) / r["alive"]),
                        top=names[top] if top is not None and parts[top] / r["alive"] >= 10 else None, dps=round(dealt / r["alive"])))
    return out


def report(data, lives):
    """Rotation summaries for every player and job in one of our reports, {(name, job): summary}.
    lives: [(pull row, {player: [(start, end, share, entry)]} lost time, until)] per pull, as built in scorecard.analyse."""
    import acts
    A = acts.report(data["code"], data["fights"])
    per = collections.defaultdict(list)
    for (row, down, until), f in zip(lives, data["fights"]):
        p = A.get(str(f["id"]))
        if not p: continue
        for sid, (name, job) in p["players"].items():
            if job not in ROLE: continue
            alive, t = [], 0.0
            for s, e in sorted((s, e) for s, e, share, _ in down.get(name, []) if share == 1.0):   # dead until raised
                if s > t: alive.append((t, min(s, until)))
                t = max(t, e)
            if t < until: alive.append((t, until))
            alive = [(a, b) for a, b in alive if b > a]
            if sum(b - a for a, b in alive) >= 20: per[(name, job)].append((p, int(sid), alive, until, row["n"]))
    out = {}
    for (name, job), items in per.items():
        iv = []
        for p, sid, *_ in items:
            ss = starts(p, sid); iv += [b - a for a, b in zip(ss, ss[1:])]
        gcd = usual_gcd(iv)
        pulls = []
        for p, sid, alive, until, n in items:
            dealt = sum(x[3] for x in p["dmg"] if x[1] == sid and any(a <= x[0] < b for a, b in alive))
            r = pull(p, sid, job, alive, until, gcd); r["n"] = n
            pulls.append((r, until, unit_costs(p, sid), dealt))
        s = summary(job, pulls, gcd)
        seqs = [opener_seq(p, sid, profile(job), OPENER_LATE) for p, sid, alive, until, n in items
                if until > OPENER_LATE and any(a <= 0.5 and b > OPENER_LATE for a, b in alive)]
        if s: out[(name, job)] = dict(s, gcd=gcd, opener=opener(job, seqs, who=name))     # raw times: the card shows both GCDs
        elif opener_source(job) == "groups" and (o := opener(job, seqs, who=name)):        # no clears: the opener alone
            out[(name, job)] = dict(gcd=gcd, opener=o, checks=[], abilities=[], opener_only=True)
    return out


# --- raid buff timing per burst ------------------------------------------------------------------------------------

BURSTS = [(-10, 40), (100, 160), (220, 300), (350, 430)]       # where each 2-minute burst's raid buffs land


def burst_of(t):
    return next((i for i, (a, b) in enumerate(BURSTS) if a <= t < b), None)


@functools.lru_cache(maxsize=None)
def clear_bursts():
    """The clears' median landing time per (raid buff, burst) and median spread of a party's buffs per burst."""
    import acts
    land, spread = collections.defaultdict(list), collections.defaultdict(list)
    for k in json.loads((HERE / "benchmark.json").read_text())["kills"]:
        by = collections.defaultdict(list)
        for t, n, job, src in acts.buff_uses(B.kill_acts(k)):
            i = burst_of(t)
            if i is not None: land[(n, i)].append(t); by[i].append(t)
        for i, ts in by.items():
            if len(ts) >= 2: spread[i].append(max(ts) - min(ts))
    return ({k: st.median(v) for k, v in land.items() if len(v) >= 3},
            {i: st.median(v) for i, v in spread.items() if len(v) >= 3})


def bursts(data, lives):
    """Raid buff timing in one of our reports against the clears: per player, buff and burst the median delay (s, + is
    late) and uses skipped while alive; per burst the spread from the party's first to last buff."""
    import acts
    A = acts.report(data["code"], data["fights"])
    ref, ref_spread = clear_bursts()
    last = {i: max(t for (n, j), t in ref.items() if j == i) for i in range(len(BURSTS)) if any(j == i for _, j in ref)}
    delays, skipped, spreads = collections.defaultdict(list), collections.Counter(), collections.defaultdict(list)
    users = {}
    for (row, down, until), f in zip(lives, data["fights"]):
        p = A.get(str(f["id"]))
        if not p: continue
        for t, n, job, src in acts.buff_uses(p): users[(p["players"][str(src)][0], n)] = job
    for (row, down, until), f in zip(lives, data["fights"]):
        p = A.get(str(f["id"]))
        if not p: continue
        uses = [(t, n, p["players"][str(src)][0]) for t, n, job, src in acts.buff_uses(p)]
        for i, end in last.items():
            if until < end + 5: continue                  # the pull did not get through this burst
            mine = [(t, n, who) for t, n, who in uses if burst_of(t) == i]
            for t, n, who in mine:
                if (n, i) in ref: delays[(who, n, i)].append(t - ref[(n, i)])
            if len(mine) >= 2: spreads[i].append(max(t for t, _, _ in mine) - min(t for t, _, _ in mine))
            for (who, n), job in users.items():
                if (n, i) not in ref or any(w == who and m == n for _, m, w in mine): continue
                dead = any(s <= ref[(n, i)] < e for s, e, share, _ in down.get(who, []) if share == 1.0)
                if not dead and who in [v[0] for v in p["players"].values()]: skipped[(who, n, i)] += 1
    keys = set(delays) | set(skipped)
    buffs = [dict(player=w, job=users.get((w, n)), buff=n, burst=i + 1, delay=round(st.median(delays[(w, n, i)]), 1) if delays[(w, n, i)] else None,
                  n=len(delays[(w, n, i)]), skipped=skipped[(w, n, i)]) for w, n, i in sorted(keys, key=lambda k: (k[2], k[1], k[0]))]
    spread = [dict(burst=i + 1, ours=round(st.median(v), 1), clears=round(ref_spread[i], 1) if i in ref_spread else None, n=len(v))
              for i, v in sorted(spreads.items())]
    return dict(buffs=buffs, spread=spread)


# --- openers -------------------------------------------------------------------------------------------------------

OPENER_END = 22.0            # seconds of opener compared (pre-pull casts included)
OPENER_LATE = 30.0           # a player's openers are read this far, then cut to as many GCDs as the clears' opener has
NOT_OPENER = ("Gemdraught", "Tincture", "Sprint")
# oGCDs that neither deal damage nor are raid buffs but are planned into openers (cards and draws, Swiftcast, gauge
# and pet skills); mitigation, movement, True North and Lucid Dreaming stay out
OPENER_ALSO = {"the Balance", "the Spear", "Astral Draw", "Umbral Draw", "Lightspeed", "Swiftcast", "Triplecast",
               "Hypercharge", "Automaton Queen", "Enshroud", "Infuriate", "Dissipation", "Salted Earth", "Salt and Darkness",
               "Enkindle Bahamut", "Enkindle Phoenix", "Enkindle Solar Bahamut", "Subtractive Palette", "Striking Muse",
               "Quadruple Technical Finish"}
SAME_STEP = {"Emboite": "Step", "Entrechat": "Step", "Jete": "Step", "Pirouette": "Step"}   # Dancer steps come in a random order


RECAST = {}                  # skill name -> recast (s), filled by opener_seq


def opener_seq(p, sid, prof, end=OPENER_END):
    """[(start, name, gcd)] of a player's casts from before the pull to `end`: GCDs, damaging oGCDs and damage
    buffs (defensives, potions and Sprint left out); hard casts are timed from their begun cast."""
    acts = gamedata.actions({a for t, s, a in p["casts"] if s == sid})
    begun = collections.defaultdict(list)
    for t, s, a in p.get("begins", []):
        if s == sid: begun[a].append(t)
    keep = set(prof["cooldowns"]) | prof["damaging"] | set(prof["windows"])
    out, last = [], -1e9              # last: the player's previous cast; a begin before it belongs to an earlier cast
    for t, s, a in sorted(x for x in p["casts"] if x[1] == sid):
        info, prev, last = acts.get(a), last, t
        if t > end or not info or any(x in info["name"] for x in NOT_OPENER): continue
        if not info["gcd"] and a not in keep and info["name"] not in BUFFS and info["name"] not in OPENER_ALSO: continue
        b = [x for x in begun[a] if 0 <= t - x < 6 and x > prev]    # instant casts have none
        RECAST[SAME_STEP.get(info["name"], info["name"])] = info.get("recast") or 0
        out.append((round(b[-1] if b else t, 2), SAME_STEP.get(info["name"], info["name"]), info["gcd"]))
    return sorted(out)


def align(ref, seq):
    """Edit-distance alignment of two name lists: [(op, i, j)] with op match / sub / del (a ref step missing) /
    ins (an extra cast)."""
    n, m = len(ref), len(seq)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): D[i][0] = i
    for j in range(m + 1): D[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (ref[i - 1] != seq[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and D[i][j] == D[i - 1][j - 1] + (ref[i - 1] != seq[j - 1]):
            ops.append(("match" if ref[i - 1] == seq[j - 1] else "sub", i - 1, j - 1)); i -= 1; j -= 1
        elif i and D[i][j] == D[i - 1][j] + 1: ops.append(("del", i - 1, None)); i -= 1
        else: ops.append(("ins", None, j - 1)); j -= 1
    return ops[::-1]


def distance(a, b):
    return sum(op != "match" for op, _, _ in align(a, b))


def medoid(seqs):
    """The sequence closest to all the others (fewest edits in total)."""
    names = [[n for _, n, _ in s] for s in seqs]
    return min(range(len(seqs)), key=lambda i: sum(distance(names[i], x) for x in names))


ECHO = 1.20                  # The Echo: a flat +20% damage


@functools.lru_cache(maxsize=None)
def clear_openers(job):
    """The clears' openers on the job (players alive past OPENER_END): [dict(seq, dmg)], dmg their opener nDPS (first
    20 s, tincture removed; Echo clears divided by ECHO), None when unknown."""
    prof, out = profile(job), []
    for k in json.loads((HERE / "benchmark.json").read_text())["kills"]:
        p = B.kill_acts(k)
        deaths, pf = {}, B.CACHE / f"phases_{k['code']}_{k['fight']}.json"
        for x in (json.loads(pf.read_text())["deaths"] if pf.exists() else []): deaths[x["name"]] = min(deaths.get(x["name"], 1e9), x["t"])
        dmg = {x["name"]: x["ndps"] / (ECHO if B.has_echo(k) else 1) for x in B.kill_opener(k) if x["job"] == job}
        for sid, (name, j) in p["players"].items():
            if j != job or deaths.get(name, 1e9) <= OPENER_END: continue
            seq = opener_seq(p, int(sid), prof)
            if seq and k["day"] > KIT_CHANGES.get(job, ("",))[0]: out.append(dict(seq=seq, dmg=dmg.get(name)))
    return out


# opener kit changes the clears predate: openers on the job are compared only with clears after the change. A job with
# fewer than three clears to compare with (after such a change, or with none at all, like Bard) is compared within our
# own groups instead. White Mage starts the pull with a Blood Lily (Afflatus Misery right away);
# none of the WHM clears (2025-03 to 2025-12-12) has it and nearly every pull of ours does, so the change came after
# 2025-12-12 (exact patch not pinned down)
KIT_CHANGES = {"WhiteMage": ("2025-12-12", "White Mage now starts the pull with a Blood Lily, which none of the WHM clears (all older) had")}
OUR_CODES = None              # our reports, for references from our own groups; None reads them from site/data.json


@functools.lru_cache(maxsize=None)
def group_openers(job):
    """Our groups' openers on the job: one entry per player over all our reports, like one clear player each (so a
    regular on the job does not outweigh the others): their usual opener to OPENER_END over pulls they were alive through
    to OPENER_LATE, and their median opener nDPS over pulls without The Echo they were alive through to OPENER_S.
    Returns [dict(seq, dmg, who)]."""
    import acts, fflogs
    from scorecard import OPENER_S
    codes = OUR_CODES if OUR_CODES is not None else list(json.loads((HERE / "site" / "data.json").read_text(encoding="utf-8"))["reports"])
    prof, seqs, dmg = profile(job), collections.defaultdict(list), collections.defaultdict(list)
    for code in codes:
        cf = fflogs.CACHE / f"report_{code}.json"
        if not cf.exists(): continue
        data = json.loads(cf.read_text())
        pulls, names = acts.report(code, data["fights"]), {a["id"]: a["name"] for a in data["masterData"]["actors"]}
        for f in data["fights"]:
            p = pulls.get(str(f["id"]))
            if not p or not p.get("players"): continue
            died = {}
            for x in data["deaths"]:
                if f["startTime"] <= x["timestamp"] <= f["endTime"] and x.get("targetID") in names:
                    died.setdefault(names[x["targetID"]], (x["timestamp"] - f["startTime"]) / 1000)
            dur = (f["endTime"] - f["startTime"]) / 1000
            for sid, (name, j) in p["players"].items():
                if j != job: continue
                if dur > OPENER_LATE and died.get(name, 1e9) > OPENER_LATE:
                    sq = opener_seq(p, int(sid), prof, OPENER_LATE)
                    if sq: seqs[name].append(sq)
            if f["id"] not in data.get("echo_pulls", []):
                for y in data.get("otables", {}).get(str(f["id"]), []):
                    if y["job"] == job and died.get(y["name"], 1e9) > OPENER_S: dmg[y["name"]].append(y["ndps"])
    out = []
    for name, sq in seqs.items():
        sq = [[x for x in q if x[0] <= OPENER_END] for q in sq]           # to 0:22, like the clears' openers
        out.append(dict(seq=sq[medoid(sq[-40:]) + max(0, len(sq) - 40)], dmg=st.median(dmg[name]) if dmg[name] else None, who=name))
    return out


def opener_source(job):
    """"clears", or "groups" when fewer than three clears are left to compare the opener with."""
    return "groups" if len(clear_openers(job)) < 3 else "clears"


@functools.lru_cache(maxsize=None)
def opener_ref(job, exclude=None):
    """The best opener the clears play on the job. Variants are openers within a few edits of each other; the one most
    clears play is the reference unless another (played by at least three) does clearly more opener damage: its median
    ahead by more than 1.5 standard errors of the difference, as the spread between players of one opener (gear, crits)
    is larger than most differences between openers. Returned as the variant's most typical sequence, the casts per
    skill in it, each skill's median first cast, and the damage of the clears that play it."""
    ops = clear_openers(job) if opener_source(job) == "clears" else [o for o in group_openers(job) if o["who"] != exclude]
    if len(ops) < 3: return None
    names = [[n for _, n, _ in o["seq"]] for o in ops]
    near = lambda i: max(2, len(names[i]) // 6)
    groups = [[k for k in range(len(ops)) if distance(names[i], names[k]) <= near(i)] for i in range(len(ops))]
    def dmg_of(g):
        d = [ops[k]["dmg"] for k in g if ops[k]["dmg"]]
        return (st.median(d), st.pstdev(d) / len(d) ** 0.5) if len(d) >= 2 else (None, None)
    v = max(range(len(ops)), key=lambda i: (len(groups[i]), dmg_of(groups[i])[0] or 0))
    basis, (m0, e0) = "played", dmg_of(groups[v])
    if m0 is not None:
        ahead = [(len(groups[i]), m, i) for i in range(len(ops)) if len(groups[i]) >= 3 for m, e in [dmg_of(groups[i])]
                 if m is not None and m - m0 > 1.5 * (e * e + e0 * e0) ** 0.5]
        if ahead: v, basis = max(ahead)[2], "damage"
    group = groups[v]
    centre = min(group, key=lambda i: sum(distance(names[i], names[k]) for k in group))
    seq = ops[centre]["seq"]
    times = collections.defaultdict(list)      # first cast of each skill, over the variant's clears
    for k in group:
        first = {}
        for t, n, g in ops[k]["seq"]: first.setdefault(n, t)
        for n, t in first.items(): times[n].append(t)
    dmg = [ops[k]["dmg"] for k in group if ops[k]["dmg"]]
    return dict(steps=[dict(t=t, name=n, gcd=g) for t, n, g in seq], counts=dict(collections.Counter(n for _, n, _ in seq)),
                first={n: round(st.median(v2), 2) for n, v2 in times.items()}, gcd={n: g for _, n, g in seq},
                dmg=round(st.median(dmg)) if dmg else None, clears=len(group), all=len(ops), basis=basis,
                all_dmg=round(st.median([o["dmg"] for o in ops if o["dmg"]])) if any(o["dmg"] for o in ops) else None)


@functools.lru_cache(maxsize=None)
def clear_opener_dps():
    """Median opener nDPS (first 20 s, tincture removed) per job over the clears without The Echo; a job with fewer than
    three such samples also gets the Echo clears, their damage divided by 1.2 (then marked `echo_corrected`)."""
    clean, echo = collections.defaultdict(list), collections.defaultdict(list)
    for k in json.loads((HERE / "benchmark.json").read_text())["kills"]:
        for x in B.kill_opener(k): (echo if B.has_echo(k) else clean)[x["job"]].append(x["ndps"])
    out = {}
    for j in set(clean) | set(echo):
        v = clean[j] if len(clean[j]) >= 3 else clean[j] + [x / ECHO for x in echo[j]]
        if len(v) >= 3: out[j] = dict(ndps=st.median(v), echo_corrected=len(clean[j]) < 3)
    return out


def opener(job, seqs, ratio=1.0, who=None):
    """A player's openers on the job against the clears' best opener (opener_ref): casts per skill in the opener
    against it over the same number of GCDs (GCD order is not compared: swapping two GCDs inside the opener changes
    nothing), when each oGCD cooldown and raid buff first went out, and their usual opener for showing side by side."""
    seqs = [x for x in seqs if x]
    source = opener_source(job)
    ref = opener_ref(job, who if source == "groups" else None)
    if not seqs or not ref: return None
    gcds = sum(1 for x in ref["steps"] if x["gcd"])     # compared over as many GCDs as the clears' opener has, so a
    def cut(sq):                                         # slower GCD from gear does not read as a missing filler
        k = [i for i, (_, _, g) in enumerate(sq) if g]
        return sq[:k[gcds]] if len(k) > gcds else sq
    full, seqs = seqs, [cut(sq) for sq in seqs]
    usual = seqs[medoid(seqs[-40:]) + max(0, len(seqs) - 40)]
    names = set(ref["counts"]) | {n for sq in seqs for _, n, _ in sq}
    gcd = dict(ref["gcd"]); gcd.update({n: g for sq in seqs for _, n, g in sq})
    timed = {c["name"] for c in profile(job)["cooldowns"].values()} | set(BUFFS) | OPENER_ALSO | {n for n in names if not gcd.get(n, True) and RECAST.get(n, 0) >= 30}   # cooldowns and raid buffs, not spenders
    rows = []
    for n in names:
        mine = st.mean(sum(1 for _, x, _ in sq if x == n) for sq in seqs)
        firsts = [next(t for t, x, _ in sq if x == n) for sq in seqs if any(x == n for _, x, _ in sq)]
        rows.append(dict(name=n, gcd=gcd.get(n, True), clears=ref["counts"].get(n, 0), theirs=round(mine, 2),
                         t_clears=ref["first"].get(n), t_theirs=round(st.median(firsts), 2) if firsts else None))
    for r in rows:
        r["fewer"] = r["clears"] - r["theirs"] >= 0.5
        r["more"] = r["theirs"] - r["clears"] >= 0.5
        r["late"] = (r["name"] in timed and r["t_clears"] is not None and r["t_theirs"] is not None and abs(r["t_theirs"] - r["t_clears"]) >= 1.5
                     and round(r["t_theirs"] - r["t_clears"], 1)) or None
    rows.sort(key=lambda r: (r["t_clears"] if r["t_clears"] is not None else 99, r["name"]))
    change = (KIT_CHANGES[job][1] if job in KIT_CHANGES else "No clear in the benchmark plays the job") if source == "groups" else None
    return dict(source=source, change=change, clears=ref["clears"], clears_all=ref["all"], basis=ref["basis"], pulls=len(full), gcds=gcds, best_dmg=ref["dmg"], all_dmg=ref["all_dmg"],
                best=ref["steps"], usual=[dict(t=t, name=n, gcd=g) for t, n, g in usual], skills=rows)
