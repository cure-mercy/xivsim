# Twelfth Circle Trainer

Drills for the mechanics of P12S (Anabaseios: The Twelfth Circle, Savage), played in the browser and published on
GitHub Pages at <https://cure-mercy.github.io/xivsim/>. The site is static: no build step, no packages.

| Path | What it is |
|---|---|
| `index.html` | The trainer: loads `js/core.js`, then one script per drill, then `Twelfth.start()` |
| `briefs.html` | One written brief per drill (`<article class="doc" id="<drill id>">`); its footer cites the sources |
| `js/core.js` | Shared machinery: tabs, role and slot, feedback, undo, the real-time helpers (`Twelfth`, `T` in a drill) |
| `mechanics/*.js` | One drill each; each calls `T.register({ id, label, phase, markup, styles, init })` |
| `css/styles.css`, `assets/` | Styles; debuff icons, arena drawings, favicon |
| `stats/` | The scorecard's public copy, written by `build_site.py --publish` |

The offline tools have their own READMEs: [tools/scorecard](tools/scorecard/README.md) (FFLogs reports to a
scorecard site), [tools/rotation](tools/rotation/README.md) (rotation optimizer), [tools/gear](tools/gear/README.md)
(best in slot), [tests](tests/README.md) (the drills' browser probes and the classifier's blame suite).

## Local preview

```
python -m http.server            then open http://localhost:8000/   (from the repository root)
```

The pages load their scripts and data by relative paths, so they need a web server rather than opening the files
from disk. `index.html` and `briefs.html` are complete documents served as they are and nothing supplies a CSS
reset, so `css/styles.css` carries its own basics: `[hidden]{display:none !important}` (without it `.layout`'s
display shows every drill's panel at once), `color-scheme` on `:root` and `body{margin:0}`.

## Deploying

The trainer is published only through GitHub Pages. A push to `main` runs `.github/workflows/pages.yml`, which
uploads the repository as it is, less `tests/`, `tools/` and `.gitignore`, and is live in about 30 s; `stats/` goes
up with it (see tools/scorecard/README.md, Publishing with a passphrase). To check that a deploy is live, fetch a
changed file from the site, e.g. `curl https://cure-mercy.github.io/xivsim/js/core.js`. One-time setup: in the
repository's Settings → Pages, set Source to "GitHub Actions".

## Unlocking a drill

While the trainer is playtested only the drills listed in `OPEN` in `js/core.js` are playable; the rest show in the
list as a locked "Mechanic N", so their titles give nothing away. To open one:

1. add its id to `OPEN`;
2. remove `hidden` from its `<article class="doc" id="…">` in `briefs.html`;
3. add it to `DRILLS` in `tools/scorecard/site/app.js`, so the scorecard links to it (see tools/scorecard/README.md,
   Focus lists and practice links).

## Real-time drills

Paradeigma I, Paradeigma II, Superchain I and Paradeigma III can be played step by step or against the fight's
clock. A new real-time mode follows `mechanics/superchain-1.js`:

- a `LIVE` timeline from the logs (next section);
- a clock and Start button in a `<x>-live` box, and a free-pick click layer (the drill's `freePick`);
- party AI walking to the plan's spots `REACT` (2.0 s) after each cue;
- a check per beat that ends a failed pull with `liveFail` and `T.drawTarget`;
- `T.castRows` with a fixed `castSlots` count, and `T.holdPrompt`, so the arena never moves as casts come and go;
- a `<x>-timed` class on the layout that hides undo, redo and rewind;
- the pace remembered in localStorage (`twelfth-<x>-pace`).

Add the drill's solver and undo pages to the suites in `tests/run.py` (see tests/README.md).

**Pause and off-plan plays** (Paradeigma III): `pauseClock()` / `startClock()` stop and resume the pull. A harmless
play that is off the group's plan pauses with `showFeedback(fb, 'warn', …)`, offering Resume, Retry from the
`checkpoint()` taken when the floor fell, or New pull; a pull survived that way ends "Cleared, off plan" with the
deviations listed. A Pause button, when added, should call the same pair.

**Debuff picker**: the "Practise" row of debuff icons plus Random (Superchain I, Paradeigma III), remembered in
localStorage (`twelfth-sc-debuff`, `twelfth-p3-debuff`). Re-render it inside `render()`, as Paradeigma III does, so
undo and redo don't leave it stale.

## Real-time timings from logs

`LIVE` timelines come from the groups' own logs (`tools/logs.csv`, one column per group), in seconds after a boss
cast; each drill's `LIVE` comment names its pulls. Paradeigma III (Oct 2026) takes the median of six clean pulls,
none more than 0.1 s off, and new real-time drills should do the same. Paradeigma I and II and Superchain I still
use a single pull.

- **What is cached.** The scorecard's `tools/scorecard/.cache/report_<code>.json` (built by `scorecard.py`) holds
  every pull's DamageTaken events with target and source positions (`targetResources.x/y`; yalms =
  (v − 10000) / 100, arena centre at 0,0) and debuff apply/remove events: enough for hit positions, tower radii and
  debuff timings.
- **What is not.** Enemy casts (begincast/cast, with add spots and AoE centres): fetch them from `tools/scorecard`
  with `fflogs.events(code, fights, "Casts", hostility="Enemies", resources=True)`, where `fights` is a list of the
  report's fight dicts (`id`, `startTime`, `endTime`; the query opens 30 s before the first) (credentials as in
  tools/scorecard/README.md, Setup).
- **Coordinates.** The drills draw 12 units to the yalm around (300, 300), so the 40-yalm floor runs from 60 to 540.
- **Duplicates.** Some cached reports are the same pull logged twice by different players: dedupe pulls by their
  timings before taking medians.
- **Other groups.** One of Paradeigma III's sources is another group's, which swaps the + and X platforms: use it
  for timings only, not for positions.

## Strategy sources

The drills were first built on Icy Veins' Twelfth Circle (Savage) guides, cross-checked with the Console Games Wiki.
Our raid groups (G1–G5 in `tools/logs.csv`) play their own plan, the raidplan
[Syncademy P12S P1](https://raidplan.io/plan/qa834veq2fssd2yc): slide 1 assignments, 2–5 Paradeigma I, 6–11
Paradeigma II, 12–22 Superchain Theory I, 23–28 Paradeigma III. **Where the two differ, the raidplan wins.** So far
only Paradeigma III follows it; the other drills still follow Icy Veins. To adapt one, read its raidplan slides
(below), compare them with the drill, then change the drill and its brief together, and cite the plan in the brief
footer. When the plan is unclear, the groups' logs show which variant they really play.

### Paradeigma III

- **Tethers.** The straight tether soaks the centre tower, the crossed tether the middle-platform one (Icy Veins has
  it the other way round).
- **Bright Souls.** They take the middle platforms by priority H1 > T1 > T2 > H2, **east to west**: the first in
  priority the eastern one (Icy Veins runs the same priority west to east). Drill, brief and the scorecard's
  `classifier.BRIGHT_PRIORITY` encode it, from 2026-10-26. The 2026-10-25 raid still played the earlier light-party
  split (LP1 the northern middle platform), and the scorecard judges that day by it (`classifier.bright_seat_lp`).
- **Waymarks.** The drill draws the groups' in-game preset "Clockspots": A north, B east, C south, D west, 1–4 on the
  intercardinals from the north-east, clockwise, every mark exactly 10 y from the centre (the raidplan's drawing
  puts them 10.0–10.9 y out; the preset is authoritative). Mark sizes come from the Waymark Studio plugin's
  `Waymark.cs` (letter circle 1.25 y radius, number square 2.2 y across). In the game's coordinates for the arena
  (MapID 943) X/Z have the centre at (100, 100), and lower Z is north.
- **Game geometry.** Where a drill squeezes geometry to fit its arena, its checks run in game geometry: the wall
  adds are drawn 21.3 y out but stand 25 y out in the fight, so the straight-tether seat on the B/D line is 35.0 y
  from its add, half a yalm past the lethal 34.5 (`MIN_STRETCH_Y`).

### Reading the raidplan

raidplan.io renders in the browser, so a plain page fetch sees only the slide numbers. The data is public JSON:

1. `curl https://raidplan.io/api/plan/<code>` gives `plan.doc_url`, e.g.
   `https://userdata.raidplan.io/<code>.json?v=<revision>`.
2. That document has `header_notes_raw` (the table of contents) and `nodes`. Each node has a `type` (`itext`: text
   in `attr.text`; `marker`: a role, job or status icon in `attr.asset`; `circle`, `rect`, `line`, `tether`,
   `ability`: shapes), `meta.step` (**0-indexed**: slide 23 is step 22) and `meta.pos`.
3. The arena node is 600×600 centred at (600, 337.5); in drill coordinates x' = 60 + (x − 300)·0.8,
   y' = 60 + (y − 37.5)·0.8. Debuff markers are `ffxiv/legacy/icon_hd/2151xx.png`, named on the plan's own legend
   slides (215182 light tower, 215183 dark tower, 215186 plus, 215187 X, 215179 / 215180 light / dark tilt).

To see a slide, screenshot it with Playwright (`channel="chrome"`) by clicking the step numbers in the viewer.

**Editing** a copy (never the original plan) needs its edit link, `raidplan.io/plan/<code>/<access_key>`, from the
editor's Share menu (`/plan/<code>/edit` is account-only). `POST /api/plans/<code>` with JSON `{access_key,
revision (the current one), steps, name, nodes, header_notes (raw), footer_notes, step_notes, single_note,
slot_numbering, player_style, player_custom, roster}`; a full read-and-post round trip saves pixel-identical.
Gotchas:

- text is Roboto with line height 1.16, so a box for n lines at font size fs is (n−1)·fs·1.13·1.16 + fs·1.13 high;
- a line's `points` are absolute (its `pos` is the top-left of their bounding box);
- a rect or cone with `meta.face` set is turned by the viewer to face that player from its own centre, so clear
  `face` when setting an angle yourself.

## AoE shapes

An ability's real shape is in the game's Action sheet, which XIVAPI v2 serves without a key:

```
curl -G https://v2.xivapi.com/api/search --data-urlencode "sheets=Action" \
  --data-urlencode 'query=Name="White Flame"' --data-urlencode "fields=Name,CastType,EffectRange,XAxisModifier"
```

`CastType` 12 is a rectangle: `EffectRange` is its length and `XAxisModifier` its full width. Several rows share a
name, so match the row id to the one the logs use (the scorecard report cache's `abilities`). Take widths from here
rather than fitting them to hits in the logs.

| Ability (Action id) | Width | In the drills (half, units) |
|---|---|---|
| White Flame (33520) | 4 y | `FLAME_HALF` 24 |
| Searing Radiance / Shadowsear (33521–33522), the Paradeigma II and III tethers | 6 y | `LASER_HALF` 36 |
| Ray of Light (33518), Paradeigma II's columns | 10 y | |

The logs agree: the classifier's `WF_LINE` 2.0 and `TETHER_HALF` 3.0 half-widths.
