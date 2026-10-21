"""A job's PvE action and trait changes from the official patch notes (the Lodestone's patch note log), patch by patch.

    python tools/rotation/patchnotes.py Reaper [--since 7.0]
    python tools/rotation/patchnotes.py "Black Mage" --grep Thunderhead

Like the job guide, the notes list each action as it appears at level 100: a change "upon learning" a trait above level
90 (e.g. Reaper's Melee Mastery III) doesn't touch the level-90 value. 7.0 lists no changes (it points to the job guide),
so the notes are deltas on top of the 7.0 kit. Pages are cached in .cache/patchnotes/.
"""
import argparse, html, re, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache" / "patchnotes"
SITE = "https://na.finalfantasyxiv.com"
LOG = "/lodestone/special/patchnote_log/"
JOBS = ["Paladin", "Warrior", "Dark Knight", "Gunbreaker", "White Mage", "Scholar", "Astrologian", "Sage", "Monk",
        "Dragoon", "Ninja", "Samurai", "Reaper", "Viper", "Bard", "Machinist", "Dancer", "Black Mage", "Summoner",
        "Red Mage", "Pictomancer", "Blue Mage"]
PVE_START = "Actions and traits have been adjusted as follows:"    # a heading; the job tables run to the next one
PVP = re.compile(r"adjustments have been made to PvP actions")


def _get(path, name):
    f = CACHE / name
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sfL", "-A", "Mozilla/5.0", "-o", str(f), SITE + path], check=True)
    return f.read_text(encoding="utf-8")


def _text(page):
    """The page as one line per paragraph, list item or table cell."""
    t = re.sub(r"<(br|/p|/li|/tr|/h\d|/div|/td)[^>]*>", "\n", page)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return [l.strip() for l in t.splitlines() if l.strip()]


def _pve(page):
    """(the job tables, the rest of the note before its PvP part) as HTML."""
    i = page.find(PVE_START)
    if i < 0: return "", page[:_pvp(page)]
    j = page.find("<h3", i)
    j = j if j > 0 else len(page)
    return page[i:j], page[:i] + page[j:_pvp(page)]


def _pvp(page):
    m = PVP.search(page)
    return m.start() if m else len(page)


def notes(since="7.0", refresh=False):
    """[(version, page)] for every patch note from `since` on, oldest first."""
    if refresh:
        for f in CACHE.glob("*.html"): f.unlink()
    log = _get(LOG, "log.html")
    out = []
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>\s*Patch (\d+\.\d+[a-z]?) Notes\s*</a>', log):
        path, v = m.groups()
        if _ver(v) >= _ver(since): out.append((v, _get(path, f"patch_{v}.html")))
    return sorted(out, key=lambda x: _ver(x[0]))


def _ver(v):
    major, minor = v.split(".")
    return int(major), float("0." + re.sub(r"\D", "", minor))


def changes(page, job):
    """[(action, [change, ...])] from the job's table in the note's PvE action changes."""
    tables, _ = _pve(page)
    out = []
    for part in re.split(r"<h4[^>]*>", tables)[1:]:
        head, _, body = part.partition("</h4>")
        if _text(head)[0].split(" / ")[-1] != job: continue
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 2: continue
            name = " ".join(_text(cells[0])) or (out[-1][0] if out else "")
            got = _text(cells[-1])
            if out and out[-1][0] == name: out[-1][1].extend(got)
            else: out.append((name, got))
    return out


def mentions(page, job):
    """Other lines of the note's non-PvP part that name the job (gauge changes and the like; item names are skipped)."""
    _, rest = _pve(page)
    rx = re.compile(re.escape(job), re.I)
    return [l for l in _text(rest) if rx.search(l) and len(l) > 40]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("job", help="job name as the notes write it, e.g. Reaper, \"Black Mage\"")
    ap.add_argument("--since", default="7.0", help="first patch, e.g. 7.2 (default 7.0, Dawntrail)")
    ap.add_argument("--grep", help="only actions or changes matching this (case-insensitive)")
    ap.add_argument("--refresh", action="store_true", help="download the notes again")
    a = ap.parse_args()
    if a.job not in JOBS: ap.error(f"unknown job {a.job!r}; one of: {', '.join(JOBS)}")
    rx = re.compile(a.grep, re.I) if a.grep else None
    for v, page in notes(a.since, a.refresh):
        got, more = changes(page, a.job), mentions(page, a.job)
        if rx:
            got = [(n, [c for c in cs if rx.search(n) or rx.search(c)]) for n, cs in got]
            more = [l for l in more if rx.search(l)]
        got = [(n, cs) for n, cs in got if cs]
        if not got and not more: continue
        print(f"\nPatch {v}")
        for n, cs in got:
            print(f"  {n}")
            for c in cs: print(f"    {c}")
        for l in more: print(f"  (elsewhere) {l}")


if __name__ == "__main__":
    main()
