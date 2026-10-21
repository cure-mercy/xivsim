"""Action data from the game files (via XIVAPI): whether an action is on the GCD, its base recast and charges.
Cached in .cache/actions.json. Base values are before traits, so level-90 cooldowns are read off the clears (checks.py).
Also action icons by name, for the site's rotations (cached in .cache/icons/)."""
import base64, json, urllib.parse, urllib.request
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


# --- icons -----------------------------------------------------------------------------------------------------------
SEARCH = "https://v2.xivapi.com/api/search?sheets=Action&query={}&fields=Name,Icon,IsPvP,ClassJob.Abbreviation,ClassJobCategory.Name"
ASSET = "https://v2.xivapi.com/api/asset?path={}&format=png"
ICONS = fflogs.CACHE / "icons"
ABBR = {"Paladin": "PLD", "Warrior": "WAR", "DarkKnight": "DRK", "Gunbreaker": "GNB", "WhiteMage": "WHM", "Scholar": "SCH",
        "Astrologian": "AST", "Sage": "SGE", "Monk": "MNK", "Dragoon": "DRG", "Ninja": "NIN", "Samurai": "SAM", "Reaper": "RPR",
        "Viper": "VPR", "Bard": "BRD", "Machinist": "MCH", "Dancer": "DNC", "BlackMage": "BLM", "Summoner": "SMN",
        "RedMage": "RDM", "Pictomancer": "PCT"}


def _icon_path(name, abbr):
    """The high-resolution icon of the job's PvE action of that name: the job's own, else one its category includes
    (role actions, a base class's spells); None if there is none. Not filtered on IsPlayerAction: actions that replace
    another on the hotbar (Paradox, Void Reaping) are not marked as player actions."""
    q = urllib.parse.quote(f'Name="{name}"')
    with urllib.request.urlopen(urllib.request.Request(SEARCH.format(q), headers=UA), timeout=60) as r:
        rows = [x["fields"] for x in json.load(r)["results"] if not x["fields"].get("IsPvP") and x["fields"].get("Name") == name]
    job = lambda f: ((f.get("ClassJob") or {}).get("fields") or {}).get("Abbreviation")
    cat = lambda f: (((f.get("ClassJobCategory") or {}).get("fields") or {}).get("Name") or "").split()
    pick = next((f for f in rows if job(f) == abbr), None) or next((f for f in rows if abbr in cat(f)), None)
    return pick["Icon"]["path_hr1"] if pick else None


def icons(job, names):
    """{action name: PNG data URI} for a job's actions (job as in the logs, e.g. "BlackMage"); names without an icon are
    left out. Icon paths are cached in .cache/icons/paths.json, the images beside it."""
    ICONS.mkdir(parents=True, exist_ok=True)
    pf = ICONS / "paths.json"
    paths = json.loads(pf.read_text()) if pf.exists() else {}
    abbr, out = ABBR.get(job, job), {}
    for n in sorted(set(names)):
        key = f"{abbr}:{n}"
        if key not in paths:
            try: paths[key] = _icon_path(n, abbr)
            except Exception: continue   # XIVAPI down: try again next time
        if not paths[key]: continue
        f = ICONS / (paths[key].rsplit("/", 1)[-1].replace(".tex", ".png"))
        if not f.exists():
            try:
                with urllib.request.urlopen(urllib.request.Request(ASSET.format(paths[key]), headers=UA), timeout=60) as r: f.write_bytes(r.read())
            except Exception: continue
        out[n] = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
    pf.write_text(json.dumps(paths, indent=1))
    return out
