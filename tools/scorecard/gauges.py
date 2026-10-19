"""Job gauges at level 90 (Dawntrail), replayed from a player's casts to find gauge wasted at the cap.

Each gauge lists what each action gains and spends. A spender cast with less gauge than it costs means the table is
wrong (a gain missing or a cost too high), so replaying the clears checks every table: checks.py only uses gauges that
replay the clears cleanly. Free spends under a status (Inner Release, Delirium, Hypercharged) are taken into account.
"""

GAUGES = {
    "Gunbreaker": [dict(label="Cartridges", cap=3, spender="Burst Strike",
                        gain={"Solid Barrel": 1, "Demon Slaughter": 1, "Bloodfest": 3},
                        spend={"Burst Strike": 1, "Fated Circle": 1, "Gnashing Fang": 1, "Double Down": 1})],
    "Warrior": [dict(label="Beast Gauge", cap=100, spender="Fell Cleave",
                     gain={"Maim": 10, "Storm's Path": 20, "Storm's Eye": 10, "Mythril Tempest": 20, "Infuriate": 50},
                     spend={"Fell Cleave": 50, "Decimate": 50, "Inner Chaos": 50, "Chaotic Cyclone": 50},
                     free={"Fell Cleave": "Inner Release", "Decimate": "Inner Release"})],
    "Reaper": [dict(label="Soul Gauge", cap=100, spender="Unveiled Gibbet",
                    gain={"Slice": 10, "Waxing Slice": 10, "Infernal Slice": 10, "Spinning Scythe": 10, "Nightmare Scythe": 10,
                          "Soul Slice": 50, "Soul Scythe": 50},
                    spend={"Blood Stalk": 50, "Unveiled Gibbet": 50, "Unveiled Gallows": 50, "Grim Swathe": 50, "Gluttony": 50}),
               dict(label="Shroud Gauge", cap=100, spender="Enshroud",
                    gain={"Gibbet": 10, "Gallows": 10, "Guillotine": 10, "Plentiful Harvest": 50},
                    spend={"Enshroud": 50})],
    "DarkKnight": [dict(label="Blood Gauge", cap=100, spender="Bloodspiller",
                        gain={"Souleater": 20, "Stalwart Soul": 20}, under={"Blood Weapon": 10},   # +10 per weaponskill under it
                        spend={"Bloodspiller": 50, "Quietus": 50},
                        free={"Bloodspiller": "Delirium", "Quietus": "Delirium"})],
    "Samurai": [dict(label="Kenki", cap=100, spender="Hissatsu: Shinten",
                     gain={"Hakaze": 5, "Jinpu": 5, "Shifu": 5, "Gekko": 10, "Kasha": 10, "Yukikaze": 15, "Mangetsu": 10,
                           "Oka": 10, "Fuko": 10, "Enpi": 10, "Ikishoten": 50},
                     spend={"Hissatsu: Shinten": 25, "Hissatsu: Kyuten": 25, "Hissatsu: Senei": 25, "Hissatsu: Guren": 25,
                            "Hissatsu: Gyoten": 10, "Hissatsu: Yaten": 10},
                     on_status={"Tengentsu's Foresight": 10})],      # being hit through Tengentsu
    "Machinist": [dict(label="Heat Gauge", cap=100, spender="Hypercharge",
                       gain={"Heated Split Shot": 5, "Heated Slug Shot": 5, "Heated Clean Shot": 5, "Scattergun": 5},
                       spend={"Hypercharge": 50}, free={"Hypercharge": "Hypercharged"}),
                  dict(label="Battery Gauge", cap=100, spender="Automaton Queen", empties={"Automaton Queen"},
                       gain={"Heated Clean Shot": 10, "Air Anchor": 20, "Chain Saw": 20},
                       spend={"Automaton Queen": 50})],
    "Dragoon": [dict(label="Firstminds' Focus", cap=2, spender="Wyrmwind Thrust",
                     gain={"Raiden Thrust": 1, "Draconian Fury": 1},
                     spend={"Wyrmwind Thrust": 2})],
}


def replay(spec, casts, auras_on, alive, until, applied=(), weaponskills=frozenset()):
    """Gauge wasted at the cap (units, inside the alive windows up to `until`), spender casts the model could not
    afford, and spends in total. casts: [(t, name)] in time order; auras_on(name, t) tells whether a status is up;
    applied: [(t, status)] statuses the player gained (for on_status gains); weaponskills: names that count for
    `under` gains. The gauge starts empty and empties at each death (a cast after a gap in the alive windows)."""
    g, wasted, short, spends = 0, 0, 0, 0
    events = sorted([(t, 0, n) for t, n in casts] + [(t, 1, n) for t, n in applied if n in spec.get("on_status", {})])
    inside = lambda t: t <= until and any(a <= t <= b for a, b in alive)
    starts = sorted(a for a, b in alive)
    nxt = iter(starts[1:])
    reset_at = next(nxt, None)
    def add(n, t):
        nonlocal g, wasted
        over = g + n - spec["cap"]
        if over > 0 and inside(t): wasted += over
        g = min(spec["cap"], g + n)
    for t, kind, name in events:
        while reset_at is not None and t >= reset_at:       # raised after a death: the gauge restarts
            g = 0; reset_at = next(nxt, None)
        if kind == 1: add(spec["on_status"][name], t); continue
        for status, n in spec.get("under", {}).items():
            if name in weaponskills and auras_on(status, t): add(n, t)
        if name in spec["spend"]:
            spends += 1
            if spec.get("free", {}).get(name) and auras_on(spec["free"][name], t): pass
            elif name in spec.get("empties", ()):
                if g < spec["spend"][name]: short += 1
                g = 0
            else:
                if g < spec["spend"][name]: short += 1
                g = max(0, g - spec["spend"][name])
        if name in spec["gain"]: add(spec["gain"][name], t)
    return wasted, short, spends
