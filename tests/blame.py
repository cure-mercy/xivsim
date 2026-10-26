"""The blame suite: pulls checked by hand, with each incident's expected culprits, against the classifier.

    python tests/run.py blame                    run it (with the other suites, or alone)
    python tests/blame.py run [--known]          the same; --known also lists each known-wrong verdict and why
    python tests/blame.py show CODE FIGHT        one pull laid out for checking by hand: players and seats, debuffs,
                                                 provokes, the classifier's faults and verdicts, every hit around them
    python tests/blame.py add CODE FIGHT "WHY"   append a pull to the cases with the classifier's current verdicts

The cases are in tests/blame_cases.json, which is git-ignored: like the site's data.json it names players and who
caused which mistake. It reads the scorecard's caches (tools/scorecard/.cache), so the suite only runs where those are.
Each case is one pull: what it covers, the wipe's culprits, and every incident (kind, victim, time) with the culprits
the strategy blames and whether it is fallout of an earlier mistake (not counted again). An incident whose `known`
says the classifier gets it wrong expects the right answer and is counted as known, not FAIL, until the classifier
gets it right (FIXED: drop the `known`); `wipe_known` does the same for the wipe. A `note` explains a verdict that
needed thought. After `add`, check every verdict against `show` before keeping the case.

A FAIL line means the classifier now blames someone else for a pull checked by hand. tools/scorecard/blame_diff.py
shows everything else the change moved, across all cached pulls.
"""
import collections, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "scorecard"))
CASES = ROOT / "tests" / "blame_cases.json"
TOL = 0.25            # seconds an incident's time may move and still be the same incident
SKIP_DEBUFFS = {"Weakness", "Brink of Death", "Damage Down", "Magic Vulnerability Up", "Physical Vulnerability Up", "Concussion"}


def _modules():
    import blame_diff, classifier, scorecard
    return blame_diff, classifier, scorecard


def find(code, fight):
    """(fight, pull number, Pull, light parties, raid day) of one cached pull."""
    D, C, S = _modules()
    hit = [x for x in D.pulls(code, C) if x[0]["id"] == fight]
    if not hit: raise SystemExit(f"{code} has no fight {fight} in the cache")
    return hit[0]


def verdicts(code, fight):
    D, C, S = _modules()
    f, n, p, lp, day = find(code, fight)
    return f, n, p, lp, day, D.judge(C, S, f, p, lp, day)


def run(known=False):
    """Checks every case; returns (log, failed). known: list the known-wrong verdicts too, not just their count."""
    if not CASES.exists():
        return f"FAIL no cases: {CASES.relative_to(ROOT)} is missing (it is git-ignored; see tests/blame.py)", True
    cases = json.loads(CASES.read_text(encoding="utf-8"))["pulls"]
    D, C, S = _modules()
    log, bad, tally = [], False, collections.Counter()
    loaded = {}
    for case in cases:
        if case["code"] not in loaded:
            loaded[case["code"]] = {x[0]["id"]: x for x in D.pulls(case["code"], C)} if (D.fflogs.CACHE / f"report_{case['code']}.json").exists() else {}
        x = loaded[case["code"]].get(case["fight"])
        if x is None:
            log.append(f"FAIL {case['code']} #{case['fight']}: not in the cache"); bad = True; continue
        f, n, p, lp, day = x
        j = D.judge(C, S, f, p, lp, day)
        head = f"{case['code']} #{case['fight']} pull {n}: {case['about']}"
        lines = []
        exp = [dict(x, t=float(x["t"])) for x in case["incidents"]]
        for want, got in D.match(exp, j["res"], TOL):
            if got is None:
                lines.append(f"FAIL {D.mmss(want['t'])} {want['kind']} {want['victim']}: no such incident any more"); continue
            where = f"{D.mmss(got['t'])} {got['kind']} {got['victim']} ({got['ability']})"
            if want is None:
                lines.append(f"FAIL {where}: a new incident, not in the case ({', '.join(got['culprits']) or 'no one'}: {got['cause']})"); continue
            ok = sorted(want["culprits"]) == sorted(got["culprits"]) and bool(want.get("fallout")) == bool(got.get("derived"))
            said = f"{', '.join(sorted(got['culprits'])) or 'no one'}{' (fallout)' if got.get('derived') else ''}"
            meant = f"{', '.join(sorted(want['culprits'])) or 'no one'}{' (fallout)' if want.get('fallout') else ''}"
            if want.get("known"):
                tally["known" if not ok else "fixed"] += 1
                lines.append(f"KNOWN {where}: classifier {said}, should be {meant}: {want['known']}" if not ok
                             else f"FIXED {where}: now {said}, as it should be; drop the case's `known`")
            elif ok: tally["ok"] += 1
            else: lines.append(f"FAIL {where}: expected {meant}, got {said}: {got['cause']}")
        if "wipe" in case:
            ok, said, meant = sorted(case["wipe"]) == j["wipe"][0], ", ".join(j["wipe"][0]) or "no one", ", ".join(sorted(case["wipe"])) or "no one"
            if case.get("wipe_known"):
                tally["known" if not ok else "fixed"] += 1
                lines.append(f"KNOWN wipe: classifier {said}, should be {meant}: {case['wipe_known']}" if not ok
                             else f"FIXED wipe: now {said}, as it should be; drop the case's `wipe_known`")
            elif ok: tally["wipes ok"] += 1
            else: lines.append(f"FAIL wipe: expected {meant}, got {said}")
        bad |= any(l.startswith("FAIL") for l in lines)
        shown = [l for l in lines if known or not l.startswith("KNOWN")]
        n_known = len(lines) - len([l for l in lines if not l.startswith("KNOWN")])
        log.append(("  " if shown else "ok ") + head + (f" ({n_known} known wrong)" if n_known and not known else ""))
        log += ["    " + l for l in shown]
    log.append(f"\n{len(cases)} pulls: {tally['ok']} incidents as checked, {tally['wipes ok']} wipes as checked, "
               f"{tally['known']} known wrong (tests/blame.py run --known lists them), {tally['fixed']} fixed" + (", FAIL" if bad else ""))
    return "\n".join(log), bad


def show(code, fight):
    """One pull laid out for checking its verdicts by hand."""
    D, C, S = _modules()
    f, n, p, lp, day, j = verdicts(code, fight)
    dur = (f["endTime"] - f["startTime"]) / 1000
    boss = f.get("bossPercentage")
    print(f"{code} #{fight} pull {n}, {day}: {D.mmss(dur)}, " + ("kill" if f.get("kill") else f"wipe at {boss}% boss HP"))
    seat = {w: "".join(map(str, s)) for w, s in C.seats_all(p, lp).items()}
    print("players: " + "; ".join(f"{w} {p.job[w]} {seat.get(w, '?')}" for w in sorted(p.job, key=lambda w: seat.get(w, "Z"))))
    deb = collections.defaultdict(list)
    for e in p.deb:
        if e["type"] == "applydebuff" and e["name"] not in SKIP_DEBUFFS and e["t"] > 0: deb[(round(e["t"]), e["name"])].append(e["who"])
    print("debuffs: " + "; ".join(f"{t} {nm}: {', '.join(ws)}" for (t, nm), ws in sorted(deb.items())))
    pv = [(t, w, a) for t, w, a in p.casts or [] if a in ("Provoke", "Shirk")]
    if pv: print("provoke / shirk: " + "; ".join(f"{t:.1f} {w} {a}" for t, w, a in pv))
    _, faults = C.classify(p, lp, day)
    print("\nfaults:")
    for x in faults:
        print(f"  {D.mmss(x['t'])} {x['mechanic']}: {', '.join(x['culprits']) or 'no one'} [{x['confidence']}] {x['rule']}"
              + (f" (victims {', '.join(sorted(x['victims']))})" if x["victims"] else "") + (f" chain {x['chain']}" if x["chain"] else ""))
    print("\nincidents:")
    for r in j["res"]:
        print(f"  {D.mmss(r['t'])} {r['kind']:5s} {r['victim']} ({r['ability']}): {', '.join(r['culprits']) or 'no one'} [{r['confidence']}"
              f"{', fallout' if r.get('derived') else ''}] {r['cause']}")
    cul, trig = j["wipe"]
    print(f"wipe: {', '.join(cul) or 'no one'}" + (f" ({D.wipe_label(S, trig)} at {D.mmss(trig['t'])})" if trig else ""))
    print("counted: " + "; ".join(f"{c} {D.mmss(t)} {S.cause_label(cause, mech)}" for c, t, cause, mech, *_ in j["counted"]))
    # every hit on a player around the incidents (the windows merged)
    spans = []
    for r in j["res"]:
        lo, hi = r["t"] - 3, r["t"] + 0.5
        if spans and lo <= spans[-1][1]: spans[-1][1] = max(spans[-1][1], hi)
        else: spans.append([lo, hi])
    for lo, hi in spans:
        print(f"\nhits {D.mmss(max(lo, 0))}-{D.mmss(hi)}:")
        for e in p.dmg:
            if not lo <= e["t"] <= hi or e["name"] == "attack" and (e.get("targetResources") or {}).get("hitPoints", 1) > 0: continue
            tr = e.get("targetResources") or {}
            print(f"  {e['t']:7.2f} {e['name'][:24]:24s} {e['who'][:18]:18s} {seat.get(e['who'], '?'):3s} hp {tr.get('hitPoints', '?')!s:>7}/{tr.get('maxHitPoints', '?')!s:<7}"
                  f" inst {e.get('sourceInstance', '-')!s:3s} pos {'(%.1f, %.1f)' % e['pos'] if e['pos'] else '-'}")


def add(code, fight, about):
    f, n, p, lp, day, j = verdicts(code, fight)
    cases = json.loads(CASES.read_text(encoding="utf-8")) if CASES.exists() else {"pulls": []}
    if any(c["code"] == code and c["fight"] == fight for c in cases["pulls"]): raise SystemExit(f"{code} #{fight} is already a case")
    cases["pulls"].append(dict(code=code, fight=fight, pull=n, day=day, about=about, wipe=j["wipe"][0],
                               incidents=[dict(t=round(r["t"], 2), kind=r["kind"], victim=r["victim"], culprits=sorted(r["culprits"]),
                                               **({"fallout": True} if r.get("derived") else {}), note=r["cause"]) for r in j["res"]]))
    CASES.write_text(json.dumps(cases, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"added {code} #{fight} pull {n} with {len(j['res'])} incidents: check each against `show` before keeping it")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd, *args = sys.argv[1:] or ["run"]
    if cmd == "show": show(args[0], int(args[1]))
    elif cmd == "add": add(args[0], int(args[1]), args[2])
    elif cmd == "run":
        out, failed = run(known="--known" in args); print(out); sys.exit(1 if failed else 0)
    else: sys.exit(__doc__)
