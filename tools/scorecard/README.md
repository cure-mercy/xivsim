# P12S P1 scorecard

Turns FFLogs reports of P12S phase 1 (Athena, Savage) progression into per-player scorecards, printed as
messages ready to paste into Discord. For every player it shows how often they caused the mistake that ended a
pull, how their damage compares with players from other groups' clears on the same job, and their GCD uptime.

## Usage

```
python tools/scorecard/scorecard.py <report link> [<report link> ...]
```

Each link is one raid group; they are labelled G1, G2, … in the order given. Full links (with or without
`#fight=…`) and bare report codes both work.

```
python tools/scorecard/scorecard.py https://www.fflogs.com/reports/7MPaxKXWvkTRFqrg
python tools/scorecard/scorecard.py 13pQaDtFrRwzX8dx HdfQj1XBFCTRv3Dk dc4hktKzMr1AWQFY qBrHCXWnMhZPvcp8
```

| Option | What it does |
|---|---|
| `--refresh` | Downloads the reports again instead of using the cache. Use it for a log that was still being uploaded. |
| `--json FILE` | Also writes the per-player numbers to `FILE`. |

The scorecard is printed to standard output as fenced code blocks, each under Discord's 2,000-character
limit; paste them one message at a time. Progress goes to standard error. After the messages comes a short
notes section that is not meant for Discord: how many first mistakes the classifier could attribute, the light
parties it inferred, and players with too few clean pulls for a reliable damage figure.

A report takes a few seconds the first time and is cached in `.cache/` afterwards.

## Setup

- Python 3.10 or newer, no extra packages.
- An FFLogs API client in `.fflogs_v2` at the repository root (it is git-excluded), two lines:

  ```
  FFLOGS_CLIENT_ID=<client id>
  FFLOGS_CLIENT_SECRET=<client secret>
  ```

  Create a client at <https://www.fflogs.com/api/clients/>. Any key names ending in `_ID` and `_SECRET` work.
  The access token is cached in `.cache/token.json` until it expires.

## Reading the scorecard

The header gives each group's pull count, best boss HP, longest pull, how many pulls stayed clean through
2:00, and the party's damage over 0:00–2:00 next to that of clearing groups.

| Column | Meaning |
|---|---|
| Mistakes | Share of the player's pulls where they caused the first mistake (a death or Damage Down). Being killed by someone else's error does not count. |
| vs Peer | rDPS over 0:00–2:00, averaged over the player's best quarter of clean pulls, against the average player on the same job in clears of 7:10 or slower. |
| vs Fast | The same against clears faster than 7:10. |
| Uptime | Active GCD time over 0:00–2:00, against clearers of the same role. |

Grades: ✓ good, ~ ok, ! worth focusing on. `*` marks a comparison against only one or two clearers, which is
rough.

| Grade | Mistakes | Damage vs fast clears | Uptime vs clearers |
|---|---|---|---|
| ✓ | 10% or less | within 5% | within 0.5 points |
| ~ | 20% or less | within 12% | within 1.5 points |
| ! | more | more | more |

The thresholds are constants at the top of `scorecard.py` (`G_MIST`, `G_DMG`, `G_UP`).

### Boss HP checkpoints

A second table shows, for each major mechanic (Paradeigma II, Superchain I, Paradeigma III, Palladion and both
Superchain II sets), the boss HP a group has to be at or below when the mechanic's cast begins:

| Column | Meaning |
|---|---|
| Clear | On pace to kill exactly at enrage (~7:38). |
| Comfy | On pace to kill about 13 seconds earlier. |
| Group cells | Best / median HP % of the pulls that reached the mechanic, and how many did. ✓ best at Comfy or better, ~ at Clear or better, ! behind. |

With one group it is a single table; with several, each mechanic gets a line of targets with the groups two to
a line underneath, so it fits a Discord message without wrapping.

The takeaways message lists who is ✓ in every column, what ended the pulls, a focus bullet for each player
with a !, and how many players are at or above peer clears.

Damage is only measured on pulls with no death or Damage Down before 2:00, and always over the same
0:00–2:00 window, so every player is compared on the same opener and the same mechanics.

## How mistakes are attributed

`classifier.py` finds every Damage Down and lethal hit in a pull and checks it against the strategy described
in the trainer's mechanic briefs (`briefs.html`). The first mistake of a pull is the earliest of these, plus
any others within 1.5 seconds.

| Mechanic | What is checked |
|---|---|
| Paradeigma I | Which light party baits each White Flame wave is learned from the group's own pulls. A missing baiter is blamed, not the players their laser hits instead. Trinity of Souls hits are the victim's. |
| Paradeigma II | The quadrant sweep (supports clockwise from north-east, DPS counter-clockwise from north-west) says where each Soul should drop its tower. Checks wrong quadrant, two towers stacked, a tower nobody soaked, the wrong soaker, unstretched tethers, and players standing in a tether laser or Soul AoE. Ray of Light hits are the victim's. |
| Superchain I | Purple pairs and orange cones, the two laser groups (by Soul and Tilt), the Heavensflame spread, and the final towers. Green orb and donut hits are the victim's. |
| Paradeigma III | Support towers, DPS tether lasers clipping supports, whether each bright tower went to the centre corner or its own tile, the White Flame baits and the opposite-colour soakers. |
| Later mechanics | Generic rules only: standing in an avoidable AoE is the victim's mistake. |

A death that follows the same player's earlier mistake is counted as part of that mistake. Anything the rules
cannot explain is left unattributed rather than guessed.

The classifier assumes the group plays the strategy in the briefs: the line-up for Paradeigma I rather than
tank invulnerabilities, the quadrant sweep, and the Paradeigma III placements. A group that plays a mechanic
differently will see players blamed wrongly for it.

## The benchmark

`benchmark.json` holds what players in other groups' clears do over 0:00–2:00, per job: Savage P1 clears
from 2025 and 2026 that took 5:30–7:50, played at level 90 in capped gear like ours. Level 100 runs and
lower-gear runs are left out, tincture damage is removed, and players who died before 2:00 are skipped. Each
job's value is the average over distinct players, kept separately for peer clears (7:10 or slower) and fast
ones.

It also holds the boss HP checkpoints. For each mechanic, a line is fitted through every benchmark kill: the
HP % left when the mechanic began against how long the kill took. Clear is that line at 7:38, Comfy at 7:25.

The file is a snapshot. To rebuild it:

```
python tools/scorecard/build_benchmark.py [--since 2025-01-01] [--until 2026-10-18] [--out FILE]
python tools/scorecard/build_benchmark.py --checkpoints-only     # only refit the HP checkpoints, same kills
```

A full rebuild reads several thousand report pages and can use an hour or more of the API's hourly budget; it
waits out the rate limit by itself and caches its progress in `.cache/benchmark/`, so it can be stopped and
resumed.

## Files

| File | Purpose |
|---|---|
| `scorecard.py` | The command: fetches, analyses and prints the scorecard |
| `classifier.py` | Mistake attribution |
| `fflogs.py` | FFLogs v2 client: token, rate-limit waits, paged events, batched tables |
| `benchmark.json` | Benchmark snapshot used for the damage and uptime comparisons |
| `build_benchmark.py` | Rebuilds `benchmark.json` |
| `.cache/` | Downloaded reports, the API token and benchmark progress (git-ignored) |

The folder is left out of the GitHub Pages site by the deploy workflow.
