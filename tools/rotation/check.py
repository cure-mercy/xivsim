"""Checks the optimizer's movement and downtime handling, independently of the search.

    python tools/rotation/check.py

1. engine.stand on hand-made move windows: a cast that leaves too little running time is refused; a cast the run can
   still follow keeps the player on their spot (Ley Lines); one that only fits if the run started first takes them off.
2. Quick searches (one heuristic, narrow beam) for both Paradeigma I slots and every variant of the other mechanics;
   each rotation is replayed from its printed history: every move window must get its running time outside cast bars
   (up to the slide point), and nothing may be cast at Athena while she is away.
3. Reaper: the reach rule on hand-made away windows and positionals in pinned ones; then quick searches for M1 and M2,
   replayed the same way, plus every away window must hold a stretch of its length without a melee action. The same
   searches for Monk, Dragoon and Viper.
4. Bard: Repertoire under each song and Army's Muse on hand-made states; then quick searches for R1 and R2 replayed:
   nothing cast at Athena while she is away, and (every action being instant) the strategy's running costs nothing.
5. Red Mage: Dualcast, Acceleration's priority, the expected procs and the far spots' reach on hand-made states; then
   quick searches for R1 and R2 replayed as in 2, plus no melee action at a far spot without Manafication.
Exits non-zero on any failure.
"""
import itertools, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine, p12s                              # noqa: E402
from engine import Fight, Move, SLIDE            # noqa: E402
from jobs import blm, brd, drg, mnk, rdm, rpr, vpr    # noqa: E402

HARM = {"Fire III", "Fire IV", "Despair", "Paradox", "Blizzard III", "Blizzard IV", "Thunder III", "Xenoglossy"}
HARM |= (set(rpr.GCDS) - {"Soulsow"}) | rpr.AVATAR | {"Gluttony", "Lemure's Slice"}
HARM |= mnk.HARM_GCDS | {"The Forbidden Chakra", "Enlightenment"}
HARM |= set(brd.POTENCY) | {"Apex Arrow", "Pitch Perfect"}
HARM |= set(drg.POTENCY)
HARM |= set(rdm.POTENCY)
HARM |= set(vpr.POTENCY)
fails = []


def expect(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok: fails.append(what)


class S:
    def __init__(s): s.mvi, s.acc, s.free, s.spot = 0, 0.0, 0.0, 0


def stand_cases():
    print("engine.stand")
    f = Fight(moves=[Move(10, 15, 3.0)])
    expect(engine.stand(S(), f, 8, 9.5, commit=False) is False, "a cast before the window: stays put")
    expect(engine.stand(S(), f, 10, 12, commit=False) is False, "a cast the run can still follow (3 s left): stays put")
    expect(engine.stand(S(), f, 10, 12.5, commit=False) is None, "a cast leaving 2.5 s of a 3 s run: refused")
    s = S(); s.free = 9.0
    expect(engine.stand(s, f, 11.5, 13, commit=False) is True, "a cast that only fits after 1.5 s of running: left the spot")
    expect(engine.stand(s, f, 11.0, 13.5, commit=False) is None, "the same with 1 s banked: refused")
    s = S(); engine.stand(s, f, 9, 10.5); engine.stand(s, f, 11, 11.5)
    expect(s.acc == 0.5 and s.spot == 0, f"0.5 s banked, the run still fits after: on the spot (acc {s.acc}, spot {s.spot})")
    engine.stand(s, f, 12, 12.5)
    expect(s.acc == 1.0 and s.spot == 1, f"2.5 s left after the next cast: part of the run came first (acc {s.acc}, spot {s.spot})")
    engine.stand(s, f, 16, 17)
    expect(s.mvi == 1 and s.spot == 1, "past the window: next window, new spot")


def replay(state, fight):
    """Cast bars and casts from a rotation's history; cast times are in its notes, and the running a dash saved
    (Red Mage) too."""
    busy, casts, dashed = [], [], []
    for t, name, note in state.history():
        m = re.match(r"\s*([\d.]+)s cast", note)
        casts.append((t, name))
        if m: busy.append((t, t + float(m[1]) - SLIDE))
        d = re.search(r"dash ([\d.]+)s", note)
        if d: dashed.append((t, float(d[1])))
    short = []
    for w in fight.moves:
        if not w.need: continue
        free = (w.hi - w.lo) - sum(max(0, min(b, w.hi) - max(a, w.lo)) for a, b in busy)
        free += sum(x for t, x in dashed if w.lo <= t < w.hi)
        if free < w.need - 1e-6: short.append(f"{w.lo:.1f}-{w.hi:.1f}s free {free:.2f} < {w.need:.2f}: {w.why}")
    away = [f"{name} at {t:.2f}" for t, name in casts if name in HARM and not fight.targetable(t)]
    return short, away, len(busy)


def reach_cases():
    print("\nReaper: reach and positionals")
    f = Fight(away=[Move(10, 20, 4.0)], pinned=[(30, 40)])
    s = rpr.State.initial(f); s.mlast = 5.0
    expect(rpr.reach(s, f, 9, commit=False), "a melee hit before the away window")
    expect(rpr.reach(s, f, 15, commit=False), "a hit at 15 s: the 4 s stretch still fits after it (15-20 s)")
    expect(rpr.reach(s, f, 17, commit=False), "a hit at 17 s, none since 5 s: the stretch was 10-14 s")
    s.mlast = 12.0
    expect(rpr.reach(s, f, 16.5, commit=False), "a hit at 16.5 s after one at 12 s: the stretch was 12-16 s")
    expect(rpr.reach(s, f, 15.5, commit=False), "a hit at 15.5 s after one at 12 s: 4.5 s still left after it")
    s.mlast = 14.0
    expect(not rpr.reach(s, f, 17, commit=False), "a hit at 17 s after one at 14 s: 3 s before, 3 s after: refused")
    rpr.reach(s, f, 15)
    expect(rpr.reach(s, f, 20.5) and s.ai == 1, "a hit at 15 s, then past the window: 15-20 s was the stretch, window done")
    s = rpr.State.initial(f)
    expect(rpr.flank_rear(s, f, 25) and not rpr.flank_rear(s, f, 35), "positionals free outside the pinned spot, not in it")
    s.tn_until = 36.0
    expect(rpr.flank_rear(s, f, 35) and not rpr.flank_rear(s, f, 37), "True North gets them in it, for its 10 s")


def gaps(state, fight, job=rpr):
    """Away windows without a stretch of their length free of melee actions."""
    hits = sorted(t for t, name, _ in state.history() if name in job.MELEE_ACTIONS)
    bad = []
    for w in fight.away:
        pts = [w.lo] + [t for t in hits if w.lo < t < w.hi] + [w.hi]
        if max(b - a for a, b in zip(pts, pts[1:])) < w.need - 1e-6: bad.append(f"{w.lo:.1f}-{w.hi:.1f}s: no {w.need} s out of reach")
    return bad


def melee_searches(job=rpr, gcd=2.49, width=200):
    print(f"\n{job.LOG_NAME} searches (width {width}) replayed")
    job.SPEED = gcd / engine.BASE_GCD
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    for slot, var in [("M1", {}), ("M2", {m: v[0] for m, v in alt.items()})]:
        f = p12s.fight(slot, var)
        s = engine.beam(job, f, width=width)
        short, away, hard = replay(s, f)
        bad = gaps(s, f, job)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not short and not away and not bad, f"{label}: {len(f.away)} away windows, {hard} hard casts, "
                                                   f"{s.dmg:,.0f} potency" + "".join(f"\n          {x}" for x in short + away + bad))
    still = engine.beam(job, p12s.fight("M1", still=True), width=width)
    bad = gaps(still, p12s.fight("M1"), job)
    expect(bool(bad), f"control: the standing-still rotation breaks {len(bad)} of the M1 away windows")


def searches(width=200):
    print(f"\nsearches (width {width}) replayed")
    blm.SPEED = 2.32 / engine.BASE_GCD
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    cases = [("R1", {}), ("R2", {m: v[0] for m, v in alt.items()})]
    for slot, var in cases:
        f = p12s.fight(slot, var)
        s = engine.beam(blm, f, width=width)
        short, away, hard = replay(s, f)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not short and not away, f"{label}: {sum(1 for w in f.moves if w.need)} windows, {hard} hard casts, "
                                       f"{s.dmg:,.0f} potency" + "".join(f"\n          {x}" for x in short + away))
    still = engine.beam(blm, p12s.fight("R1", still=True), width=width)
    short, _, _ = replay(still, p12s.fight("R1"))
    expect(bool(short), f"control: the standing-still rotation breaks {len(short)} of the R1 windows")


def bard_cases():
    print("\nBard: Repertoire and Army's Muse")
    f = Fight(until=60)
    s = brd.State.initial(f); s.first = False
    s.caustic = (0.0, 1.0)
    brd.sing(s, "The Wanderer's Minuet", 1.0)
    brd.advance(s, f, 7.0)                      # ticks at 1.5 and 4.5 s
    expect(abs(s.rep - 1.6) < 1e-9 and abs(s.sv - 8) < 1e-9, f"Minuet: two ticks, 1.6 stacks and 8 Soul Voice ({s.rep:.2f}, {s.sv:.1f})")
    brd.advance(s, f, 20.0)
    expect(s.rep == 3 and s.waste[0] > 0, f"Minuet: capped at three, the rest wasted ({s.rep}, {s.waste[0]:.1f})")
    brd.use_cd(s, "Bloodletter", 20.0); brd.use_cd(s, "Bloodletter", 20.0)
    brd.sing(s, "Mage's Ballad", 20.0)
    expect(s.waste[2] == 3, "a song over the Minuet drops its stacks")
    brd.advance(s, f, 23.0)                     # a tick at 22.5: 6 s off Bloodletter's 15 s
    expect(abs(brd.charges(s, "Bloodletter", 23.0)[1] - 29.0) < 1e-9, "Ballad: a tick takes 0.8 x 7.5 s off Bloodletter")
    brd.sing(s, "Army's Paeon", 30.0)
    brd.advance(s, f, 48.0)                     # five ticks: four stacks, 16% haste
    expect(s.rep == 4 and abs(brd.haste(s, 48.0) - 0.16) < 1e-9, f"Paeon: four stacks, 16% haste ({brd.haste(s, 48.0):.0%})")
    brd.sing(s, "The Wanderer's Minuet", 48.0)
    expect(abs(brd.haste(s, 50.0) - 0.12) < 1e-9 and brd.haste(s, 58.5) == 0, "Army's Muse: 12% for 10 s after four stacks")


def bard_searches(width=200):
    print(f"\nBard searches (width {width}) replayed")
    brd.SPEED = 2.49 / engine.BASE_GCD
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    still = engine.beam(brd, p12s.fight("R1", still=True), width=width)
    for slot, var in [("R1", {}), ("R2", {m: v[0] for m, v in alt.items()})]:
        f = p12s.fight(slot, var)
        s = engine.beam(brd, f, width=width)
        _, away, _ = replay(s, f)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not away and abs(s.dmg - still.dmg) < 1e-6, f"{label}: {s.dmg:,.0f} potency, standing still {still.dmg:,.0f}"
                                                           + "".join(f"\n          {x}" for x in away))


def rdm_cases():
    print("\nRed Mage: Dualcast, Acceleration, procs, reach")
    f = Fight(until=60)
    s = rdm.State.initial(f); s.first = False
    s = rdm.do_gcd(s, f, "Jolt III", ev=True)
    expect(s.dc > s.t and abs(s.black - 2) < 1e-9, "a hard-cast Jolt III grants Dualcast and 2 / 2 mana")
    a = rdm.do_gcd(s, f, "Verthunder III", ev=True)
    expect(a.dc < a.t and abs(a.vf - 0.5) < 1e-9, f"the next Verthunder III is instant, spends Dualcast, 50% Verfire Ready ({a.vf})")
    b = rdm.do_gcd(rdm.do_gcd(a, f, "Jolt III", ev=True), f, "Verthunder III", ev=True)
    expect(abs(b.vf - 0.75) < 1e-9 and abs(b.waste[1] - 0.25) < 1e-9, f"another: 75% up, 0.25 overwritten ({b.vf}, {b.waste[1]})")
    c = rdm.do_gcd(b, f, "Verfire", ev=True)
    expect(c.vf == 0 and abs(c.black - (b.black + 0.75 * 5 + 0.25 * 2)) < 1e-9, "Verfire at 75%: the mixture's mana, the proc gone")
    d = rdm.do_ogcd(s, f, "Acceleration")
    d = rdm.do_gcd(d, f, "Veraero III", ev=True)
    expect(d.dc > d.t and d.accel < d.t and d.vs == 1.0, "under Dualcast and Acceleration: Acceleration is spent, Dualcast kept, a sure proc")
    g = Fight(until=60, away=[Move(10, 12, 2.0)])
    s = rdm.State.initial(g); s.first = False; s.black = s.white = 60.0; s.t = s.gcd = 10.5
    expect(rdm.do_gcd(s, g, "Enchanted Riposte", ev=True) is None, "no melee combo at a far spot")
    m = rdm.do_ogcd(s, g, "Manafication")
    expect(m is not None and rdm.do_gcd(m, g, "Enchanted Riposte", ev=True) is not None, "...unless Manafication extends its reach")
    expect(rdm.do_ogcd(m, g, "Engagement") is None, "Engagement never reaches from there")
    print("\nRed Mage: dashes")
    h = Fight(until=60, moves=[Move(10, 15, 4.0, dash=(("in", 0.0, 6.0),)), Move(20, 30, 4.0, dash=(("out", 3.0, 18.0),))])
    s = rdm.State.initial(h); s.first = False; s.t, s.gcd, s.free = 9.0, 10.8, 9.0
    c = rdm.do_ogcd(s, h, "Corps-a-Corps")
    expect(c.history()[-1][0] == 10 and abs(c.acc - 1.0) < 1e-9, f"Corps-a-corps waits for the run to open and saves its 6 y "
                                                                  f"({c.history()[-1][0]} s, {c.acc:.2f} s banked)")
    s.t, s.gcd, s.free = 12.0, 13.0, 9.0
    c = rdm.do_ogcd(s, h, "Corps-a-Corps")
    expect(c is not None and c.acc == 0, f"2 s into the run (12 y behind: free time counts as run), it saves nothing ({c.acc:.2f} s)")
    s.t, s.gcd, s.free = 20.2, 22.0, 20.0
    expect(rdm.do_ogcd(s, h, "Displacement") is None, "Displacement only once the 3 y before its stretch are behind")
    s.t, s.gcd, s.free = 21.0, 23.0, 20.0
    d = rdm.do_ogcd(s, h, "Displacement")
    expect(abs(d.acc - 2.5) < 1e-9, f"1 s in (6 y behind), its 15 y backstep saves 2.5 s of the 15 y left ({d.acc:.2f})")
    s2 = rdm.State.initial(Fight(until=60, moves=[Move(20, 30, 2.0, dash=(("out", 0.0, 9.0),))])); s2.first = False
    s2.t, s2.gcd, s2.free = 21.0, 23.0, 21.0
    e = rdm.do_ogcd(s2, Fight(until=60, moves=[Move(20, 30, 2.0, dash=(("out", 0.0, 9.0),))]), "Displacement")
    expect(abs(e.acc - 0.5) < 1e-9, f"a 9 y stretch: the backstep overshoots 6 y and walks back, saving 3 y ({e.acc:.2f} s)")
    f = Fight(until=60, moves=[Move(10, 15, 4.0, dash=(("in", 0.0, 6.0),))], away=[Move(9.3, 10.7, 1.4)])
    s = rdm.State.initial(f); s.first = False; s.t, s.gcd, s.free = 9.4, 11.5, 9.4
    s.cds["Corps-a-Corps"] = (1, None)
    c = rdm.do_ogcd(s, f, "Corps-a-Corps")
    expect(c is not None and c.history()[-1][0] == 10, "at a far spot, Corps-a-corps waits for the snapshot (the bait), then dashes")
    s.t = 9.5; s.gcd = 9.9
    expect(rdm.do_ogcd(s, f, "Corps-a-Corps") is None, "...and can't be used before it")


def far_hits(state, fight):
    """Melee actions inside a far spot's stretch out of reach, not under Manafication, nor after a Corps-a-corps that
    brought the player back once the spot's snapshot (the stretch's middle) was past."""
    h = state.history()
    back = lambda w, t: any(n == "Corps-a-Corps" and (w.lo + w.hi) / 2 - 1e-9 <= c <= t for c, n, _ in h)
    return [f"{name} at {t:.2f}" for t, name, note in h if name in rdm.MELEE_ACTIONS and "Mfic" not in note
            and any(w.lo < t < w.hi and not back(w, t) for w in fight.away)]


def dash_faults(state, fight):
    """Dashes that save more running than the window's stretch of their kind allows: a gap closer the stretch, a
    backstep its length or the stretch."""
    out = []
    for t, name, note in state.history():
        d = re.search(r"dash ([\d.]+)s", note)
        if not d: continue
        kind, dist = rdm.DASHES[name]
        w = next((w for w in fight.moves if w.lo <= t < w.hi), None)
        cap = max((min(length, dist or length) / engine.RUN for k, _, length in (w.dash if w else ()) if k == kind), default=0)
        if float(d[1]) > cap + 0.01: out.append(f"{name} at {t:.2f} saves {d[1]} s, at most {cap:.2f}")
    return out


def rdm_searches(width=200):
    print(f"\nRed Mage searches (width {width}) replayed")
    rdm.SPEED = 2.50 / engine.BASE_GCD
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    for slot, var in [("R1", {}), ("R2", {m: v[0] for m, v in alt.items()})]:
        f = p12s.fight(slot, var, far_spots=True)
        s = engine.beam(rdm, f, width=width)
        short, away, hard = replay(s, f)
        bad = far_hits(s, f) + dash_faults(s, f)
        dashes = sum(1 for _, _, note in s.history() if "dash " in note)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not short and not away and not bad, f"{label}: {sum(1 for w in f.moves if w.need)} windows, {len(f.away)} far spots, "
                                                   f"{hard} hard casts, {dashes} dashes, {s.dmg:,.0f} potency" + "".join(f"\n          {x}" for x in short + away + bad))
    still = engine.beam(rdm, p12s.fight("R1", still=True), width=width)
    short, _, _ = replay(still, p12s.fight("R1"))
    expect(bool(short), f"control: the standing-still rotation breaks {len(short)} of the R1 windows")


if __name__ == "__main__":
    stand_cases()
    searches()
    reach_cases()
    melee_searches()
    melee_searches(mnk, 2.43)
    melee_searches(drg, 2.49)
    melee_searches(vpr, 2.49)
    bard_cases()
    bard_searches()
    rdm_cases()
    rdm_searches()
    print("\n" + ("all checks passed" if not fails else f"{len(fails)} FAILED"))
    sys.exit(1 if fails else 0)
