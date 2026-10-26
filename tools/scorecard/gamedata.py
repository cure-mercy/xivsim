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
# FFLogs' job names, with the game's abbreviation and the role the scorecard compares within
JOBS = {"Paladin": ("PLD", "Tank"), "Warrior": ("WAR", "Tank"), "DarkKnight": ("DRK", "Tank"), "Gunbreaker": ("GNB", "Tank"),
        "WhiteMage": ("WHM", "Healer"), "Scholar": ("SCH", "Healer"), "Astrologian": ("AST", "Healer"), "Sage": ("SGE", "Healer"),
        "Monk": ("MNK", "Melee"), "Dragoon": ("DRG", "Melee"), "Ninja": ("NIN", "Melee"), "Samurai": ("SAM", "Melee"),
        "Reaper": ("RPR", "Melee"), "Viper": ("VPR", "Melee"), "Bard": ("BRD", "Ranged"), "Machinist": ("MCH", "Ranged"),
        "Dancer": ("DNC", "Ranged"), "BlackMage": ("BLM", "Caster"), "Summoner": ("SMN", "Caster"), "RedMage": ("RDM", "Caster"),
        "Pictomancer": ("PCT", "Caster")}
ABBR = {name: abbr for name, (abbr, _) in JOBS.items()}
ROLE = {name: role for name, (_, role) in JOBS.items()}


def _icon_path(name, abbr):
    """The high-resolution icon of the job's PvE action of that name: the job's own, else one its category includes
    (role actions, a base class's spells); None if there is none. Not filtered on IsPlayerAction: actions that replace
    another on the hotbar (Paradox, Void Reaping) are not marked as player actions. A name the game capitalises
    differently (Corps-a-corps, the Forbidden Chakra) is found by a case-blind search, also when the exact name only
    matches a jobless placeholder row (The Forbidden Chakra, The Wanderer's Minuet)."""
    job = lambda f: ((f.get("ClassJob") or {}).get("fields") or {}).get("Abbreviation")
    cat = lambda f: (((f.get("ClassJobCategory") or {}).get("fields") or {}).get("Name") or "").split()
    for op in ("=", "~"):
        q = urllib.parse.quote(f'Name{op}"{name}"')
        with urllib.request.urlopen(urllib.request.Request(SEARCH.format(q), headers=UA), timeout=60) as r:
            rows = [x["fields"] for x in json.load(r)["results"] if not x["fields"].get("IsPvP")
                    and (x["fields"].get("Name") or "").lower() == name.lower()]
        pick = next((f for f in rows if job(f) == abbr), None) or next((f for f in rows if abbr in cat(f)), None)
        if pick: return pick["Icon"]["path_hr1"]
    return None


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
        uri = _asset(paths[key])
        if uri: out[n] = uri
    pf.write_text(json.dumps(paths, indent=1))
    return out


def _asset(path):
    """A game texture as a PNG data URI, the image cached in .cache/icons/; None if XIVAPI can't be reached."""
    f = ICONS / (path.rsplit("/", 1)[-1].replace(".tex", ".png"))
    if not f.exists():
        try:
            with urllib.request.urlopen(urllib.request.Request(ASSET.format(path), headers=UA), timeout=60) as r: f.write_bytes(r.read())
        except Exception: return None
    return "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()


ITEM = "https://v2.xivapi.com/api/sheet/Item?rows={}&fields=Icon"


def item_icons(ids):
    """{item id: PNG data URI} for items (gear, materia, food), the game's 40 px icons (the gear cards draw them at
    32-36 px); ids without an icon are left out. Icon paths are cached in .cache/icons/items.json."""
    ICONS.mkdir(parents=True, exist_ok=True)
    pf = ICONS / "items.json"
    paths = json.loads(pf.read_text()) if pf.exists() else {}
    want = sorted(str(i) for i in ids if str(i) not in paths)
    for k in range(0, len(want), 100):
        try:
            for r in _get(ITEM.format(",".join(want[k:k + 100]))):
                paths[str(r["row_id"])] = ((r["fields"] or {}).get("Icon") or {}).get("path")
        except Exception: break   # XIVAPI down: try again next time
    pf.write_text(json.dumps(paths, indent=1))
    out = {}
    for i in ids:
        uri = paths.get(str(i)) and _asset(paths[str(i)])
        if uri: out[str(i)] = uri
    return out


# the jobs' ClassJob rows; the game's job icon (the role-coloured frame of the party list) is icon 062100 + row
CLASSJOB = {"PLD": 19, "MNK": 20, "WAR": 21, "DRG": 22, "BRD": 23, "WHM": 24, "BLM": 25, "SMN": 27, "SCH": 28, "NIN": 30,
            "MCH": 31, "DRK": 32, "AST": 33, "SAM": 34, "RDM": 35, "GNB": 37, "DNC": 38, "RPR": 39, "SGE": 40, "VPR": 41,
            "PCT": 42}


def job_icon(job):
    """The job's icon as a PNG data URI (job as in the logs, e.g. "BlackMage"); None for an unknown job or no XIVAPI."""
    row = CLASSJOB.get(ABBR.get(job, job))
    if not row: return None
    ICONS.mkdir(parents=True, exist_ok=True)
    return _asset(f"ui/icon/062000/{62100 + row:06d}_hr1.tex")
