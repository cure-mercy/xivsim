"""Checks the optimizer's movement and downtime handling, independently of the search.

    python tools/rotation/check.py

1. engine.stand on hand-made move windows: a cast that leaves too little running time is refused; a cast the run can
   still follow keeps the player on their spot (Ley Lines); one that only fits if the run started first takes them off.
2. Quick searches (one heuristic, narrow beam) for both Paradeigma I slots and every variant of the other mechanics;
   each rotation is replayed from its printed history: every move window must get its running time outside cast bars
   (up to the slide point), and nothing may be cast at Athena while she is away.
Exits non-zero on any failure.
"""
import itertools, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine, p12s                              # noqa: E402
from engine import Fight, Move, SLIDE            # noqa: E402
from jobs import blm                             # noqa: E402

HARM = {"Fire III", "Fire IV", "Despair", "Paradox", "Blizzard III", "Blizzard IV", "Thunder III", "Xenoglossy"}
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
    """Cast bars and casts from a rotation's history; cast times are in its notes."""
    busy, casts = [], []
    for t, name, note in state.history():
        m = re.match(r"\s*([\d.]+)s cast", note)
        casts.append((t, name))
        if m: busy.append((t, t + float(m[1]) - SLIDE))
    short = []
    for w in fight.moves:
        if not w.need: continue
        free = (w.hi - w.lo) - sum(max(0, min(b, w.hi) - max(a, w.lo)) for a, b in busy)
        if free < w.need - 1e-6: short.append(f"{w.lo:.1f}-{w.hi:.1f}s free {free:.2f} < {w.need:.2f}: {w.why}")
    away = [f"{name} at {t:.2f}" for t, name in casts if name in HARM and not fight.targetable(t)]
    return short, away, len(busy)


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


if __name__ == "__main__":
    stand_cases()
    searches()
    print("\n" + ("all checks passed" if not fails else f"{len(fails)} FAILED"))
    sys.exit(1 if fails else 0)
