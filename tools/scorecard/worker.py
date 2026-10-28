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
its error on the row for the admin page. The keys come from .supabase (or SCORECARD_SUPABASE), as for supa.py.
"""
import argparse, datetime, json, sys, time, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site, fflogs, supa

POLL = 30            # s between reads of the list
LIVE_EVERY = 180     # s between FFLogs checks of a live report
IDLE_STOP = 90 * 60  # s without a new event in a live log before watching stops
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
                if site["reports"].pop(code, None): done.append(code)
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
            except (Exception, SystemExit) as ex:   # S.fetch raises SystemExit for a report without P12S pulls (yet)
                plain = isinstance(ex, (ValueError, SystemExit, RuntimeError))   # RuntimeError: FFLogs' own answer ("This report does not exist.")
                patch(code, state="error", message=(str(ex) if plain else f"{type(ex).__name__}: {ex}")[:500], **({"segments": log["segments"]} if log else {}))
                if not plain: traceback.print_exc()
        if done:
            build_site.finish(site, bench)
            supa.upload(build_site.fragments(site))
        for code in gone: supa.call("DELETE", f"/rest/v1/report_sources?code=eq.{supa.q(code)}")
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    a = ap.parse_args()
    if not supa.config(): raise SystemExit("no Supabase keys: see supa.py")
    bench = json.loads((build_site.HERE / "benchmark.json").read_text())
    print(f"worker: {supa.config()['url']}, list every {POLL} s, live reports every {LIVE_EVERY} s", file=sys.stderr)
    while True:
        try:
            done = step(bench)
            if done: print(f"built or removed: {', '.join(done)}", file=sys.stderr)
        except Exception:
            traceback.print_exc()   # Supabase or the network away: try again next round
        if a.once: break
        time.sleep(POLL)


if __name__ == "__main__":
    main()
