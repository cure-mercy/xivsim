"""Action data from the game files (via XIVAPI): whether an action is on the GCD, its base recast and charges.
Cached in .cache/actions.json. Base values are before traits, so level-90 cooldowns are read off the clears (checks.py)."""
import json, urllib.request
import fflogs

URL = ("https://v2.xivapi.com/api/sheet/Action?rows={}&fields=Name,ActionCategory.Name,CooldownGroup,"
       "AdditionalCooldownGroup,Recast100ms,MaxCharges,IsPlayerAction,ActionCombo")
GCD_GROUP = 58
CF = fflogs.CACHE / "actions.json"
UA = {"User-Agent": "xivsim-scorecard/1.0"}      # XIVAPI refuses Python's default user agent


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: return json.load(r)["rows"]


def actions(ids):
    """{action id: dict(name, gcd, category, recast, charges, combo)} for the ids that are game actions; combo is the
    action that has to come right before for the combo bonus (0 for none)."""
    have = json.loads(CF.read_text()) if CF.exists() else {}
    have = {k: v for k, v in have.items() if v is None or "combo" in v}     # entries cached before combo was read
    want = sorted({int(i) for i in ids if 0 < int(i) < 100000 and str(int(i)) not in have})
    for i in range(0, len(want), 100):
        part = want[i:i + 100]
        try:
            rows = _get(URL.format(",".join(map(str, part))))
        except Exception:
            rows = []
            for a in part:   # a bad id fails the whole request: fall back to one at a time
                try: rows += _get(URL.format(a))
                except Exception: have[str(a)] = None
        for r in rows:
            f = r["fields"]
            have[str(r["row_id"])] = dict(name=f["Name"], gcd=GCD_GROUP in (f["CooldownGroup"], f["AdditionalCooldownGroup"]),
                                          category=(f.get("ActionCategory") or {}).get("fields", {}).get("Name"),
                                          recast=f["Recast100ms"] / 10, charges=f["MaxCharges"],
                                          combo=(f.get("ActionCombo") or {}).get("row_id") or 0)
        for a in part: have.setdefault(str(a), None)
    CF.write_text(json.dumps(have))
    return {int(k): v for k, v in have.items() if v and int(k) in {int(i) for i in ids}}
