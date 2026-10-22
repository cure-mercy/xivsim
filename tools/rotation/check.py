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
6. Pictomancer: Inspiration's haste and stacks, the landscape after a long run and a short one, the shared Aetherhues
   step, Monochrome Tones, motifs while Athena is away and the capped muse charges on hand-made states; then quick
   searches for R1 and R2 replayed as in 2, plus no inspired GCD after a run past the landscape since Starry Muse.
7. Machinist: heat and Hypercharge, Barrel Stabilizer, Blazing Shot's recast and cuts, Wildfire's count, the queen's
   battery, downtime and redeploy, the pre-pull Reassemble and Drill's skill-speed recast on hand-made states; then
   quick searches for R1 and R2 replayed as for the Bard.
8. Ninja: mudra charges, Kassatsu, Ten Chi Jin, Raiju Ready, Bunshin, Meisui, Trick Attack's window, Kazematoi and
   mudras while Athena is away on hand-made states; then the melee searches of 3.
Exits non-zero on any failure.
"""
import dataclasses, itertools, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine, p12s                              # noqa: E402
from engine import Fight, Move, SLIDE            # noqa: E402
from jobs import blm, brd, drg, mch, mnk, nin, pct, rdm, rpr, sam, smn, vpr    # noqa: E402

HARM = {"Fire III", "Fire IV", "Despair", "Paradox", "Blizzard III", "Blizzard IV", "Thunder III", "Xenoglossy"}
HARM |= (set(rpr.GCDS) - {"Soulsow"}) | rpr.AVATAR | {"Gluttony", "Lemure's Slice"}
HARM |= mnk.HARM_GCDS | {"The Forbidden Chakra", "Enlightenment"}
HARM |= set(brd.POTENCY) | {"Apex Arrow", "Pitch Perfect"}
HARM |= set(drg.POTENCY)
HARM |= set(rdm.POTENCY)
HARM |= set(vpr.POTENCY)
HARM |= set(sam.POTENCY)
HARM |= set(pct.POTENCY)
HARM |= set(mch.POTENCY) | {"Wildfire"}
HARM |= set(nin.POTENCY)
HARM |= set(smn.POTENCY) | set(smn.DEMIS) | set(smn.PRIMALS) | {"Enkindle Bahamut", "Enkindle Phoenix"}
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
    """Cast bars and casts from a rotation's history; cast times are in its notes, the time a player stands still
    without a cast bar (Samurai's Meditate) and the running a dash saved (Red Mage) too."""
    busy, casts, dashed = [], [], []
    for t, name, note in state.history():
        m = re.match(r"\s*([\d.]+)s cast", note)
        casts.append((t, name))
        if m: busy.append((t, t + float(m[1]) - SLIDE))
        m = re.match(r"\s*stand ([\d.]+)s", note)
        if m: busy.append((t, t + float(m[1])))
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


def melee_searches(job=rpr, gcd=2.49, width=200, control=True):
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
    if not control: return                      # (the Ninja's is nin_control)
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


def pct_cases():
    print("\nPictomancer: Inspiration, the landscape, the colour steps, Comet, motifs, capped charges")
    pct.SPEED = 0.98
    f = Fight(until=60)
    s = pct.State.initial(f); s.first = False; s.t = s.gcd = 1.0
    m = pct.do_ogcd(s, f, "Starry Muse")
    a = pct.do_gcd(m, f, "Fire in Red")
    t, _, note = a.history()[-1]
    expect("insp" in note and a.hyper == 4 and abs(a.gcd - t - 2.45 * 0.75) < 0.01,
           f"after Starry Muse, Fire in Red is inspired: a stack spent, a 25% shorter recast ({a.gcd - t:.2f} s)")
    h = pct.do_gcd(pct.do_ogcd(a, f, "Striking Muse"), f, "Hammer Stamp")
    expect(h.hyper == 4 and abs(h.gcd - h.history()[-1][0] - 2.45) < 0.01, "a hammer takes no stack and no haste")
    b = pct.do_ogcd(a, f, "Subtractive Palette")
    expect(b.gauge == 0 and b.spec_until < b.t and b.mono, "Subtractive Palette spends Subtractive Spectrum first, grants Monochrome")
    expect(pct.do_gcd(b, f, "Blizzard in Cyan") is None and pct.do_gcd(b, f, "Stone in Yellow") is not None,
           "after Fire in Red the subtractive step is Stone in Yellow (Aetherhues is shared)")
    c = pct.do_gcd(pct.do_gcd(b, f, "Stone in Yellow"), f, "Thunder in Magenta")
    expect(c.paint == 1 and c.gauge == 0 and c.sp == 1, f"Thunder in Magenta: a White Paint, no gauge ({c.paint}, {c.gauge})")
    expect(pct.do_gcd(c, f, "Holy in White") is None and pct.do_gcd(c, f, "Comet in Black") is not None,
           "under Monochrome Tones the paint goes to Comet in Black, not Holy")
    for yalms, kept in ((15.0, False), (6.0, True)):
        g = Fight(until=60, moves=[Move(10, 14, yalms / engine.RUN)])
        s = pct.State.initial(g); s.first = False; s.t = s.gcd = 1.0
        m = pct.do_ogcd(s, g, "Starry Muse"); m.t = m.gcd = 15.0
        n = pct.do_gcd(m, g, "Fire in Red")
        expect(("insp" in n.history()[-1][2]) == kept, f"a {yalms:.0f} y run after Starry Muse: " +
               ("still in the landscape" if kept else "out of the landscape, no Inspiration"))
    d = Fight(until=60, untargetable=[(10, 30)])
    s = pct.State.initial(d); s.first = False; s.t = s.gcd = 12.0; s.creature = None
    w = pct.do_gcd(s, d, "Wing Motif")
    expect(w is not None and w.creature == "wing" and pct.do_ogcd(w, d, "Winged Muse") is None,
           "a motif is painted while Athena is away; its Muse waits for her")
    s = pct.State.initial(f); s.first = False
    full = sum(pct.VALUE[k] for k in pct.CAPPED.values())
    expect(abs(pct.capped(s, 20.0) - 20 * full) < 1e-6, "every muse full since the pull: 20 s capped each")
    s.t = 20.0; u = pct.do_ogcd(s, f, "Pom Muse")
    expect(abs(pct.capped(u, 30.0) - 20 * pct.VALUE["cap_living"] - 30 * (full - pct.VALUE["cap_living"])) < 1e-6,
           "a Muse used at 20 s stops Living Muse's count; the others go on")


def landscape_faults(state, fight):
    """Inspired GCDs after a run longer than the landscape's radius that lay wholly between Starry Muse and the GCD, and
    Smudges saving more than its 15 y."""
    h = state.history()
    muses = [t for t, n, _ in h if n == "Starry Muse"]
    out = []
    for t, name, note in h:
        if " insp" in note:
            m = max((x for x in muses if x <= t), default=None)
            out += [f"{name} at {t:.2f} inspired after the {w.lo:.1f}-{w.hi:.1f}s run" for w in fight.moves
                    if m is not None and w.need * engine.RUN > pct.LANDSCAPE and w.lo >= m and w.hi <= t]
        d = re.search(r"dash ([\d.]+)s", note)
        if d and float(d[1]) > pct.SMUDGE_Y / engine.RUN + 0.01: out.append(f"{name} at {t:.2f} saves {d[1]} s")
    return out


def pct_searches(width=200):
    print(f"\nPictomancer searches (width {width}) replayed")
    pct.SPEED = 0.98
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    for slot, var in [("R1", {}), ("R2", {m: v[0] for m, v in alt.items()})]:
        f = p12s.fight(slot, var)
        s = engine.beam(pct, f, width=width)
        short, away, hard = replay(s, f)
        bad = landscape_faults(s, f)
        insp = sum(1 for _, _, note in s.history() if " insp" in note)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not short and not away and not bad, f"{label}: {sum(1 for w in f.moves if w.need)} windows, {hard} hard casts, "
                                                   f"{insp} inspired GCDs, {s.dmg:,.0f} potency" + "".join(f"\n          {x}" for x in short + away + bad))
        if slot == "R1": r1, f1 = s, f
    # controls: a standing-still Pictomancer rotation happens to fit our runs (1.5 s casts on a 2.45 s GCD, many
    # instants), so the R1 rotation is replayed against the same runs at twice their length instead, and the
    # standing-still one against R1's runs for the landscape
    double = dataclasses.replace(f1, moves=[dataclasses.replace(w, need=min(2 * w.need, w.hi - w.lo)) for w in f1.moves])
    short, _, _ = replay(r1, double)
    expect(bool(short), f"control: the R1 rotation breaks {len(short)} of the R1 windows at twice their running")
    still = engine.beam(pct, p12s.fight("R1", still=True), width=width)
    bad = landscape_faults(still, f1)
    expect(bool(bad), f"control: the standing-still rotation casts {len(bad)} inspired GCDs that R1's runs take out of the landscape")


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


def mch_cases():
    print("\nMachinist: heat, Hypercharge, Blazing Shot, Wildfire, the queen, Reassemble")
    mch.SPEED = 0.98
    f = Fight(until=120)
    s = mch.State.initial(f); s.first = False; s.ra_until = -1.0
    for g in mch.COMBO: s = mch.do_gcd(s, f, g)
    expect(s.heat == 15 and s.batt == 10 and s.combo == 0, f"a combo gives 15 heat and 10 battery ({s.heat}, {s.batt})")
    expect(mch.do_ogcd(s, f, "Hypercharge") is None, "no Hypercharge below 50 heat")
    h = mch.do_ogcd(mch.do_ogcd(s, f, "Barrel Stabilizer"), f, "Hypercharge")
    expect(h is not None and h.heat == 15 and h.oh == 5, "Barrel Stabilizer's Hypercharged pays for it: five stacks, heat kept")
    g = mch.do_ogcd(h, f, "Gauss Round")
    nxt = mch.charges(g, "Gauss Round", g.t)[1]
    b = mch.do_gcd(g, f, "Blazing Shot")
    expect(abs(mch.charges(b, "Gauss Round", b.t)[1] - (nxt - 15)) < 1e-9 and abs(b.gcd - b.t + mch.ANIM_LOCK - 1.5) < 1e-9,
           "Blazing Shot takes 15 s off Gauss Round and runs on a 1.5 s recast")
    expect(mch.candidates(b, f, b.gcd) == ["Blazing Shot"], "the search plays only Blazing Shot while Overheated")
    w = mch.do_ogcd(b, f, "Wildfire")
    for _ in range(4): w = mch.do_gcd(w, f, "Blazing Shot")
    for g in mch.COMBO: w = mch.do_gcd(w, f, g)
    expect(w.wf_n == 6 and abs(w.dotp - 1440) < 1e-6, f"Wildfire counts six weaponskills, 1,440 as ticks ({w.wf_n}, {w.dotp:,.0f})")
    q = mch.State.initial(f); q.first = False; q.batt = 100; q.t = q.gcd = 10.0; q.auto_next = 1e9
    d0 = q.dmg; q = mch.do_ogcd(q, f, "Automaton Queen")
    expect(abs(q.dmg - d0 - 24.15 * 100) < 1e-6 and q.batt == 0, f"a queen at 100 battery: {q.dmg - d0:,.0f} potency")
    q.batt = 50
    expect(mch.do_ogcd(q, f, "Automaton Queen") is None, "no second queen while the first is out")
    d = Fight(until=120, untargetable=[(20.0, 60.0)])
    q = mch.State.initial(d); q.first = False; q.batt = 50; q.t = q.gcd = 10.0; q.auto_next = 1e9
    d0 = q.dmg; q = mch.do_ogcd(q, d, "Automaton Queen")
    expect(abs(q.dmg - d0 - 2.2 * 3 * 50) < 1e-6, f"a queen running into downtime keeps the three punches before it ({q.dmg - d0:,.0f})")
    r = mch.State.initial(f)
    r = mch.do_gcd(r, f, "Drill")
    expect(abs(r.critp - 620) < 1e-6 and r.ra_until < r.t, "the pre-pull Reassemble makes the first Drill a critical direct hit")
    expect(abs(mch.charges(r, "Drill", 0.0)[1] - 20 * 0.98) < 1e-9, "Drill's recast scales with skill speed (19.6 s)")


def mch_searches(width=200):
    print(f"\nMachinist searches (width {width}) replayed")
    mch.SPEED = 0.98
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    still = engine.sweep(mch, p12s.fight("R1", still=True), width)
    for slot, var in [("R1", {}), ("R2", {m: v[0] for m, v in alt.items()})]:
        f = p12s.fight(slot, var)
        s = engine.sweep(mch, f, width)
        _, away, _ = replay(s, f)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not away and abs(s.dmg - still.dmg) < 1e-6, f"{label}: {s.dmg:,.0f} potency, standing still {still.dmg:,.0f}"
                                                           + "".join(f"\n          {x}" for x in away))


def nin_cases():
    print("\nNinja: mudras, Ten Chi Jin, Raiju, Bunshin, Shadow Walker, debuffs")
    f = Fight(until=200)
    s = nin.State.initial(f)
    expect(nin.charges(s, "Mudra", 0.0) == (1, nin.PREPULL + 20), "the pull opens with one mudra charge used before it")
    s = nin.expand(s, f)[0]; s.auto_next = 1e9         # no auto-attacks in the damage differences below
    expect(s.history()[-1][1] == "Suiton" and s.sw_until > 0, "the search opens on the pre-pull Suiton: Shadow Walker")
    r = nin.chain(s, f, ("Ten", "Chi", "Raiton"))
    expect(nin.charges(r, "Mudra", r.t)[0] == 0 and abs(r.gcd - s.gcd - 2.5) < 1e-9 and r.raiju == 1,
           "Raiton: a charge, two 0.5 s mudras and a 1.5 s ninjutsu, a Raiju Ready")
    expect(nin.do_gcd(r, f, "Ten") is None, "no mudra without a charge")
    k = nin.do_ogcd(r, f, "Kassatsu")
    h = nin.chain(k, f, ("Ten", "Jin", "Hyosho Ranryu"))
    expect(h is not None and nin.charges(h, "Mudra", h.t)[0] == 0 and abs(h.dmg - r.dmg - 1300 * 1.3) < 1e-6,
           "Kassatsu: mudras without a charge, Hyosho Ranryu x1.3")
    w = nin.do_gcd(h, f, "Spinning Edge")
    expect(w.raiju == 0 and w.waste[2] == 1, "a melee weaponskill ends Raiju Ready")
    t = nin.do_ogcd(nin.do_gcd(h, f, "Spinning Edge"), f, "Ten Chi Jin")
    expect(nin.do_gcd(t, f, "Gust Slash") is None, "only ninjutsu under Ten Chi Jin")
    t3 = nin.chain(t, f, nin.TCJ_ORDER)
    gaps = [b[0] - a[0] for a, b in zip(t3.history()[-3:], t3.history()[-2:])]
    expect(all(abs(x - 1.0) < 0.011 for x in gaps) and abs(t3.gcd - t3.history()[-1][0] - 1.5) < 0.011 and t3.sw_until > t3.t and t3.raiju == 1,
           "Ten Chi Jin: Fuma, Raiton, Suiton 1.0 s apart, 1.5 s after the last")
    m = nin.do_ogcd(t3, f, "Meisui", policy=False)
    expect(m.ninki == t3.ninki + 50 and m.sw_until < 0 and nin.do_ogcd(m, f, "Trick Attack") is None,
           "Meisui spends Shadow Walker for 50 Ninki: no Trick Attack after it")
    b = nin.do_ogcd(m, f, "Bunshin")
    d0 = b.dmg; g = nin.do_gcd(b, f, "Fleeting Raiju")
    expect(g.bun == 4 and abs(g.dmg - d0 - 560 - nin.SHADOW) < 1e-6 and g.ninki == b.ninki + 10,
           "Bunshin: Fleeting Raiju's shadow copies it (148) for 5 more Ninki")
    p = nin.do_gcd(g, f, "Phantom Kamaitachi")
    expect(p.bun == 4 and p.pk_until < 0, "Phantom Kamaitachi takes no Bunshin stack")
    q = nin.State.initial(f); q.first = False; q.t = q.gcd = 10.0; q.sw_until = 20.0; q.auto_next = 1e9
    a = nin.do_ogcd(q, f, "Trick Attack")
    expect(abs(nin.mult(a, f, 10.8) - 1.10) < 1e-9 and nin.mult(a, f, 10.7) == 1.0 and nin.mult(a, f, 25.9) == 1.0,
           "Trick Attack: +10% on hits executed from its own landing (10.8 s) for 15 s")
    c = nin.State.initial(f); c.first = False; c.t = c.gcd = 10.0; c.auto_next = 1e9
    c = nin.chain(c, f, ("Spinning Edge", "Gust Slash", "Armor Crush", "Spinning Edge", "Gust Slash"))
    d0 = c.dmg; c = nin.do_gcd(c, f, "Aeolian Edge")
    expect(c.kaz == 1 and abs(c.dmg - d0 - 480) < 1e-6, "Armor Crush gives two Kazematoi; Aeolian Edge spends one for +100")
    dn = Fight(until=60, untargetable=[(20, 30)])
    z = nin.State.initial(dn); z.first = False; z.t = z.gcd = 21.0; z.seq = (); z.cds["Mudra"] = (2, None)
    out = [nin.chain(w, dn, ("Ten", "Chi", "Jin", "Suiton")) for w in nin.expand(z, dn)]
    expect(any(o is not None and o.history()[-1][0] == 30.0 for o in out), "mudras while Athena is away: Suiton as she returns")


def nin_control(width=200):
    """A Ninja's mudras and ninjutsu leave 2.5-4 s without a melee action, so a standing-still rotation can fit the
    away windows by chance (the melee control above finds it breaks none); against the same windows twice as long, it
    has to break some, and the M1 search must not."""
    nin.SPEED = 0.984
    f = p12s.fight("M1")
    f2 = dataclasses.replace(f, away=[dataclasses.replace(w, need=2 * w.need) for w in f.away])
    still = engine.beam(nin, p12s.fight("M1", still=True), width=width)
    s2 = engine.beam(nin, f2, width=width)
    bad, bad2 = gaps(still, f2, nin), gaps(s2, f2, nin)
    expect(bool(bad) and not bad2, f"control: against M1's away windows at twice their length the standing-still rotation"
                                   f" breaks {len(bad)}, the search for them {len(bad2)} ({s2.dmg:,.0f} potency)")


def smn_cases():
    print("\nSummoner: demi-summons and pets, primals and attunement, favors, Aetherflow, Searing Light, Crimson Strike's reach")
    smn.SPEED = 0.98
    f = Fight(until=200)
    s = smn.State.initial(f)
    s = smn.do_gcd(s, f, "Ruin III")
    expect(s.history()[-1][0] < 0 and smn.candidates(s, f, s.gcd) and smn.do_gcd(s, f, "Astral Impulse") is None,
           "the opener is a pre-cast Ruin III; no Astral Impulse before a trance")
    d0 = s.dmg; b = smn.do_gcd(s, f, "Summon Bahamut")
    expect(abs(b.dmg - d0 - 4 * 119) < 1e-6 and len(b.arc) == 3, "Summon Bahamut: four Wyrmwaves booked, three Arcanum")
    expect(smn.candidates(b, f, b.gcd) == ["Astral Impulse"] and smn.do_gcd(b, f, "Summon Titan II") is None,
           "in the trance only Astral Impulse; no primal until it ends")
    e = smn.do_ogcd(b, f, "Enkindle Bahamut")
    t0 = b.history()[-1][0]
    expect(abs(e.dmg - b.dmg - 1030) < 1e-6 and smn.do_ogcd(e, f, "Enkindle Bahamut") is None,
           "Enkindle Bahamut: Akh Morn once a trance")
    x = b
    while smn.in_trance(x, max(x.t, x.gcd)): x = smn.do_gcd(x, f, "Astral Impulse")
    n = sum(1 for _, a, _ in x.history() if a == "Astral Impulse")
    expect(n == 6 and smn.do_gcd(x, f, "Astral Impulse") is None, f"six Astral Impulses in the 15 s trance at a 2.45 s GCD ({n})")
    expect(abs(smn.charges(x, "Demi", x.t)[1] - (t0 + 60 * 0.98)) < 1e-9 and smn.do_gcd(x, f, "Summon Phoenix") is None,
           "the next demi is Summon Phoenix, 58.8 s after (spell speed)")
    t = smn.do_gcd(x, f, "Summon Titan II")
    r = smn.do_gcd(t, f, "Topaz Rite")
    expect(r.mb and r.stacks == 3 and smn.do_ogcd(r, f, "Mountain Buster") is not None, "Topaz Rite: Titan's Favor for a Mountain Buster")
    r2 = smn.do_gcd(r, f, "Topaz Rite")
    expect(r2.waste[2] == 1, "a second Topaz Rite over an unspent Titan's Favor loses it")
    g = smn.do_gcd(r, f, "Summon Garuda II")
    expect(g.att == "emerald" and g.stacks == 4 and g.waste[1] == 3 and g.favor == "garuda" and not g.mb,
           "a primal over three Topaz stacks: lost, with Titan's Favor; Garuda's Favor and four Emerald stacks")
    em = smn.do_gcd(g, f, "Emerald Rite")
    expect(abs(em.gcd - em.history()[-1][0] - 1.5) < 1e-9, "Emerald Rite: a fixed 1.5 s recast")
    d0 = em.dmg; sl = smn.do_gcd(em, f, "Slipstream")
    expect(abs(sl.dmg - d0 - 430 - 6 * 30) < 1e-6 and abs(sl.dotp - 180) < 1e-6 and sl.favor is None,
           "Slipstream: 430 and six 30-potency windstorm ticks")
    i = smn.do_gcd(sl, f, "Summon Ifrit II")
    c = smn.do_gcd(i, f, "Crimson Cyclone")
    expect(c.csr and c.favor is None and smn.do_gcd(c, f, "Crimson Strike") is not None, "Ifrit's Favor: Crimson Cyclone, then Crimson Strike")
    ed = smn.do_ogcd(i, f, "Energy Drain")
    expect(ed.af == 2 and smn.further_ruin(ed, ed.t), "Energy Drain: two Aetherflow, Further Ruin")
    l = smn.do_ogcd(i, f, "Searing Light")
    d0 = l.dmg; l2 = smn.do_gcd(l, f, "Ruby Rite")
    expect(abs(l2.dmg - d0 - 510 * 1.05) < 1e-6, "Searing Light: +5% on the Summoner's own hits")
    dn = Fight(until=200, untargetable=[(20.0, 60.0)])
    z = smn.State.initial(dn); z.first = False; z.t = z.gcd = 10.0
    d0 = z.dmg; z = smn.do_gcd(z, dn, "Summon Bahamut")
    expect(abs(z.dmg - d0 - 2 * 119) < 1e-6, "a demi summoned 10 s before Athena leaves: two Wyrmwaves land")
    a = Fight(until=200, away=[Move(30, 40, 4.0)])
    y = smn.State.initial(a); y.first = False; y.favor = "ifrit"; y.t = y.gcd = 31.0
    expect(smn.do_gcd(y, a, "Crimson Cyclone") is None, "no Crimson Cyclone off a far spot before its snapshot")
    y.t = y.gcd = 36.0; y = smn.do_gcd(y, a, "Crimson Cyclone")
    expect(y is not None and smn.do_gcd(y, a, "Crimson Strike") is not None, "after the snapshot it brings the player back: Crimson Strike")
    w = smn.State.initial(a); w.first = False; w.csr = True; w.t = w.gcd = 36.5; w.mlast = 33.0
    expect(smn.do_gcd(w, a, "Crimson Strike") is None, "no Crimson Strike that leaves a far spot's 4 s stretch no room (3.5 s each side)")


def smn_faults(state, fight):
    """Crimson Strikes inside a far spot's stretch out of reach not brought back by a Crimson Cyclone after the spot's
    snapshot, and Crimson Cyclones saving more running than the window's stretch toward Athena."""
    h, out = state.history(), []
    back = lambda w, t: any(n == "Crimson Cyclone" and (w.lo + w.hi) / 2 - 1e-9 <= c <= t for c, n, _ in h)
    out += [f"{name} at {t:.2f}" for t, name, _ in h if name in smn.MELEE_ACTIONS
            and any(w.lo < t < w.hi and not back(w, t) for w in fight.away)]
    for t, name, note in h:
        d = re.search(r"dash ([\d.]+)s", note)
        w = next((w for w in fight.moves if w.lo <= t < w.hi), None)
        cap = max((length / engine.RUN for k, _, length in (w.dash if w else ()) if k == "in"), default=0)
        if d and float(d[1]) > cap + 0.01: out.append(f"{name} at {t:.2f} saves {d[1]} s, at most {cap:.2f}")
    return out


def smn_searches(width=200):
    print(f"\nSummoner searches (width {width}) replayed")
    smn.SPEED = 0.98
    alt = {m: [v for v in vs if v != p12s.DEFAULT_VAR[m]] for m, vs in p12s.PLAN.items() if m in p12s.DEFAULT_VAR}
    for slot, var in [("R1", {}), ("R2", {m: v[0] for m, v in alt.items()})]:
        f = p12s.fight(slot, var, far_spots=True)
        s = engine.sweep(smn, f, width)
        short, away, hard = replay(s, f)
        bad = smn_faults(s, f)
        dashes = sum(1 for _, _, note in s.history() if "dash " in note)
        label = f"{slot}" + "".join(f", {v}" for v in var.values())
        expect(not short and not away and not bad, f"{label}: {sum(1 for w in f.moves if w.need)} windows, {len(f.away)} far spots, "
                                                   f"{hard} hard casts, {dashes} dashes, {s.dmg:,.0f} potency" + "".join(f"\n          {x}" for x in short + away + bad))
        if slot == "R1": r1, f1 = s, f
    # control (as Pictomancer's): a Summoner has so many instants that the R1 rotation is replayed against its runs at
    # twice their length, which it must break
    double = dataclasses.replace(f1, moves=[dataclasses.replace(w, need=min(2 * w.need, w.hi - w.lo)) for w in f1.moves])
    short, _, _ = replay(r1, double)
    expect(bool(short), f"control: the R1 rotation breaks {len(short)} of the R1 windows at twice their running")


if __name__ == "__main__":
    stand_cases()
    searches()
    reach_cases()
    melee_searches()
    melee_searches(mnk, 2.43)
    melee_searches(drg, 2.49)
    melee_searches(vpr, 2.49)
    melee_searches(sam, 2.40)
    bard_cases()
    bard_searches()
    rdm_cases()
    rdm_searches()
    pct_cases()
    pct_searches()
    mch_cases()
    mch_searches()
    nin_cases()
    melee_searches(nin, 2.46, control=False)
    nin_control()
    smn_cases()
    smn_searches()
    print("\n" + ("all checks passed" if not fails else f"{len(fails)} FAILED"))
    sys.exit(1 if fails else 0)
