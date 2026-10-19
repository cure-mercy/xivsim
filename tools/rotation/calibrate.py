"""Replays logged casts through a job model to check it: every cast should be legal at its logged time, the model's MP
should match the logged MP, its cast times should match begin-cast -> cast, and its damage per hit should track the
logged plain hits (no crit, no direct hit, buffs divided out).

    python tools/rotation/calibrate.py [--since 2025-04-01] [--until 125]
"""
import argparse, collections, datetime, json, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import logs                                      # noqa: E402
from engine import Fight                         # noqa: E402
from jobs import blm as J                        # noqa: E402

from engine import SLIDE                         # noqa: E402


def replay(p, until, out, fight=None):
    n = p["names"]
    fight = fight or Fight(until=until + 30, pot=True)
    s = J.State.initial(fight)
    begins = {}
    for x in p["casts"]:
        if x["type"] == "begincast": begins[x["abilityGameID"]] = x["t"]
    seq = []
    last_begin = {}
    for x in p["casts"]:
        name = n[str(x["abilityGameID"])]
        if x["type"] == "begincast": last_begin[name] = x["t"]; continue
        if x["type"] != "cast" or x["t"] > until: continue
        b = last_begin.pop(name, None)
        seq.append((x["t"], b, name, x.get("sourceResources", {}).get("mp")))
    for t, b, name, mp in seq:
        if name.startswith("Grade") and "Gemdraught" in name: name = "Tincture"
        if name in J.GCDS:
            start = b if b is not None and t - b < 4 else t
            if not s.first:
                if s.gcd - start > 0.15: out["early"].append((p["name"], t, name, round(s.gcd - start, 2)))
                s.t = s.gcd = start
            pre = s.copy(); J.advance(pre, start)
            if mp is not None and not s.first: out["mp"].append((name, pre.el, pre.mp, mp, p["name"], t))
            c, _ = J.cast_time(pre, name, start)
            if b is not None and c: out["cast"][(name, pre.el, pre.ll > start)].append((t - b + SLIDE, c))
            ns = J.do_gcd(s, fight, name)
            if ns is None:
                out["illegal"].append((p["name"], round(t, 2), name, dict(el=pre.el, mp=pre.mp, hearts=pre.hearts, poly=pre.poly,
                                                                         paradox=pre.paradox, fs=pre.fs > start, th=pre.th > start)))
                # carry on by forcing the cast through with the rules relaxed
                ns = force(s, fight, name, start)
            s = ns
        elif name in J.CDS:
            s.t = t
            ns = J.do_ogcd(s, fight, name, policy=False)
            if ns is None:
                out["illegal"].append((p["name"], round(t, 2), name, {"charges": J.charges(s, name, t)}))
                ns = s
            s = ns
        else:
            s.t = max(s.t, t)       # role actions and movement tools: they only take time
    return s


def gcd_of(p):
    """The player's unhasted GCD: the most common spacing of consecutive GCD starts outside Ley Lines."""
    n = p["names"]
    ll = [x["t"] for x in p["buffs"] if n[str(x["abilityGameID"])] == "Ley Lines" and x["type"] in ("applybuff", "removebuff")]
    inll = lambda t: any(a <= t < b for a, b in zip(ll[0::2], ll[1::2]))
    starts, lb = [], {}
    for x in p["casts"]:
        name = n[str(x["abilityGameID"])]
        if x["type"] == "begincast": lb[name] = x["t"]; continue
        if x["type"] == "cast" and name in J.GCDS:
            b = lb.pop(name, None)
            starts.append(b if b is not None and x["t"] - b < 4 else x["t"])
    gaps = sorted(round(b - a, 2) for a, b in zip(starts, starts[1:]) if 2.0 <= b - a <= 2.6 and not inll(a))
    return gaps[len(gaps) // 4] if gaps else None     # lower quartile: clean back-to-back GCDs, not delayed ones


def fit_phase(p, until):
    """The server tick phase (0-3 s) that best explains the log: fewest illegal casts, then fewest MP mismatches."""
    best = None
    for i in range(30):
        J.TICK_PHASE = i / 10
        out = dict(illegal=[], early=[], mp=[], cast=collections.defaultdict(list))
        replay(p, until, out)
        score = (len(out["illegal"]), sum(1 for m in out["mp"] if abs(m[2] - m[3]) > 250))
        if best is None or score < best[0]: best = (score, i / 10)
    return best[1]


def replay_fight(p, fight):
    """The logged rotation's damage in this fight (its buffs and scoring window)."""
    out = dict(illegal=[], early=[], mp=[], cast=collections.defaultdict(list))
    return replay(p, fight.until, out, fight)


def force(s, fight, name, start):
    s = s.copy()
    if name == "Paradox": s.paradox = True
    if name == "Thunder III": s.th = start + 1
    if name == "Xenoglossy": s.poly = max(s.poly, 1)
    if name in ("Fire IV", "Despair"): s.el = max(s.el, 1); s.mp = max(s.mp, 1600)
    s.mp = max(s.mp, J.mp_cost(s, name))
    return J.do_gcd(s, fight, name) or s


def model_potency(name, el):
    """The model's potency for a GCD cast in element state `el` (element bonuses and Enochian included)."""
    pot = J.POTENCY[name] * ((J.AF_FIRE[el] if el >= 0 else J.UI_FIRE[-el]) if name in J.FIRE else 1)
    return pot * (J.AF_ICE[el] if name in J.ICE and el > 0 else 1) / (J.ENOCHIAN if el == 0 else 1)


def plain_hits(p, until):
    """[(spell, element at the cast, logged damage with external buffs divided out, model potency)] for the player's
    plain hits (no crit, no direct hit, no tincture) on GCDs up to `until`."""
    n = p["names"]
    pot = [x["t"] for x in p["buffs"] if n[str(x["abilityGameID"])] == "Medicated" and x["type"] == "applybuff"]
    plain = {}
    for x in p["hits"]:
        if x["type"] == "damage" and x.get("hitType") == 1 and not x.get("directHit") and not x.get("tick")                 and not any(a <= x["t"] < a + 30 for a in pot):
            plain.setdefault(n[str(x["abilityGameID"])], []).append((x["t"], x["amount"] / x.get("multiplier", 1)))
    fight = Fight(until=until + 30)
    s = J.State.initial(fight)
    out = []
    for x in p["casts"]:
        if x["type"] != "cast" or x["t"] > until: continue
        name = n[str(x["abilityGameID"])]
        if name in J.GCDS:
            h = [v for ht, v in plain.get(name, []) if 0 <= ht - x["t"] < 1.5]
            if h and J.POTENCY[name]: out.append((name, s.el, h[0], model_potency(name, s.el)))
            s.t = s.gcd = x["t"]
            s = J.do_gcd(s, fight, name) or force(s, fight, name, x["t"])
        elif name in J.CDS:
            s.t = x["t"]; s = J.do_ogcd(s, fight, name, policy=False) or s
    return out


def damage_check(L, until):
    """Model potency of each GCD against the logged plain hit, scaled so the player's Xenoglossy matches the model."""
    rows = collections.defaultdict(list)
    for p in L:
        hits = plain_hits(p, until)
        xeno = [v for name, _, v, _ in hits if name == "Xenoglossy"]
        if not xeno: continue
        k = st.median(xeno) / J.POTENCY["Xenoglossy"]
        for name, el, v, model in hits: rows[(name, el)].append((v / k, model))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", default="2025-04-01")
    ap.add_argument("--until", type=float, default=125)
    a = ap.parse_args()
    days = {(k["code"], k["fight"]): k["day"] for k in json.loads(logs.BENCH.read_text())["kills"]}
    L = [p for p in logs.clears("BlackMage") if days[(p["code"], p["fight"])] >= a.since]
    print(f"{len(L)} Black Mage logs since {a.since}, replaying 0:00-{a.until:.0f}s")
    out = dict(illegal=[], early=[], mp=[], cast=collections.defaultdict(list))
    phases = []
    for p in L:
        ph = fit_phase(p, a.until); phases.append(ph)
        J.TICK_PHASE = ph
        replay(p, a.until, out)
    print("server tick phase fitted per log: " + ", ".join(f"{x:.1f}" for x in phases))
    print(f"\nillegal casts: {len(out['illegal'])}")
    for x in out["illegal"][:25]: print("  ", x)
    print(f"\nGCDs started earlier than the model allows (>0.15 s): {len(out['early'])}")
    for x in out["early"][:15]: print("  ", x)
    bad = [m for m in out["mp"] if abs(m[2] - m[3]) > 250]
    print(f"\nMP mismatches (>250): {len(bad)} of {len(out['mp'])}")
    for x in bad[:25]: print(f"   {x[4][:14]:<14} {x[5]:7.2f} {x[0]:<13} el {x[1]:+d}  model {x[2]:>5}  log {x[3]:>5}")
    print("\ncast times: logged (begin->cast + 0.5 s slide) vs model, by spell / element / Ley Lines")
    for k, v in sorted(out["cast"].items(), key=str):
        print(f"   {k[0]:<13} el {k[1]:+d} LL {'y' if k[2] else 'n'}: logged {st.median(a for a, _ in v):.2f}  model {st.median(b for _, b in v):.2f}  ({len(v)})")
    print("\ndamage: logged plain hit (scaled to Xenoglossy) vs model potency, by spell and element at the cast")
    for k, v in sorted(damage_check(L, a.until).items(), key=str):
        print(f"   {k[0]:<13} el {k[1]:+d}: logged {st.median(a for a, _ in v):6.0f}  model {st.median(b for _, b in v):6.0f}  ({len(v)})")


if __name__ == "__main__":
    main()
