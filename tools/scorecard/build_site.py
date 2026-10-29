"""Adds FFLogs reports to the scorecard website's data (site/data.json).

    python tools/scorecard/build_site.py <report link> [<report link> ...] [--refresh] [--names "G1,G2,..."]
    python tools/scorecard/build_site.py --remove <report code>
    python tools/scorecard/build_site.py --reanalyse              (after a classifier or label change)
    python tools/scorecard/build_site.py [links ...] --publish [DIR]
    python tools/scorecard/build_site.py --upload                 (Supabase only, no page files)
    python -m http.server -d tools/scorecard/site 8000          then open http://localhost:8000

Each link is one raid group's report. Reports are grouped into raid days by the date they were logged; a report
already in the data is analysed again and keeps its group name unless --names gives a new one. New reports on a
day get the next free G1, G2, ... in the order given. The analysis itself is in scorecard.py.

site/data.json holds player names and who caused which mistake, so it is git-ignored.

--publish writes a copy of the site for public hosting into DIR (default: stats/ at the repository root, which
the GitHub Pages workflow deploys like the rest of the repo): the page files and public.json (what the rotation and
gear pages need, PUBLIC_KEYS, open to everyone). The rest goes to Supabase when .supabase holds its keys (supa.py:
staff accounts an admin approved), with config.json telling the page where to log in. When a passphrase is set
(SCORECARD_PASSPHRASE, or .PUBLISH_KEY at the repository root), it also goes to data.enc.json, encrypted with it
(encrypt_data.js, needs Node), for staff who open the site with the passphrase instead of an account. Without
Supabase, data.enc.json is the only way in, and the passphrase is asked for twice when neither is set. The plaintext
data.json is never copied there, and nothing is published if a player's name turns up in public.json. To stop publishing, delete DIR; to move host, upload DIR (or serve site/ with its plaintext data behind
the new host's own login).

The worker (worker.py) builds the reports the admin page lists, with the same functions; site_lock() keeps it and a
command-line build from writing data.json at the same time.
"""
import argparse, base64, contextlib, datetime, getpass, hashlib, json, os, shutil, socket, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classifier as C
import fflogs
import scorecard as S

HERE = Path(__file__).resolve().parent
DATA = HERE / "site" / "data.json"
PUBLISH_DIR = HERE.parent.parent / "stats"
PAGE_FILES = ["index.html", "style.css", "app.js"]
# what goes into public.json, unencrypted: a whitelist, so a new key stays behind the passphrase until it is added
# here. The rotation and gear pages read only these (benchmark: only its clears, from public FFLogs reports); our
# players' figures on those pages (`ours`) stay locked
PUBLIC_KEYS = {"generated": None, "rotations": None, "gear": None, "job_icons": None, "benchmark": ["pools"]}
# what the staff's pages load first for every report (Supabase's progress table), a small part of the full record:
# group-level figures, mistakes by mechanic and pulls; the full record (report_full) follows when a page needs it
PROGRESS_KEYS = ["code", "group", "day", "start", "pulls_total", "kills", "best", "longest", "clean2", "party", "hp", "lost_total", "lost_dd", "echo",
                 "causes", "wipe_causes", "lost_causes", "lost_unattributed"]
PROGRESS_PULL_KEYS = ["n", "at", "dur", "boss", "kill", "first", "deaths", "hp", "echo"]


def plain(v):
    """JSON-safe copy: tuples to lists, Counters to dicts, datetimes to ISO strings."""
    if isinstance(v, dict): return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)): return [plain(x) for x in v]
    if isinstance(v, datetime.datetime): return v.isoformat(timespec="minutes")
    if isinstance(v, float): return round(v, 4)
    return v


def report_entry(code, group, data, bench):
    g = S.analyse(group, data, bench)
    boss = bench["hp_checkpoints"]["boss_hp"]
    for row in g["pull_rows"]:   # boss HP at each checkpoint the pull reached
        row["hp"] = {} if row["id"] in data.get("echo_pulls", []) else {m: round(100 * (1 - v / boss), 1) for m, v in data["hp"].get(str(row["id"]), {}).items()}
        row["echo"] = row["id"] in data.get("echo_pulls", [])
    # the report's start (ms) and each player's actor id, for links into the report on FFLogs
    actors = {a["name"]: a["id"] for a in data["masterData"]["actors"] if a["subType"] in S.ROLE}
    # who played, with their home world and FFLogs character id, for linking accounts to players (supa.py)
    servers = data.get("servers", {})
    roster = [dict(name=n, world=servers.get(n), id=fflogs.character_id(n, servers.get(n), data.get("region"), lookup=not S.CACHED_ONLY))
              for n in sorted({p["name"] for p in g["players"]})]
    return plain(dict(code=code, group=group, roster=roster, day=g["date"].date().isoformat(), start=g["date"], start_ms=data["startTime"], actors=actors, title=data.get("title"),
                      pulls_total=g["pulls"], kills=g["kills"], best=g["best"], longest=g["longest"], clean2=g["clean2"], party=g["party"],
                      hp=g["hp"], causes=dict(g["causes"]), wipe_causes=dict(g["wipe_causes"]), coverage=dict(g["coverage"]),
                      light_parties=[sorted(g["lp"][0]), sorted(g["lp"][1])], players=g["players"], pulls=g["pull_rows"],
                      lost_total=g["lost_total"], lost_dd=g.get("lost_dd"), cost_each=g.get("cost_each"), lost_causes=g["lost_causes"], lost_unattributed=g["lost_unattributed"], burst=g.get("burst"), echo=g.get("echo")))


def mistake_times(codes):
    """Medians over our reports: seconds dead until raised, and how long a Damage Down lasts (for the mistake budget)."""
    dead, dd = [], []
    for code in codes:
        cf = fflogs.CACHE / f"report_{code}.json"
        if not cf.exists(): continue
        d = json.loads(cf.read_text())
        for f in d["fights"]:
            deb = [x for x in d["debuffs"] if f["startTime"] <= x["timestamp"] <= f["endTime"]]
            for x in d["deaths"]:
                if not f["startTime"] <= x["timestamp"] <= f["endTime"]: continue
                rz = [e["timestamp"] for e in deb if e.get("targetID") == x.get("targetID") and e.get("abilityGameID") in (1000043, 1000044)
                      and e["type"] == "applydebuff" and e["timestamp"] > x["timestamp"]]
                if rz: dead.append((min(rz) - x["timestamp"]) / 1000)
            on = {}
            for e in sorted(deb, key=lambda e: e["timestamp"]):
                if e.get("abilityGameID") != S.DD: continue
                if e["type"] == "applydebuff": on[e.get("targetID")] = e["timestamp"]
                elif e["type"] == "removedebuff" and e.get("targetID") in on: dd.append((e["timestamp"] - on.pop(e.get("targetID"))) / 1000)
    import statistics as st
    return dict(dead_s=round(st.median(dead), 1) if dead else 10.0, dd_s=round(st.median(dd), 1) if dd else 6.7, deaths=len(dead), dds=len(dd))


def benchmark_summary(bench, codes=()):
    return dict(built=bench["built"], hp_checkpoints=bench["hp_checkpoints"],
                pools={p: dict(kills=v["kills"], kill_median_s=v["kill_median_s"], party_dps_median=v["party_dps_median"], party_dps_min=v.get("party_dps_min"),
                               role_uptime=v["role_uptime"], jobs=v["jobs"]) for p, v in bench["pools"].items()},
                grades=dict(mistakes=S.G_MIST, wipes=S.G_WIPE, damage=S.G_DMG, uptime=S.G_UP), window_s=S.WINDOW,
                windows=bench.get("windows", []),
                # seconds of kill time per 1% of boss HP, at the pace of a clear
                sec_per_hp=bench["pools"]["clears"]["kill_median_s"] / 100, raise_penalty=S.RAISE_PENALTY, raise_s=S.RAISE_S,
                dd_penalty=S.DD_PENALTY, mistake_times=mistake_times(codes),
                # when each mechanic a mistake is filed under starts (s), for rates per pull that reached it
                mech_start=dict({"other": 0.0}, **{m: float(lo) for lo, hi, m in C.MECH}),
                mech_end={m: float(hi) for lo, hi, m in C.MECH})   # and when it ends, for links to the whole mechanic on FFLogs


def ours_by_job(reports, rotations):
    """Our players' figures on the rotation pages, per job and without names: every clean 0:00-2:00 pull's rDPS and
    the buffs it gave others, how many players those come from, and each player's rotation ceiling with their clean
    pulls on it (the first one seen, as the band of the older ceiling uses it)."""
    out, names, own = {}, {}, {}
    for r in reports.values():
        for p in r["players"]:
            job, pulls = p["job"], p.get("clean_pulls") or []
            o = out.setdefault(job, {"rdps": [], "given": [], "players": 0, "own": []})
            for c in pulls:
                o["rdps"].append(c["rdps"]); o["given"].append(c.get("given") or 0)
                names.setdefault(job, set()).add(p["name"])
            if p.get("ceiling") and p.get("ceiling_key") in (rotations.get(job) or {}).get("rotations", {}):
                x = own.setdefault((job, p["name"]), {"ceiling": p["ceiling"], "key": p["ceiling_key"], "n": 0})
                x["n"] += len(pulls)
    for (job, _), x in own.items(): out[job]["own"].append(x)
    for job, o in out.items(): o["players"] = len(names.get(job, ()))
    return out


def split_public(site):
    """(public, private): the PUBLIC_KEYS part of the site data, and the rest. The private part keeps the whole
    benchmark, since the page merges it over the public one once it is unlocked."""
    public = {k: (site[k] if sub is None else {s: site[k][s] for s in sub if s in site[k]}) for k, sub in PUBLIC_KEYS.items() if k in site}
    private = {k: v for k, v in site.items() if k not in PUBLIC_KEYS or PUBLIC_KEYS[k] is not None}
    return public, private


def leaked_names(site, text):
    """Player names (every report's players and actors) that appear in text as a whole name ("Chi Ji" is not in
    "Ten Chi Jin")."""
    names = {p["name"] for r in site["reports"].values() for p in r["players"]} | {n for r in site["reports"].values() for n in r.get("actors", {})}
    part = lambda c: c.isalnum() or c in "_'"   # a character that would make the match part of a longer word
    def whole(n):
        i = text.find(n)
        while i >= 0:
            if not (i and part(text[i - 1])) and not (i + len(n) < len(text) and part(text[i + len(n)])): return True
            i = text.find(n, i + 1)
        return False
    return sorted(n for n in names if n and whole(n))


def progress_of(r):
    """A report's progress fragment: PROGRESS_KEYS, its players' names (which reports a player page needs), and per pull
    PROGRESS_PULL_KEYS, how many players were in it, its mistakes and their shares added up, and how it ended."""
    out = {k: r.get(k) for k in PROGRESS_KEYS}
    out["names"] = sorted({p["name"] for p in r["players"]})
    first = {p["name"]: p for p in reversed(r["players"])}   # as app.js stats(): each name once, its first entry
    out["player_pulls"] = sum(p["pulls"] for p in first.values())
    # the players index (#/players): per player their jobs, pulls, and mistakes and wipes as their shares added up
    # and per job: its pulls, vs Clears and the best-quarter rDPS it comes from (jobs without clears compare with ours)
    def per_job(n, f): return {q["job"]: f(q) for q in r["players"] if q["name"] == n}
    out["people"] = [dict(name=n, jobs=[q["job"] for q in r["players"] if q["name"] == n], pulls=p["pulls"],
                          m=p.get("mistakes_w", p.get("mistakes", 0)), w=p.get("wipes_w", p.get("wipes", 0)),
                          jp=per_job(n, lambda q: len(q.get("pull_detail") or []) or q["pulls"]), vs=per_job(n, lambda q: q.get("vs")),
                          bq=per_job(n, lambda q: q.get("best_quarter"))) for n, p in sorted(first.items())]
    out["pulls"] = []
    for q in r["pulls"]:
        x = {k: q.get(k) for k in PROGRESS_PULL_KEYS}
        x["np"], x["m"] = len(q.get("players") or []), round(sum(m.get("share", 1) for m in q.get("mistakes") or []), 4)
        if q.get("wipe"): x["wipe"] = {k: q["wipe"].get(k) for k in ("t", "mechanic", "label")}
        x["mistakes"] = [{k: m.get(k) for k in ("mechanic", "label", "share")} for m in q.get("mistakes") or []]
        out["pulls"].append(x)
    return out


def fragments(site):
    """The site's private part as rows for Supabase's tables (staff read them all; ACCESS_CONCEPT.md)."""
    reports = sorted(site["reports"].values(), key=lambda r: (r["day"], r["group"]))
    _, private = split_public(site)
    return dict(
        reports=[dict(code=r["code"], day=r["day"], group_name=r["group"]) for r in reports],
        progress={r["code"]: progress_of(r) for r in reports},
        full={r["code"]: r for r in reports},
        meta={k: v for k, v in private.items() if k != "reports"},   # strategies, the whole benchmark, ours
    )


def check_public(site):
    """public.json's text, after making sure it names no player."""
    public, _ = split_public(site)
    text = json.dumps(public, ensure_ascii=False, separators=(",", ":"))
    if leaked := leaked_names(site, text):
        raise SystemExit(f"public.json would name {len(leaked)} player(s) ({', '.join(leaked[:5])}); nothing published")
    return text


def passphrase(ask):
    """The passphrase for data.enc.json: SCORECARD_PASSPHRASE, else .PUBLISH_KEY at the repository root (git-ignored),
    else asked for twice when ask (no Supabase: the passphrase is the only way in). None: no data.enc.json."""
    pw, key = os.environ.get("SCORECARD_PASSPHRASE"), HERE.parent.parent / ".PUBLISH_KEY"
    if not pw and key.exists(): pw = key.read_text(encoding="utf-8").strip()
    if not pw and ask:
        pw = getpass.getpass("Passphrase for the published data: ")
        if pw != getpass.getpass("Again: "): raise SystemExit("the passphrases differ; nothing published")
    if pw and len(pw) < 12: raise SystemExit("use a passphrase of at least 12 characters (several words is best); nothing published")
    return pw or None


def publish(out):
    """Copy the page files and the public data to out, and the rest to Supabase (with config.json for the page) when
    .supabase is set up, and to data.enc.json, encrypted, when there is a passphrase; never the private part in plaintext."""
    import supa
    site = json.loads(DATA.read_text(encoding="utf-8"))
    public_text = check_public(site)
    cfg = supa.config()
    pw = passphrase(ask=not cfg)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    for f in PAGE_FILES: shutil.copyfile(HERE / "site" / f, out / f)
    page = (out / "index.html").read_text(encoding="utf-8")   # version the files so browsers fetch the new ones
    for f in ("style.css", "app.js"):
        v = hashlib.sha256((HERE / "site" / f).read_bytes()).hexdigest()[:10]
        page = page.replace(f'"{f}"', f'"{f}?v={v}"')
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "data.json").unlink(missing_ok=True)
    rest = []
    if cfg:
        supa.upload(fragments(site))
        (out / "config.json").write_text(json.dumps(supa.page_config(cfg, passphrase=bool(pw))), encoding="utf-8")   # the public URL and key
        rest.append(f"config.json (Supabase at {cfg['url']})")
    else: (out / "config.json").unlink(missing_ok=True)
    if pw:
        _, private = split_public(site)
        env = dict(os.environ, SCORECARD_PASSPHRASE=pw)   # the private part goes to the encryption on stdin, never to a file
        subprocess.run(["node", str(HERE / "encrypt_data.js"), "-", str(out / "data.enc.json")], env=env, check=True,
                       input=json.dumps(private, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        rest.append("data.enc.json (passphrase)")
    else: (out / "data.enc.json").unlink(missing_ok=True)
    rest = ", ".join(rest)
    (out / "public.json").write_text(public_text, encoding="utf-8")
    print(f"published to {out}: {', '.join(PAGE_FILES)}, public.json ({len(public_text.encode()) // 1024} KB), {rest}")


# ---------- building, shared with worker.py ----------
LOCK = HERE / "site" / ".build.lock"


@contextlib.contextmanager
def site_lock(wait=900):
    """One build at a time: the worker and a command-line build both rewrite data.json. A lock older than two hours is
    taken to be left over from a crashed build."""
    LOCK.parent.mkdir(exist_ok=True)
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); break
        except FileExistsError:
            try:
                if time.time() - LOCK.stat().st_mtime > 7200: LOCK.unlink(); continue
            except FileNotFoundError: continue
            if time.time() - t0 > wait: raise SystemExit(f"another build holds {LOCK}; try again later")
            time.sleep(2)
    os.write(fd, f"{socket.gethostname()} pid {os.getpid()}".encode()); os.close(fd)
    try: yield
    finally: LOCK.unlink(missing_ok=True)


def load_site():
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"reports": {}}


def add_report(site, code, group, refresh, bench):
    """Analyse one report into the site data, under group (None: its existing name, or the day's next free G1, G2, ...).
    Returns its entry. A name another report of that day already has is refused (ValueError)."""
    import checks
    data = S.fetch(code, refresh, bench)
    codes = sorted(set(site["reports"]) | {code})   # for references from our own groups
    if codes != checks.OUR_CODES or refresh:   # their openers are cached per job, from these reports' downloads: not in a
        checks.OUR_CODES = codes               # long run (the worker) after a report came, went or was downloaded again
        checks.group_openers.cache_clear(); checks.opener_ref.cache_clear()
    day = datetime.datetime.fromtimestamp(data["startTime"] / 1000).date().isoformat()
    taken = {r["group"]: c for c, r in site["reports"].items() if r["day"] == day and c != code}
    if not group: group = site["reports"][code]["group"] if code in site["reports"] else next(f"G{n}" for n in range(1, 99) if f"G{n}" not in taken)
    if group in taken: raise ValueError(f"{group} is taken on {day} by {taken[group]}")
    print(f"{day} {group}: {code}", file=sys.stderr)
    site["reports"][code] = report_entry(code, group, data, bench)
    return site["reports"][code]


def finish(site, bench):
    """Everything derived from the whole set of reports and the parts that come from the other tools; then write."""
    site["benchmark"] = benchmark_summary(bench, list(site["reports"]))
    site["rotations"] = S.rotations()   # the optimizer's rotations, per job and GCD (tools/rotation/dps.py --site)
    for v in site["rotations"].values():   # how many of our players are at each GCD: not shown, and the rotations are public
        for x in v["rotations"].values(): x.pop("players", None)
    site["gear"] = S.gear()             # the best-in-slot sets (tools/gear/sheets.py)
    import gamedata                      # every job's icon, for the job columns (the rotations' own are only their jobs')
    site["job_icons"] = {j: u for j in gamedata.ABBR if (u := gamedata.job_icon(j))}
    # FFLogs' "Unknown" job (a player it could not tell the job of): the game's "Any" icon with a question mark
    # (job_unknown.png, drawn by scratch/icons/draw_unknown.py)
    site["job_icons"]["Unknown"] = "data:image/png;base64," + base64.b64encode((HERE / "job_unknown.png").read_bytes()).decode()
    site["strategies"] = C.strategy_dates()   # when each mechanic's strategy began to be blamed, for the charts
    site["ours"] = ours_by_job(site["reports"], site["rotations"])   # our players' figures on the rotation pages, without names
    site["generated"] = datetime.datetime.now().isoformat(timespec="minutes")
    DATA.parent.mkdir(exist_ok=True)
    tmp = DATA.with_suffix(".tmp")   # write and swap, so the page server never reads half a file
    tmp.write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, DATA)
    days = sorted({r["day"] for r in site["reports"].values()})
    print(f"wrote {DATA} ({len(site['reports'])} reports over {len(days)} raid days, {DATA.stat().st_size // 1024} KB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("links", nargs="*", help="FFLogs report links or codes, one per raid group")
    ap.add_argument("--refresh", action="store_true", help="refetch reports instead of using the cache")
    ap.add_argument("--names", help="comma-separated group names for the links, in order")
    ap.add_argument("--remove", nargs="+", metavar="CODE", help="remove these reports from the site data")
    ap.add_argument("--reanalyse", action="store_true", help="analyse every report already on the site again (after a classifier or label change)")
    ap.add_argument("--publish", nargs="?", const=str(PUBLISH_DIR), metavar="DIR",
                    help=f"also write the copy for public hosting (default {PUBLISH_DIR}); the private part goes to Supabase, or encrypted")
    ap.add_argument("--upload", action="store_true", help="also send the data to Supabase, without writing page files")
    ap.add_argument("--cached", action="store_true", help="use the cache only: skip parts a cached report is missing "
                    "(e.g. the rDPS raid buffs gave others) instead of fetching them, for when FFLogs is down")
    a = ap.parse_args()
    S.CACHED_ONLY = a.cached
    bench = json.loads((HERE / "benchmark.json").read_text())
    with site_lock():
        site = load_site()
        for code in a.remove or []:
            print(f"removed {code}" if site["reports"].pop(code, None) else f"{code} was not in the data", file=sys.stderr)
        names = a.names.split(",") if a.names else []
        links = list(a.links)
        if a.reanalyse:   # every report already on the site, from the cache, keeping its group name
            given = {fflogs.report_code(l) for l in links}
            links += [c for c in sorted(site["reports"], key=lambda c: (site["reports"][c]["day"], site["reports"][c]["group"])) if c not in given]
        for i, link in enumerate(links):
            try: add_report(site, fflogs.report_code(link), names[i].strip() if i < len(names) else None, a.refresh, bench)
            except ValueError as e: raise SystemExit(f"{fflogs.report_code(link)}: {e}; nothing written")
        finish(site, bench)
        import supa
        if a.publish: publish(a.publish)
        elif a.upload:
            if not supa.config(): raise SystemExit("no Supabase keys (see supa.py); nothing uploaded")
            supa.upload(fragments(site))
        if (a.publish or a.upload) and supa.config():   # what reached Supabase, for the admin page's audit log
            supa.audit("command-line build", None, {k: v for k, v in dict(added=[fflogs.report_code(l) for l in a.links], removed=a.remove,
                       reanalysed=a.reanalyse or None, published=a.publish, uploaded=a.upload or None).items() if v}, by="command line")


if __name__ == "__main__":
    main()
