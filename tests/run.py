"""Plays the trainer's drills in headless Chrome and prints what happened.

Each suite builds probe pages from the real index.html (with the slot, the drill and its pace set in
localStorage), adds solvers from tests/solvers/ that play the drill the way a player would, runs them with
Chrome's virtual time, and prints each page's log: the verdict of every pull, the recaps the drill showed,
and any script errors.

    python tests/run.py                  every suite
    python tests/run.py superchain undo  only these
    PROBE_SEED=N python tests/run.py     the same pulls as the run that printed seed N

Suites:
    para1, engrave, superchain, para3
                                real-time solvers: the right play clears, each kind of mistake fails as it should
    undo                        step by step: undo and redo give back exactly the page they should
    blame                       the scorecard's mistake classifier against pulls checked by hand (tests/blame.py; no
                                Chrome, needs the scorecard's caches and the git-ignored tests/blame_cases.json)

Chrome is looked for on the usual paths (only when a drill suite runs); set CHROME to its executable to choose one.
Each run writes its probe pages to a folder of its own in tests/out/ (git-ignored), so runs from two sessions don't
clash: removed after a clean run, kept after a failing one. The pages start longest first, by the times of earlier
runs (tests/out/times.json); more than four Chromes at once only slows each down. Every page draws its pulls from a
seeded Math.random, the seed printed first. Exits non-zero if a solver crashed, the page threw an error or a check
logged FAIL.
"""
import html, json, os, random, re, shutil, subprocess, sys, tempfile, time, zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests' / 'out'
TIMES = OUT / 'times.json'

# Superchain's solver reads the pull from inside the drill, through a hook added to a copy of its script.
SC_HOOK = ("    const newRound = T.trackRounds('superchain', startRound);",
           "    window.__sc = { st: () => st, spotFirst, spotLaser, spotLast, spotTowers, towerSpot, CPOS };\n")
# and so does Paradeigma III's
P3_HOOK = ("    const newRound = T.trackRounds('para3', startRound);",
           "    window.__p3 = { st: () => st, plan, LIVE, supTowerSpot, plainTower, centreCorner, dpsKey,\n"
           "      dropSpot: (role, t) => mx(PLAN.drop[role][t.row]), baitSpotOf: id => baitSpot(st.actors[id]), soakSpotOf: id => soakSpot(st.actors[id]),\n"
           "      inPlus, inSaltire, MARK_NEAR };\n")

PARA1 = dict(tab='para1', pace='twelfth-p1-pace', panel='panel-para1', clock='p1-clock')
ENGRAVE = dict(tab='engrave', pace='twelfth-eg-pace', panel='panel-engrave', clock='eg-clock')
SUPERCHAIN = dict(tab='superchain', pace='twelfth-sc-pace', panel='panel-superchain', clock='sc-clock')
PARA3 = dict(tab='para3', pace='twelfth-p3-pace', panel='panel-para3', clock='p3-clock')

# what the undo snapshots leave out: layers of passing effects, and a class that only animates
UNDO_ENGRAVE = {'pace': 'steps', 'skip': ['eg-lasers', 'eg-fx', 'eg-debuffBadge'], 'strip': ['eg-untilted']}
UNDO_SUPERCHAIN = {'pace': 'steps', 'skip': ['sc-beams', 'sc-fx']}
UNDO_PARA3 = {'pace': 'steps', 'skip': ['p3-lasers', 'p3-fx']}
WINDOW = '1400,1000'

# suite -> pages: (page name, drill, slot, solvers, probe settings, virtual time budget in ms). The settings
# reach the page as window.__probe; `pace` (default live) is also used here. The undo solvers are busy rather than
# waiting, which spends virtual time at the pace of real time: their budget leaves room for a loaded machine.
SUITES = {
    'para1': [(f'para1-{s}', PARA1, s, 'para1', {}, 250_000) for s in ['R1', 'R2', 'T1', 'H2']],
    'engrave': [(f'engrave-{s}', ENGRAVE, s, 'engrave', {}, 1_600_000) for s in ['H1', 'M2']],
    'superchain': [(f'superchain-{s}', SUPERCHAIN, s, 'superchain', {}, 500_000) for s in ['T1', 'H2', 'M1', 'R2']],
    'para3': [(f'para3-{s}', PARA3, s, 'para3', {}, 900_000) for s in ['H1', 'T2', 'M1']],
    'undo': [(f'undo-para1-{s}', PARA1, s, 'para1-undo', {'pace': 'steps'}, 600_000) for s in ['T1', 'R2']]
          + [(f'undo-engrave-{s}', ENGRAVE, s, 'undo', UNDO_ENGRAVE, 600_000) for s in ['H1', 'M1']]
          + [(f'undo-superchain-{s}', SUPERCHAIN, s, 'undo', UNDO_SUPERCHAIN, 600_000) for s in ['T1', 'R2']]
          + [(f'undo-para3-{s}', PARA3, s, 'undo', UNDO_PARA3, 600_000) for s in ['H2', 'M1']],
}
# suites run in Python, not in Chrome: name -> run() returning (log, failed)
PY_SUITES = {'blame': lambda: __import__('blame').run()}

# Math.random seeded before the page's scripts load: core.js seeds every pull from it, so a seed gives back the pulls
SEEDED = ("(()=>{let s=%d;Math.random=()=>{let t=(s=(s+0x6D2B79F5)>>>0);t=Math.imul(t^(t>>>15),t|1);"
          "t^=t+Math.imul(t^(t>>>7),t|61);return((t^(t>>>14))>>>0)/4294967296;};})();")


def find_chrome():
    if os.environ.get('CHROME'):
        return os.environ['CHROME']
    for p in [r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']:
        if os.path.exists(p):
            return p
    for name in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']:
        if shutil.which(name):
            return shutil.which(name)
    sys.exit('Chrome not found: set CHROME to its executable.')


def build(run_dir, seed, name, drill, slot, solvers, extra):
    page = (ROOT / 'index.html').read_text(encoding='utf-8')
    rel = run_dir.relative_to(ROOT).as_posix()
    for d, script, hook in ((SUPERCHAIN, 'superchain-1', SC_HOOK), (PARA3, 'paradeigma-3', P3_HOOK)):
        if drill is not d: continue
        src = (ROOT / 'mechanics' / f'{script}.js').read_text(encoding='utf-8')
        assert hook[0] in src, f'the hook point in {script}.js has moved'
        (run_dir / f'{script}.dbg.js').write_text(src.replace(hook[0], hook[1] + hook[0]), encoding='utf-8')
        page = page.replace(f'<script src="mechanics/{script}.js">', f'<script src="{rel}/{script}.dbg.js">')
    probe = dict(extra, slot=slot, panel=drill['panel'], clock=drill['clock'])
    pace = extra.get('pace', 'live')
    setup = ('<base href="../../../">'
             "<script>window.__errors=[];window.addEventListener('error',e=>window.__errors.push(e.message+' @'+(e.filename||'').split('/').pop()+':'+e.lineno));"
             + SEEDED % (seed ^ zlib.crc32(name.encode())) +
             f"window.__probe={json.dumps(probe)};"
             f"try{{localStorage.clear();localStorage.setItem('twelfth-tab','{drill['tab']}');localStorage.setItem('twelfth-slot','{slot}');"
             f"localStorage.setItem('{drill['pace']}','{pace}');}}catch(e){{}}</script>")
    solvers = [solvers] if isinstance(solvers, str) else solvers
    solve = ''.join(f'<script src="tests/solvers/{s}.js"></script>' for s in ['common'] + solvers)
    assert '<head>' in page and '</body>' in page
    path = run_dir / f'{name}.html'
    path.write_text(page.replace('<head>', '<head>' + setup, 1).replace('</body>', solve + '</body>', 1), encoding='utf-8')
    return path


def play(chrome, path, budget):
    """The page's log, and the seconds it took."""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as profile:
        dom = subprocess.run([chrome, '--headless=new', '--disable-gpu', f'--user-data-dir={profile}',
                              f'--window-size={WINDOW}', '--allow-file-access-from-files',
                              f'--virtual-time-budget={budget}', '--dump-dom', path.as_uri()],
                             capture_output=True, text=True, encoding='utf-8', timeout=1800).stdout
    m = re.search(r'<pre id="__log">(.*?)</pre>', dom, re.S)
    return (html.unescape(m.group(1)) if m else 'NO LOG (the solver did not finish within its time budget)'), time.perf_counter() - t0


def main():
    # the logs carry ✓ and ✕, which a Windows console's default encoding cannot print
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    picked = sys.argv[1:] or list(SUITES) + list(PY_SUITES)
    unknown = [s for s in picked if s not in SUITES and s not in PY_SUITES]
    if unknown:
        sys.exit(f'Unknown suite {", ".join(unknown)}: pick from {", ".join(list(SUITES) + list(PY_SUITES))}.')
    seed = int(os.environ.get('PROBE_SEED') or random.randrange(2 ** 32))
    OUT.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix='run-', dir=OUT))
    pages = [(name, build(run_dir, seed, name, drill, slot, solvers, extra), budget)
             for suite in picked if suite in SUITES for name, drill, slot, solvers, extra, budget in SUITES[suite]]
    chrome = find_chrome() if pages else None
    times = json.loads(TIMES.read_text()) if TIMES.exists() else {}
    # longest first, so the slowest page is not the last to start; a page not timed yet goes first
    order = sorted(pages, key=lambda p: -times.get(p[0], float('inf')))
    with ThreadPoolExecutor(max_workers=4) as pool, ThreadPoolExecutor(max_workers=1) as py:
        py_runs = [(suite, py.submit(PY_SUITES[suite])) for suite in picked if suite in PY_SUITES]
        done = dict(zip([p[0] for p in order], pool.map(lambda p: play(chrome, p[1], p[2]), order)))
    print(f'seed {seed} (PROBE_SEED={seed} plays these pulls again)\n')
    bad = False
    for suite, run in py_runs:
        log, failed = run.result()
        print(f'== {suite}\n{log}\n')
        bad |= failed
    for name, *_ in pages:
        log = done[name][0]
        print(f'== {name}\n{log}\n')
        if 'CRASH' in log or 'NO LOG' in log or ' FAIL' in log or 'ERRORS=[]' not in log:
            bad = True
    if pages:
        times = json.loads(TIMES.read_text()) if TIMES.exists() else {}   # again: another run may have written since
        TIMES.write_text(json.dumps(dict(times, **{n: round(t, 1) for n, (_, t) in done.items()}), indent=1, sort_keys=True))
    if bad and pages: print(f'probe pages kept in {run_dir.relative_to(ROOT).as_posix()}/')
    else: shutil.rmtree(run_dir, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
