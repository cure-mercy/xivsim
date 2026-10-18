"""A small FFLogs v2 client: token, GraphQL with retries, paged events and batched tables.

Credentials come from .fflogs_v2 at the repository root (git-excluded), two KEY=value lines whose keys end in
_ID and _SECRET. The bearer token is cached in .cache/token.json next to this file until it expires.
"""
import base64, json, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / ".cache"
API = "https://www.fflogs.com/api/v2/client"
TOKEN_URL = "https://www.fflogs.com/oauth/token"


def _credentials():
    kv = dict(l.split("=", 1) for l in (ROOT / ".fflogs_v2").read_text().split() if "=" in l)
    cid = next(v for k, v in kv.items() if k.upper().endswith("_ID"))
    secret = next(v for k, v in kv.items() if k.upper().endswith("_SECRET"))
    return cid, secret


def token():
    CACHE.mkdir(exist_ok=True)
    tf = CACHE / "token.json"
    if tf.exists():
        t = json.loads(tf.read_text())
        if t.get("expires_at", 0) > time.time() + 3600: return t["access_token"]
    cid, secret = _credentials()
    req = urllib.request.Request(TOKEN_URL, data=b"grant_type=client_credentials",
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=60) as r: t = json.load(r)
    t["expires_at"] = time.time() + t.get("expires_in", 0)
    tf.write_text(json.dumps(t))
    return t["access_token"]


def gql(query, variables=None, tries=30):
    """Run a query; waits out rate limits and transient errors instead of failing."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(API, data=body, headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r: res = json.load(r)
            if "errors" not in res: return res["data"]
            msg = res["errors"][0].get("message", "")
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
