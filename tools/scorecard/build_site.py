"""Adds FFLogs reports to the scorecard website's data (site/data.json).

    python tools/scorecard/build_site.py <report link> [<report link> ...] [--refresh] [--names "G1,G2,..."]
    python tools/scorecard/build_site.py --remove <report code>
    python tools/scorecard/build_site.py --reanalyse              (after a classifier or label change)
    python tools/scorecard/build_site.py [links ...] --publish [DIR]
    python -m http.server -d tools/scorecard/site 8000          then open http://localhost:8000

Each link is one raid group's report. Reports are grouped into raid days by the date they were logged; a report
already in the data is analysed again and keeps its group name unless --names gives a new one. New reports on a
day get the next free G1, G2, ... in the order given. The analysis itself is in scorecard.py.

site/data.json holds player names and who caused which mistake, so it is git-ignored.

--publish writes a copy of the site for public hosting into DIR (default: stats/ at the repository root, which
the GitHub Pages workflow deploys like the rest of the repo): the page files and data.enc.json, the data encrypted
with a passphrase (encrypt_data.js, needs Node). The plaintext data.json is never copied there. The passphrase is
read from SCORECARD_PASSPHRASE, or asked for twice. To stop publishing, delete DIR; to move host, upload DIR (or
serve site/ with its plaintext data behind the new host's own login).
"""
import argparse, datetime, getpass, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classifier as C
import fflogs
import scorecard as S

HERE = Path(__file__).resolve().parent
DATA = HERE / "site" / "data.json"
PUBLISH_DIR = HERE.parent.parent / "stats"
PAGE_FILES = ["index.html", "style.css", "app.js"]


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
    return plain(dict(code=code, group=group, day=g["date"].date().isoformat(), start=g["date"], title=data.get("title"),
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
                conf_weight=S.CONF_WEIGHT,   # what a mistake or wipe counts in the rates, by the classifier's confidence
                windows=bench.get("windows", []),
                # seconds of kill time per 1% of boss HP, at the pace of a clear
                sec_per_hp=bench["pools"]["clears"]["kill_median_s"] / 100, raise_penalty=S.RAISE_PENALTY, raise_s=S.RAISE_S,
                dd_penalty=S.DD_PENALTY, mistake_times=mistake_times(codes),
                # when each mechanic a mistake is filed under starts (s), for rates per pull that reached it
                mech_start=dict({"other": 0.0}, **{m: float(lo) for lo, hi, m in C.MECH}))


def publish(out):
    """Copy the page files and the encrypted data to out; never the plaintext."""
    pw = os.environ.get("SCORECARD_PASSPHRASE")
    if not pw:
        pw = getpass.getpass("Passphrase for the published data: ")
        if pw != getpass.getpass("Again: "): raise SystemExit("the passphrases differ; nothing published")
    if len(pw) < 12: raise SystemExit("use a passphrase of at least 12 characters (several words is best); nothing published")
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    for f in PAGE_FILES: shutil.copyfile(HERE / "site" / f, out / f)
    page = (out / "index.html").read_text(encoding="utf-8")   # version the files so browsers fetch the new ones
    for f in ("style.css", "app.js"):
        v = hashlib.sha256((HERE / "site" / f).read_bytes()).hexdigest()[:10]
        page = page.replace(f'"{f}"', f'"{f}?v={v}"')
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "data.json").unlink(missing_ok=True)
    env = dict(os.environ, SCORECARD_PASSPHRASE=pw)
    subprocess.run(["node", str(HERE / "encrypt_data.js"), str(DATA), str(out / "data.enc.json")], env=env, check=True)
    print(f"published to {out}: {', '.join(PAGE_FILES)}, data.enc.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("links", nargs="*", help="FFLogs report links or codes, one per raid group")
    ap.add_argument("--refresh", action="store_true", help="refetch reports instead of using the cache")
    ap.add_argument("--names", help="comma-separated group names for the links, in order")
    ap.add_argument("--remove", nargs="+", metavar="CODE", help="remove these reports from the site data")
    ap.add_argument("--reanalyse", action="store_true", help="analyse every report already on the site again (after a classifier or label change)")
    ap.add_argument("--publish", nargs="?", const=str(PUBLISH_DIR), metavar="DIR",
                    help=f"also write the passphrase-protected copy for public hosting (default {PUBLISH_DIR})")
    ap.add_argument("--cached", action="store_true", help="use the cache only: skip parts a cached report is missing "
                    "(e.g. the rDPS raid buffs gave others) instead of fetching them, for when FFLogs is down")
    a = ap.parse_args()
    S.CACHED_ONLY = a.cached
    bench = json.loads((HERE / "benchmark.json").read_text())
    site = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"reports": {}}
    for code in a.remove or []:
        print(f"removed {code}" if site["reports"].pop(code, None) else f"{code} was not in the data", file=sys.stderr)
    names = a.names.split(",") if a.names else []
    links = list(a.links)
    if a.reanalyse:   # every report already on the site, from the cache, keeping its group name
        given = {fflogs.report_code(l) for l in links}
        links += [c for c in sorted(site["reports"], key=lambda c: (site["reports"][c]["day"], site["reports"][c]["group"])) if c not in given]
    import checks
    checks.OUR_CODES = sorted(set(site["reports"]) | {fflogs.report_code(l) for l in links})   # for references from our own groups
    for i, link in enumerate(links):
        code = fflogs.report_code(link)
        data = S.fetch(code, a.refresh, bench)
        day = datetime.datetime.fromtimestamp(data["startTime"] / 1000).date().isoformat()
        if i < len(names): group = names[i].strip()
        elif code in site["reports"]: group = site["reports"][code]["group"]
        else:
            taken = {r["group"] for r in site["reports"].values() if r["day"] == day}
            group = next(f"G{n}" for n in range(1, 99) if f"G{n}" not in taken)
        print(f"{day} {group}: {code}", file=sys.stderr)
        site["reports"][code] = report_entry(code, group, data, bench)
    site["benchmark"] = benchmark_summary(bench, list(site["reports"]))
    site["rotations"] = S.rotations()   # the optimizer's rotations, per job and GCD (tools/rotation/dps.py --site)
    site["gear"] = S.gear()             # the best-in-slot sets (tools/gear/sheets.py)
    site["generated"] = datetime.datetime.now().isoformat(timespec="minutes")
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    days = sorted({r["day"] for r in site["reports"].values()})
    print(f"wrote {DATA} ({len(site['reports'])} reports over {len(days)} raid days, {DATA.stat().st_size // 1024} KB)")
    if a.publish: publish(a.publish)


if __name__ == "__main__":
    main()
