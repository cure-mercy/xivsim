"""Plays the trainer's drills in headless Chrome and prints what happened.

Each suite builds probe pages from the real index.html (with the slot, the drill and its pace set in
localStorage), adds solvers from tests/solvers/ that play the drill the way a player would, runs them with
Chrome's virtual time, and prints each page's log: the verdict of every pull, the recaps the drill showed,
and any script errors.

    python tests/run.py                  every suite
    python tests/run.py superchain undo  only these

Suites:
    para1, engrave, superchain  real-time solvers: the right play clears, each kind of mistake fails as it should
    undo                        step by step: undo and redo give back exactly the page they should
    steady                      the real-time solvers again, checking the arena never moves on the page,
                                in a stacked layout (800 px) and with three columns (1400 px)

Chrome is looked for on the usual paths; set CHROME to its executable to choose one. The probe pages are
written to tests/out/, which git ignores. Exits non-zero if a solver crashed, the page threw an error or a
check logged FAIL.
"""
import html, json, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests' / 'out'

# Superchain's solver reads the pull from inside the drill, through a hook added to a copy of its script.
SC_HOOK = ("    const newRound = T.trackRounds('superchain', startRound);",
           "    window.__sc = { st: () => st, spotFirst, spotLaser, spotLast, spotTowers, towerSpot, CPOS };\n")

PARA1 = dict(tab='para1', pace='twelfth-p1-pace', panel='panel-para1', clock='p1-clock')
ENGRAVE = dict(tab='engrave', pace='twelfth-eg-pace', panel='panel-engrave', clock='eg-clock')
SUPERCHAIN = dict(tab='superchain', pace='twelfth-sc-pace', panel='panel-superchain', clock='sc-clock')

# what the undo snapshots leave out: layers of passing effects, and a class that only animates
UNDO_ENGRAVE = {'pace': 'steps', 'skip': ['eg-lasers', 'eg-fx', 'eg-debuffBadge'], 'strip': ['eg-untilted']}
UNDO_SUPERCHAIN = {'pace': 'steps', 'skip': ['sc-beams', 'sc-fx']}
NARROW, WIDE = '800,1000', '1400,1000'

# suite -> pages: (page name, drill, slot, solvers, probe settings, virtual time budget in ms). The settings
# reach the page as window.__probe; `pace` (default live) and `window` (Chrome's window size) are also used here.
SUITES = {
    'para1': [(f'para1-{s}', PARA1, s, 'para1', {}, 250_000) for s in ['R1', 'R2', 'T1', 'H2']],
    'engrave': [(f'engrave-{s}', ENGRAVE, s, 'engrave', {}, 1_600_000) for s in ['H1', 'M2']],
    'superchain': [(f'superchain-{s}', SUPERCHAIN, s, 'superchain', {}, 500_000) for s in ['T1', 'H2', 'M1', 'R2']],
    'undo': [(f'undo-para1-{s}', PARA1, s, 'para1-undo', {'pace': 'steps'}, 120_000) for s in ['T1', 'R2']]
          + [(f'undo-engrave-{s}', ENGRAVE, s, 'undo', UNDO_ENGRAVE, 120_000) for s in ['H1', 'M1']]
          + [(f'undo-superchain-{s}', SUPERCHAIN, s, 'undo', UNDO_SUPERCHAIN, 120_000) for s in ['T1', 'R2']],
    'steady': [(f'steady-{name}-{w}', drill, slot, ['steady', name], {'arena': arena, 'window': size}, budget)
               for name, drill, slot, arena, budget in [('para1', PARA1, 'R1', 'p1-arena', 250_000),
                                                         ('engrave', ENGRAVE, 'H1', 'eg-arena', 1_600_000),
                                                         ('superchain', SUPERCHAIN, 'T1', 'sc-arena', 500_000)]
               for w, size in [('narrow', NARROW), ('wide', WIDE)]],
}


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


def build(name, drill, slot, solvers, extra):
    page = (ROOT / 'index.html').read_text(encoding='utf-8')
    if drill is SUPERCHAIN:
        src = (ROOT / 'mechanics' / 'superchain-1.js').read_text(encoding='utf-8')
        assert SC_HOOK[0] in src, 'the hook point in superchain-1.js has moved'
        (OUT / 'superchain-1.dbg.js').write_text(src.replace(SC_HOOK[0], SC_HOOK[1] + SC_HOOK[0]), encoding='utf-8')
        page = page.replace('<script src="mechanics/superchain-1.js">', '<script src="tests/out/superchain-1.dbg.js">')
    probe = dict(extra, slot=slot, panel=drill['panel'], clock=drill['clock'])
    pace = extra.get('pace', 'live')
    setup = ('<base href="../../">'
             "<script>window.__errors=[];window.addEventListener('error',e=>window.__errors.push(e.message+' @'+(e.filename||'').split('/').pop()+':'+e.lineno));"
             f"window.__probe={json.dumps(probe)};"
             f"try{{localStorage.clear();localStorage.setItem('twelfth-tab','{drill['tab']}');localStorage.setItem('twelfth-slot','{slot}');"
             f"localStorage.setItem('{drill['pace']}','{pace}');}}catch(e){{}}</script>")
    solvers = [solvers] if isinstance(solvers, str) else solvers
    solve = ''.join(f'<script src="tests/solvers/{s}.js"></script>' for s in ['common'] + solvers)
    assert '<head>' in page and '</body>' in page
    path = OUT / f'{name}.html'
    path.write_text(page.replace('<head>', '<head>' + setup, 1).replace('</body>', solve + '</body>', 1), encoding='utf-8')
    return path


def play(chrome, path, budget, window):
    with tempfile.TemporaryDirectory() as profile:
        dom = subprocess.run([chrome, '--headless=new', '--disable-gpu', f'--user-data-dir={profile}',
                              f'--window-size={window}', '--allow-file-access-from-files',
                              f'--virtual-time-budget={budget}', '--dump-dom', path.as_uri()],
                             capture_output=True, text=True, encoding='utf-8', timeout=1800).stdout
    m = re.search(r'<pre id="__log">(.*?)</pre>', dom, re.S)
    return html.unescape(m.group(1)) if m else 'NO LOG (the solver did not finish within its time budget)'


def main():
    # the logs carry ✓ and ✕, which a Windows console's default encoding cannot print
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    picked = sys.argv[1:] or list(SUITES)
    unknown = [s for s in picked if s not in SUITES]
    if unknown:
        sys.exit(f'Unknown suite {", ".join(unknown)}: pick from {", ".join(SUITES)}.')
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    pages = [(name, build(name, drill, slot, solvers, extra), budget, extra.get('window', WIDE))
             for suite in picked for name, drill, slot, solvers, extra, budget in SUITES[suite]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        logs = list(pool.map(lambda p: play(chrome, *p[1:]), pages))
    bad = False
    for (name, *_), log in zip(pages, logs):
        print(f'== {name}\n{log}\n')
        if 'CRASH' in log or 'NO LOG' in log or ' FAIL' in log or 'ERRORS=[]' not in log:
            bad = True
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
