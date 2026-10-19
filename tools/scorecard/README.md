# P12S P1 scorecard

Turns FFLogs reports of P12S phase 1 (Athena, Savage) progression into a website you can drill down from raid
days to a day's groups to a group's players. For every player it shows how many mistakes they make and how
many wipes they caused, how much damage their mistakes cost, and how their damage compares with players from
other groups' clears on the same job, overall and per phase of the fight.

## Usage

```
python tools/scorecard/build_site.py <report link> [<report link> ...]
python -m http.server -d tools/scorecard/site 8000          then open http://localhost:8000
```

Each link is one raid group's report; full links (with or without `#fight=…`) and bare report codes both work.
Reports are grouped into raid days by the date they were logged, and new reports on a day are named G1, G2, …
in the order given. A report already on the site is analysed again and keeps its name.

| Option | What it does |
|---|---|
| `--names "Static A,Static B"` | Group names for the links, in order, instead of G1, G2, … |
| `--refresh` | Downloads the reports again instead of using the cache. Use it for a log that was still being uploaded. |
| `--reanalyse` | Analyses every report already on the site again from the cache. Needed after the classifier or the cause labels change, since the site stores what it was built with. |
| `--remove CODE` | Removes a report from the site. |
| `--publish [DIR]` | Also writes the passphrase-protected copy for public hosting (see below). |

A report takes a few seconds the first time and is cached in `.cache/` afterwards. The page needs a web server
because it loads `data.json`; opening `index.html` straight from disk will not work. `site/data.json` holds
player names and who caused which mistake, so it is git-ignored, and `tools/` is left out of the GitHub Pages
deploy.

## Setup

- Python 3.10 or newer, no extra packages. Node, only for `--publish`.
- An FFLogs API client in `.fflogs_v2` at the repository root (it is git-excluded), two lines:

  ```
  FFLOGS_CLIENT_ID=<client id>
  FFLOGS_CLIENT_SECRET=<client secret>
  ```

  Create a client at <https://www.fflogs.com/api/clients/>. Any key names ending in `_ID` and `_SECRET` work.
  The access token is cached in `.cache/token.json` until it expires.

## Publishing with a passphrase

GitHub Pages sites are public, so the published copy carries its data encrypted and asks for a passphrase:

```
python tools/scorecard/build_site.py [<report link> ...] --publish
```

This writes `stats/` at the repository root: the three page files and `data.enc.json`, the data compressed and
encrypted with AES-256-GCM under a key derived from the passphrase (PBKDF2-SHA256, 600,000 rounds). The
plaintext `data.json` is never copied there. The passphrase is asked for twice (or read from
`SCORECARD_PASSPHRASE`) and must be at least 12 characters; several unrelated words are best, since anyone can
download the encrypted file and try passphrases offline. Encrypting needs Node (`encrypt_data.js`); the browser
decrypts with its built-in Web Crypto, which works on https and on localhost. After a check that the result
decrypts, commit and push `stats/`; the existing Pages workflow deploys it with the rest of the repository, at
`/stats/` under the trainer's address. Run `--publish` again after adding or re-analysing reports. Browsers may
keep the old page files for a few minutes after a deploy; a hard refresh (Ctrl+F5) picks up the new ones.

Readers enter the passphrase once per browser session (unless they untick "Remember"); the Lock button forgets
it. The page is marked `noindex` and is not linked from the trainer. What this does not give you: individual
accounts. Everyone shares one passphrase, so changing it (and publishing again) is the only way to revoke
access.

**Undoing or moving it.** Nothing outside `stats/` depends on the published copy: delete `stats/` and push to take
it down. The page itself does not care where it is hosted: on any static host, upload `stats/` as it is; on a
host with its own login, upload `site/` with the plaintext `data.json` instead, and the passphrase prompt never
appears (the page only asks when `data.json` is missing and `data.enc.json` is there).

## What the site shows

| Page | What it shows |
|---|---|
| Raid days | Trends across days (best boss HP, pulls clean through 2:00, mistakes per pull, damage lost to deaths, party DPS against peer and fast clears) and a table of days |
| Day | The day's groups side by side, each group's boss HP checkpoints, and heatmaps of all mistakes and of what wiped each group |
| Group | The player scorecard; every pull's length with its first mistake and what lost it; boss HP checkpoints; damage lost to deaths, by player and by cause; every player's damage per phase against clearers; heatmaps of mistakes and wipes by player |
| Player | Mistakes per pull, wipes, damage against clearers, uptime and what their mistakes cost; damage per phase; mistakes and their cost by cause; rDPS on every clean pull; every mistake with its pull and time; the player across raid days |

Every chart has a Table button for the same numbers as a table and shows details on hover or keyboard focus.
The theme follows the system and can be switched with the button (or `?theme=light` / `?theme=dark` in the
link).

### The scorecard

| Column | Meaning |
|---|---|
| Mistakes/pull | The player's mistakes per pull: every death or Damage Down they caused, not just a pull's first. A mistake that kills several players counts once, and deaths that are only fallout of the player's own earlier mistake are not counted again. Being killed by someone else's error does not count. Mistakes are counted until the pull is lost; the collapse after that is not. |
| Wipes | Share of the player's pulls where their mistake is what lost the pull (see below). |
| vs Peer | rDPS over 0:00–2:00, averaged over the player's best quarter of clean pulls, against the average player on the same job in clears of 7:10 or slower. |
| vs Fast | The same against clears faster than 7:10. |
| Uptime | Active GCD time over 0:00–2:00, against clearers of the same role. |

Grades are coloured dots: green good, yellow ok, red worth focusing on. `*` marks a comparison against only one
or two clearers, which is rough.

| Grade | Mistakes per pull | Wipes | Damage vs fast clears | Uptime vs clearers |
|---|---|---|---|---|
| green | 0.30 or fewer | 10% or less | within 5% | within 0.5 points |
| yellow | 0.60 or fewer | 20% or less | within 12% | within 1.5 points |
| red | more | more | more | more |

With eight players and one wipe a pull, a fair share of the wipes is 12.5%. The thresholds are constants at the
top of `scorecard.py` (`G_MIST`, `G_WIPE`, `G_DMG`, `G_UP`). Damage over 0:00–2:00 is only measured on pulls
with no death or Damage Down before 2:00, so every player is compared on the same opener and mechanics.

### Who lost the pull

Pulls run until the whole party is dead, so every pull that is not a kill is a wipe. The collapse is the last run
of deaths with less than 15 seconds between them (`CASCADE_GAP`); earlier deaths the group recovered from do not
count. A mass death in the collapse (four or more players to one ability within 3 seconds, such as a tower
explosion or Electrify) decides the wipe; otherwise the collapse's first death with a culprit does. When a tower
went unsoaked because its soaker was already dead, the wipe goes to whoever caused that death.

### Boss HP checkpoints

For each major mechanic (Paradeigma II, Superchain I, Paradeigma III, Palladion and both Superchain II sets),
the chart shows how far the best and the median pull were ahead of or behind the pace for a kill at enrage when
the mechanic's cast began: Clear is on pace to kill exactly at enrage (~7:38), Comfy about 13 seconds earlier.
The dot after each best value is green at Comfy or better, yellow at Clear or better, red behind. The table view
has the exact HP.

### Damage lost to deaths

Every death costs the time spent dead, from the lethal hit until a raise (or the end of the pull), and after a
raise 100 seconds of Weakness, which cuts a player's damage by 4.9% (Brink of Death 6.8%). Both are measured on
these logs from hit sizes with every other buff accounted for; Damage Down, it turns out, does not reduce damage
in this fight, so it costs nothing by itself. The lost time is valued at the dead player's own rDPS in that phase
of the fight (from their clean pulls), so a dead buffer also costs the buffs they would have given, and a death
in a downtime phase costs less than one in the opener. Only time before the pull was lost counts.

The cost goes to whoever caused the death, split when the classifier names several, and is shown as boss HP and
as seconds of kill time at the pace of a peer clear. Deaths without a culprit are shown as "No culprit found".

### Damage by phase

The fight is split at the HP checkpoints into seven phases (`WINDOWS` in `scorecard.py`). In each phase a
player's nDPS is compared with clearers on the same job in the same phase, pots removed. nDPS leaves out other
players' buffs, so a phase reads the player's own rotation whatever the party's buffers did. A phase is only
measured from pulls where the player was alive and unweakened through all of it before the pull was lost, and
needs two such pulls before it is compared; late phases rarely have them yet. The tooltip and table view add
uptime in the phase against clearers of the role.

## How mistakes are attributed

`classifier.py` finds every Damage Down and lethal hit in a pull and checks it against the strategy described
in the trainer's mechanic briefs (`briefs.html`). The first mistake of a pull is the earliest of these, plus
any others within 1.5 seconds.

| Mechanic | What is checked |
|---|---|
| Paradeigma I | Which light party baits each White Flame wave is learned from the group's own pulls. A missing baiter is blamed, not the players their laser hits instead. Trinity of Souls hits are the victim's. |
| Paradeigma II | The quadrant sweep (supports clockwise from north-east, DPS counter-clockwise from north-west) says where each Soul should drop its tower. Checks wrong quadrant, two towers stacked, a tower nobody soaked, the wrong soaker, unstretched tethers, and players standing in a tether laser or Soul AoE. Ray of Light hits are the victim's. |
| Superchain I | Purple pairs and orange cones, the two laser groups (by Soul and Tilt), the Heavensflame spread, and the final towers. Green orb and donut hits are the victim's. |
| Paradeigma III | Support towers: a support missing from their tower, or two supports in one, leaves a tower empty and Electrify wipes the raid; the support who does not belong on that platform is blamed (Quartered north, X-Marked south, bright Souls in the middle). The + and X: dropped from the wrong platform, or the owner not stepping out of their own arms. DPS tether lasers that are unstretched or clip a support. Whether each bright tower went to the centre corner or its own tile, the White Flame baits (the + and X supports and the same-colour DPS pair), and the opposite-colour soakers. |
| Later mechanics | Generic rules only: standing in an avoidable AoE is the victim's mistake. |

A death that follows the same player's earlier mistake is counted as part of that mistake. When a mechanic
fails because the player who should have done it was already dead (an unsoaked tower, a bait that found
someone else), the blame passes to whoever caused that death. A player who dies to a hit that was theirs to
take is marked as healing or mitigation, with no culprit. Anything the rules cannot explain is left
unattributed rather than guessed.

The classifier assumes the group plays the strategy in the briefs: the line-up for Paradeigma I rather than
tank invulnerabilities, the quadrant sweep, and the Paradeigma III placements. A group that plays a mechanic
differently will see players blamed wrongly for it.

## The benchmark

`benchmark.json` holds what players in other groups' clears do, per job: Savage P1 clears from 2025 and 2026
that took 5:30–7:50, played at level 90 in capped gear like ours. Level 100 runs and lower-gear runs are left
out, tincture damage is removed, and players who died are skipped. Each job's value is the average over
distinct players, kept separately for peer clears (7:10 or slower) and fast ones. It covers 0:00–2:00 (rDPS,
nDPS, uptime) and every phase of the fight (nDPS, uptime; only phases a kill lived through, so Superchain IIB
comes from the slower clears alone).

It also holds the boss HP checkpoints. For each mechanic, a line is fitted through every benchmark kill: the
HP % left when the mechanic began against how long the kill took. Clear is that line at 7:38, Comfy at 7:25.

The file is a snapshot. To rebuild it:

```
python tools/scorecard/build_benchmark.py [--since 2025-01-01] [--until 2026-10-18] [--out FILE]
python tools/scorecard/build_benchmark.py --checkpoints-only     # only refit the HP checkpoints, same kills
python tools/scorecard/build_benchmark.py --windows-only         # only redo the per-phase values, same kills
```

A full rebuild reads several thousand report pages and can use an hour or more of the API's hourly budget; it
waits out the rate limit by itself and caches its progress in `.cache/benchmark/`, so it can be stopped and
resumed. Run `build_site.py --reanalyse` afterwards so the site picks up the new values.

## Files

| File | Purpose |
|---|---|
| `build_site.py` | The command: adds reports to the website's data (`site/data.json`); `--publish` writes the passphrase-protected copy to `stats/` |
| `scorecard.py` | The analysis: fetching, mistakes and wipes, damage against clearers, damage lost to deaths, damage per phase |
| `classifier.py` | Mistake attribution |
| `fflogs.py` | FFLogs v2 client: token, rate-limit waits, paged events, batched tables |
| `benchmark.json` | Benchmark snapshot used for the damage, uptime and HP checkpoint comparisons |
| `build_benchmark.py` | Rebuilds `benchmark.json` |
| `encrypt_data.js` | Encrypts the data for `--publish` (Node) |
| `site/` | The website: `index.html`, `style.css`, `app.js`, and the generated `data.json` (git-ignored) |
| `.cache/` | Downloaded reports, the API token and benchmark progress (git-ignored) |

The folder is left out of the GitHub Pages site by the deploy workflow.
