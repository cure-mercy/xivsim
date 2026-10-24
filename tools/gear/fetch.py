"""Builds gear_db.json from xivgear.app's data API: the gear, materia and food the P12S gear model chooses from.

    python tools/gear/fetch.py [--refresh]

Kept: every DPS job's gear at item level 640-669 (the level-90 savage, tomestone, crafted and Criterion gear, and the
level-91+ gear that syncs down) and 780 up (level-100 gear, synced to the 660 caps), plus two relics: the
Mandervillous weapons (665) and the newest Phantom weapons (Occultum, 795). Also the ItemLevel rows those need (stat
values per item level), the BaseParams (each stat's share per slot and meld parameter), the job stat multipliers,
substat materia and food. The API's downloads (~9 MB a job) are cached in .cache/.
"""
import argparse, json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
DB = HERE / "gear_db.json"
API = "https://data.xivgear.app"
JOBS = ["BLM", "SMN", "RDM", "PCT", "BRD", "MCH", "DNC", "MNK", "DRG", "NIN", "SAM", "RPR", "VPR"]
BANDS = [(640, 669), (780, 999)]
RELICS = ("Mandervillous ", "Phantom ")              # relic names start so; of the Phantom ones only the newest (ilvl)
SYNC = 660                                          # level 90's item level: gear above level 90 syncs to it
# BaseParam ids: main stats, substats, weapon damage
STATS = {1: "str", 2: "dex", 3: "vit", 4: "int", 5: "mnd", 6: "pie", 19: "ten", 22: "dh", 27: "crit", 44: "det",
         45: "sks", 46: "sps", 12: "wdPhys", 13: "wdMag"}
SUBSTATS = ("crit", "dh", "det", "sks", "sps")
SLOTS = ("head", "body", "gloves", "legs", "feet", "ears", "neck", "wrists", "fingerL")
ILVL_KEYS = {"str": "strength", "dex": "dexterity", "vit": "vitality", "int": "intelligence", "mnd": "mind",
             "pie": "piety", "ten": "tenacity", "dh": "directHitRate", "crit": "criticalHit", "det": "determination",
             "sks": "skillSpeed", "sps": "spellSpeed", "wdPhys": "physicalDamage", "wdMag": "magicalDamage"}
SLOT_KEYS = {"weapon": "twoHandWeaponPercent", "head": "headPercent", "body": "chestPercent",
             "gloves": "handsPercent", "legs": "legsPercent", "feet": "feetPercent", "ears": "earringPercent",
             "neck": "necklacePercent", "wrists": "braceletPercent", "ring": "ringPercent"}


def _get(path, name, refresh=False):
    f = CACHE / name
    if refresh or not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sfL", "-m", "300", "-o", str(f), API + path], check=True)
    return json.loads(f.read_text(encoding="utf-8"))["items"]


def _slot(cat):
    """The item's slot: weapon (two-handed: every DPS job's), an armour slot or ring; None for an off-hand."""
    if cat["mainHand"]: return "weapon"
    if cat["fingerL"] or cat["fingerR"]: return "ring"
    return next((s for s in SLOTS if cat[s]), None)


def _stats(m):
    return {STATS[int(k)]: v for k, v in m.items() if int(k) in STATS and v}


def _keep(it):
    i = it["ilvl"]
    if it["acquisitionSource"] == "Relic":
        return it["name"].startswith(RELICS)
    return any(lo <= i <= hi for lo, hi in BANDS) and it["equipLevel"] >= 90


def build(refresh=False):
    items = {}
    for job in JOBS:
        for it in _get(f"/Items?job={job}", f"items_{job}.json", refresh):
            if not _keep(it): continue
            slot = _slot(it["equipSlotCategory"])
            if slot is None: continue
            row = items.setdefault(it["rowId"], dict(
                id=it["rowId"], name=it["name"], ilvl=it["ilvl"], level=it["equipLevel"], slot=slot,
                source=it["acquisitionSource"], unique=it["unique"], rarity=it["rarity"],
                stats=_stats(it["baseParamMapHQ"] if it["canBeHq"] else it["baseParamMap"]),
                wdPhys=it["damagePhysHQ"] if it["canBeHq"] else it["damagePhys"],
                wdMag=it["damageMagHQ"] if it["canBeHq"] else it["damageMag"],
                delay=it["delayMs"] / 1000, slots=it["materiaSlotCount"], overmeld=it["advancedMeldingPermitted"],
                meldParam=it["meldParamIndex"], jobs=[]))
            row["jobs"].append(job)
    # of the Phantom relics only the newest stage (the highest item level)
    top = max(i["ilvl"] for i in items.values() if i["name"].startswith("Phantom "))
    items = {k: v for k, v in items.items() if not (v["name"].startswith("Phantom ") and v["ilvl"] < top)}

    ilvls = sorted({i["ilvl"] for i in items.values()} | {SYNC})
    il = {r["rowId"]: r for r in _get("/ItemLevel", "itemlevel.json", refresh)}
    ilvl = {str(n): {k: il[n][v] for k, v in ILVL_KEYS.items()} for n in ilvls}

    bp = {}
    for r in _get("/BaseParams", "baseparams.json", refresh):
        if r["rowId"] in STATS:
            bp[STATS[r["rowId"]]] = dict(slots={s: r[k] for s, k in SLOT_KEYS.items()}, meldParam=r["meldParam"])

    jobs = {r["abbreviation"]: dict(str=r["modifierStrength"], dex=r["modifierDexterity"],
                                    int=r["modifierIntelligence"], mnd=r["modifierMind"], vit=r["modifierVitality"])
            for r in _get("/Jobs", "jobs.json", refresh) if r["abbreviation"] in JOBS}

    materia = []
    for r in _get("/Materia", "materia.json", refresh):
        stat = STATS.get(r["baseParam"])
        if stat not in SUBSTATS: continue
        for g, (v, item) in enumerate(zip(r["value"], r["item"]), start=1):
            if v and item:
                materia.append(dict(stat=stat, grade=g, value=v, ilvl=item.get("ilvl", 0), id=item["rowId"],
                                    name=item["name"]))

    food = []
    for r in _get("/Food", "food.json", refresh):
        b = {STATS[int(k)]: dict(pct=v["percentage"], max=v["max"]) for k, v in r["bonusesHQ"].items()
             if int(k) in STATS and v["max"]}
        if set(b) & set(SUBSTATS):
            food.append(dict(id=r["rowId"], name=r["name"], ilvl=r["levelItem"], bonus=b))

    db = dict(source=API, sync=SYNC, jobs=jobs, baseParams=bp, ilvl=ilvl, materia=materia, food=food,
              items=sorted(items.values(), key=lambda i: (i["slot"], i["ilvl"], i["id"])))
    DB.write_text(json.dumps(db, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{DB.name}: {len(db['items'])} items, {len(materia)} materia, {len(food)} foods, ilvls {ilvls}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download again instead of using .cache/")
    build(ap.parse_args().refresh)
