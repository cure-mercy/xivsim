"""The gear model for P12S: items under the level-90 / item-level sync, materia, food, and a set's stats and damage
multipliers, after xivgear.app's rules and formulas (github.com/xiv-gear-planner/gear-planner, packages/xivmath).

    python tools/gear/gear.py --caps                      # per slot: from which item level every stat syncs to the cap
    python tools/gear/gear.py --job blm --items body      # a slot's items for a job, as the fight sees them

The fight syncs the player to level 90 without an item-level sync: an item above level 90 is synced down to level 90's
item level, 660, weapons too (every stat cut to the slot's cap at 660), and its materia is off. Level-90 gear is never
synced, so the 665 weapons keep their stats and materia. Our groups' logged main stats (3514-3540, every DPS and healer
uploader) are those of capped gear at 660 throughout; a weapon at 665 would give 3544 or more. xivgear's in-instance
tests (its issue 317) say the same. A meld adds up to the item's own cap for that stat. Level-90 gear (at most 665)
takes Materia X (36) and IX (12): XI and XII need item level 690. Crafted gear that allows overmelding has five slots,
the fourth and fifth for IX only.

Relics have no fixed substats. Mandervillous (665): two at the cap and one at 72; Phantom Occultum (795): two at its own
cap and one at 108, then synced like any other level-100 item (two at the 660 cap, the 108 under it).

Stats: base main stat 390 x the job's modifier, +3 for the clan, substats 400 (determination 390), the gear, food (8-10%
of the gear and base, up to its maximum; not synced), then +5% main stat for a full party's five roles.
"""
import argparse, itertools, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = json.loads((HERE / "gear_db.json").read_text(encoding="utf-8"))

# level 90 (xivconstants LEVEL_STATS)
MAIN, SUB, DIV, AP_MOD = 390, 400, 1900, 195
CLAN = 3                       # every main stat has a +3 clan
PARTY = 5                      # % main stat: five roles in the party
SUBSTATS = ("crit", "dh", "det", "sks", "sps")
MATERIA_X, MATERIA_IX = 36, 12

JOBS = {   # main stat, speed stat, trait multiplier (Magic and Mend II, Increased Action Damage II), trait haste %
    "BLM": ("int", "sps", 1.3, 0), "SMN": ("int", "sps", 1.3, 0), "RDM": ("int", "sps", 1.3, 0),
    "PCT": ("int", "sps", 1.3, 0), "BRD": ("dex", "sks", 1.2, 0), "MCH": ("dex", "sks", 1.2, 0),
    "DNC": ("dex", "sks", 1.2, 0), "NIN": ("dex", "sks", 1.0, 15), "VPR": ("dex", "sks", 1.0, 0),
    "MNK": ("str", "sks", 1.0, 20), "DRG": ("str", "sks", 1.0, 0), "SAM": ("str", "sks", 1.0, 0),
    "RPR": ("str", "sks", 1.0, 0)}
CASTER = {"BLM", "SMN", "RDM", "PCT"}


def fl(x):
    return math.floor(x + 1e-9)


def _round(x):
    """JavaScript's Math.round: halves go up."""
    return math.floor(x + 0.5)


def cap(stat, slot, ilvl, meld_param):
    """The most of `stat` an item of `slot` at `ilvl` can hold (xivmath statCapWithJob)."""
    v = DB["ilvl"][str(ilvl)][stat]
    bp = DB["baseParams"][stat]
    pct = bp["slots"][slot]
    if not v or not pct: return None
    mp = bp["meldParam"][meld_param] if meld_param is not None and meld_param < len(bp["meldParam"]) else 100
    return _round(fl(fl(v * mp / 100) * pct / 100) / 10)


class Item:
    """An item as the fight sees it: `stats` after sync (relic substats not yet chosen), `room` per stat for melds,
    `melds` the materia slots it keeps ((value of the best grade, high grade allowed), ...)."""

    def __init__(self, row):
        self.row, self.id, self.name, self.slot = row, row["id"], row["name"], row["slot"]
        self.ilvl, self.unique = row["ilvl"], row["unique"]
        sync = DB["sync"]
        self.synced = row["level"] > 90
        stats = dict(row["stats"], wdPhys=row["wdPhys"], wdMag=row["wdMag"])
        stats = {k: v for k, v in stats.items() if v}
        native = {k: cap(k, self.slot, row["ilvl"], row["meldParam"]) for k in set(stats) | set(SUBSTATS)}
        if self.synced:
            at = {k: cap(k, self.slot, sync, row["meldParam"]) for k in native}
            stats = {k: min(v, at[k]) if at[k] else v for k, v in stats.items()}
            self.caps, self.melds = at, ()
        else:
            self.caps = native
            n = row["slots"]
            self.melds = ((MATERIA_X, True),) * n + (((MATERIA_X, True),) + ((MATERIA_IX, False),) * (4 - n)
                                                      if row["overmeld"] and n < 5 else ())
        self.stats, self.delay = stats, row["delay"]
        # a custom relic: no materia slots, no substats of its own (xivgear isCustomRelic)
        self.relic = None
        if row["source"] == "Relic" and not row["slots"] and not set(row["stats"]) & set(SUBSTATS):
            small = {665: 72, 795: 108}[row["ilvl"]]
            large = cap("crit", self.slot, row["ilvl"], row["meldParam"])     # the item's own cap, before sync
            self.relic = (large, small)

    def variants(self, job):
        """Every way to fill the item for `job`: [(label, stats)] with materia melded (or relic substats chosen) on
        the stats the job uses."""
        main, speed = JOBS[job][0], JOBS[job][1]
        useful = ("crit", "dh", "det", speed)
        base = {k: v for k, v in self.stats.items() if k in (main, "wdMag" if job in CASTER else "wdPhys") or k in useful}
        if self.relic:
            out = []
            large, small = self.relic
            for big in itertools.combinations(useful, 2):
                for lil in (s for s in useful if s not in big):
                    st = dict(base)
                    for s in big: st[s] = min(large, self.caps[s]) if self.synced else large
                    st[lil] = min(small, self.caps[lil]) if self.synced else small
                    out.append((f"relic {'/'.join(big)} +{lil}", st))
            return out
        if not self.melds:
            return [("", base)]
        out, seen = [], set()
        for combo in itertools.combinations_with_replacement(useful, len(self.melds)):
            for order in set(itertools.permutations(combo)):
                st = dict(base)
                for (val, _), s in zip(self.melds, order):
                    st[s] = min(st.get(s, 0) + val, max(self.caps[s] or 0, st.get(s, 0)))
                key = tuple(sorted(st.items()))
                if key in seen: continue
                seen.add(key)
                out.append(("+".join(order), st))
        return out


def items(job, slot=None):
    rows = [r for r in DB["items"] if job in r["jobs"] and (slot is None or r["slot"] == slot)]
    return [Item(r) for r in rows]


def foods(job):
    """Food rows for the job's substats: [(name, {stat: (pct, max)})]."""
    useful = {"crit", "dh", "det", JOBS[job][1]}
    return [(f["name"], {k: (v["pct"], v["max"]) for k, v in f["bonus"].items() if k in useful})
            for f in DB["food"] if set(f["bonus"]) & useful]


KEYS = ("main", "wd", "crit", "dh", "det", "speed")      # a set's gear totals, the job's own main stat and speed


def vector(job, st):
    """An item variant's stats as a KEYS tuple for `job`."""
    main, speed = JOBS[job][0], JOBS[job][1]
    return (st.get(main, 0), st.get("wdMag" if job in CASTER else "wdPhys", 0), st.get("crit", 0), st.get("dh", 0),
            st.get("det", 0), st.get(speed, 0))


class Stats:
    """A set's final stats and multipliers at level 90 (xivmath: xivstats finalizeStats and xivmath.ts), from its gear
    totals (KEYS order) and food ({stat: (pct, max)})."""

    def __init__(self, job, totals=(0,) * 6, food=None):
        self.job = job
        main, speed, self.trait, self.haste = JOBS[job]
        mod = DB["jobs"][job]
        raw = dict(zip(KEYS, totals))
        raw["main"] += fl(MAIN * mod[main] / 100) + CLAN
        raw["det"] += MAIN
        for k in ("crit", "dh", "speed"): raw[k] += SUB
        # food on the gear and base stats, before the party bonus
        for k, (pct, mx) in (food or {}).items():
            k = "speed" if k == speed else k
            if k in raw: raw[k] += min(mx, fl(raw[k] * pct / 100))
        raw["main"] = fl(raw["main"] * (1 + PARTY / 100))
        self.raw = raw
        self.main, self.wd, self.crit, self.dh, self.det, self.speed = (raw[k] for k in KEYS)
        self.main_multi = (math.trunc(AP_MOD * (self.main - MAIN) / MAIN) + 100) / 100
        self.wd_multi = fl(MAIN * mod[main] / 1000 + self.wd) / 100
        self.det_multi = (1000 + fl(140 * (self.det - MAIN) / DIV)) / 1000
        self.crit_rate = fl(200 * (self.crit - SUB) / DIV + 50) / 1000
        self.crit_dmg = (1400 + fl(200 * (self.crit - SUB) / DIV)) / 1000
        self.dh_rate = fl(550 * (self.dh - SUB) / DIV) / 1000
        self.auto_dh = fl(140 * (self.dh - SUB) / DIV) / 1000     # a sure direct hit's extra (on determination)
        self.dot_multi = (1000 + fl(130 * (self.speed - SUB) / DIV)) / 1000
        self.permille = 1000 - fl(130 * (self.speed - SUB) / DIV)    # the speed factor on recasts (the jobs' SPEED x 1000)

    def gcd(self, base=2.5, haste=None):
        """The GCD after speed and haste (the job's trait haste unless given), as the game rounds it."""
        h = self.haste if haste is None else haste
        return fl(fl(self.permille * base) * (100 - h) / 1000) / 100

    # expected damage per potency, by kind of hit (the trait multiplier left out: it never changes with gear)
    def hit(self):
        return self.main_multi * self.det_multi * self.wd_multi * (1 + self.crit_rate * (self.crit_dmg - 1)) \
            * (1 + self.dh_rate * 0.25)

    def dot(self):
        return self.hit() * self.dot_multi

    def sure_crit(self):
        return self.main_multi * self.det_multi * self.wd_multi * self.crit_dmg * (1 + self.dh_rate * 0.25)

    def sure_crit_dh(self):
        return self.main_multi * (self.det_multi + self.auto_dh) * self.wd_multi * self.crit_dmg * 1.25

    def auto(self):
        """Auto-attacks per second: a longer weapon delay hits harder by delay / 3 and as much less often, so only the
        weapon damage and skill speed (on physical jobs the speed stat) are left (xivmath autoAttackModifier)."""
        return self.hit() * self.dot_multi

    def sheet(self):
        return (f"main {self.main}  WD {self.wd}  crit {self.crit} ({self.crit_rate:.1%} x{self.crit_dmg:.3f})  "
                f"DH {self.dh} ({self.dh_rate:.1%})  det {self.det} (x{self.det_multi:.3f})  "
                f"speed {self.speed} (GCD {self.gcd(haste=0):.2f})")


def caps_report():
    """Per slot and item level: how many of the items' stats reach the synced cap (synced items only)."""
    rows = {}
    for r in DB["items"]:
        it = Item(r)
        if not it.synced: continue
        st = {k: v for k, v in r["stats"].items() if k in SUBSTATS or k in ("str", "dex", "int")}
        capped = all(st[k] >= (it.caps[k] or 0) for k in st)
        rows.setdefault((it.slot, it.ilvl, it.row["level"]), []).append(capped)
    print(f"  {'slot':<8} {'ilvl':>4} {'lvl':>3}  every stat at the cap")
    for (slot, ilvl, lvl), c in sorted(rows.items()):
        print(f"  {slot:<8} {ilvl:>4} {lvl:>3}  {sum(c)}/{len(c)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--caps", action="store_true", help="which synced items reach the cap in every stat")
    ap.add_argument("--job", default="BLM")
    ap.add_argument("--items", metavar="SLOT", help="list a slot's items for --job, as synced")
    a = ap.parse_args()
    if a.caps: caps_report()
    if a.items:
        for it in sorted(items(a.job.upper(), a.items), key=lambda i: i.ilvl):
            v = it.variants(a.job.upper())
            print(f"  {it.ilvl:>3} {it.name:<44} {'synced' if it.synced else f'{len(it.melds)} melds':<8} "
                  f"{it.stats}  {len(v)} variants")
