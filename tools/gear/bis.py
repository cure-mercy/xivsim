"""Best in slot for P12S phase 1 (level 90, gear above level 90 synced to 660), jointly with the rotation optimizer.

    python tools/gear/bis.py --job blm                     # the best set per GCD tier, the rotation's mix at the job's GCD
    python tools/gear/bis.py --job blm --combined          # gear and rotation together: a whole-phase search per tier

A set is worth what the job's whole-phase rotation (tools/rotation, 0:00 to the clears' median kill, no raid buffs)
deals with it: the rotation's potency split by how each part scales (gear.Stats), times the set's multipliers:

  normal hits   main stat x determination x weapon damage x expected crit and direct hit (pets too)
  DoT ticks     as normal hits (the models' ticks carry the speed stat's DoT bonus at the set's speed)
  sure crits    a sure crit's damage (Monk's Bootshine, Samurai's Midare and Ogi), or a sure critical direct hit's with
                direct hit's bonus on determination (Machinist's Reassembled tools, Pictomancer's hammers, Starfall;
                Starfall under Devilment, whose rates a sure hit takes as damage)
  autos         ... x skill speed (the weapon's delay cancels out per second)

The GCD comes from the speed stat in tiers (the game rounds to 0.01 s, after a trait's haste: Monk, Ninja; under
Fuka, Swiftscaled or Ley Lines it rounds the hasted GCD again, so a tier there is the pair). Within a tier the rotation
is the same, so each tier gets its own best set; across tiers the rotation differs. --combined searches the rotation at
each tier's set's speed factor and own rates (crit rate, crit damage, direct-hit rate: chakra, Life Surge, own crit
buffs, sure-hit weights), takes the mix from it, finds the tier's set again and repeats until the set holds; the tiers
then compare at potency x multipliers.

Per tier the set is found by a dynamic program over the slots, keyed by the gear's total speed, on stat weights taken
from the set's own gradient, then a local search (one or two slots changed) on the exact, floored formulas; repeated
until the set stops changing. Rings go as pairs (a unique ring once).
"""
import argparse, itertools, json, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "rotation"))
import gear                                           # noqa: E402
from gear import JOBS, Stats, vector                  # noqa: E402

CACHE = HERE / ".cache"
SLOTS = ("weapon", "head", "body", "gloves", "legs", "feet", "ears", "neck", "wrists", "ring")
SURE_DH = {"MCH", "PCT", "DNC"}                       # sure crits that are critical direct hits
BUFF_HASTE = {"SAM": 13, "VPR": 15, "BLM": 15}        # Fuka, Swiftscaled, Ley Lines: the hasted GCD is part of the tier
ROUNDED = {"BLM", "SAM", "VPR", "MNK", "NIN"}         # job models whose speed-scaled times go through engine.recast
FIT_X = {"SAM": 1, "VPR": 1}                         # the GCD the potency is fitted on: Fuka, Swiftscaled nearly always up
PLAIN_DOT = {"MCH"}                                   # the model's DoT share is Wildfire's detonation: no crit, no direct hit,
                                                      # no speed scaling
SURE_BUFF = {"DNC": (0.20, 0.20)}                     # own crit / direct-hit rate buffs every sure hit lands under: Devilment
RATES = {"CRIT": "crit_rate", "CRIT_RATE": "crit_rate", "CRIT_DMG": "crit_dmg", "DH_RATE": "dh_rate"}  # job constant: Stats


class Mix:
    """A rotation's potency by how it scales with gear (over the scored window)."""

    def __init__(self, normal, dot=0.0, sure=0.0, auto=0.0):
        self.normal, self.dot, self.sure, self.auto = normal, dot, sure, auto

    @property
    def total(self):
        return self.normal + self.dot + self.sure + self.auto

    def __repr__(self):
        t = self.total
        return (f"{t:,.0f} potency: normal {self.normal / t:.1%}, DoT {self.dot / t:.1%}, sure crits {self.sure / t:.1%}, "
                f"autos {self.auto / t:.1%}")


def value(job, s, mix):
    """The set's damage over the window from the mix (the trait multiplier in, a job's own constant multipliers out)."""
    sure = s.sure_crit_dh() if job in SURE_DH else s.sure_crit()
    if job in SURE_BUFF:            # a sure hit takes a crit / direct-hit rate buff as damage (xivmath autoCritBuffDmg)
        c, d = SURE_BUFF[job]
        sure *= round(1 + (s.crit_dmg - 1) * c, 3) * round(1 + 0.25 * d, 3)
    # a DoT's speed bonus is in the model's tick potency (dot_tick: the rotation is replayed at the set's speed)
    dot = s.main_multi * s.det_multi * s.wd_multi if job in PLAIN_DOT else s.hit()
    return s.trait * (mix.normal * s.hit() + mix.dot * dot + mix.sure * sure) + mix.auto * s.auto()


def tier(job, s):
    """The set's GCD tier: the GCD after the job's trait haste, and the hasted one where a buff hastes it, as the game
    rounds them (engine.recast)."""
    return (s.gcd(),) + ((s.gcd(haste=BUFF_HASTE[job]),) if job in BUFF_HASTE else ())


# ---------------------------------------------------------------------------------------------------------- candidates

def _prune(rows, distinct=1):
    """Drops a variant another beats or ties in every stat at the same speed. Rings (`distinct`=2): only when variants
    of two other items do, so a unique ring's second best stays."""
    seen, uniq = set(), []
    for v, desc in rows:        # identical stats: one per item for rings, one in all otherwise
        key = (v, desc[0][0].id if distinct > 1 else None)
        if key not in seen: seen.add(key); uniq.append((v, desc))
    out = []
    for sp in sorted({v[5] for v, _ in uniq}):
        grp = [r for r in uniq if r[0][5] == sp]
        a = np.array([v[:5] for v, _ in grp])
        ids = np.array([d[0][0].id for _, d in grp])
        dom = (a[None, :, :] >= a[:, None, :]).all(-1)          # dom[i, j]: j beats or ties i everywhere
        np.fill_diagonal(dom, False)
        if distinct == 1:
            same = (a[None, :, :] == a[:, None, :]).all(-1)
            dom &= ~same | (np.arange(len(grp))[None, :] < np.arange(len(grp))[:, None])
            keep = ~dom.any(1)
        else:
            keep = np.array([len(set(ids[dom[i] & (ids != ids[i])])) < distinct for i in range(len(grp))])
        out += [r for r, k in zip(grp, keep) if k]
    return out


def candidates(job):
    """Per slot, [(KEYS vector, [(item, fill label)])], pruned; the ring slot holds pairs."""
    per = {}
    for it in gear.items(job):
        for label, stat in it.variants(job):
            per.setdefault(it.slot, []).append((vector(job, stat), [(it, label)]))
    out = {}
    for slot in SLOTS:
        if slot == "ring":
            ring = _prune(per["ring"], distinct=2)
            pairs = [(tuple(a + b for a, b in zip(u, v)), du + dv) for (u, du), (v, dv) in itertools.combinations(ring, 2)
                     if not (du[0][0].id == dv[0][0].id and du[0][0].unique)]
            out[slot] = _prune(pairs)
        else:
            out[slot] = _prune(per[slot])
    return out


def foods(job):
    """The job's foods, without those another gives at least as much of every stat (all are 10%, up to their max)."""
    fs = gear.foods(job)
    beats = lambda a, b: a != b and all(k in a and a[k][1] >= m for k, (_, m) in b.items())
    out = [(n, b) for n, b in fs if not any(beats(a, b) for _, a in fs)]
    return list({tuple(sorted((k, m) for k, (_, m) in b.items())): (n, b) for n, b in out}.values())


# ------------------------------------------------------------------------------------------------------------- search

def _total(cands, pick):
    return tuple(sum(cands[s][i][0][k] for s, i in zip(SLOTS, pick)) for k in range(6))


def _grad(job, totals, food, mix, d=40):
    """Stat weights: the value's change per point of each stat around the set (speed only for its DoT and autos)."""
    out = []
    for k in range(6):
        hi = list(totals); lo = list(totals)
        hi[k] += d; lo[k] = max(0, lo[k] - d)
        out.append((value(job, Stats(job, hi, food), mix) - value(job, Stats(job, lo, food), mix)) / (hi[k] - lo[k]))
    return np.array(out)


def _dp(cands, w, length):
    """best[g]: the highest weighted score of a set whose gear speed totals g, and the choices behind it."""
    best = np.full(length, -np.inf); best[0] = 0.0
    back = []
    for slot in SLOTS:
        vs = np.array([v for v, _ in cands[slot]], dtype=float)
        score, sp = vs @ w, vs[:, 5].astype(int)
        new, arg = np.full(length, -np.inf), np.full(length, -1)
        for i in range(len(vs)):
            sh = np.full(length, -np.inf)
            sh[sp[i]:] = best[:length - sp[i]] + score[i]
            m = sh > new
            new[m], arg[m] = sh[m], i
        back.append(arg); best = new
    return best, back


def _pick(back, cands, g):
    pick = []
    for slot, arg in zip(reversed(SLOTS), reversed(back)):
        i = int(arg[g]); pick.append(i); g -= int(cands[slot][i][0][5])
    return pick[::-1]


def _refine(job, cands, pick, food, mix, want, top=8):
    """Local search on the exact value, keeping the tier: one slot changed, then two among each slot's `top`."""
    def score(p):
        s = Stats(job, _total(cands, p), food)
        return value(job, s, mix) if tier(job, s) == want else -1.0
    cur = score(pick)
    while True:
        best = (cur, None)
        for si, slot in enumerate(SLOTS):
            for i in range(len(cands[slot])):
                p = pick[:si] + [i] + pick[si + 1:]
                v = score(p)
                if v > best[0] + 1e-9: best = (v, p)
        if best[1] is None:
            w = _grad(job, _total(cands, pick), food, mix)
            short = {s: sorted(range(len(cands[s])), key=lambda i: -np.dot(cands[s][i][0], w))[:top] for s in SLOTS}
            for a, b in itertools.combinations(range(len(SLOTS)), 2):
                for i in short[SLOTS[a]]:
                    for j in short[SLOTS[b]]:
                        p = list(pick); p[a], p[b] = i, j
                        v = score(p)
                        if v > best[0] + 1e-9: best = (v, p)
        if best[1] is None: return pick, cur
        cur, pick = best


def best_in_tier(job, cands, food, mix, want, start=None):
    """The best set (choice per slot) in the GCD tier `want` with this food and mix, or None if no set reaches it."""
    length = sum(max(v[5] for v, _ in cands[s]) for s in SLOTS) + 1
    ok = np.array([tier(job, Stats(job, (0, 0, 0, 0, 0, g), food)) == want for g in range(length)])
    if not ok.any(): return None
    # the first weights at a set of every slot's highest stats, halved: about where the sets are
    totals = start or tuple(sum(max(v[k] for v, _ in cands[s]) for s in SLOTS) // 2 for k in range(6))
    seen, pick = set(), None
    for _ in range(8):
        w = _grad(job, totals, food, mix)
        best, back = _dp(cands, w, length)
        masked = np.where(ok, best, -np.inf)
        if not np.isfinite(masked).any(): return None
        p = _pick(back, cands, int(np.argmax(masked)))
        p, v = _refine(job, cands, p, food, mix, want)
        key = tuple(p)
        if key in seen: break
        seen.add(key)
        if pick is None or v > pick[1]: pick = (p, v)
        totals = _total(cands, p)
    return pick


def reachable(job, cands, food):
    """The GCD tiers some set reaches with this food, slowest first."""
    lo = sum(min(v[5] for v, _ in cands[s]) for s in SLOTS)
    hi = sum(max(v[5] for v, _ in cands[s]) for s in SLOTS)
    return sorted({tier(job, Stats(job, (0, 0, 0, 0, 0, g), food)) for g in range(lo, hi + 1)}, reverse=True)


def solve(job, mix_at, tiers=None, log=print):
    """{tier: (value, food name, food, pick)} for every reachable tier (or those given), with mix_at(tier) -> Mix."""
    cands = candidates(job)
    out = {}
    for fname, fb in foods(job):
        for t in tiers or reachable(job, cands, fb):
            r = best_in_tier(job, cands, fb, mix_at(t), t)
            if r and (t not in out or r[1] > out[t][0]):
                out[t] = (r[1], fname, fb, r[0])
    return cands, out


def describe(job, cands, food, pick):
    s = Stats(job, _total(cands, pick), food)
    lines = [f"    {s.sheet()}"]
    for slot, i in zip(SLOTS, pick):
        for it, label in cands[slot][i][1]:
            lines.append(f"    {it.slot:<7} {it.ilvl} {it.name:<44} {label}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------- rotation

def _rot():
    import dps
    return dps


def tier_speed(job, t):
    """The speed factor (a job's SPEED) a tier's rotation is searched at: the smallest that gives the tier, the jobs'
    own convention (SPEED = GCD / 2.5); every factor in the tier gives its GCD and hasted GCD (engine.recast)."""
    h = gear.JOBS[job][3]
    gcd = lambda pm, x: gear.fl(gear.fl(pm * 2.5) * (100 - x) / 1000) / 100
    of = lambda pm: (gcd(pm, h),) + ((gcd(pm, h + BUFF_HASTE[job]),) if job in BUFF_HASTE else ())
    return min(pm for pm in range(800, 1001) if of(pm) == t) / 1000


def rates(jobkey, s):
    """The rates of the set's the job model takes as constants (crit rate, crit damage, direct-hit rate)."""
    jm = _rot().JOBS[jobkey][0]
    return {k: getattr(s, a) for k, a in RATES.items() if hasattr(jm, k)}


class configured:
    """The job module at a speed factor and rates (its derive() rerun), restored afterwards."""

    def __init__(self, job, speed, params):
        self.job, self.set = job, dict(params, SPEED=speed)

    def __enter__(self):
        self.keep = {k: getattr(self.job, k) for k in self.set}
        for k, v in self.set.items(): setattr(self.job, k, v)
        if hasattr(self.job, "derive"): self.job.derive()
        return self.job

    def __exit__(self, *exc):
        for k, v in self.keep.items(): setattr(self.job, k, v)
        if hasattr(self.job, "derive"): self.job.derive()


def rotation(jobkey, speed, params, width=None, until=None, with_setting=False):
    """The rotation's history at this speed factor and these rates over the whole phase (or 0:00-`until`: the site's
    0:00-2:00 ceiling), searched and polished as dps.ceiling does, cached in .cache/rot/. `with_setting`: (history,
    the heuristic setting it was searched at); a file saved before the setting was kept is searched again."""
    key = "_".join([f"{speed:.3f}"] + [f"{k}{v:.3f}" for k, v in sorted(params.items())]) + (f"_w{until:.0f}" if until else "")
    f = CACHE / "rot" / f"{jobkey}_{key}.json"
    d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    if d is None or (with_setting and isinstance(d, list)):
        dps = _rot()
        import polish
        job = dps.JOBS[jobkey][0]
        fight = dps.site_fight(job, until or dps.FULL)[1]
        with configured(job, speed, params):
            s, setting, _ = dps.engine.search(jobkey, fight, width=width, speed=speed, params=params or None)
            s, _ = polish.polish(jobkey, fight, s, setting, speed, params=params or None, log=lambda m: None)
        new = dict(setting=list(setting), hist=s.history())
        if isinstance(d, list) and [list(x) for x in d] != json.loads(json.dumps(new["hist"])):
            print(f"  {f.name}: searched again for its setting, and the search now finds another rotation", flush=True)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(new), encoding="utf-8")
        d = new
    hist = [tuple(x) for x in (d["hist"] if isinstance(d, dict) else d)]
    return (hist, tuple(d["setting"])) if with_setting else hist


def mix(jobkey, hist, speed, params):
    """The rotation's potency over the whole phase by kind: its history replayed at the speed factor and rates, once
    more without auto-attacks for theirs."""
    dps = _rot()
    import polish
    job = dps.JOBS[jobkey][0]
    fight = dps.site_fight(job, dps.FULL)[1]

    def replay():
        """Plain potency to the window's end: job.final (the swings and ticks still to come) without the weight it puts
        on sure crits (Machinist, Samurai, Pictomancer, Dancer); gear.Stats prices them."""
        w = getattr(job, "SURE_W", None) or getattr(job, "STAR_W", None) or 1.0
        steps, states = polish.split(job, fight, job.State.initial(fight), hist)
        s = states[-1]
        sure = getattr(s, "critp", 0.0)
        return job.final(s, fight) - (w - 1) * sure, getattr(s, "dotp", 0.0), sure
    with configured(job, speed, params):
        total, dot, sure = replay()
        auto = 0.0
        if hasattr(job, "AUTO"):
            keep, job.AUTO = job.AUTO, 0
            try: auto = total - replay()[0]
            finally: job.AUTO = keep
    return Mix(total - dot - sure - auto, dot, sure, auto)


def _stats(job, cands, r):
    return Stats(job, _total(cands, r[3]), r[2])


def tier_rotation(jobkey, cands, t, r, rounds=3):
    """A tier's own rotation and set: searched at the set's speed factor and rates, again while they move. `r`: a set
    in the tier to start from. Returns (mix, (value, food name, food, pick))."""
    job = jobkey.upper()
    cur = setting(jobkey, t, _stats(job, cands, r))
    for _ in range(rounds):
        m = mix(jobkey, rotation(jobkey, *cur), *cur)
        r = solve(job, lambda _: m, [t])[1][t]
        new = setting(jobkey, t, _stats(job, cands, r))
        if new == cur: break
        cur = new
    return m, r


def setting(jobkey, t, s):
    """(speed factor, rates) a set's rotation is searched at. Where every speed-scaled time goes through engine.recast
    (ROUNDED) the set's own factor: within a GCD tier a Black Mage's casts still differ (2.0 s: 1.85 s at 0.928, 1.86 s
    at 0.930). Elsewhere the jobs scale continuously (BASE_GCD x SPEED), and the tier's smallest factor gives the
    game's GCD exactly."""
    job = jobkey.upper()
    speed = s.permille / 1000 if job in ROUNDED else tier_speed(job, t)
    return speed, rates(jobkey, s)


SLACK = 0.02          # potency can beat the GCD's ratio a little: a fixed timeline fits casts unevenly (Red Mage's 2.50 s)
STOP, STOP_SPAN = 0.015, 0.05     # the grid stops once STOP_SPAN s of it in a row stayed STOP under its best so far
TIE = 0.004       # the search's noise: a grid search this close to the best searched tier (or better) is searched too
GRID_STEP = {"BLM": 0.01}         # every tier, unfitted: Black Mage's potency jumps at some GCDs (2.18 s, 2.32 s),
                                  # which a fit smooths out (the 2026-10-24 grid every 0.03 s missed 2.18-2.24 s)


def span_of(job, first):
    """The tiers that could still win: a set's multipliers (its first-pass value at one mix) times the most a faster
    GCD can add to the potency, the GCDs' ratio (plus SLACK), at least the best first-pass value. The first-pass best
    is the slowest tier's (the most crit and determination), so a flat cut against it reaches less far than the
    potency can make up (Black Mage's 2.18 s: 0.886 of it, 8.7% more potency than 2.38 s)."""
    x = lambda t: t[FIT_X.get(job, 0)]
    top = max(first, key=lambda t: first[t][0])
    reach = lambda t: first[t][0] * max(1.0, x(top) / x(t)) * (1 + SLACK)
    return sorted((t for t in first if reach(t) >= first[top][0]), reverse=True)


def combined(jobkey, step=0.03, top=3, log=print):
    """Gear and rotation together. Every tier's set at the job's own rotation's mix first; then the whole-phase
    rotation searched on a grid of GCDs every `step` s (GRID_STEP), slowest first, over the tiers that could still win
    (span_of), until STOP_SPAN s of grid in a row stay STOP under the best grid value so far (each grid point priced
    at its tier's set with its own mix); the potency fitted over the grid (search noise ~0.4%; GRID_STEP jobs take
    the grid's own) and the mix's shares interpolated; every tier's set again at its fitted mix; the `top` tiers then
    searched at their own GCD, and so is every grid tier whose one-round grid search came within TIE of the best of
    them or above it (a lucky grid point lifts the fit, but it is a set and a rotation that were searched: Monk's 1.94 s
    grid point beat the three fitted best by 1.1%, 2026-10-25). Returns (cands, {tier: (fitted dps, food name, food,
    pick, mix)}, {tier: searched (dps, ...)}, {tier: grid search (dps, ...)}, grid {gcd: mix})."""
    job, dps = jobkey.upper(), _rot()
    cands, W = candidates(job), dps.FULL
    jm = dps.JOBS[jobkey][0]
    m0 = mix(jobkey, rotation(jobkey, jm.SPEED, {}), jm.SPEED, {})        # the job's own speed and rates
    log(f"{job}: own rotation at {jm.SPEED * dps.engine.BASE_GCD:.2f}: {m0}")
    _, first = solve(job, lambda t: m0)
    span = span_of(job, first)
    x = lambda t: t[FIT_X.get(job, 0)]
    step = GRID_STEP.get(job, step)
    order = sorted(span, key=x, reverse=True)
    log(f"  span {'/'.join(f'{v:.2f}' for v in order[0])} to {'/'.join(f'{v:.2f}' for v in order[-1])} "
        f"({len(order)} tiers), grid every {step:.2f} s")
    mixes, vals, last, below, grid = {}, {}, None, None, {}
    for t in order:
        if not (last is None or last - x(t) >= step - 1e-9 or t == order[-1]): continue
        mixes[x(t)], r = tier_rotation(jobkey, cands, t, first[t], rounds=1)
        vals[x(t)], last = r[0], x(t)
        grid[t] = (r[0] / W, r[1], r[2], r[3], mixes[x(t)])
        log(f"  grid {'/'.join(f'{v:.2f}' for v in t)}: {r[0] / W:,.0f}  {mixes[x(t)]}")
        below = None if r[0] >= (1 - STOP) * max(vals.values()) else below if below is not None else x(t)
        if below is not None and below - x(t) >= STOP_SPAN - 1e-9:
            log(f"  grid stops: {below:.2f}-{x(t):.2f} s stayed {STOP:.1%} under its best")
            break
    span = [t for t in span if x(t) >= last - 1e-9]       # no extrapolation past the grid
    gs = sorted(mixes)
    fit = None if job in GRID_STEP else np.polyfit(gs, [mixes[g].total for g in gs], min(2, len(gs) - 1))

    def mix_at(t):
        tot = float(np.interp(x(t), gs, [mixes[g].total for g in gs]) if fit is None else np.polyval(fit, x(t)))
        share = lambda k: float(np.interp(x(t), gs, [getattr(mixes[g], k) / mixes[g].total for g in gs]))
        return Mix(*(tot * share(k) for k in ("normal", "dot", "sure", "auto")))
    _, sets = solve(job, mix_at, span)
    fitted = {t: (r[0] / W, r[1], r[2], r[3], mix_at(t)) for t, r in sets.items()}
    searched = {}
    for t in sorted(fitted, key=lambda t: -fitted[t][0])[:top]:
        m, r = tier_rotation(jobkey, cands, t, sets[t])
        searched[t] = (r[0] / W, r[1], r[2], r[3], m)
        log(f"  searched {'/'.join(f'{v:.2f}' for v in t)}: {searched[t][0]:,.0f} (fitted {fitted[t][0]:,.0f})  {r[1]}")
    for t, g in sorted(grid.items(), key=lambda kv: -kv[1][0]):      # grid points that tie or beat them: searched too
        if t in searched or g[0] < (1 - TIE) * max(v[0] for v in searched.values()): continue
        m, r = tier_rotation(jobkey, cands, t, (g[0] * W, g[1], g[2], g[3]))     # from its grid set
        searched[t] = (r[0] / W, r[1], r[2], r[3], m)
        log(f"  searched {'/'.join(f'{v:.2f}' for v in t)}: {searched[t][0]:,.0f} (grid {g[0]:,.0f}, fitted "
            f"{fitted[t][0] if t in fitted else float('nan'):,.0f})  {r[1]}")
    return cands, fitted, searched, grid, mixes


def save(jobkey, cands, fitted, searched, grid=None):
    """The combined optimum to .cache/bis_<job>.json: the best searched tier's set (items, fills, food, final stats), the
    speed factor and rates its rotation is searched at, its mix, every searched tier's set (`sets`, best first: the site
    shows the ties, sheets.py), every tier's fitted DPS (tools/gear/ceiling.py reads it) and the grid's one-round
    searches (`grid`, the site's chart)."""
    job = jobkey.upper()
    t, (d, fname, fb, pick, m) = max(searched.items(), key=lambda x: x[1][0])
    s = Stats(job, _total(cands, pick), fb)
    speed, rt = setting(jobkey, t, s)
    gear_ = [dict(slot=it.slot, id=it.id, name=it.name, ilvl=it.ilvl, fill=label)
             for sl, i in zip(SLOTS, pick) for it, label in cands[sl][i][1]]
    sets = [dict(tier=list(k), dps=r[0], food=r[1], foodBonus={x: list(v) for x, v in r[2].items()}, totals=list(_total(cands, r[3])),
                 gear=[dict(slot=it.slot, id=it.id, name=it.name, ilvl=it.ilvl, fill=label)
                       for sl, i in zip(SLOTS, r[3]) for it, label in cands[sl][i][1]])
            for k, r in sorted(searched.items(), key=lambda x: -x[1][0])]     # every searched tier's set (sheets.py: ties)
    out = dict(job=job, tier=list(t), dps=d, food=fname, foodBonus={k: list(v) for k, v in fb.items()}, gear=gear_, sets=sets,
               totals=list(_total(cands, pick)), stats={k: getattr(s, k) for k in ("main", "wd", "crit", "dh", "det", "speed")},
               rates=dict(crit_rate=s.crit_rate, crit_dmg=s.crit_dmg, dh_rate=s.dh_rate), speed=speed, params=rt,
               mix=dict(normal=m.normal, dot=m.dot, sure=m.sure, auto=m.auto),
               searched={"/".join(f"{v:.2f}" for v in k): r[0] for k, r in searched.items()},
               fitted={"/".join(f"{v:.2f}" for v in k): r[0] for k, r in fitted.items()},
               grid={"/".join(f"{v:.2f}" for v in k): r[0] for k, r in (grid or {}).items()})
    (CACHE / f"bis_{jobkey}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--job", default="blm")
    ap.add_argument("--combined", action="store_true", help="search the rotation per tier (slow: one whole-phase search each)")
    ap.add_argument("--gcd", type=float, help="without --combined: the rotation's GCD for the mix (default the job's)")
    ap.add_argument("--top", type=int, default=3, help="sets printed in full")
    a = ap.parse_args()
    job = a.job.upper()
    if a.combined:
        cands, fitted, searched, grid, _ = combined(a.job, top=a.top)
        save(a.job, cands, fitted, searched, grid)
        print(f"\n{job}: DPS per GCD tier over the whole phase (no raid buffs; the job's own constant multipliers out)")
        print("  fitted:", "  ".join(f"{'/'.join(f'{v:.2f}' for v in t)} {r[0]:,.0f}"
                                     for t, r in sorted(fitted.items(), reverse=True)))
        for t, (d, fname, fb, pick, m) in sorted(searched.items(), key=lambda x: -x[1][0]):
            print(f"\n  {'/'.join(f'{v:.2f}' for v in t)}  {d:,.0f} searched ({fitted[t][0] if t in fitted else float('nan'):,.0f} fitted)  {fname}  {m}\n"
                  f"{describe(job, cands, fb, pick)}")
    else:
        dps = _rot()
        g = a.gcd or round(dps.JOBS[a.job][0].SPEED * dps.engine.BASE_GCD, 2)
        sp = g / dps.engine.BASE_GCD
        m = mix(a.job, rotation(a.job, sp, {}), sp, {})
        print(f"{job}: the rotation at {g:.2f}: {m}")
        cands, res = solve(job, lambda t: m)
        base = max(v for v, *_ in res.values())
        for t, (v, fname, fb, pick) in sorted(res.items(), key=lambda x: -x[1][0])[:a.top]:
            print(f"  {'/'.join(f'{x:.2f}' for x in t)}  {v / base:.4f}  {fname}\n{describe(job, cands, fb, pick)}")
        print("  every tier:", "  ".join(f"{'/'.join(f'{x:.2f}' for x in t)} {v / base:.4f}"
                                         for t, (v, *_) in sorted(res.items(), reverse=True)))
