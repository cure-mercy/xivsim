"""Casts and outgoing damage per pull, for burst alignment and ability-level comparisons with same-job clearers.

Each pull is kept compactly, times in seconds from the pull:
    players  {id: [name, job]}
    casts    [[t, player id, ability id], ...]           finished casts only, from 30 s before the pull
    dmg      [[t, player id, ability id, amount], ...]   hits on enemies; pets count for their owner
    names    {ability id: name}
Our reports are cached in .cache/acts_{code}.json, the benchmark's kills in .cache/benchmark/acts_{code}_{fight}.json.
"""
import json
import fflogs

# raid buffs by the name of the cast that grants them; all last 20 s and land about 0.6 s after the cast
RAID_BUFFS = {"Divination": "Astrologian", "Quadruple Technical Finish": "Dancer", "Technical Finish": "Dancer", "Brotherhood": "Monk",
              "Battle Litany": "Dragoon", "Chain Stratagem": "Scholar", "Embolden": "RedMage", "Searing Light": "Summoner",
              "Arcane Circle": "Reaper", "Dokumori": "Ninja", "Mug": "Ninja", "Radiant Finale": "Bard", "Battle Voice": "Bard",
              "Starry Muse": "Pictomancer"}
BUFF_S, BUFF_DELAY = 20, 0.6
DOT = 500000                    # FFLogs reports damage-over-time ticks under this one ability id
NAMES = {DOT: "DoT ticks"}

META = '''query($c:String!,$f:[Int]!){reportData{report(code:$c){
    fights(fightIDs:$f){id startTime endTime friendlyPlayers}
    masterData{players:actors(type:"Player"){id name subType} pets:actors(type:"Pet"){id petOwner} abilities{gameID name}}}}}'''


def pulls(code, ids):
    """{fight id: pull} for the given fights of one report."""
    r = fflogs.gql(META, {"c": code, "f": list(ids)})["reportData"]["report"]
    fights, md = r["fights"], r["masterData"]
    owner = {a["id"]: a["petOwner"] for a in md["pets"]}
    names = {**{a["gameID"]: a["name"] for a in md["abilities"]}, **NAMES}
    casts = fflogs.events(code, fights, "Casts")
    dmg = fflogs.events(code, fights, "DamageDone")
    out = {}
    for f in fights:
        s, fp = f["startTime"], set(f["friendlyPlayers"] or [])
        players = {a["id"]: [a["name"], a["subType"]] for a in md["players"] if a["id"] in fp and a["subType"] != "LimitBreak"}
        c = [[round((x["timestamp"] - s) / 1000, 2), x["sourceID"], x["abilityGameID"]] for x in casts
             if x.get("fight") == f["id"] and x["type"] == "cast" and x.get("sourceID") in players]
        d = [[round((x["timestamp"] - s) / 1000, 2), owner.get(x.get("sourceID"), x.get("sourceID")), x["abilityGameID"], x["amount"]] for x in dmg
             if x.get("fight") == f["id"] and x["type"] == "damage" and x.get("amount", 0) > 0 and x.get("targetID") not in players
             and owner.get(x.get("sourceID"), x.get("sourceID")) in players]
        used = {a for _, _, a in c} | {a for _, _, a, _ in d}
        out[f["id"]] = dict(start=s, end=round((f["endTime"] - s) / 1000, 2), players={str(k): v for k, v in players.items()},
                            casts=c, dmg=d, names={str(a): names.get(a, str(a)) for a in sorted(used)})
    return out


def report(code, fights, refresh=False):
    """Every pull of one of our reports, cached."""
    cf = fflogs.CACHE / f"acts_{code}.json"
    have = {} if refresh or not cf.exists() else json.loads(cf.read_text())
    missing = [f["id"] for f in fights if str(f["id"]) not in have]
    if missing:
        have.update({str(k): v for k, v in pulls(code, missing).items()})
        cf.write_text(json.dumps(have))
    return have


def buff_uses(p):
    """[(t the buff lands, buff name, job, player id)], one entry per use (Technical Finish logs two casts)."""
    out, last = [], {}
    for t, src, a in p["casts"]:
        n = p["names"].get(str(a))
        if n not in RAID_BUFFS: continue
        n = "Technical Finish" if "Technical" in n else n
        if t - last.get((src, n), -99) < 3: continue
        last[(src, n)] = t
        out.append((round(t + BUFF_DELAY, 2), n, p["players"][str(src)][1], src))
    return out
