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
| `--cached` | Uses the cache only: parts a cached report is missing (such as the rDPS raid buffs gave others) are left out instead of fetched. For when FFLogs is down; a normal run later fills them in. |

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

### Archived reports

FFLogs archives reports after a while (in October 2026, everything logged before about July 2024). Their fight
list stays public, but their content is only readable by an account with an FFLogs subscription, through its
user API. To let the tools read them, register a redirect address on the API client (at
<https://www.fflogs.com/api/clients/>, for example `http://localhost:8765/fflogs-callback`) and log in once:

```
python tools/scorecard/fflogs.py --login [--redirect http://localhost:8765/fflogs-callback]
python tools/scorecard/fflogs.py --check      # confirms an archived report can be read
```

The login opens FFLogs' sign-in page in the browser and catches the reply on that address (authorization code
with PKCE). The user token is saved in `.cache/user_token.json` (git-ignored) and renewed automatically when
FFLogs gives a refresh token. From then on, a query that FFLogs refuses as archived is asked again through the
user API; everything else keeps using the app token.

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
`/stats/` under the trainer's address. Run `--publish` again after adding or re-analysing reports. The published
`index.html` loads `style.css` and `app.js` with a version stamp (`?v=` and a hash of the file), so browsers fetch new
page files after a deploy rather than mixing a cached stylesheet with a new script.

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
| Raid days | Tiles: pulls, best pull, furthest seen (the longest pull, the mechanic it reached, its day, group and pull), latest day, mistakes per pull; the burndown; trends across days (how far pulls got, pulls clean through each mechanic, mistakes per pull and per minute, damage lost to mistakes, party DPS against the clears) and a table of days |
| Day | The day's groups side by side, each group's boss HP checkpoints, and heatmaps of all mistakes and of what wiped each group (rows named by mechanic, see below) |
| Group | The player scorecard; every pull's length with its first mistake and what lost it; boss HP checkpoints; damage lost to deaths, by player and by cause; every player's damage per phase against clearers; heatmaps of mistakes and wipes by player |
| Rotations | The optimizer's rotations (`#/rotations`, linked in the header): a chart and a table of every job it covers, then each job's GCDs and each GCD's rotation on the fight timeline (see Rotation ceiling) |
| Gear | The best-in-slot sets (`#/gear`, linked in the header): a table of each job's set and, per job, the set drawn like the game's character window with its DPS per GCD tier (see Best-in-slot gear) |
| Player | Mistakes per pull and wipes (weighted by confidence, with their counts by confidence), damage and opener damage against clearers, uptime, what one death of theirs costs (time dead plus the full Weakness at their rDPS, as boss HP, kill time and against the group's mistake budget); damage per phase; mistakes by cause (one bar each: dark red for the mistake that lost the pull, red for other deaths, orange for Damage Downs; wipes put on them without a recorded mistake of theirs count only in Wipes caused); rDPS on every clean pull, with the rotation ceiling for jobs the optimizer covers and how far their pulls are from it, linking to its rotation (see below); every mistake with its pull, time and confidence; every death with its pull and time, the hit that killed them, the classifier's cause and the culprit (self, another player, or none found) with its confidence, marked when it decided the wipe or came after it (`death_list` on each pull); the player across raid days (mistakes per pull and per minute in pulls) |

The player page's "What their mistakes cost" card (boss HP lost to deaths they caused, by cause) is hidden for now: set `SHOW_MISTAKE_COST` in `site/app.js` to `true` to bring it back.

Wherever a mistake is named (the mistake and wipe heatmaps, Raid leader focus, a player's Work on this, Mistakes by cause and top issues), it starts with the major mechanic it happened in, in the short form of How far pulls get, then the mistake: "SC I: Orange cone overlap", "Para II: Soul tower in the wrong quadrant". A mistake that happens in several mechanics gets a row for each (Trinity of Souls in Para I, Dialogos and SC I). Labels that already name the mechanic don't repeat it. The stored labels are unchanged; the names are made when the page draws (`causeName` in `site/app.js`).

Every chart has a Table button for the same numbers as a table and shows details on hover or keyboard focus.
The theme follows the system and can be switched with the button (or `?theme=light` / `?theme=dark` in the
link).

### The scorecard

| Column | Meaning |
|---|---|
| Mistakes/pull | The player's mistakes per pull: every death or Damage Down they caused, not just a pull's first. A mistake that kills several players counts once, and deaths that are only fallout of the player's own earlier mistake are not counted again. Being killed by someone else's error does not count. Mistakes are counted until the pull is lost; the collapse after that is not. Each counts by the classifier's confidence in its culprit (see Confidence below): high in full, medium 0.75, low 0.5. Deaths/pull and DD/pull split it the same way. |
| Wipes | Share of the player's pulls where their mistake is what lost the pull (see below), each wipe counted by the confidence of the entry that decided it, as mistakes are. |
| vs Clears | rDPS over 0:00–2:00, averaged over the player's best quarter of clean pulls, against the average player on the same job in the benchmark's clears without The Echo; * when only 1–2 clearers played the job. |
| Uptime | Active GCD time over 0:00–2:00, against clearers of the same role. |

Grades are coloured dots: green good, yellow ok, red worth focusing on. `*` marks a comparison against only one
or two clearers, which is rough.

| Grade | Mistakes per pull | Wipes | Damage vs clears | Uptime vs clearers |
|---|---|---|---|---|
| green | 0.30 or fewer | 10% or less | within 5% | within 0.5 points |
| yellow | 0.60 or fewer | 20% or less | within 12% | within 1.5 points |
| red | more | more | more | more |

With eight players and one wipe a pull, a fair share of the wipes is 12.5%. The thresholds are constants at the
top of `scorecard.py` (`G_MIST`, `G_WIPE`, `G_DMG`, `G_UP`), and so are the confidence weights (`CONF_WEIGHT`). The
group and day pages' mistakes per pull are weighted the same way. Damage over 0:00–2:00 is only measured on pulls
with no death or Damage Down before 2:00, so every player is compared on the same opener and mechanics.

### Who lost the pull

Pulls run until the whole party is dead, so every pull that is not a kill is a wipe. A death without a hit in the
last 20 seconds of a pull (`JUMP_S`; above half HP after any hit in the 5 seconds before) is a player jumping off the
arena once the wipe is called: only deaths before the first jump count, and a pull with none before it was called
without one ("Wipe called", no culprit). 419 of the 427 deaths without a hit come that close to the end; the other
eight, single players mid-pull, stay ordinary deaths without a culprit. The collapse is the last run of deaths with
less than 15 seconds between them (`CASCADE_GAP`); earlier deaths the group recovered from do not count. One player
outliving the rest by more than that (an invulnerability, a late raise) does not make a collapse of their own unless
the wipe was called. A mass death in the collapse (four or more players to one ability within 3 seconds, or two to a
tower explosion or Electrify, which kill everyone left, within 5 seconds of the collapse's start: `RAIDWIDE`) decides
the wipe; otherwise the collapse's first death does, or a death with a culprit within 1.5 seconds of it (the same
hit). Deaths within 0.6 seconds of the deciding one (`SIMULTANEOUS_S`: one step of a mechanic; its next step comes
0.8 s or more later), each to its own mistake, lost the pull with it, so their culprits share the wipe; so do the
culprits of a mass death's other deaths, except that an explosion or Electrify is its own cause's alone. When no rule
explains that first death and no mistake came before it in the pull, the wipe has no culprit ("No culprit found")
rather than going to a later death that may be its fallout; when it follows an earlier mistake, the collapse's first
death with a culprit decides. When a tower went unsoaked because its soaker was already dead, the wipe goes to
whoever caused that death. A collapse in a mechanic not blamed yet (see the rule book below) has no culprit ("Not
blamed yet").

### Boss HP checkpoints

For each major mechanic (Paradeigma II, Superchain I, Paradeigma III, Palladion and both Superchain II sets),
the chart shows how far the best and the median pull were ahead of or behind the pace for a kill at enrage when
the mechanic's cast began: Clear is on pace to kill exactly at enrage (~7:38), Comfy about 13 seconds earlier.
The dot after each best value is green at Comfy or better, yellow at Clear or better, red behind. The table view
has the exact HP.

### Damage lost to mistakes

Every death costs the time spent dead, from the lethal hit until a raise (or the end of the pull), and after a
raise 100 seconds of Weakness, which cuts a player's damage by 22% (Brink of Death taken as 50%). Every Damage Down
costs 38% of the player's damage until it wears off (or they die). These are measured from each player's own hits of
the same skill during and around the debuff: Damage Down x0.62 over 1,264 windows (an in-game combat log agrees),
Weakness x0.78 over 479; Brink of Death had too few samples. (An earlier regression on FFLogs' per-hit buff list read
Damage Down as costing nothing and Weakness as 5%: FFLogs does not list those debuffs reliably on hits.) The lost time
is valued at the player's own rDPS in that phase of the fight (from their clean pulls), so a dead buffer also costs
the buffs they would have given, and a death in a downtime phase costs less than one in the opener. Only time before
the pull was lost counts.

The cost goes to whoever caused the mistake, split when the classifier names several, and is shown as boss HP and
as seconds of kill time at the pace of a clear, combined and split into deaths and Damage Down. Mistakes without a
culprit are shown as "No culprit found".

**Mistake budget** (group and day pages): how much boss HP a group can lose to mistakes over a whole kill and still
kill before enrage, 1 - (minimum party DPS to clear / the group's 0:00-2:00 party DPS), also given as deaths or Damage
Downs. Those are priced at full length, since in a kill they are not cut short by a wipe: a death is the median time
dead until raised (10 s in our reports) plus the raise's Weakness, a Damage Down its median length (6.6 s) at -38%, both
at the group's average player DPS (party DPS / 8). The scorecard also splits each player's mistakes into Deaths/pull
(mistakes that killed someone) and DD/pull (those that only gave Damage Down).

### Rotation ceiling

For every DPS job the rotation optimizer covers (`tools/rotation`), the player page's rDPS-on-clean-pulls chart marks
each pull with a ceiling: the best rotation without raid buffs at the player's GCD over 0:00-2:00, with the runs our
strategy needs at their worst for the role (the Paradeigma I slot with the most running, R1 or M2, and each mechanic's
variant with the most), converted to their DPS (their damage per potency and crit / direct-hit gain from their own hits,
the same for every pull), plus what that pull's raid buffs added to the other players' damage (FFLogs' rDPS given: a
Reaper's Arcane Circle), which rDPS credits to them. The table view splits the two. The player page's "vs optimized
rotation" card, under Damage, gives their median clean pull's share of the ceiling (and the gap in DPS), their best
pull's and the ceiling itself (in rDPS, the median over their pulls, split into its nDPS and the buffs' credit), and
links to the rotation at their GCD.

**Which FFLogs metric is which.** FFLogs' fields relate exactly (checked on every player of the cached clears):
nDPS = raw damage − what others' buffs added to it (`totalRDPSTaken`); rDPS = nDPS + what the player's own buffs and
debuffs added to others' damage (`totalRDPSGiven`); aDPS = raw − only the single-target buffs received (Dance Partner,
cards); cDPS = aDPS + the credit given. A player's own buffs on themselves count as their damage in all four. On the site:
our players' pulls and the clears are rDPS, with tinctures taken out of both (ours: `fetch_pots` / `pot_gain`, the clears'
way); the optimizer's ceiling and the rotation pages' expected DPS are nDPS (no one's buffs, no credit given), labelled so;
the ceiling becomes rDPS on player pages by adding each pull's `given`, and the best rotation's expected rDPS (the
Rotations table and chart) adds the job's credit up to Palladion. Opener damage and damage by phase are nDPS.

**The Rotations pages** (`#/rotations`, the Rotations link in the header) list the jobs the optimizer covers, grouped by
role (melee, physical ranged, magical ranged) with job icons and ordered by expected rDPS:

- **The chart**, all of it over 0:00-2:00: a box over our players' clean rDPS (whiskers to 1.5 times the box's width),
  a tick at the job's ceiling with a band behind it, and a dot per clear player (`rdps_each`, each one's mean over their
  kills). The ceiling and band come from the gear model (`tools/gear`; `ceiling.py` writes `tools/gear/.cache/bis_site.json`,
  which `scorecard.rotations()` adds as each job's `bis`): the rotation searched for 0:00-2:00 with the job's best-in-slot
  gear, materia and food at the GCD where gear and rotation together do best over the phase, in nDPS, plus our median
  credit for buffs given; the band one standard deviation either side from crit and direct-hit luck alone (the rotation's
  hits one by one, at the set's rates; Reaper: ±427 on 13,577, 3.1%). A job without a `bis` entry keeps the older ceiling,
  the best of its rotations' own 0:00-2:00 searches at our players' median conversion, its band from the weakest to the
  strongest player's gear (each player's own ceiling over the median's at their GCD, players with 5+ clean pulls,
  `BAND_PULLS`; for a job none of ours plays, the clears' `dps_lo` / `dps_hi`); the chart's note names such jobs. A
  ceiling is an expected value (average crits, direct hits and procs), so single pulls beat it on luck: our best pulls
  reach 0.99-1.085 of their own ceiling, medians 0.87-0.98. Summoner's top clear sits ~3% over the band, whose top is our
  stronger Summoner's conversion (our two convert 21% apart): better gear than ours.
- **The table**: each job's best rotation (by expected nDPS) with its expected nDPS to Palladion plus what the job's
  raid buffs give the others over that stretch, which is our players' median 0:00-2:00 credit (the clears' `given` for a
  job none of ours plays) times the job's `given_ratio` in `benchmark.json` (the clears' credit rate up to Palladion over
  their 0:00-2:00 rate: three bursts against one and steady buffs like Dance Partner, from the clear players who used
  their raid buff in each burst as the optimized rotations do; `given_ratio_all` for a job without clears). Its 0:00-2:00
  ceiling column is the best of the job's rotations' own 0:00-2:00 searches (`ceiling_2min`, at the median conversion)
  plus our players' median 0:00-2:00 credit, no scaling needed. The rotation to Palladion is not the 0:00-2:00 one: it
  holds resources for after the downtime, and its stretch has three bursts against 0:00-2:00's one and pre-pull
  preparation, so it sits 7% under (Pictomancer) to 3% over (Dragoon) the 0:00-2:00 ceiling.
- **A job's page**: the same columns for each of its GCDs (every GCD it was searched at: our players' and any extra),
  under what P1 asks of the job with our strategy (`ROT_CHALLENGES` in `site/app.js`, from the optimizer's findings:
  update it when a job's rotation or our strategy changes), the fight timeline without a rotation (hovering or tapping a
  point marks the stretches it is about), and the set card of Best-in-slot gear; the GCD that is the set's carries a BiS
  tag. Monk's rotations also depend on the crit rate (its chakra), so its are per GCD and crit rate.
- **A GCD's page**: the rotation from the pull until Palladion takes Athena away (4:41) with its expected DPS over that
  stretch, its own 0:00-2:00 ceiling (a search over the scorecard's window, which is what players' ceilings use), its
  potency, casts per skill and any resources wasted. It is drawn compactly in the game's action icons, a line for each
  stretch between major mechanics: every GCD on the line with the oGCDs woven after it smaller and raised beside it (the
  table view has every GCD's start time, cast and running). The icons come from XIVAPI by action name (`gamedata.icons`,
  cached in `.cache/icons/`) and go into the site data as data URIs, so the published copy carries them encrypted like the
  rest. GCDs cast while running are marked (a green bar under an instant GCD the player runs through, a blue one under a
  hard cast whose run fits only in its slidecast and the gap after), with how much running falls before the next GCD:
  the optimizer only makes sure each run fits outside cast bars, so `dps.py` places them (longest stretches outside cast
  bars first, as late as they allow, which puts them on instant GCDs where it can). On top, the fight timeline it plays
  around: each major mechanic's start (its boss cast), the windows in which our strategy needs a run (the seconds needed;
  "movement" for the raidplan's mechanics, lighter "movement, pre-position" between them, where the clears' median path
  is used), a melee's stretches out of reach and spots the plan fixes (positionals need True North), and the rotation's
  GCDs and oGCDs. The timeline comes with the rotations (`dps.py --site`, from `p12s.py`).

**Expected DPS** converts the potency at our players' damage per potency and crit / direct-hit gain on the job, the
median of them, each player moved to the rotation's GCD first: Spell or Skill Speed comes out of the same gear budget as
critical hit, direct hit and determination, so a faster GCD costs about 0.4% damage per potency per 0.01 s (level-90
formulas; our Black Mages' gear falls 0.38% per 0.01 s). The range is the same over those players. A job none of our
players plays (Ninja) gets its rotations too, at the GCDs of the benchmark clears' players on it since the job's
`CONVERT_SINCE`, and expected DPS converts at theirs; the pages say so, and no player page links there.

**Refreshing them**: `python tools/rotation/dps.py --job blm --site` (and `--job rpr`, `--job drg`, ...; `--offline`
converts from the acts caches when FFLogs is down, and the pages say so; `--gcds 2.30,2.40` adds GCDs none of our
players has; `2.48/2.15` names the hasted GCD where a tier holds two, as Samurai's, Viper's and Black Mage's can), then
`build_site.py --reanalyse` (the rotations themselves are picked up by any `build_site.py` run).

### Best-in-slot gear

The Gear pages (`#/gear`, `#/gear/<job>`) and the set card on each Rotations job page show the gear model's sets
(`tools/gear`, `sheets.py`; `scorecard.gear()` adds them to `data.json` as `gear`, with the item, materia and food
icons from XIVAPI, cached in `.cache/icons/`): the best searched GCD tier's set and, as tabs, the searched tiers within
0.4% of it. A job's Rotations table tags the GCD that is a set's (the rotations' GCDs are before a trait's haste, so
Monk's and Ninja's compare at that); the tag only shows where a rotation was searched at that GCD (`dps.py --bis-gcds`, with the hasted GCD for Samurai and Viper;
`scratch/gear/rerun_all.py` adds the missing ones). Such rotations are marked `bis_gcd`: once no set sits at their GCD and no
player plays it, the next `rerun_all.py` run drops them, while extras asked for with `--gcds` stay.
Any `build_site.py` run picks up new sets.

### Damage by phase

The fight is split at the HP checkpoints into seven phases (`WINDOWS` in `scorecard.py`). In each phase a
player's nDPS is compared with clearers on the same job in the same phase, pots removed. nDPS leaves out other
players' buffs, so a phase reads the player's own rotation whatever the party's buffers did. A phase is only
measured from pulls where the player was alive and unweakened through all of it before the pull was lost, and
needs two such pulls before it is compared; late phases rarely have them yet. The tooltip and table view add
uptime in the phase against clearers of the role.

### Progress

- **Burndown** (overview): every pull's boss HP at its end, all groups together in the order they were played (groups
  mix players, so there is one burndown), the best so far (steps) and dotted lines at the first pull that reached each
  mechanic, as on tomestone.gg; above it the pull count, hours in combat and best pull. Pulls with The Echo are drawn
  but not counted for the best.
- **How far pulls get** (overview): the share of each day's pulls that reached each mechanic.
- **Where pulls ended** (group page): pulls that ended between each pair of mechanics, by pull length; the longest
  bar is the wall.
- **Their top issues** (player page, Across raid days): their three most frequent mistakes and their costliest
  rotation issues per minute, raid day by raid day. Mistakes are per pull that reached the mechanic they happen in
  (still going when it began; start times from `MECH` in `classifier.py`, passed on as `mech_start`), so getting
  further on later days doesn't read as more mistakes. Each row is one mistake in one mechanic (Trinity of Souls in
  Para I and in Dialogos are separate rows). Rotation issues are per minute alive, only on days with the same job. Trend:
  improving or worse when the later days differ from the earlier by 20% or more.

### Focus lists and practice links

**Raid leader focus** (group page) lists what to raise first: the mechanics that ended the most pulls and who failed
them, the most common mistake, the costliest rotation issues against the clearers, the latest raid buff and weak
openers. **Work on this** (player page) does the same for one player, at most five points: mechanics whose mistakes
lost pulls, their most frequent other mistake, the two costliest rotation issues, an opener 5% or more below clearers (with the skills cast fewer times than in the clears' opener and the cooldowns that went out late),
and a raid buff pressed 1.5 s late or skipped. Every point links to its section, and mistakes in a mechanic the trainer
has a drill for link to it: **Drill** opens the trainer on that mechanic (`index.html#<mechanic>`) and **Brief** its
brief (`briefs.html#<mechanic>`). The open drills are listed in `DRILLS` in `site/app.js` (Paradeigma I, Paradeigma II,
Superchain I, Paradeigma III); add a mechanic there when its drill opens. The links point one level up from the scorecard,
which is the trainer on GitHub Pages.

### Burst

On a group's page, each 2-minute burst: when every raid buff landed against the clears' median for that buff and burst
(seconds, + is late), from pulls that got through the burst; uses skipped while the buff's user was alive; and the
spread from the party's first raid buff to its last against the clears.

### Opener

On a player's page, their openers against the best opener the clears play (`opener_ref` in `checks.py`): GCDs,
damaging oGCDs, raid buffs and the other oGCDs planned into openers (`OPENER_ALSO`: Astrologian cards and draws,
Lightspeed, Swiftcast, Infuriate, Enshroud, Hypercharge and the like). Potions, Sprint, mitigation, movement, True North
and Lucid Dreaming are left out. A hard cast is timed from its begun cast, an instant (Swiftcast, Lightspeed, Dualcast,
procs) from the cast itself. Clears' openers run from before the pull to 0:22; openers within a few casts of each
other count as one variant. The reference is the variant most clears play, unless another one played by at least three
clears clearly does more opener damage: its median ahead by more than 1.5 standard errors of the difference. Within one
opener, gear and crits spread players by about 1,000 nDPS, more than most openers differ, so the highest median alone
would chase noise. Echo clears count with their damage divided by 1.2.

Compared is what matters, not the order:
- **Casts per skill**, over as many GCDs as the reference opener has (the player's casts are read to 0:30 and cut
  there), so a slower GCD from gear doesn't count as a missing filler. Flagged at half a cast or more per pull fewer or
  more than the reference.
- **First cast of each cooldown and raid buff** (oGCDs with a recast of 30 s or more, the job's cooldowns, raid buffs;
  not gauge spenders), median over their pulls against the median over the variant's clears. Flagged at 1.5 s or more
  either way.
- **GCD order is not compared.** Swapping two GCDs inside the opener changes nothing.

**Jobs with fewer than three clears** are compared within our own groups instead (`group_openers` in `checks.py`).
Every other player on the job counts like one clear, with their usual opener and median opener damage over all raid
days, so a regular on the job doesn't outweigh the others; the player themselves is left out. Bard has no clears at
all, so a BRD gets only this opener comparison, no rotation checks. With four BRDs the reference is thin (each is
compared with three others, often one other player's opener), and the card and tile say so below five players.
**Kit changes the clears predate** (`KIT_CHANGES`): only clears after the change count for the job's opener. White
Mage is the one so far: it now starts the pull with a Blood Lily (Afflatus Misery
right away, in 98% of our pulls), which none of the 12 WHM clears (2025-03 to 2025-12-12) had, so the change came after
2025-12-12. The card, the opener tile ("vs groups") and the focus lists say when a job is compared within our groups.

The card lists the flagged differences and shows the reference opener next to their usual one (red: a skill the other
doesn't have); its table view has the per-skill counts and first casts. Dancer steps count as one step, since they come
in a random order. Opener damage is nDPS over 0:00-0:20 (tinctures removed), from pulls the player was alive through,
against the clears playing the reference opener and against all clears on the job. The card's title carries the same colour dot as the opener tile, from the latter: green from −5%, yellow from −12%,
red below. For the latter, clears with The
Echo are left out; a job with fewer than three other samples includes them, damage divided by 1.2, and the card says so.

### Abilities

On a player's page, casts per minute of every damaging skill against clearers on the job, over the same stretches as
the rotation checks (0:00-0:55 against clears that move through Paradeigma I). GCD skills are compared at the player's
own GCD speed, since a slower GCD from gear fits fewer casts without any mistake. The difference is worth the player's
own average damage per cast (DoT ticks included). It overlaps with the GCD gaps: those say when time was lost, this
says which casts it cost.

**Grades on the Rotation and Abilities cards.** Each card's title carries a colour dot for the potential gain against
the clears as a share of the player's DPS: green under 5%, yellow under 15%, red from 15%.
- **Rotation:** the costed checks added up.
- **Abilities:** net, so extra casts of one skill offset missing casts of another (counting only shortfalls would
  inflate it: casting more of one skill usually means casting less of another).

The two overlap, so they are graded apart, never added. Over our 175 player-days, rotation splits 127 / 39 / 9
(green / yellow / red) and abilities 93 / 57 / 25. Healers come out highest (median 10.8% on abilities), partly from
healing GCDs our groups need.

### Pulls

Under each group, **Pulls** lists every pull: length, boss HP, how it ended and whose mistake decided it, mistakes,
deaths before the wipe, boss HP lost to deaths, and two party figures: the players' average nDPS against clearers on
their jobs (over the phases they were alive through) and their summed rotation loss against the clears. Each pull has
its own page with every player's mistakes, a death that came before the pull was lost, damage against clearers and that
pull's rotation loss with its biggest check, plus the pull's mistakes in time order. The group page's pull chart and the
pull numbers in a player's mistake list link there.

### Rotation

Simple, nameable rotation mistakes per player and job (`checks.py`), each against clearers on the job:

| Check | What counts |
|---|---|
| *Cooldown* held | an oGCD sat ready at full charges while the player was alive. Only oGCDs that deal damage or are damage buffs / resource generators, and that the clears use on cooldown (75-115% of possible uses) |
| GCD gaps | time between GCD starts (the begun cast for hard casts) beyond the player's usual GCD + 0.3 s, longer casts and GCDs with their own recast allowed for; split into *after an interrupted cast*, *weaving delayed the GCD* (the GCD started as an oGCD's animation lock ended) and *nothing cast* |
| Casts interrupted | a begun cast that never went off (its time is in the gap row) |
| Healing GCDs | healers: GCDs that never deal damage for the job; Eukrasia, raises, Esuna and White Mage's lily heals (they pay back through Afflatus Misery) aside |
| Combo broken / Positional missed | a hit with less bonus (FFLogs' `bonusPercent`, the share of its potency from combo and positional bonuses) than the clears usually get on that skill; no bonus after the wrong GCD is a broken combo. The damage lost is exact: hit x ((1 - got) / (1 - usual) - 1) |
| DoT ticks missed | ticks missing after the first one, for jobs whose clears keep a DoT up |
| *Proc* expired / overwritten | short self-buffs the clears spend with a cast (85%+ of them removed at a cast's own timestamp): run out unspent while alive, or refreshed while still up. Priced at the cast that normally spends it, less the filler when that cast is a GCD |
| *Buff* down | self-buffs the clears keep up (85%+): seconds down while alive after 0:15; damage buffs priced at their value (Surging Tempest, Power Surge, Hunter's Instinct +10%, Fugetsu +13%, Standard Finish +5%), haste buffs shown in seconds |
| GCDs in *buff* | GCDs started inside the player's own damage buff (20 s; Wildfire 10 s), per window, against the clears' average |
| *Gauge* overcapped | gauge wasted at the cap, replayed from casts with a table of gains and spends per job (`gauges.py`): Gunbreaker cartridges, Warrior Beast Gauge, Reaper Soul and Shroud, Dark Knight Blood (with Blood Weapon's +10 per weaponskill), Samurai Kenki (with Tengentsu's Foresight), Machinist Heat and Battery, Dragoon Firstminds' Focus. A table is used only when it replays the clears with under 6% of spenders unaffordable, which tests it. Priced per unit at the main spender's hit (less the filler for GCD spenders); gauges whose spender opens a sequence (Heat, Battery, Shroud) are not priced. Healer gauges buy healing, and Monk Chakra, Dancer Esprit and feathers, and Ninja Ninki come from crits, procs or shadow hits, so they are not replayed. Black Mage: Polyglot overcapped (`tools/rotation`) |

Every check runs from 0:00 until the player died or the pull was lost, skipping time dead, and the clears are
measured over the same stretch (0:00 to the same time), so movement and other mechanics that cost everyone uptime
cancel out. Level-90 cooldowns and charges come from how the clears use them (the game data's values are before
traits); whether an action is a GCD comes from the game data via XIVAPI (`gamedata.py`). The cost of the difference
uses the player's own hits: a held damaging oGCD at its average hit, a missed tick at their median tick, an idle GCD
second at their damage per second alive, a lost Polyglot at their average Xenoglossy. Buffs held get no cost, since
their value depends on what they would have covered. The idea list follows xivanalysis's modules, adapted to level 90 and to
comparison with the clears. Checks such as Thunderhead or Firestarter left unused were
tried and dropped: the clears let them lapse as often as we do, so they are not mistakes.

## How mistakes are attributed

`classifier.py` finds every Damage Down and lethal hit in a pull and checks it against the strategy described
in the trainer's mechanic briefs (`briefs.html`). The first mistake of a pull is the earliest of these, plus
any others within 1.5 seconds.

| Mechanic | What is checked |
|---|---|
| Paradeigma I | Which light party baits each White Flame wave is learned from the group's own pulls. A missing baiter is blamed, not the players their laser hits instead; when the baiter was already dead, whoever caused that death is. A player hit only by lasers that also hit a baiter of that wave stood in that baiter's line: their own mistake (medium), not the missing baiter's. Trinity of Souls hits are the victim's. Athena's auto-attacks are magical and a White Flame leaves Magic Vulnerability Up for 6 s, so whoever holds her at ~50.5 s must not have been hit by wave 2: light party 1's tank baits wave 1 and keeps her (in 708 pulls), light party 2's baits wave 2. A death to that auto-attack through wave 2's vulnerability goes to whoever caused the other tank's death when they were already dead (most of them), to the victim when they provoked Athena while carrying it or, as light party 1's tank, took a wave 2 laser, to the other tank when they shirked aggro onto them, and to both tanks otherwise (medium). |
| Paradeigma II | The quadrant sweep (supports clockwise from north-east, DPS counter-clockwise from north-west) says where each Soul should drop its tower. Checks wrong quadrant, two towers stacked, a tower nobody soaked, the wrong soaker, unstretched tethers, and players standing in a tether laser or Soul AoE. Ray of Light hits are the victim's. The four players without a Soul hold the tethers: a laser that hit only Soul holders lost its holder, so when its holder was already dead the blame goes to whoever caused that death, and otherwise the Soul holder it hit stood in its line (or took the tether; medium). A Soul holder who dies before dropping still has a tower: the game drops it on another player (a Glow with no living owner came after a holder of its colour died, and hit one player, in every one of the 91 cached), so that hit and the tower going unsoaked are fallout of the holder's death. |
| Glaukopis | The tank swap. The first hit goes to the tank holding aggro when the cast begins and leaves Magic Vulnerability Up; the second goes to whoever holds aggro 1.2 s after the first (`SNAPSHOT`); a heavy auto-attack (~290k unmitigated) 3.2 s later goes to whoever holds it 1.2 s after the second. Our groups' swap: the second tank provokes during the cast, the first provokes back as the second hit lands. Only a death counts (a tank taking both and living meant to). The same tank killed by both hits: the first tank provoked back too early (from their casts: up to +1.1 s from the first hit put the second on them, from +1.2 s it did not), or the second tank never provoked, or, when the second tank's provoke came during the cast and the first held aggro anyway, both share it (medium). The second tank killed by the auto-attack: the first tank provoked back after +1.2 s from the second hit, or not at all (494 provokes back by +1.2 s took the auto-attack; every death to it came from +1.3 s or never). Casts come from the acts cache. |
| Superchain I | Purple pairs and orange cones, the two laser groups (by Soul and Tilt), the Heavensflame spread, and the final towers. Green orb and donut hits are the victim's, and a Damage Down from a green orb that lands with an orange cone is the orb's. The first resolution's spots: the cluster with two short chains sits on an intercardinal (`CLUSTER`, 8.25 y out on each axis, fitted to clean spreads) and the party stands in a ring around it (7.9 y), seat by seat: facing Athena from the cluster, the tanks either side of the line to her, then melee, healers, and ranged at the back, the 1s on the right, the 2s on the left (`SPOT_ANGLE`, measured in clean spreads: tanks 17 degrees off that line, melee 50, healers 98, ranged 146). Orange fires a cone from the cluster at each player, so players sharing one stood at the same angle: the one at least 20 degrees (`SPOT_MARGIN`) further off their spot is blamed (high from 40), all of them when each is that far off (a swap, medium), and otherwise they share it (low). A pull whose whole party fits its seats better mirrored (1s on the left) is read mirrored: it happens in rVkKM2 (6 of 7 spreads) and NjF16Q (6 of 14), early reports from before the groups followed one strategy. Purple fires at all DPS or all supports, each shared with the seat partner beside them (M1 with T1, M2 with T2, R1 with H1, R2 with H2): a target alone blames their seat partner (missing, or in another pair) when every player has a seat of their own, otherwise every missing player; three or more in one pair blames whoever's partner is not in it, or, failing that, those who are not of the pair whose spot (midway between its two seats) the crowd stood at. There are always 8 orange cones and 4 purple ones, so a dead player's goes to someone else (orange: a player hit twice; purple: someone at random): with a player already dead, the extra hits are blamed on whoever caused that death. A player in the laser not theirs is blamed for their own death (it kills through six sharers with its colour's Tilt), and a laser a sharer short blames whoever of its group lived and took the other laser or neither. The bright Souls' small AoE as they drop their towers is the owner's alone: a Strong Soul in it stepped in too early, a Heavensflame player in it did not spread away (a Heavensflame player left low by it and killed by their own Theos's Holy counts as this too, unless another Holy hit them), two bright Souls in each other's mean their towers dropped together (both, medium, the owner's own death to it too, and the Strong Souls' deaths soaking the two stacked towers are its fallout), and a bright Soul that took the wrong laser group dropped its tower on the wrong side. A dead bright Soul's tower is dropped on another player, as in Paradeigma II: that hit is the dead Soul's fallout. A tower soaked only by someone else is unsoaked: when its soaker was dead, whoever caused that death is blamed, wherever it dropped. |
| Dialogos | Apodialogos or Peridialogos is a hit the two tanks share (one tank alone takes twice the damage) and Dialogos, about 0.6 s later, a stack the rest of the party shares. Athena stands at the centre: Peridialogos aims the tanks' hit at the closest player and the stack at the farthest, Apodialogos the other way round, so the tanks belong at the centre for Peridialogos and out for Apodialogos, the party the opposite. Each player's place is read from their position at either hit, against the bands of clean pulls (`CENTRE_R`: Peridialogos tanks within 5.6 y of the centre, party from 7.7; Apodialogos party within 8.4, tanks from 9.8). A non-tank in the tanks' hit is blamed (standing in the tanks' place, or in line with them), unless the hit was aimed at a non-tank standing where the party belongs: then the tanks were out of place and are blamed. A living tank not in the hit is blamed for leaving it to the other. A stack aimed at a tank blames that tank; a stack aimed at the party blames whoever of the party is not in it, except a player the tanks' hit had just killed: that shortfall is whoever caused that death's. |
| Paradeigma III | Support towers: a support missing from their tower, or two supports in one, leaves a tower empty and Electrify wipes the raid; the supports who missed theirs share it, and of two in one tower the one who does not belong on that platform is blamed (Quartered north, X-Marked south, bright Souls in the middle). The + and X: dropped from the wrong platform, or the owner not stepping out of their own arms. DPS tether lasers that are unstretched or clip a support. Whether each bright tower went to the centre corner or its own tile, the White Flame baits (the + and X supports and the same-colour DPS pair), and the opposite-colour soakers. An unsoaked bright tower whose soakers were all dead is whoever caused those deaths', wherever it stood; one whose soakers took the White Flame its baiters missed is both pairs' (their roles swapped, medium); one both soakers left for the other tower is theirs together (medium); a dead bright Soul's tower dropped on someone is the dead Soul's fallout, as in Paradeigma II. Dying with a destroyed tile as its platform falls (`Sample`, like `Unnatural Enchainment`) is the victim's mistake. |
| Palladion | Not blamed yet (see the rule book). |
| Later mechanics | Generic rules only: standing in an avoidable AoE is the victim's mistake. |

A death goes to the faults about the very hit that killed it (several about one hit, like an explosion of two
unsoaked towers or one Electrify from two empty towers, are one cause, their culprits together); otherwise, unless the
hit was an avoidable one (which stays the victim's), to the earliest fault that hit them in the 4.5 seconds before. A
death within a second of an avoidable hit on the same player (STUNG_S: a donut just before a short laser share, a
green orb with an orange cone) is the victim's own whatever their HP, even when another player's fault made the
killing hit worse; across the caches these gaps run 0 to 1.0 s and the mechanic's next step comes 1.3 s or more later.
A death that follows the same player's earlier Damage Down or death is counted as part of that mistake. A later death in
the same mechanic from a mistake that hurt the player earlier is that mistake's: fallout when it was already counted,
counted there when it was not (a laser line that killed no one at once). When a mechanic fails because the player who
should have done it was already dead (an unsoaked tower, a bait that found someone else), the blame passes to whoever
caused that death (that death's culprits, not an older mistake of theirs); those culprits are named on the deaths it
leads to but their mistake is counted once, at the death that started it. A player who dies to a hit that was theirs
to take is marked as healing or mitigation, with no culprit. Anything the rules cannot explain is left unattributed
rather than guessed.

**Confidence.** Every blame carries how sure its rule is of the culprit: *high* (the rule says who: an avoidable hit,
a missing baiter, a Soul in the wrong quadrant), *medium* (inferred: who stood in whose line, both tanks for a swap that
neither cast explains, a crowd joining a pair) or *low* (shared between players the rule cannot tell apart, mostly
orange cones). Blame passed on through an earlier death (an unsoaked tower whose soaker was dead) is as sure as the
least sure of the deaths it comes from; blame for a death after the player's own earlier mistake is medium. Mistakes per
pull and Wipes count each by `CONF_WEIGHT` in `scorecard.py`: high 1, medium 0.75, low 0.5. On the hand-checked pulls
(below), counted mistakes were right 83% of the time at high (all 52 avoidable hits, 76% of the rule-based ones), 77%
at medium (48) and in 2 of 3 at low; wipes 72% at high against 44-58% at medium, counting a wipe that names part of its
culprits as half. So medium mistakes are about as reliable as rule-based high ones, while medium wipes are clearly
weaker; 0.75 sits between the two. Low is too rare to measure (19 counted mistakes over all reports) and is weighted
as blame split between two. These were measured on the classifier before the rules were fixed against the same pulls
(2026-10-26), so the suite agreeing with them now is no measure of accuracy: re-measuring needs pulls not yet checked.

**Testing a change.** `python tests/run.py blame` checks the classifier against 35 pulls checked by hand, every
incident's expected culprits and each pull's wipe (`tests/blame.py`; the cases, in `tests/blame_cases.json`, name
players, so they are git-ignored like `site/data.json`, and the suite needs the caches). It fails when a hand-checked
verdict changes. Verdicts the classifier is known to get wrong are recorded with the right answer and why (`python
tests/blame.py run --known` lists them; a fix that gets one right shows as FIXED). `python tools/scorecard/blame_diff.py`
then prints every attribution that changed over all cached pulls between the working tree and a git revision
(`--rev`, default HEAD) or saved copies (`--old-dir`), and totals of counted mistakes by mechanic, cause and confidence
and of wipes by what lost them, old against new, so a fix in one mechanic that moves counts in another shows up.
`python tests/blame.py show CODE FIGHT` lays a pull out for checking by hand, and `add` appends one to the cases.

The classifier assumes the group plays the strategy in the briefs: the line-up for Paradeigma I rather than
tank invulnerabilities, the quadrant sweep, and the Paradeigma III placements. A group that plays a mechanic
differently will see players blamed wrongly for it.

**The rule book** (`RULEBOOK` in `classifier.py`) says which rules judge each mechanic from which raid day (the report's
date, as the site groups raid days). A pull is judged by the latest entry dated on or before its day, so a strategy
change is a new dated entry and older pulls keep the rules they were played under; run `build_site.py --reanalyse`
after changing it. An entry is a rule function, `GENERIC` (only the generic rules; also any mechanic not listed) or
`NOT_YET`, which blames no one for anything in the mechanic: its deaths and Damage Downs are listed with their cause
and "not blamed", for a mechanic the groups are still learning. Fallout of an earlier mistake keeps its blame.

| Mechanic | Entries |
|---|---|
| Paradeigma III | From the start: two bright Souls in one middle tower share the blame. From 2026-10-26: the priority H1 > T1 > T2 > H2, west to east, says which of them belongs on the other platform, and only they are blamed. The seats come from the light parties learned in Paradeigma I (light party 1 is T1, H1, M1, R1). |
| Palladion | `NOT_YET`. To start blaming it, add `("YYYY-MM-DD", GENERIC)` or a rule. |

## The benchmark

**Minimum party DPS to clear.** The Party DPS 0:00-2:00 views show the 0:00-2:00 party DPS that is on pace to kill
just before enrage (7:38): boss HP over the enrage time, times the clears' median ratio of their 0:00-2:00 party DPS
to their whole-fight average (about 1.11; they front-load opener and burst). Stored as `party_dps_min` in
`benchmark.json`; about 79.4k with the current clears.

**The Echo.** Some clears were played with The Echo turned on (+20% damage, HP and healing): 16 of the 45, all among the
faster kills (Echo is what made them fast). They still count for everything about casts and timing (rotation checks, openers, burst, cooldowns, gauges)
but not for damage, boss HP checkpoints or kill time. The exception is a job with fewer than three clear players without The Echo: its
Echo clears count too, damage divided by 1.2 (rDPS, damage by phase, opener damage), marked `echo_corrected`. That
fills Dragoon, Gunbreaker, White Mage, Summoner, Red Mage and others; the corrected values land within a few percent
of the few clean ones. `python tools/scorecard/build_benchmark.py --rebuild` recomputes
`benchmark.json` from the kills it already lists. Our own reports are checked the same way: pulls with The Echo are left
out of every damage figure (rDPS against clearers, damage by phase, opener damage, party DPS, boss HP checkpoints, damage
lost to deaths) and the group, day and player pages say so; mistakes, deaths and rotation checks still count.

`benchmark.json` holds what players in other groups' clears do, per job: Savage P1 clears from Dawntrail on
(28 June 2024, patch 7.0; jobs played differently before it, so no earlier clear is ever used) that took
5:30–7:50, played at level 90 in capped gear like ours. Level 100 runs and lower-gear runs are left
out, tincture damage is removed, and players who died are skipped. Each job's value is the average over
distinct players, over every clear without The Echo (29 clears; an earlier split into peer
and fast clears was dropped: without The Echo the faster ones were only 6:54-7:08 and within 1% in party DPS). It covers 0:00–2:00 (rDPS,
nDPS, the rDPS their buffs gave others, uptime, and each player's rDPS), the buffs' credit up to Palladion against
0:00-2:00 per job (`given_ratio`, over every clear, The Echo included since it changes both alike, and only players who
used their raid buff in each 2-minute burst: about half the clears' Reapers hold the second Arcane Circle to 2:56-3:12,
leaving two before Palladion) and every phase of the fight (nDPS, uptime; only phases a kill lived through, so Superchain IIB
comes from the slower clears alone).

It also holds the boss HP checkpoints. For each mechanic, a line is fitted through every benchmark kill: the
HP % left when the mechanic began against how long the kill took. Clear is that line at 7:38, Comfy at 7:25.

The file is a snapshot. To rebuild it:

```
python tools/scorecard/build_benchmark.py [--since 2025-01-01] [--until 2026-10-18] [--out FILE]
python tools/scorecard/build_benchmark.py --checkpoints-only     # only refit the HP checkpoints, same kills
python tools/scorecard/build_benchmark.py --windows-only         # only redo the per-phase values, same kills
python tools/scorecard/build_benchmark.py --add --since 2024-06-28 --until 2024-12-31   # add a period's clears
```

`--since` is never earlier than 28 June 2024. Clears in archived reports count only after `fflogs.py --login`.

A full rebuild reads several thousand report pages and can use an hour or more of the API's hourly budget; it
waits out the rate limit by itself and caches its progress in `.cache/benchmark/`, so it can be stopped and
resumed. Run `build_site.py --reanalyse` afterwards so the site picks up the new values.

## Files

| File | Purpose |
|---|---|
| `build_site.py` | The command: adds reports to the website's data (`site/data.json`); `--publish` writes the passphrase-protected copy to `stats/` |
| `scorecard.py` | The analysis: fetching, mistakes and wipes, damage against clearers, damage lost to deaths, damage per phase |
| `classifier.py` | Mistake attribution, and the rule book of which rules apply from which raid day |
| `blame_diff.py` | Every attribution that changes between two versions of the classifier, over every cached report |
| `checks.py` | Rotation checks against the clears |
| `acts.py` | Casts, begun casts and outgoing damage per pull, cached |
| `gamedata.py` | Action data (GCD or not, base recast, charges) and action icons from XIVAPI, cached |
| `fflogs.py` | FFLogs v2 client: token, rate-limit waits, paged events, batched tables; `--login` for archived reports |
| `benchmark.json` | Benchmark snapshot used for the damage, uptime and HP checkpoint comparisons |
| `build_benchmark.py` | Rebuilds `benchmark.json` |
| `encrypt_data.js` | Encrypts the data for `--publish` (Node) |
| `site/` | The website: `index.html`, `style.css`, `app.js`, and the generated `data.json` (git-ignored) |
| `.cache/` | Downloaded reports, the API token and benchmark progress (git-ignored) |

The folder is left out of the GitHub Pages site by the deploy workflow.
