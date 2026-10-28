"""The blame suite: pulls checked by hand, with each incident's expected culprits, against the classifier.

    python tests/run.py blame                    run it (with the other suites, or alone)
    python tests/blame.py run [--known]          the same; --known also lists each known-wrong verdict and why
    python tests/blame.py show CODE FIGHT [--own-day]  one pull laid out for checking by hand: players and seats, debuffs,
                                                 provokes, the classifier's faults and verdicts, every hit around them
    python tests/blame.py add CODE FIGHT "WHY" [--own-day]
                                                 append a pull to the cases with the classifier's current verdicts,
                                                 judged as the case will be (--own-day: by its raid day's rule book)

The cases are in tests/blame_cases.json, which is git-ignored: like the site's data.json it names players and who
caused which mistake. It reads the scorecard's caches (tools/scorecard/.cache), so the suite only runs where those are.
Each case is one pull: what it covers, the wipe's culprits, and every incident (kind, victim, time) with the culprits
the strategy blames and whether it is fallout of an earlier mistake (not counted again). An incident whose `known`
says the classifier gets it wrong expects the right answer and is counted as known, not FAIL, until the classifier
gets it right (FIXED: drop the `known`); `wipe_known` does the same for the wipe. A `note` explains a verdict that
needed thought. After `add`, check every verdict against `show` before keeping the case. A `rules_day` judges the
pull by the rule book of that day instead of its raid day's: the pulls checked from before a strategy was introduced
(Superchain I, 2026-10-06; the last, Paradeigma III, 2026-10-25: RULES_DAY) still test them, while the scorecard does
not blame those days by them. A case with `own_day` is judged by its raid day instead, to test the dates themselves.
An incident's `cause_has` is text its cause must contain, and a case's `wipe_label` the label of what lost the pull:
for rules whose wording or label matters, not only whom they blame. An incident with `saved` is a death that saved the
pull (the site's green "saved the pull"); every other incident must not be marked so.

A FAIL line means the classifier now blames someone else for a pull checked by hand. tools/scorecard/blame_diff.py
shows everything else the change moved, across all cached pulls.
"""
import collections, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "scorecard"))
CASES = ROOT / "tests" / "blame_cases.json"
TOL = 0.25            # seconds an incident's time may move and still be the same incident
RULES_DAY = "2026-10-25"   # the last strategy's introduction: pulls checked from before it are judged by its rule book
SKIP_DEBUFFS = {"Weakness", "Brink of Death", "Damage Down", "Magic Vulnerability Up", "Physical Vulnerability Up", "Concussion"}
BUILT = {}   # report code -> its pulls, built once per process: a later run (scratch/blame/mutate.py's) reuses them


def _loaded(code, D, C):
    """A cached report's pulls by fight id. A Pull holds only the report's data, so it is built once; the light parties
    are inferred afresh on every call, as they run classifier rules that a caller may have swapped since."""
    if code not in BUILT:
        BUILT[code] = D.pulls(code, C) if (D.fflogs.CACHE / f"report_{code}.json").exists() else []
    rows = BUILT[code]
    lp = C.infer_light_parties([p for _, _, p, _, _ in rows]) if rows else None
    return {f["id"]: (f, n, p, lp, day) for f, n, p, _, day in rows}


def _modules():
    import blame_diff, classifier, scorecard
    return blame_diff, classifier, scorecard


def find(code, fight):
    """(fight, pull number, Pull, light parties, raid day) of one cached pull."""
    D, C, S = _modules()
    hit = [x for x in D.pulls(code, C) if x[0]["id"] == fight]
    if not hit: raise SystemExit(f"{code} has no fight {fight} in the cache")
    return hit[0]


def verdicts(code, fight, own_day=False):
    """A pull judged as its case is: by RULES_DAY's rule book when it is older, unless own_day."""
    D, C, S = _modules()
    f, n, p, lp, day = find(code, fight)
    return f, n, p, lp, day, D.judge(C, S, f, p, lp, day if own_day or day >= RULES_DAY else RULES_DAY)


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
            loaded[case["code"]] = _loaded(case["code"], D, C)
        x = loaded[case["code"]].get(case["fight"])
        if x is None:
            log.append(f"FAIL {case['code']} #{case['fight']}: not in the cache"); bad = True; continue
        f, n, p, lp, day = x
        j = D.judge(C, S, f, p, lp, case.get("rules_day", day))
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
            if want.get("cause_has") and want["cause_has"] not in got["cause"]:
                lines.append(f"FAIL {where}: the cause no longer says \"{want['cause_has']}\": {got['cause']}")
            if bool(want.get("saved")) != bool(got.get("saved")):
                lines.append(f"FAIL {where}: " + ("no longer marked as saving the pull" if want.get("saved") else "marked as saving the pull, which the case does not say"))
        if "wipe" in case:
            ok, said, meant = sorted(case["wipe"]) == j["wipe"][0], ", ".join(j["wipe"][0]) or "no one", ", ".join(sorted(case["wipe"])) or "no one"
            if case.get("wipe_known"):
                tally["known" if not ok else "fixed"] += 1
                lines.append(f"KNOWN wipe: classifier {said}, should be {meant}: {case['wipe_known']}" if not ok
                             else f"FIXED wipe: now {said}, as it should be; drop the case's `wipe_known`")
            elif ok: tally["wipes ok"] += 1
            else: lines.append(f"FAIL wipe: expected {meant}, got {said}")
        if case.get("wipe_label") and (lab := D.wipe_label(S, j["wipe"][1]) if j["wipe"][1] else None) != case["wipe_label"]:
            lines.append(f"FAIL wipe label: expected \"{case['wipe_label']}\", got \"{lab}\"")
        bad |= any(l.startswith("FAIL") for l in lines)
        shown = [l for l in lines if known or not l.startswith("KNOWN")]
        n_known = len(lines) - len([l for l in lines if not l.startswith("KNOWN")])
        log.append(("  " if shown else "ok ") + head + (f" ({n_known} known wrong)" if n_known and not known else ""))
        log += ["    " + l for l in shown]
    # the rule book's dates: a strategy is blamed only from the day it was introduced
    for mech, day, want in [(m, d, w) for ms, since, before in ((("Paradeigma I", "Paradeigma II", "Glaukopis", "Glaukopis / Ultima Blade"), "2026-09-29", "2026-09-23"),
                                                                 (("Superchain I", "Dialogos"), "2026-10-06", "2026-09-30"),
                                                                 (("Paradeigma III",), "2026-10-25", "2026-10-18"))
                            for m in ms for d, w in ((before, C.AVOIDABLE_ONLY), (since, callable))]:
        got = C.rules_on(day)[mech]
        if not (callable(got) if want is callable else got == want):
            log.append(f"FAIL rule book: {mech} on {day} is {getattr(got, '__name__', got)}, not {'a rule' if want is callable else want}"); bad = True
    log.append(f"\n{len(cases)} pulls: {tally['ok']} incidents as checked, {tally['wipes ok']} wipes as checked, "
               f"{tally['known']} known wrong (tests/blame.py run --known lists them), {tally['fixed']} fixed" + (", FAIL" if bad else ""))
    return "\n".join(log), bad


def show(code, fight, own_day=False):
    """One pull laid out for checking its verdicts by hand."""
    D, C, S = _modules()
    f, n, p, lp, day, j = verdicts(code, fight, own_day)
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
    _, faults = C.classify(p, lp, day if own_day or day >= RULES_DAY else RULES_DAY)
    print("\nfaults:")
    for x in faults:
        print(f"  {D.mmss(x['t'])} {x['mechanic']}: {', '.join(x['culprits']) or 'no one'} [{x['confidence']}] {x['rule']}"
              + (f" (victims {', '.join(sorted(x['victims']))})" if x["victims"] else "") + (f" chain {x['chain']}" if x["chain"] else ""))
    print("\nincidents:")
    for r in j["res"]:
        print(f"  {D.mmss(r['t'])} {r['kind']:5s} {r['victim']} ({r['ability']}): {', '.join(r['culprits']) or 'no one'} [{r['confidence']}"
              f"{', fallout' if r.get('derived') else ''}{', saved the pull' if r.get('saved') else ''}] {r['cause']}")
    cul, trig = j["wipe"]
    print(f"wipe: {', '.join(cul) or 'no one'}" + (f" ({D.wipe_label(S, trig)} at {D.mmss(trig['t'])})" if trig else ""))
    print("counted: " + "; ".join(f"{c} {D.mmss(t)} {D.label(S, cause, mech, tag)}" for c, t, cause, mech, kind, conf, tag in j["counted"]))
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


def add(code, fight, about, own_day=False):
    D, C, S = _modules()
    f, n, p, lp, day = find(code, fight)
    rules = day if own_day or day >= RULES_DAY else RULES_DAY
    j = D.judge(C, S, f, p, lp, rules)
    cases = json.loads(CASES.read_text(encoding="utf-8")) if CASES.exists() else {"pulls": []}
    if any(c["code"] == code and c["fight"] == fight for c in cases["pulls"]): raise SystemExit(f"{code} #{fight} is already a case")
    cases["pulls"].append(dict(code=code, fight=fight, pull=n, day=day, about=about, wipe=j["wipe"][0],
                               **({"own_day": True} if own_day else {"rules_day": rules} if rules != day else {}),
                               incidents=[dict(t=round(r["t"], 2), kind=r["kind"], victim=r["victim"], culprits=sorted(r["culprits"]),
                                               **({"fallout": True} if r.get("derived") else {}), **({"saved": True} if r.get("saved") else {}),
                                               note=r["cause"]) for r in j["res"]]))
    CASES.write_text(json.dumps(cases, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"added {code} #{fight} pull {n} with {len(j['res'])} incidents: check each against `show` before keeping it")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd, *args = sys.argv[1:] or ["run"]
    if cmd == "show": show(args[0], int(args[1]), own_day="--own-day" in args)
    elif cmd == "add": add(args[0], int(args[1]), args[2], own_day="--own-day" in args)
    elif cmd == "run":
        out, failed = run(known="--known" in args); print(out); sys.exit(1 if failed else 0)
    else: sys.exit(__doc__)
