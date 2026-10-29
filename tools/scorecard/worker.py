"""Builds the reports the admin page lists (Supabase's report_sources table) and keeps live ones up to date.

    python tools/scorecard/worker.py            runs until stopped (in WSL: worker.service, see the README)
    python tools/scorecard/worker.py --once     one pass, for testing

Every POLL seconds it reads the list and, for each row:
- want 'absent' (the admin removed it): takes the report off the site and deletes the row;
- not on the site yet, a new group name, or a rebuild the admin asked for: analyses it (a rebuild downloads it again);
- live (live_until in the future): every LIVE_EVERY seconds asks FFLogs whether the report has grown (uploaded segments,
  pulls). FFLogs has no webhooks or subscriptions, so this is polled. When it has grown, the report is downloaded and
  analysed again. Watching stops at live_until, which the database caps at 12 hours after it was set, and earlier when
  the log has had nothing new for IDLE_STOP.
After any change it writes data.json (build_site.finish) and uploads what changed (supa.upload). A failed build puts
its error on the row for the admin page. Every SEARCH_POLL seconds it also answers the admin page's searches for a raid
day's P12S reports on FFLogs (report_searches, see search). The keys come from .supabase (or SCORECARD_SUPABASE), as for
supa.py.
"""
import argparse, datetime, json, sys, time, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site, fflogs, supa
import scorecard as S

POLL = 30            # s between reads of the list
LIVE_EVERY = 180     # s between FFLogs checks of a live report
IDLE_STOP = 90 * 60  # s without a new event in a live log before watching stops
SEARCH_POLL = 5      # s between looks for a search the admin page asked for
ZONE = 54            # Anabaseios, the zone FFLogs files P12S reports under
UTC = datetime.timezone.utc


def when(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds")


def patch(code, **cols):
    supa.call("PATCH", f"/rest/v1/report_sources?code=eq.{supa.q(code)}", cols)


def step(bench):
    """One pass over the list. Returns the codes it built or removed."""
    rows = supa.call("GET", "/rest/v1/report_sources?select=*&order=added_at")
    now = datetime.datetime.now(UTC)
    with build_site.site_lock():
        site = build_site.load_site()
        done, gone = [], []
        for r in rows:
            code = r["code"]
            if r["want"] == "absent":
                if site["reports"].pop(code, None): done.append(code); supa.audit("report removed", code, {"group": r["group_name"]}, by="worker")
                gone.append(code); continue
            on, live = site["reports"].get(code), r["live_until"] and when(r["live_until"]) > now
            log = None
            if live and (not r["checked_at"] or (now - when(r["checked_at"])).total_seconds() >= LIVE_EVERY):
                try:
                    log = fflogs.report_state(code)
                except Exception as e:
                    patch(code, checked_at=iso(now), message=f"FFLogs check failed: {e}"[:500]); continue
                end = datetime.datetime.fromtimestamp(log["end"] / 1000, UTC)
                patch(code, checked_at=iso(now), report_end=iso(end))
            grown = log is not None and log["segments"] != r["segments"]   # each upload of a live log adds a segment
            why, refresh = None, False
            if r["state"] == "error" and not grown: pass   # waits for new pulls, or for the admin to change or rebuild it
            elif on is None: why, refresh = "new", grown
            elif r["group_name"] and r["group_name"] != on["group"]: why = "renamed"
            elif r["rebuild_at"] and (not r["built_at"] or when(r["rebuild_at"]) > when(r["built_at"])): why, refresh = "rebuild", True
            if on is not None and grown: why, refresh = why or "new pulls", True
            if log and not grown and (now - end).total_seconds() > IDLE_STOP:
                patch(code, live_until=iso(now), message=f"Stopped watching: nothing new in the log since {end:%a %d %b %H:%M} UTC.")
            if not why:
                if r["state"] in ("queued", "building"): patch(code, state="ok")   # e.g. only live watching was switched on
                continue
            print(f"{code}: {why}", file=sys.stderr)
            patch(code, state="building", message=None)
            try:
                e = build_site.add_report(site, code, r["group_name"], refresh, bench)
                log = log or fflogs.report_state(code)
                patch(code, state="ok", message=None, group_name=e["group"], day=e["day"], pulls=e["pulls_total"],
                      segments=log["segments"], built_at=iso(datetime.datetime.now(UTC)))
                done.append(code)
                supa.audit("report built", code, dict(why=why, group=e["group"], day=e["day"], pulls=e["pulls_total"]), by="worker")
            except (Exception, SystemExit) as ex:   # S.fetch raises SystemExit for a report without P12S pulls (yet)
                plain = isinstance(ex, (ValueError, SystemExit, RuntimeError))   # RuntimeError: FFLogs' own answer ("This report does not exist.")
                patch(code, state="error", message=(str(ex) if plain else f"{type(ex).__name__}: {ex}")[:500], **({"segments": log["segments"]} if log else {}))
                supa.audit("build failed", code, dict(why=why, message=str(ex)[:300]), by="worker")
                if not plain: traceback.print_exc()
        if done:
            build_site.finish(site, bench)
            supa.upload(build_site.fragments(site))
        for code in gone: supa.call("DELETE", f"/rest/v1/report_sources?code=eq.{supa.q(code)}")
    return done


def search(day, names):
    """A raid day's P12S Savage reports on FFLogs (fflogs.find_reports: the zone's, and our uploaders' under another
    zone), each with the names it has of ours (players in the site's reports) and of the asked ones. Other players are
    only counted. names: comma-separated, "Name" or "Name@World", in any case."""
    site = build_site.load_site()
    d0 = datetime.datetime.combine(datetime.date.fromisoformat(day), datetime.time())   # local midnight, as the site dates reports
    start, end = d0.timestamp() * 1000, (d0 + datetime.timedelta(days=1)).timestamp() * 1000
    users = {u for u in fflogs.report_owners(sorted(site["reports"])).values() if u}
    found = fflogs.find_reports(start, end, S.P1, S.SAVAGE, ZONE, users)
    ours = {(x["name"], x["world"]) for r in site["reports"].values() for x in r.get("roster", [])}
    asked = [(n.strip(), w.strip() or None) for n, _, w in (x.partition("@") for x in names.split(",")) if n.strip()]
    def is_asked(name, server, a): return name.lower() == a[0].lower() and (not a[1] or (server or "").lower() == a[1].lower())
    rows = {r["code"]: r for r in supa.call("GET", "/rest/v1/report_sources?select=code,state,want")}
    # the same night uploaded twice (another player's log of it, often public when ours is unlisted): most pulls start
    # within a few seconds of a report's on the site, or of one found before it
    seen = []
    for c, r in site["reports"].items():
        cf = fflogs.CACHE / f"report_{c}.json"
        if r["day"] == day and cf.exists():
            d = json.loads(cf.read_text())
            seen.append((dict(code=c, group=r["group"]), [round((d["startTime"] + f["startTime"]) / 1000) for f in d["fights"]]))
    def same(at):
        return next((who for who, t in seen if sum(any(abs(x - y) <= 5 for y in t) for x in at) * 2 >= len(at)), None)
    out = []
    for r in found:
        on = site["reports"].get(r["code"])
        dup = None if on else same(r["at"])
        seen.append((dict(code=r["code"], group=None), r["at"]))
        out.append(dict({k: r[k] for k in ("code", "title", "start", "end", "owner", "visibility", "pulls", "kills")}, players=len(r["players"]), same=dup,
                        ours=[n for n, w in r["players"] if (n, w or None) in ours], asked=[n for n, w in r["players"] if any(is_asked(n, w, a) for a in asked)],
                        site=dict(group=on["group"], day=on["day"]) if on else None, listed=(rows.get(r["code"]) or {}).get("state")))
    hit = {a for r in found for a in asked for n, w in r["players"] if is_asked(n, w, a)}
    return dict(reports=out, not_found=[f"{n}@{w}" if w else n for n, w in asked if (n, w) not in hit], uploaders=len(users))


def searches():
    """Answers the searches the admin page asked for, oldest first, and forgets those older than a week."""
    for q in supa.call("GET", "/rest/v1/report_searches?select=id,day,names&state=eq.queued&order=asked_at"):
        supa.call("PATCH", f"/rest/v1/report_searches?id=eq.{q['id']}", dict(state="running"))
        print(f"search {q['day']}" + (f" for {q['names']}" if q["names"] else ""), file=sys.stderr)
        try: cols = dict(state="done", results=search(q["day"], q["names"]))
        except Exception as ex:
            traceback.print_exc(); cols = dict(state="error", message=f"{type(ex).__name__}: {ex}"[:500])
        supa.call("PATCH", f"/rest/v1/report_searches?id=eq.{q['id']}", dict(cols, done_at=iso(datetime.datetime.now(UTC))))
    week = iso(datetime.datetime.now(UTC) - datetime.timedelta(days=7))
    supa.call("DELETE", f"/rest/v1/report_searches?asked_at=lt.{supa.q(week)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    a = ap.parse_args()
    if not supa.config(): raise SystemExit("no Supabase keys: see supa.py")
    bench = json.loads((build_site.HERE / "benchmark.json").read_text())
    print(f"worker: {supa.config()['url']}, list every {POLL} s, live reports every {LIVE_EVERY} s", file=sys.stderr)
    supa.call("PATCH", "/rest/v1/report_searches?state=eq.running", dict(state="queued"))   # cut off by a restart: ask again
    last = None
    while True:
        if last is None or time.monotonic() - last >= POLL:
            last = time.monotonic()
            try:
                done = step(bench)
                if done: print(f"built or removed: {', '.join(done)}", file=sys.stderr)
            except Exception:
                traceback.print_exc()   # Supabase or the network away: try again next round
        try: searches()
        except Exception: traceback.print_exc()
        if a.once: break
        time.sleep(SEARCH_POLL)


if __name__ == "__main__":
    main()
