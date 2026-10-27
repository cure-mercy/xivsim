"""Every attribution that changes between two versions of the classifier, over every cached report.

    python tools/scorecard/blame_diff.py                  the working tree against HEAD
    python tools/scorecard/blame_diff.py --rev HEAD~3     against an older commit (any git revision)
    python tools/scorecard/blame_diff.py --old-dir DIR    against copies saved in DIR (classifier.py, and scorecard.py if
                                                          it changed too), e.g. before an edit on top of uncommitted ones
    python tools/scorecard/blame_diff.py --report CODE    only these reports
    python tools/scorecard/blame_diff.py --causes         also incidents whose cause text alone changed
    python tools/scorecard/blame_diff.py --summary        only the totals at the end

The old side is classifier.py and scorecard.py (wipe_of, mistakes_of, cause_label) as they are at the revision, read
from git; the new side is the working tree. Each cached pull (.cache/report_*.json, with the acts cache's casts where
there is one; nothing is fetched) is judged by both, on its raid day's rules. Incidents are matched by kind, victim and
time, and printed when the culprits, the confidence, whether it is fallout of an earlier mistake, or the summary label
changes, with the pulls whose wipe went to someone else. The totals at the end count the scorecard's mistakes (as
mistakes per pull counts them: until the pull was lost) by mechanic and by cause, and the wipes by label, old against
new, so a fix in one mechanic that moves the counts in another shows up.

tests/run.py blame checks hand-checked pulls against the working tree; this shows everything else a change moved.
"""
import argparse, collections, datetime, inspect, json, subprocess, sys, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classifier, fflogs
import scorecard

RANK = {"high": 0, "medium": 1, "low": 2}


def at_rev(rev, folder=None):
    """(classifier, scorecard) modules as they are at a git revision, or as saved in a folder (its scorecard.py, when it
    has none, the working tree's)."""
    def src(name):
        if folder:
            p = Path(folder) / name
            return (p if p.exists() or name != "scorecard.py" else HERE / name).read_text(encoding="utf-8")
        r = subprocess.run(["git", "show", f"{rev}:tools/scorecard/{name}"], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
        if r.returncode: raise SystemExit(f"git show {rev}:tools/scorecard/{name}: {r.stderr.strip()}")
        return r.stdout
    C = types.ModuleType("classifier"); C.__file__ = str(HERE / "classifier.py")
    exec(compile(src("classifier.py"), f"{rev}:classifier.py", "exec"), C.__dict__)
    S = types.ModuleType("scorecard"); S.__file__ = str(HERE / "scorecard.py")
    keep = sys.modules.get("classifier")
    sys.modules["classifier"] = C            # the old scorecard's `from classifier import ...` gets the old classifier
    try: exec(compile(src("scorecard.py"), f"{rev}:scorecard.py", "exec"), S.__dict__)
    finally: sys.modules["classifier"] = keep
    return C, S


def cached_codes():
    return sorted(f.stem[len("report_"):] for f in fflogs.CACHE.glob("report_*.json"))


def pulls(code, C=classifier):
    """(fight, pull number, Pull, light parties, raid day) for every pull of a cached report, built by classifier C."""
    data = json.loads((fflogs.CACHE / f"report_{code}.json").read_text())
    af = fflogs.CACHE / f"acts_{code}.json"
    A = json.loads(af.read_text()) if af.exists() else {}
    rep = {"masterData": data["masterData"], "deaths": data["deaths"]}
    ev = {"abilities": data["abilities"], "dmg": data["dmg"], "debuffs": data["debuffs"], "wf": data.get("wf")}
    with_acts = "acts" in inspect.signature(C.Pull).parameters    # older classifiers read no casts
    ps = [C.Pull(code, f, rep, ev, **({"acts": A.get(str(f["id"]))} if with_acts else {})) for f in data["fights"]]
    lp = C.infer_light_parties(ps)
    day = datetime.datetime.fromtimestamp(data["startTime"] / 1000).date().isoformat()   # the raid day, as build_site.py's
    return [(f, n, p, lp, day) for n, (f, p) in enumerate(zip(data["fights"], ps), 1)]


def judge(C, S, f, p, lp, day):
    """What the scorecard makes of one pull: the classifier's entries, the wipe (culprits, deciding entry) and the
    mistakes it counts, [(culprit, t, cause, mechanic, kind, confidence)], until the pull was lost."""
    res, _ = C.classify(p, lp, day) if "day" in inspect.signature(C.classify).parameters else C.classify(p, lp)
    cul, trig = S.wipe_of(res) if not f.get("kill") else ([], None)
    cutoff = trig["t"] + S.MISTAKE_AFTER_WIPE if trig else (f["endTime"] - f["startTime"]) / 1000
    counted = [tuple(m[:5]) + ((m[5] if len(m) > 5 else None),) for m in S.mistakes_of(res) if m[1] <= cutoff]
    return dict(res=res, wipe=(sorted(cul), trig), counted=counted)


def match(old, new, tol=0.25):
    """Pairs of (old entry, new entry) by kind, victim and the nearest time within tol; None for one without a partner."""
    left, out = list(new), []
    for r in old:
        cand = [q for q in left if q["kind"] == r["kind"] and q["victim"] == r["victim"] and abs(q["t"] - r["t"]) <= tol]
        q = min(cand, key=lambda q: abs(q["t"] - r["t"]), default=None)
        if q is not None: left.remove(q)
        out.append((r, q))
    return out + [(None, q) for q in left]


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def view(r, S):
    """What of an entry is compared: culprits, confidence, fallout or not, and its summary label."""
    return (tuple(sorted(r["culprits"])), r["confidence"], bool(r.get("derived")),
            S.cause_label(r["cause"], r["mechanic"]) if r["culprits"] else "-")


def say(r, S):
    cul, conf, derived, lab = view(r, S)
    return f"{', '.join(cul) or 'no one'} [{conf}{', fallout' if derived else ''}] {lab}"


def wipe_label(S, trig):
    """S's name for what lost the pull (scorecards before wipe_label named only the culprit's cause)."""
    if trig is None: return "Unclear"
    if hasattr(S, "wipe_label"): return S.wipe_label(trig)
    return S.cause_label(trig["cause"], trig["mechanic"]) if trig["culprits"] else "No culprit found"


def wipe_text(w, S):
    cul, trig = w
    if trig is None: return "none" if not cul else ", ".join(cul)
    return f"{', '.join(cul) or 'no one'} ({wipe_label(S, trig)} at {mmss(trig['t'])})"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rev", default="HEAD", help="git revision of the old classifier (default HEAD)")
    ap.add_argument("--old-dir", metavar="DIR", help="the old classifier.py (and scorecard.py) from this folder instead of git")
    ap.add_argument("--report", nargs="+", metavar="CODE", help="only these cached reports")
    ap.add_argument("--causes", action="store_true", help="also show incidents whose cause text alone changed")
    ap.add_argument("--summary", action="store_true", help="only the totals")
    a = ap.parse_args()
    OC, OS = at_rev(a.rev, a.old_dir)
    old_name = a.old_dir or a.rev
    site = HERE / "site" / "data.json"     # group names, when the report is on the site
    groups = {c: f"{r['day']} {r['group']}" for c, r in json.loads(site.read_text(encoding="utf-8"))["reports"].items()} if site.exists() else {}
    codes = a.report or cached_codes()
    n_pulls = n_inc = n_changed = n_wipes = 0
    tot = {k: collections.Counter() for k in ("mech_old", "mech_new", "cause_old", "cause_new", "wipe_old", "wipe_new", "conf_old", "conf_new")}
    by_mech = collections.Counter()
    for code in codes:
        olds, news = pulls(code, OC), pulls(code, classifier)
        for (f, n, op, olp, day), (_, _, np_, nlp, _) in zip(olds, news):
            o, w = judge(OC, OS, f, op, olp, day), judge(classifier, scorecard, f, np_, nlp, day)
            n_pulls += 1; n_inc += len(w["res"])
            for side, j, S in (("old", o, OS), ("new", w, scorecard)):
                for c, t, cause, mech, kind, conf in j["counted"]:
                    tot[f"mech_{side}"][mech] += 1; tot[f"cause_{side}"][S.cause_label(cause, mech)] += 1; tot[f"conf_{side}"][conf or "?"] += 1
                if not f.get("kill"):
                    tot[f"wipe_{side}"][wipe_label(S, j["wipe"][1])] += 1
            lines = []
            for r, q in match(o["res"], w["res"]):
                if r is None: lines.append(f"  + {mmss(q['t'])} {q['kind']:5s} {q['victim']:18s} {q['ability'][:24]:24s} new: {say(q, scorecard)}")
                elif q is None: lines.append(f"  - {mmss(r['t'])} {r['kind']:5s} {r['victim']:18s} {r['ability'][:24]:24s} gone: {say(r, OS)}")
                elif view(r, OS) != view(q, scorecard) or a.causes and r["cause"] != q["cause"]:
                    lines.append(f"    {mmss(q['t'])} {q['kind']:5s} {q['victim']:18s} {q['ability'][:24]:24s} {say(r, OS)}\n"
                                 f"    {'':48s}-> {say(q, scorecard)}")
                    if a.causes and r["cause"] != q["cause"]: lines.append(f"    {'':48s}   was: {r['cause']}\n    {'':48s}   now: {q['cause']}")
                else: continue
                by_mech[(q or r)["mechanic"]] += 1
            wo, wn = o["wipe"], w["wipe"]
            wipe_moved = wo[0] != wn[0] or wipe_label(OS, wo[1]) != wipe_label(scorecard, wn[1])
            n_changed += len(lines) and 1; n_wipes += wipe_moved
            if (lines or wipe_moved) and not a.summary:
                print(f"== {code} #{f['id']} pull {n} ({groups.get(code, day)})" + (f"   wipe: {wipe_text(wo, OS)} -> {wipe_text(wn, scorecard)}" if wipe_moved else ""))
                for l in lines: print(l)
    print(f"\n{old_name} -> working tree over {len(codes)} reports, {n_pulls} pulls, {n_inc} incidents: "
          f"{sum(by_mech.values())} incidents changed in {n_changed} pulls, {n_wipes} wipes changed")
    if by_mech: print("  incidents changed by mechanic: " + ", ".join(f"{m} {v}" for m, v in by_mech.most_common()))

    def table(title, old, new, only_changed=False):
        keys = sorted(set(old) | set(new), key=lambda k: -max(old[k], new[k]))
        rows = [k for k in keys if not only_changed or old[k] != new[k]]
        print(f"\n{title}" + (" (changed only)" if only_changed else "") + f": {sum(old.values())} -> {sum(new.values())}")
        for k in rows: print(f"  {old[k]:6d} {new[k]:6d} {new[k] - old[k]:+6d}  {k}")
        if not rows: print("  no change")
    table("counted mistakes by mechanic", tot["mech_old"], tot["mech_new"])
    table("counted mistakes by cause", tot["cause_old"], tot["cause_new"], only_changed=True)
    table("counted mistakes by confidence", tot["conf_old"], tot["conf_new"])
    table("wipes by what lost the pull", tot["wipe_old"], tot["wipe_new"], only_changed=True)


if __name__ == "__main__":
    main()
