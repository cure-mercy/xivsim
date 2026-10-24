"""Checks of the gear model's rules on gear_db.json: sync, caps, materia, relics, rings, food and the level-90 formulas.

    python tools/gear/check.py

Exits non-zero on a failure. The damage formula itself was checked against our groups' logs (each DPS uploader's
logged stats against their measured damage per potency, 2026-10-23: within 1.4%; scratch/gear/kcheck.py).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gear, bis          # noqa: E402

FAILS = []


def ok(cond, what):
    print(f"  {'ok  ' if cond else 'FAIL'} {what}")
    if not cond: FAILS.append(what)


def item(name):
    return gear.Item(next(r for r in gear.DB["items"] if r["name"] == name))


def main():
    print("sync")
    asc, occ, mdv = item("Rod of Ascension"), item("Phantom Staff Occultum"), item("Mandervillous Rod")
    ok(not asc.synced and len(asc.melds) == 2, "a level-90 665 weapon keeps its stats and two melds")
    body = item("Grand Champion's Coat of Casting")
    ok(body.synced and not body.melds, "level-100 gear is synced and loses its materia")
    ok(body.stats["int"] == item("Ascension Robe of Casting").stats["int"] and body.stats["crit"] == body.stats["det"] == 292,
       "synced 790 body: main stat and both substats at the 660 body cap (292)")
    ok(occ.stats["int"] == 409 and occ.stats["wdMag"] == 131, "a level-100 weapon syncs to 660 (409, weapon damage 131)")
    lvl93 = next(gear.Item(r) for r in gear.DB["items"] if r["level"] == 93 and r["ilvl"] == 660)
    ok(lvl93.synced and not lvl93.melds, "level-93 gear at 660 is synced: its materia is off")
    caps = [i for i in map(gear.Item, gear.DB["items"]) if not i.synced and not i.relic and set(i.row["stats"]) & set(gear.SUBSTATS)]
    ok(all(max((v, k) for k, v in i.row["stats"].items() if k in gear.SUBSTATS)[0]
           == i.caps[max((v, k) for k, v in i.row["stats"].items() if k in gear.SUBSTATS)[1]] for i in caps),
       f"every unsynced item's larger substat sits at its computed cap ({len(caps)} items)")

    print("materia")
    v = dict(asc.variants("BLM"))
    ok(v["crit+crit"]["crit"] == 306 and v["dh+dh"]["dh"] == 72, "melds stop at the item's cap (crit 306 stays 306)")
    craft = item("Diadochos Rod")
    ok([m[0] for m in craft.melds] == [36, 36, 36, 12, 12], "crafted overmeld: X, X, X, then IX, IX")
    ok(all(m["ilvl"] >= 690 for m in gear.DB["materia"] if m["value"] in (18, 54)),
       "Materia XI and XII need item level 690 (none fit level-90 gear)")

    print("relics")
    rv = dict(mdv.variants("BLM"))
    m = rv["relic crit/det +dh"]
    ok((m["crit"], m["det"], m["dh"]) == (306, 306, 72), "Mandervillous: two substats at 306, one at 72")
    o = dict(occ.variants("BLM"))["relic crit/det +dh"]
    ok((o["crit"], o["det"], o["dh"]) == (303, 303, 108), "Occultum synced: two at the 660 cap (303), one at 108")

    print("rings")
    cands = bis.candidates("BLM")
    ok(all(not (a.id == b.id and a.unique) for _, ((a, _), (b, _)) in cands["ring"]), "no unique ring twice")

    print("stats")
    s = gear.Stats("BLM", (0, 0, 2114, 0, 0, 0))                     # crit 2514
    ok(s.crit_rate == 0.272 and s.crit_dmg == 1.622, "crit 2514: 27.2%, x1.622")
    ok(gear.Stats("BLM", (0, 0, 0, 0, 0, 620)).gcd() == 2.39, "spell speed 1020: 2.39 s")
    ok(gear.Stats("MNK", (0, 0, 0, 0, 0, 0)).gcd() == 2.0, "Monk at base speed: 2.50 s x 0.8 = 2.00 s")
    f = gear.Stats("BLM", (0, 0, 2000, 0, 0, 0), {"crit": (10, 151)})
    ok(f.crit == 2400 + 151, "food: 10% of gear and base, up to its max")
    full = sum(gear.cap("int", s_, 660, None) for s_ in ("head", "body", "gloves", "legs", "feet", "ears", "neck",
                                                        "wrists", "ring", "ring", "weapon"))
    ok(gear.Stats("BLM", (full, 0, 0, 0, 0, 0)).main == 3540,
       "capped gear at 660, +3 clan and +5% party: 3540 (our uploaders log 3514-3540)")

    print("rotation model: rounding and own rates")
    sys.path.insert(0, str(HERE.parent / "rotation"))
    import engine
    ok((engine.recast(2.5, 0.960, 0.87), engine.recast(2.5, 0.962, 0.87)) == (2.08, 2.09),
       "a 2.40 s GCD under Fuka: 2.08 or 2.09 s by the speed factor (the engine took 2.088)")
    ok(engine.recast(2.5, 0.972, 0.8) == 1.94 and engine.recast(2.0, 0.928, 0.85) == 1.57,
       "Monk's 1.94 s; a 2.0 s cast at 0.928 under Ley Lines 1.57 s")
    ok([bis.tier_speed("SAM", t) for t in ((2.40, 2.08), (2.40, 2.09))] == [0.96, 0.962],
       "Samurai's 2.40 s tier splits by its hasted GCD")
    sam = engine.configure("sam", 0.96, (220, 0.5, 0.0), {"CRIT_RATE": 0.30, "CRIT_DMG": 1.65})
    ok(abs(sam.SURE_W - 1.65 / (1 + 0.30 * 0.65)) < 1e-12, "engine.configure reruns derive(): SURE_W from the set's rates")
    sam.CRIT_RATE, sam.CRIT_DMG = 0.25, 1.60; sam.derive()
    s = gear.Stats("DNC", (0, 0, 2000, 1000, 0, 0))
    m = bis.Mix(0, sure=1.0)
    ok(abs(bis.value("DNC", s, m) / (s.trait * s.sure_crit_dh()) - round(1 + (s.crit_dmg - 1) * 0.2, 3) * 1.05) < 1e-9,
       "Starfall under Devilment: its crit and direct-hit rate taken as damage")

    print("site ceiling: crit and direct-hit luck")
    import ceiling
    s = gear.Stats("RPR", (0, 0, 2000, 1000, 0, 0))
    p, c, q = s.crit_rate, s.crit_dmg, s.dh_rate
    outcomes = [(p * q, c * 1.25), (p * (1 - q), c), ((1 - p) * q, 1.25), ((1 - p) * (1 - q), 1.0)]
    mean = sum(w * x for w, x in outcomes)
    var = sum(w * x * x for w, x in outcomes) - mean * mean
    K = s.trait * s.main_multi * s.det_multi * s.wd_multi
    one = lambda kind: {k: (1.0, 1.0) if k == kind else (0.0, 0.0) for k in ("normal", "auto", "sure", "dot")}
    ok(abs(ceiling.spread("RPR", s, one("normal")) - K * var ** 0.5) < 1e-9, "a hit's spread: the four crit x direct-hit outcomes")
    t = gear.Stats("SAM", (0, 0, 2000, 1000, 0, 0))
    Kt, ct, qt = t.trait * t.main_multi * t.det_multi * t.wd_multi, t.crit_dmg, t.dh_rate
    ok(abs(ceiling.spread("SAM", t, one("sure")) - Kt * ct * (qt * 1.5625 + (1 - qt) - (qt * 1.25 + 1 - qt) ** 2) ** 0.5) < 1e-9,
       "a sure crit varies by its direct hit only")
    ok(ceiling.spread("MCH", gear.Stats("MCH", (0, 0, 2000, 1000, 0, 0)), one("sure")) == 0
       and ceiling.spread("MCH", gear.Stats("MCH", (0, 0, 2000, 1000, 0, 0)), one("dot")) == 0,
       "sure critical direct hits and Wildfire don't vary")

    print("combined search: the span")
    first = {(2.50, 2.12): (1.0,), (2.38, 2.02): (0.955,), (2.18, 1.85): (0.886,), (2.10, 1.79): (0.80,)}
    ok(bis.span_of("BLM", first) == [(2.50, 2.12), (2.38, 2.02), (2.18, 1.85)],
       "a faster tier stays while its multipliers times the GCDs' ratio can reach the best (Black Mage's 2.18 s at 0.886)")

    print("site sets (sheets.py)")
    import sheets
    js = {k: sheets.sheet(k.lower()) for k in gear.JOBS}
    js = {k: v for k, v in js.items() if v}
    ok(all(tuple(sum(i["final"].get(k, 0) for i in x["items"]) for k in gear.KEYS) == tuple(x["totals"])
           for v in js.values() for x in v["sets"]),
       f"every set's items, rebuilt from their fills, add up to the saved totals ({len(js)} jobs)")
    ok(all(len(x["items"]) == 11 and sum(i["slot"] == "ring" for i in x["items"]) == 2 for v in js.values() for x in v["sets"]),
       "every set has eleven items, two of them rings")
    ok(all(not i["melds"] for v in js.values() for x in v["sets"] for i in x["items"] if i["synced"]),
       "synced items show no materia")

    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
