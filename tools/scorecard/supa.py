"""Supabase for the scorecard (ACCESS_CONCEPT.md, step 2): uploads the data split by who may read it, and a few
account commands.

    python tools/scorecard/supa.py status                  rows, and accounts by role
    python tools/scorecard/supa.py admin <email | name>    make an account an admin (they must have logged in once)
    python tools/scorecard/supa.py staff <email | name>    approve an account as staff (as the admin page does)
    python tools/scorecard/supa.py audit [N]               the last N entries of the audit log (default 30)
    python tools/scorecard/supa.py probe                   checks the row-level security with a throwaway account

build_site.py --publish (and --upload, and worker.py) call upload(). The keys come from .supabase at the repository
root (git-ignored), or from the file SCORECARD_SUPABASE names (.supabase.local for the local stack in WSL):

    SUPABASE_URL=https://<project>.supabase.co
    SUPABASE_ANON_KEY=<publishable / anon key: public, it goes into the page's config.json>
    SUPABASE_SERVICE_KEY=<secret / service_role key: bypasses row-level security, never leaves this machine>
    SCORECARD_EMAIL_LOGIN=1          optional: the page offers email + password next to Discord (local testing)

Only what changed since the last upload to that project is sent (hashes in .cache/supabase_sent.json).
"""
import hashlib, json, os, secrets, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SENT = HERE / ".cache" / "supabase_sent.json"


def config():
    """{url, anon, service, email_login} from the keys file, or None when there is none (the site then falls back
    to the passphrase)."""
    f = Path(os.environ.get("SCORECARD_SUPABASE") or ROOT / ".supabase")
    if not f.exists(): return None
    kv = dict(l.strip().split("=", 1) for l in f.read_text().splitlines() if "=" in l and not l.lstrip().startswith("#"))
    if not kv.get("SUPABASE_URL") or not kv.get("SUPABASE_SERVICE_KEY"): return None
    return dict(url=kv["SUPABASE_URL"].rstrip("/"), anon=kv.get("SUPABASE_ANON_KEY", ""), service=kv["SUPABASE_SERVICE_KEY"],
                email_login=kv.get("SCORECARD_EMAIL_LOGIN") == "1")


def page_config(cfg, passphrase=False):
    """What the page needs to log in (published as config.json): the project's address and its public key, and whether
    data.enc.json is there for the passphrase."""
    return dict(supabase_url=cfg["url"], anon_key=cfg["anon"], email_login=cfg["email_login"], passphrase=passphrase)


def _headers(key, token=None):
    h = {"apikey": key, "Content-Type": "application/json"}
    if token or key.startswith("eyJ"): h["Authorization"] = f"Bearer {token or key}"   # new sb_ keys go in apikey only
    return h


def call(method, path, body=None, prefer=None, key=None, token=None, cfg=None):
    """One request to the project (REST, auth or RPC), as the service role unless another key / user token is given."""
    cfg = cfg or config()
    h = _headers(key or cfg["service"], token)
    if prefer: h["Prefer"] = prefer
    data = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    req = urllib.request.Request(cfg["url"] + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path.split('?')[0]}: {e.code} {e.read().decode(errors='replace')[:300]}") from None


def q(v):
    return urllib.parse.quote(str(v), safe="")


def in_list(values):   # a PostgREST in.(...) list, each value quoted
    return "(" + ",".join('"' + str(v).replace('"', '\\"') + '"' for v in values) + ")"


def upload(fr, cfg=None):
    """Bring the project's tables in line with build_site.fragments(): upsert what changed, delete reports that are no
    longer on the site (their progress and full record go with them)."""
    cfg = cfg or config()
    sent_all = json.loads(SENT.read_text()) if SENT.exists() else {}
    sent = sent_all.setdefault(cfg["url"], {})
    h = lambda doc: hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    def changed(table, items):
        old = sent.setdefault(table, {})
        return {k: v for k, v in items.items() if old.get(k) != h(v)}
    def mark(table, items):
        sent.setdefault(table, {}).update({k: h(v) for k, v in items.items()})
    codes = [r["code"] for r in fr["reports"]]
    # reports that left the site: deleting them cascades to progress and report_full
    gone = call("GET", "/rest/v1/reports?select=code" + (f"&code=not.in.{q(in_list(codes))}" if codes else ""))
    for r in gone:
        call("DELETE", f"/rest/v1/reports?code=eq.{q(r['code'])}")
        for t in sent.values(): t.pop(r["code"], None)
    if fr["reports"]: call("POST", "/rest/v1/reports?on_conflict=code", [dict(r, built="now()") for r in fr["reports"]], "resolution=merge-duplicates")
    full = changed("report_full", fr["full"])
    for code, doc in full.items():   # one at a time: a full record is a few hundred kB
        call("POST", "/rest/v1/report_full?on_conflict=code", [dict(code=code, doc=doc)], "resolution=merge-duplicates")
    mark("report_full", full)
    prog = changed("progress", fr["progress"])
    if prog: call("POST", "/rest/v1/progress?on_conflict=code", [dict(code=c, doc=d) for c, d in prog.items()], "resolution=merge-duplicates")
    mark("progress", prog)
    meta = changed("site_meta", fr["meta"])
    if meta: call("POST", "/rest/v1/site_meta?on_conflict=key", [dict(key=k, doc=d) for k, d in meta.items()], "resolution=merge-duplicates")
    mark("site_meta", meta)
    sync_sources(fr, full, cfg)
    SENT.parent.mkdir(exist_ok=True); SENT.write_text(json.dumps(sent_all))
    print(f"Supabase {cfg['url']}: {len(codes)} reports ({len(full)} full records sent, {len(prog)} progress, "
          f"{len(meta)} meta), {len(gone)} removed", file=sys.stderr)


def sync_sources(fr, rebuilt, cfg):
    """The admin page's list of reports follows the site: a report built from the command line is added to it (or its
    group name, day and pulls updated), and one removed from the command line leaves it. Rows still waiting for the
    worker, or that failed, stay."""
    rows = {r["code"]: r for r in call("GET", "/rest/v1/report_sources?select=code,state,group_name", cfg=cfg)}
    by = {r["code"]: r for r in fr["reports"]}
    new = [dict(code=c, group_name=r["group_name"], day=r["day"], pulls=fr["progress"][c]["pulls_total"], state="ok", built_at="now()")
           for c, r in by.items() if c not in rows]
    if new: call("POST", "/rest/v1/report_sources", new, cfg=cfg)
    for c in rebuilt:
        if c in rows: call("PATCH", f"/rest/v1/report_sources?code=eq.{q(c)}", dict(group_name=by[c]["group_name"], day=by[c]["day"],
                          pulls=fr["progress"][c]["pulls_total"], built_at="now()"), cfg=cfg)
    stale = [c for c, r in rows.items() if c not in by and r["state"] == "ok"]
    if stale: call("DELETE", f"/rest/v1/report_sources?code=in.{q(in_list(stale))}", cfg=cfg)


# ---------- accounts ----------
def users(cfg=None):
    """Every auth user with their profile: [{id, email, name, provider, role}]."""
    out, page = [], 1
    while True:
        r = call("GET", f"/auth/v1/admin/users?page={page}&per_page=200", cfg=cfg)
        us = r.get("users", r) if isinstance(r, dict) else r
        out += us
        if len(us) < 200: break
        page += 1
    prof = {p["user_id"]: p for p in call("GET", "/rest/v1/profiles?select=*", cfg=cfg)}
    return [dict(id=u["id"], email=u.get("email"), name=(prof.get(u["id"]) or {}).get("display_name"),
                 provider=(u.get("app_metadata") or {}).get("provider"), role=(prof.get(u["id"]) or {}).get("role")) for u in out]


def audit(action, target=None, detail=None, by=None, cfg=None):
    """An entry in the audit log the admin page shows, for what the command line or the worker did (by: who, e.g.
    "worker"); what admins do on the page the database logs itself (supabase/migrations/20261029000000_staff.sql)."""
    try: call("POST", "/rest/v1/audit_log", dict(action=action, target=target, detail=detail, actor_name=by), cfg=cfg)
    except Exception as e: print(f"audit log: {e}", file=sys.stderr)   # never stop a build over the log (HTTP or network errors)


def set_role(who, role, cfg=None):
    m = [u for u in users(cfg) if who.lower() in ((u["email"] or "").lower(), (u["name"] or "").lower(), u["id"])]
    if len(m) != 1: raise SystemExit(f"{len(m)} users match {who!r}; give the email, the exact display name or the user id")
    call("PATCH", f"/rest/v1/profiles?user_id=eq.{m[0]['id']}", dict(role=role), cfg=cfg)
    print(f"{m[0]['name'] or m[0]['email']} is {'an admin' if role == 'admin' else role} now")


def count(table, cfg=None):
    """Rows in a table (Content-Range of an exact count; a plain select stops at the project's max rows)."""
    cfg = cfg or config()
    h = dict(_headers(cfg["service"]), Prefer="count=exact", Range="0-0")
    with urllib.request.urlopen(urllib.request.Request(cfg["url"] + f"/rest/v1/{table}?select=*", headers=h, method="HEAD"), timeout=60) as r:
        return int(r.headers["Content-Range"].split("/")[-1])


def status(cfg=None):
    us = users(cfg)
    src = call("GET", "/rest/v1/report_sources?select=state", cfg=cfg)
    print(f"{cfg['url']}: {count('reports', cfg)} reports, {count('report_full', cfg)} full records, {count('audit_log', cfg)} audit log entries")
    print(f"{len(us)} accounts: " + ", ".join(f"{sum(u['role'] == r for u in us)} {r}" for r in ("admin", "staff", "pending")))
    print("report list: " + ", ".join(f"{n} {s}" for s, n in sorted({s: sum(r['state'] == s for r in src) for s in {r['state'] for r in src}}.items())))


def show_audit(n, cfg=None):
    for e in reversed(call("GET", f"/rest/v1/audit_log?select=*&order=at.desc&limit={int(n)}", cfg=cfg)):
        print(f"{e['at'][:16].replace('T', ' ')}  {e['actor_name'] or '(service key)':16} {e['action']:22} {e['target'] or ''}"
              + (f"  {json.dumps(e['detail'], ensure_ascii=False)}" if e["detail"] else ""))


def probe(cfg=None):
    """Row-level security from outside: the public key alone, an account waiting for approval and a staff account must
    see exactly what they may (ACCESS_CONCEPT.md, staff only), and neither may raise its own role, remove accounts,
    start an FFLogs search or write the audit log. Uses a throwaway account, deleted after; its audit entries stay."""
    cfg = cfg or config()
    key = {"site_meta": "key", "profiles": "user_id", "report_searches": "id", "audit_log": "id"}
    tables = ["reports", "progress", "report_full", "site_meta", "profiles", "report_sources", "report_searches", "audit_log"]
    def rows(t, token=None):   # refused outright counts as nothing seen
        try: return call("GET", f"/rest/v1/{t}?select={key.get(t, 'code')}", key=cfg["anon"], token=token, cfg=cfg)
        except RuntimeError as e:
            if " 401 " in str(e) or " 403 " in str(e): return []
            raise
    def attempt(method, path, body, token):   # "refused", or "accepted" when the request went through
        try: call(method, path, body, key=cfg["anon"], token=token, cfg=cfg); return "accepted"
        except RuntimeError as e: return "refused" if any(f" {c} " in str(e) for c in (400, 401, 403)) else str(e)
    fails = []
    def expect(who, what, got, want):
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'} {who:8} {what:18} {got} (want {want})")
        if not ok: fails.append((who, what))
    for t in tables: expect("anon", t, len(rows(t)), 0)
    pw = secrets.token_urlsafe(18)
    email = f"probe-{secrets.token_hex(4)}@example.invalid"
    u = call("POST", "/auth/v1/admin/users", dict(email=email, password=pw, email_confirm=True), cfg=cfg)
    role = lambda: call("GET", f"/rest/v1/profiles?select=role&user_id=eq.{u['id']}", cfg=cfg)[0]["role"]
    n = lambda t: len(call("GET", f"/rest/v1/{t}?select={key.get(t, 'code')}", cfg=cfg))
    try:
        tok = call("POST", "/auth/v1/token?grant_type=password", dict(email=email, password=pw), key=cfg["anon"], cfg=cfg)["access_token"]
        for who in ("pending", "staff"):
            if who == "staff": call("PATCH", f"/rest/v1/profiles?user_id=eq.{u['id']}", dict(role="staff"), cfg=cfg)
            for t in tables:
                want = 1 if t == "profiles" else n(t) if who == "staff" and t in ("reports", "progress", "report_full", "site_meta") else 0
                expect(who, t, len(rows(t, tok)), want)
            call("PATCH", f"/rest/v1/profiles?user_id=eq.{u['id']}", dict(role="admin"), key=cfg["anon"], token=tok, cfg=cfg)
            expect(who, "raise own role", role(), who)
            expect(who, "search FFLogs", attempt("POST", "/rest/v1/report_searches", dict(day="2026-01-01"), tok), "refused")
            expect(who, "write audit log", attempt("POST", "/rest/v1/audit_log", dict(action="forged"), tok), "refused")
            expect(who, "remove an account", attempt("POST", "/rest/v1/rpc/remove_account", dict(p_user=u["id"]), tok), "refused")
            expect(who, "add a report", attempt("POST", "/rest/v1/report_sources", dict(code="A" * 16), tok), "refused")
        logged = {e["action"] for e in call("GET", f"/rest/v1/audit_log?select=action&target=eq.{q(email.split('@')[0])}", cfg=cfg)}
        expect("audit", "throwaway account", sorted(logged & {"account created", "logged in", "approved as staff"}),
               ["account created", "approved as staff", "logged in"])
    finally:
        call("DELETE", f"/auth/v1/admin/users/{u['id']}", cfg=cfg)
    print("probe: " + ("all checks passed" if not fails else f"{len(fails)} FAILED"))
    return not fails


if __name__ == "__main__":
    cfg = config()
    if not cfg: raise SystemExit("no Supabase keys: put them in .supabase at the repository root (see this file's docstring)")
    cmd = sys.argv[1:] or ["status"]
    if cmd[0] == "status": status(cfg)
    elif cmd[0] in ("admin", "staff") and len(cmd) == 2: set_role(cmd[1], cmd[0], cfg)
    elif cmd[0] == "audit": show_audit(cmd[1] if len(cmd) > 1 else 30, cfg)
    elif cmd[0] == "probe": sys.exit(0 if probe(cfg) else 1)
    else: print(__doc__)
