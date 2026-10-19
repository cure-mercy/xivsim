"""A small FFLogs v2 client: token, GraphQL with retries, paged events and batched tables.

Credentials come from .fflogs_v2 at the repository root (git-excluded), two KEY=value lines whose keys end in
_ID and _SECRET. The app's bearer token is cached in .cache/token.json next to this file until it expires.

Archived reports are only readable through FFLogs' user API, as the subscribing account. Log in once to get a user
token (saved in .cache/user_token.json); after that, queries refused as archived are retried through the user API:

    python tools/scorecard/fflogs.py --login [--redirect http://localhost:8765/fflogs-callback]
    python tools/scorecard/fflogs.py --check      # can an archived report be read?

The redirect address has to be registered on the API client at https://www.fflogs.com/api/clients/ first.
"""
import argparse, base64, hashlib, http.server, json, secrets, threading, time, urllib.error, urllib.parse, urllib.request, webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / ".cache"
API = "https://www.fflogs.com/api/v2/client"
USER_API = "https://www.fflogs.com/api/v2/user"
TOKEN_URL = "https://www.fflogs.com/oauth/token"
AUTHORIZE_URL = "https://www.fflogs.com/oauth/authorize"
REDIRECT = "http://localhost:8765/fflogs-callback"
ARCHIVED_SAMPLE = "hJR9wbKYB8ynCTLH"   # a P12S report from February 2024, archived


def _credentials():
    kv = dict(l.split("=", 1) for l in (ROOT / ".fflogs_v2").read_text().split() if "=" in l)
    cid = next(v for k, v in kv.items() if k.upper().endswith("_ID"))
    secret = next(v for k, v in kv.items() if k.upper().endswith("_SECRET"))
    return cid, secret


def _post_token(form, basic=True):
    cid, secret = _credentials()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if basic: headers["Authorization"] = "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(form).encode(), headers=headers), timeout=60) as r:
        t = json.load(r)
    t["expires_at"] = time.time() + t.get("expires_in", 0)
    return t


def token():
    """The app's token (client credentials): reads every public report."""
    CACHE.mkdir(exist_ok=True)
    tf = CACHE / "token.json"
    if tf.exists():
        t = json.loads(tf.read_text())
        if t.get("expires_at", 0) > time.time() + 3600: return t["access_token"]
    t = _post_token({"grant_type": "client_credentials"})
    tf.write_text(json.dumps(t))
    return t["access_token"]


def user_token():
    """The logged-in account's token, refreshed when it can be; None if nobody has logged in."""
    tf = CACHE / "user_token.json"
    if not tf.exists(): return None
    t = json.loads(tf.read_text())
    if t.get("expires_at", 0) > time.time() + 300: return t["access_token"]
    if not t.get("refresh_token"): return None
    try:
        n = _post_token({"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
    except urllib.error.HTTPError:
        return None
    n.setdefault("refresh_token", t["refresh_token"])
    tf.write_text(json.dumps(n))
    return n["access_token"]


def login(redirect=REDIRECT, timeout=300):
    """Authorization code flow with PKCE: the browser signs in at FFLogs, a local listener receives the code."""
    cid, secret = _credentials()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(dict(client_id=cid, code_challenge=challenge, code_challenge_method="S256",
                                                            state=state, redirect_uri=redirect, response_type="code"))
    got = {}
    target = urllib.parse.urlparse(redirect)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if u.path != target.path: self.send_response(404); self.end_headers(); return
            q = dict(urllib.parse.parse_qsl(u.query)); got.update(q)
            ok = q.get("state") == state and "code" in q
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(("<p>Logged in to FFLogs; you can close this tab.</p>" if ok else
                              "<p>Login did not complete: " + (q.get("error_description") or q.get("error") or "unexpected reply") + "</p>").encode())

        def log_message(self, *a): pass

    srv = http.server.HTTPServer((target.hostname, target.port or 80), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Opening the FFLogs sign-in page. If no browser opens, visit:\n  {url}")
    webbrowser.open(url)
    t0 = time.time()
    while "code" not in got and "error" not in got and time.time() - t0 < timeout: time.sleep(0.2)
    srv.shutdown()
    if got.get("state") != state or "code" not in got:
        raise SystemExit(f"login failed: {got.get('error_description') or got.get('error') or 'no reply within the time limit'}")
    t = _post_token(dict(grant_type="authorization_code", client_id=cid, client_secret=secret, code=got["code"],
                         code_verifier=verifier, redirect_uri=redirect), basic=False)
    CACHE.mkdir(exist_ok=True)
    (CACHE / "user_token.json").write_text(json.dumps(t))
    days = t.get("expires_in", 0) / 86400
    print(f"Logged in. The user token is saved in {CACHE / 'user_token.json'} (valid {days:.0f} days"
          f"{', renewed automatically' if t.get('refresh_token') else '; log in again then'}).")


def gql(query, variables=None, tries=30):
    """Run a query; waits out rate limits and transient errors instead of failing. A report refused as archived
    is asked for again through the user API when someone has logged in."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    api, tok = API, token
    for attempt in range(tries):
        try:
            req = urllib.request.Request(api, data=body, headers={"Authorization": f"Bearer {tok()}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r: res = json.load(r)
            if "errors" not in res: return res["data"]
            msg = res["errors"][0].get("message", "")
            if "archived" in msg.lower() and api == API and user_token():
                api, tok = USER_API, user_token; continue
            if "rate" not in msg.lower() and "timeout" not in msg.lower(): raise RuntimeError(msg)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504): raise
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(min(120, 5 * (attempt + 1)))
    raise RuntimeError("FFLogs API kept failing")


EVENTS = '''query($c:String!,$f:[Int]!,$s:Float!,$e:Float!,$dt:EventDataType!,$h:HostilityType,$fx:String,$res:Boolean){
  reportData{report(code:$c){events(fightIDs:$f,startTime:$s,endTime:$e,dataType:$dt,hostilityType:$h,
  filterExpression:$fx,includeResources:$res,limit:10000){data nextPageTimestamp}}}}'''


def events(code, fights, data_type, hostility="Friendlies", filter=None, resources=False):
    s, e = min(f["startTime"] for f in fights) - 30000, max(f["endTime"] for f in fights)
    out = []
    while s is not None:
        p = gql(EVENTS, {"c": code, "f": [f["id"] for f in fights], "s": s, "e": e, "dt": data_type, "h": hostility,
                         "fx": filter, "res": resources})["reportData"]["report"]["events"]
        out += p["data"]; s = p["nextPageTimestamp"]
    return out


def tables(code, windows, data_type="DamageDone", extra="", batch=20):
    """One table per (start, end) window, many per query through aliases."""
    out = []
    for i in range(0, len(windows), batch):
        part = windows[i:i + batch]
        q = "query($c:String!){reportData{report(code:$c){" + " ".join(
            f"t{j}:table(dataType:{data_type},startTime:{s},endTime:{e}{extra})" for j, (s, e) in enumerate(part)) + "}}}"
        r = gql(q, {"c": code})["reportData"]["report"]
        out += [r[f"t{j}"]["data"] for j in range(len(part))]
    return out


def report_code(link):
    """Accepts a full FFLogs report link (with or without #fight=...) or a bare code."""
    path = urllib.parse.urlparse(link).path or link
    return [p for p in path.split("/") if p][-1].split("#")[0]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FFLogs login for archived reports")
    ap.add_argument("--login", action="store_true", help="sign in as the subscribing account (opens a browser)")
    ap.add_argument("--redirect", default=REDIRECT, help=f"the redirect address registered on the API client (default {REDIRECT})")
    ap.add_argument("--check", action="store_true", help="try to read an archived report")
    a = ap.parse_args()
    if a.login: login(a.redirect)
    if a.check or a.login:
        print("user token:", "present" if user_token() else "none (run --login)")
        try:
            # the fight list stays public; the content (events, tables) is what archiving locks
            f = gql("query($c:String!){reportData{report(code:$c){fights{id}}}}", {"c": ARCHIVED_SAMPLE})["reportData"]["report"]["fights"]
            r = gql("query($c:String!,$f:[Int]!){reportData{report(code:$c){events(fightIDs:$f,dataType:Deaths,limit:5){data}}}}",
                    {"c": ARCHIVED_SAMPLE, "f": [x["id"] for x in f]})
            print(f"archived report {ARCHIVED_SAMPLE}: readable ({len(r['reportData']['report']['events']['data'])} death events fetched)")
        except RuntimeError as e:
            print(f"archived report {ARCHIVED_SAMPLE}: not readable ({e})")
    if not (a.login or a.check): ap.print_help()
