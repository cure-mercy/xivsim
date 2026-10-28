# Tests

Two kinds of check live here, both run by `tests/run.py`: probes that play the drill site's real-time drills in
headless Chrome with solvers that act as a player would, and the blame suite, which checks the scorecard's mistake
classifier (`tools/scorecard/`, see [its README](../tools/scorecard/README.md)) against pulls checked by hand.

```
python tests/run.py                  every suite
python tests/run.py superchain undo  only these
PROBE_SEED=N python tests/run.py     the same pulls as the run that printed seed N
```

After a drill change, run that drill's suite and `undo`; after a classifier or wipe-rule change, run `blame` (below).

## Suites

| Suite | What it checks |
|---|---|
| `para1`, `engrave`, `superchain`, `para3` | real-time solvers: the right play clears, each kind of mistake fails as it should |
| `undo` | step by step: undo and redo give back exactly the page they should |
| `blame` | the scorecard's mistake classifier against hand-checked pulls (`tests/blame.py`; see below) |

## How a run works

`run.py` builds probe pages from the real `index.html` (slot, drill and pace set in localStorage) into a folder of its
own, `tests/out/run-*/` (git-ignored; removed after a clean run, kept after a failing one so the pages can be opened),
adds `tests/solvers/common.js` and the suite's solvers, and plays each page in headless Chrome with virtual time
(`--virtual-time-budget`, `--dump-dom`). Chrome is looked for on the usual paths; `CHROME` overrides it. The run exits 1
on a solver crash, a page error, a missing log (the solver did not finish within its budget) or any `FAIL` line.

Superchain I's and Paradeigma III's solvers read the pull from inside the drill: `SC_HOOK` / `P3_HOOK` splice a
`window.__sc` / `window.__p3` hook into a copy of the drill's script (`*.dbg.js`), and the run stops with an assertion
if the hook point in the drill has moved.

Pages start longest first, by `tests/out/times.json` (each page's seconds from earlier runs). Python suites
(`PY_SUITES`, currently `blame`) need no Chrome and run on a thread beside it.

**Seeds.** Every page's `Math.random` is seeded before its scripts load, and `js/core.js` seeds every pull from it. The
run prints `seed N` first; `PROBE_SEED=N python tests/run.py` plays the same pulls again byte for byte. This is also
how to prove a solver or runner change changes nothing: run it with the previous run's seed and compare the logs.

**Speed.** A full run takes about a minute on a 6-core desktop. Four headless Chromes at once already saturate six
cores (measured before the longest-first order: 4, 6 and 8 workers took 107, 123 and 149 s), so the runner uses four,
and two runs from different sessions at once slow each other the same way. The cost is the pages' own JavaScript, not
virtual time or Chrome's start-up (0.35 s a page). `undo-para1` is the critical path: its solver is busy, CPU-bound, so
virtual time advances at real speed, hence the undo pages' 600 s budgets. Its 20 px click grid must stay that fine:
step 1 passes on only about five points (a 25 px radius), and a coarser grid would miss them.

A `steady` suite (an arena-movement monitor at 800 and 1400 px windows) was removed: it forced a layout every 50 ms and
took 37% of the whole suite's CPU, more than the regressions it guarded against were worth. What keeps the arena
still now is the drills' timed layout (`p1-timed` and the like) with a fixed number of cast-bar slots (`st.castSlots`).

## Adding a probe

A new solver goes in `tests/solvers/<name>.js` and a page entry in `SUITES` in `run.py`: (page name, drill dict, slot,
solvers, probe settings, virtual-time budget in ms). The settings reach the page as `window.__probe`. A new real-time
drill gets both a solver suite and `undo` entries, with the layers its snapshots skip (as `UNDO_PARA3`). If the solver
needs the drill's internals, add a hook like `P3_HOOK` rather than copying logic into the solver.

## Blame suite: the scorecard's mistake classifier

`python tests/run.py blame` (or `python tests/blame.py run [--known]`) runs the hand-checked pulls in
`tests/blame_cases.json` through `tools/scorecard/classifier.py` and the wipe rules (`scorecard.wipe_of`). It fails when
any hand-checked verdict changes: an incident's culprits, fallout, shares, cause text or saved mark, or a pull's wipe
(its culprits, shares or label); it also checks the rule book's dates. A verdict the classifier is known to get wrong
is recorded with the right answer and counted as known; `--known` lists them, and a fix shows as FIXED, meaning the
case's `known` can go. The suite needs no Chrome, but it needs the scorecard's report caches
(`tools/scorecard/.cache/`) and the cases file, which names players and so is git-ignored like `site/data.json`. The
case fields (`known`, `wipe_known`, `rules_day`, `own_day`, `shares`, `wipe_shares`, `cause_has`, `cause_lacks`,
`wipe_label`, `saved`, `note`) are described in `tests/blame.py`'s docstring.

The suite holds 100 pulls (1,109 incidents, 92 wipes put on someone; counted 2026-10-28). One wipe is known
wrong: a Superchain I laser aimed before its Strong Soul ran, which the rules can't see because they only read
positions at the hit.

**After a classifier or wipe-rule change**, run the suite, then `python tools/scorecard/blame_diff.py` to see everything
the change moved over all cached pulls, against `--rev` (default HEAD) or `--old-dir` copies. Read the FAIL and FIXED
lines together with blame_diff's totals: a fix in one mechanic can move counts in another.

**Adding cases.** Every new rule gets cases that exercise it. `python tests/blame.py add CODE FIGHT "WHY" [--own-day]`
appends a pull with the classifier's current verdicts; check each against `python tests/blame.py show CODE FIGHT`
before keeping the case. The hand corrections are kept in the git-ignored `scratch/blame/handcheck.py`, which
re-applies them over `add` drafts and rewrites the cases file.

**Is every rule guarded?** `scratch/blame/mutate.py [NAME]` (git-ignored) turns the rules off one at a time, in memory:
it rewrites a classifier or scorecard function's source, and rule-book entries that hold the function get the new one
too. It then runs the suite, which must FAIL for each mutant; a surviving mutant means no case exercises that rule. So
far the survivors are rules no cached pull reaches, such as `CAMPS_APART`, a laser hit at its very edge, or a lone
death whose next step kills two or more. Built pulls are kept per process (`blame.BUILT`) and only the light parties
are inferred again, so 83 mutants take about 50 s instead of 335 s; a mutant that changes `Pull.__init__` or
`blame_diff.pulls` needs `blame.BUILT.clear()` first. Piped output only appears when the run exits.

The suite doesn't check confidence levels, and its pulls were used to fix the rules, so passing it says nothing about
accuracy. For that, see the held-out measurement under Confidence in the
[scorecard's README](../tools/scorecard/README.md#how-mistakes-are-attributed).
