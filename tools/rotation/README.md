# Rotation optimizer

Searches for the highest-potency rotation of a job over P12S phase 1 (level 90), from the pull to the kill, against
the fight's fixed timeline: when Athena can't be hit, and where our groups' strategy makes the player run. Phase 2
(Pallas Athena) is a later effort. The target is the job's own potency: raid buffs are opt-in (`--party`), since party
compositions vary.

```
python tools/rotation/solve.py                                # Black Mage, R1, 2.32 s GCD, no raid buffs, 0:00 to the median kill (449 s)
python tools/rotation/solve.py --slot R2 --var para2=debuff --var para3=cross
python tools/rotation/solve.py --still                        # no forced movement: what running costs
python tools/rotation/solve.py --gcd 2.14 --party RPR,SCH,RDM --until 120 --compare
python tools/rotation/solve.py --job rpr --slot M2            # another job (table below)
python tools/rotation/p12s.py [--slot R2]                     # the move windows; --build refetches the timeline
python tools/rotation/check.py                                # movement, downtime and job-rule checks
python tools/rotation/calibrate.py [--job rpr] [--ours]       # replay the clears' (or our) logs through a job model
python tools/rotation/tune.py --job rpr                       # pick a job's heuristic settings
python tools/rotation/solve.py --job nin --no-restarts        # polish without restarting the search along the rotation (faster)
python tools/rotation/montecarlo.py --job dnc [--replan 20]   # the rotation under drawn procs, followed or re-planned
python tools/rotation/patchnotes.py Reaper [--since 7.2] [--grep Gibbet]   # the job's PvE changes in the official patch notes
python tools/rotation/dps.py [--job rpr]                      # our players: ceiling in DPS next to their scorecard rDPS
python tools/rotation/dps.py --job rpr --site [--gcds 2.40]   # ...and save ceilings and rotations for the scorecard site
python tools/rotation/dps.py --job drg --site --offline       # ...from the scorecard's cached events, when FFLogs is down
python tools/rotation/dps.py --job nin --site --restarts      # ...with polish's restarts (~0-1% more, minutes a search)
```

| `--job` | Job | Default GCD | Slot | Best over the phase | Standing still | Search |
|---|---|---|---|---|---|---|
| `blm` | Black Mage | 2.32 s | R1 / R2 | 100,021 / 99,881 | 100,358 | ~70 s |
| `rpr` | Reaper | 2.49 s | M1 = M2 | 132,687 | 133,165 | |
| `mnk` | Monk | 1.94 s (2.43 s before Greased Lightning) | M1 / M2 | 135,217 / 134,833 | 137,203 | ~2.5 min |
| `brd` | Bard | 2.49 s | R1 = R2 = still | 84,780 | | ~2 min |
| `drg` | Dragoon | 2.49 s | M1 = M2 | 127,315 | 127,909 | ~70 s |
| `rdm` | Red Mage | 2.50 s | R1 / R2 | 93,948 / 92,856 | 93,376 | ~35 s |
| `vpr` | Viper | 2.49 s (2.12 s under Swiftscaled) | M1 = M2 | 145,194 | 145,736 | ~55 s |
| `sam` | Samurai | 2.40 s (2.09 s under Fuka) | M1 = M2 | 130,980 | 132,418 | ~2 min |
| `pct` | Pictomancer | 2.45 s | R1 / R2 | 93,782 / 93,146 (103,194 / 102,558 \*) | 94,243 (103,725 \*) | ~30 s |
| `mch` | Machinist | 2.45 s | R1 = R2 = still | 107,858 (111,688 \*) | | ~30 s |
| `nin` | Ninja | 2.09 s (2.46 s before Increase Attack Speed) | M1 = M2 | 131,531 | 131,976 | ~50 s |
| `smn` | Summoner | 2.45 s | R1 / R2 | 94,559 / 94,556 | 94,602 | ~20 s |
| `dnc` | Dancer | 2.49 s | R1 = R2 = still | 84,431 (86,750 \*) | | ~40 s |

Potency without raid buffs, over 0:00-449 s, as each job's section last recorded it. \* with sure critical (direct)
hits at their expected worth, which is what the search ranks by (the melee jobs' second slot and standing still:
2026-10-26, with restarts). The runs behind the table and the sections' costs log to
`.cache/cost_runs/<job>_slot<R1|R2|M1|M2>.log` and `<job>_still.log` (git-ignored).

| Option | Meaning |
|---|---|
| `--job` | the job (table above; default `blm`) |
| `--gcd` | the player's GCD without haste (spell or skill speed; default the clears' median); `--compare` prints each clear's |
| `--crit` | critical-hit rate, for a job whose resources or buffs turn on crits (Monk's chakra, Dragoon's Life Surge; default 0.25) |
| `--slot` | Paradeigma I: `R1` / `M1` bait the first lasers, `R2` / `M2` the second. Default `R1`, or `M1` for a melee |
| `--var` | a mechanic's variant: `para2=tether/debuff`, `sc1=spread/laser`, `para3=straight/cross`; default: the one with the most running |
| `--still` | no forced movement |
| `--party` | jobs whose raid buffs are present (default none: the job's own potency), at the benchmark clears' median times |
| `--move` | extra windows in which nothing may be hard-cast (the last 0.46 s of a cast can be slid) |
| `--pot` | allow one tincture (off by default: the scorecard strips tinctures) |
| `--carry` | also value resources still held at the end, instead of dumping everything |
| `--until` | end of the scored window, seconds (default the clears' median kill, 449 s; enrage is 458 s) |
| `--width` | search width per heuristic setting (default the job's `SWEEP_WIDTH`; `WIDTH` with `--layers gcd`) |
| `--layers` | `time` (default): states compete with others at the same time (`engine.sweep`); `gcd`: after as many GCDs (`engine.beam`) |
| `--no-polish` | skip the local search on the best rotation (`polish.py`) |
| `--no-restarts` | polish without its restarts (searching the rest of the fight afresh along the rotation; see The search): faster, ~0-1% less |
| `--compare` | replay every benchmark clear's logged rotation under the same buffs, downtime and window, at the player's own speed, against the optimum standing still at their GCD (a replay plays the log's own path; one search per GCD) |

Damage is potency times the raid buffs active when each hit lands; crit and direct-hit buffs count at their expected
value, and on a guaranteed hit as the damage the game turns their rate into (x(1 + rate x (crit damage - 1)), x(1 +
rate x 0.25) for direct hit; `Fight.sure`: Monk's, Samurai's, Dragoon's sure crits, Machinist's, Pictomancer's and
Dancer's sure critical direct hits).

## How a job model is built

Each `jobs/<job>.py` starts from the official job guide and the patch notes since 7.0 (`patchnotes.py`). Both show
level-100 values, and most jobs have a trait between 91 and 100 that raises their potencies, so the level-90 values
are measured from logs: per player and action, the plain-hit cluster (no crit, no direct hit, own damage buffs divided
out, others' divided out or, where a log can't, hits under others' raid buffs left out, `acts.buff_uses`; the median
of the hits within 13% of the lowest tenth), scaled to a reference action that no trait or patch touches; FFLogs'
`bonusPercent` (a hit's share of potency from its combo or positional) confirms each split. Two sources: the full
FFLogs logs (`logs.py`, cached in `.cache/`: crit flags, multipliers, buffs on each hit, positions, MP, but only the
player's own hits, no pets) and the scorecard's acts caches (`tools/scorecard/.cache/acts_*` and
`tools/scorecard/.cache/benchmark/acts_*`, format in `tools/scorecard/acts.py`: every pull of ours and the benchmark
kills, every player's casts, begun casts, hits with
`bonusPercent`, pet hits under their owner and self-applied statuses; no crit or direct-hit flags, multipliers, others'
buffs on a hit, positions or MP). A log built from the acts caches (`logs.from_acts`, for `calibrate.replay` or
`dps.py --offline`) stays in memory: written to `.cache/`, `player_log` would take it for a full log. The measuring
scripts live in the repo's git-ignored `scratch/<job>/`.

7.0's notes list no action changes (they point to the job guide), so the notes are deltas on the 7.0 kit; their index
gives no release dates. Each job's `LOGS_SINCE` is the first day of logs on its current level-90 kit, and only clears
from then are used by `calibrate.py` (`--since` overrides it), `solve.py --compare` and `dps.py` (`CONVERT_SINCE`
where it differs). Patch dates: 7.0 2024-07-02, 7.05 2024-08-06, 7.1 2024-11-12, 7.3 2025-08-05, 7.5 2026-04-28;
Black Mage takes 7.2 from 2025-04-01, Monk and Reaper start at 2025-01-01.

`calibrate.py` then replays every logged cast through the model at its logged time, over the whole pull up to the
player's first death (`report_<code>.json` deaths for our pulls): every cast should be legal, cast times should match
begin-cast to cast, and each action's plain hits should match the model's potency. Each job's replay is legal but for
the casts its section notes (in most jobs only second tinctures, which the model doesn't allow). A tamper control
(`scratch/<job>/tamper.py`: rules broken on purpose) shows each broken rule as illegal or early casts. Rules the logs
need and the guide doesn't give are listed per job.

Statuses run their tooltip length from when their action lands, not from the cast: ~0.5-0.8 s after it for an
oGCD, the hit's delay for a weaponskill. FFLogs logs some at the cast (True North, Riddle of Fire, Meikyo Shisui,
Viper's Honed and Venom statuses: they then run 0.5-1.6 s past their tooltip in the log) and some on landing (the
raid buffs, Brotherhood, Lucid Dreaming: on 0.53-0.76 s after the cast, then their exact length); either way a status
ends about cast + landing + tooltip, and each model times it so (`scratch/timing/status_len.py` and `granted_end.py`
measure a job's). Since a damage buff never makes a cast illegal, calibrate also checks each job's `STATUSES` (its
view of the player's own statuses) against the log just before every cast, both ways. Every job defines `STATUSES`,
and a new job should pass the check clean but for the noise its section names. The usual miss is a buff timed from its
cast instead of its landing, and a resource gain that fits the logs only when larger than the guide's can be covering
for one: Samurai's Gekko and Kasha fitted 15 Kenki until Tengentsu (a 4.0 s hit window against its ~4.6 s status) and
Meikyo Shisui (20 s against ~20.8 s) were timed from their landing; since, the guide's 10 replays every pull with no
cast short of Kenki. So check a job's status timings before fitting a larger gain.

## Black Mage

`jobs/blm.py`, checked against the 11 Black Mage clears since patch 7.2 (April 2025, when the kit changed):

- every cast is legal except a second tincture; cast times match within 0.02 s at each player's own GCD (2.14-2.45 s);
  each spell's plain hits match within ~2-3%; MP matches 1,846 of 1,911 logged snapshots (most of the rest predate a
  refill);
- a spell resolves (its logged cast event: damage, gauge, MP) 0.52 s before its bar ends, for every cast length; the
  player may move for the last 0.46 s (the slidecast), so the two are kept apart;
- since 7.2: Fire IV, Despair and Blizzard IV cast in 2.0 s, Ley Lines lasts 20 s, Thunderhead and Firestarter never
  expire (only lost by being granted again), Fire III and Blizzard III deal 290;
- Ley Lines' circle (Circle of Power) lands 0.49 s after the cast (0.48-0.54 s, 1,036 casts) and lasts 20 s from then; it
  can't be cast again until the circle is gone (xivintheshell's rule; no logged recast comes sooner, 21.2 s at least);
- from the logs alone: a hard-cast Fire III from Umbral Ice III costs no MP (4 of 4 casts), and the Polyglot timer
  starts when the first fire or ice spell lands (Fire III's 1.29 s flight), not when it resolves.

Over the whole phase the best rotation deals 100,021 potency in R1 and 99,881 in R2 (2026-10-25); standing still
100,358, so our strategy's ~59 s of running costs 0.4-0.5%, about the search's noise: instants, slidecasts and weaves
cover most of it (at speed factor 0.930, `calibrate.speed_for`'s pick for 2.32 s, 2.0 s casts take 1.86 s as logged;
a factor one step off moves the figures by ~1%). The best clear's own rotation, replayed with its own movement
(`--compare`), deals 99,731 at the same 2.32 s GCD, 99.4% of the standing-still optimum; the other clears replay at
84-98% of the optimum at their own GCD.

## Reaper

`jobs/rpr.py`. Melee Mastery III (94) raises most potencies in the guide; at level 90 they are Endwalker's, scaled to
Communio (1,100): Slice 320, Waxing / Infernal 400 / 500 in combo, Soul Slice 460, Void / Cross Reaping 460 (+60
enhanced), Lemure's Slice 240, Unveiled 400, Harvest Moon 600, Gluttony 560 (7.5 raised it: 520 in older clears).

- Gibbet and Gallows: 400, +60 from the flank / rear, +60 enhanced;
- Plentiful Harvest grants Ideal Host (one Enshroud without gauge) and no Shroud gauge; Gluttony two Soul Reaver
  (Executioner 96, Sacrificium 92, Perfectio 100 lie above P12S);
- Arcane Circle's statuses land 0.63 s after the cast (Bloodsown Circle 0.62-0.67 s, 708 casts), so Bloodsown Circle,
  which bars Plentiful Harvest, ends 6.63 s after it (no logged Plentiful Harvest came sooner);
- Void and Cross Reaping run on a fixed 1.5 s GCD; Communio casts in 1.3 s like a spell; combos aren't broken by
  other GCDs; auto-attacks 96 potency every 3.2 s; Plentiful Harvest assumes a full party's eight stacks.

Every cast in the 15 benchmark logs and our 79 clean pulls replays legal. The search needs width 3,000 (at 1,000 the
settings spread 3%); its ranking gives no credit for running banked toward a run (`move_credit`), which made it burn
Enshroud early. Under raid buffs (`--party`) the settings still spread 3.4% at that width (2026-10-22), so a buffed
Reaper result needs the whole `HEURISTICS` portfolio. Over the phase 132,687 in M1 and M2 (2026-10-25); standing still 133,165 (-0.4%): five True Norths for
the fixed spots, ranged GCDs in the stretches out of reach. Over 0:00-380 s standing still the clears' own rotations replay at
79-93% of the best (they hold Soul Slice and Enshroud for raid buffs, lose uptime, some die).

## Monk

`jobs/mnk.py`, checked against the 19 benchmark clears with a Monk and our 64 clean pulls. Melee Mastery (84) sets the
level-90 values: Bootshine 220, True Strike 300, Snap Punch 270, Twin Snakes 380, Demolish 320, Dragon Kick 280, The
Forbidden Chakra 400 (the reference); from the logs Phantom Rush 1,400, Six-Sided Star 710 (the logs' spelling).

- auto-attacks 78 potency every 2.05 s (1.03 s under Riddle of Wind); hit delays 0.40 s (Phantom Rush) to 1.60 s
  (Demolish); the meditations recast in a fixed 1 s; Six-Sided Star's 4 s shrinks with skill speed, not Greased
  Lightning;
- every Bootshine under Perfect Balance or Formless Fist crits, as in opo-opo form;
- Perfect Balance takes the form held away (and Formless Fist) and its actions grant none: after it only an opo-opo
  action or a Masterful Blitz follows (no form status in 1,552 logged endings; the form held goes in 1,480 of 1,482);
  Form Shift under it grants no Formless Fist (xivintheshell's rule; no logged Form Shift falls inside one);
- forms and Fury: Dragon Kick, Twin Snakes and Demolish bank +200 / +200 / 2 x +150 for Bootshine, True Strike and the
  Snap Punches; Perfect Balance makes the beast chakra for Elixir Field, Rising Phoenix and Phantom Rush;
- chakra is random: the search counts the expected `--crit` per weaponskill, one per opo-opo Bootshine, one more under
  Meditative Brotherhood, and the party's 20% chances (0.57 a second in our windows, 0.51 in the clears); a replay takes
  the log's own crits. One window's party share swings 0.4-0.7 a second, so ~55-70 of 1,500 replayed Forbidden
  Chakras come out a chakra short: luck, not a rule (Brotherhood's party chakra starts as it lands, 0.76 s on);
- Bootshine's sure crits are kept apart (`critp`) and `dps.py` converts them at the player's own sure crit, searching
  each player's ceiling at their crit rate.

Six-Sided Star about ties the rotation per second, so it is only offered before Palladion and at the window's end.
Over the phase 135,217 in M1 and 134,833 in M2 (2026-10-25 / 26); standing still 137,203 (-1.4% / -1.7%): the fixed
spots' positionals take True Norths and the away stretches can't be filled (out of reach a Monk can only meditate,
Form Shift or use Enlightenment).

## Bard

`jobs/brd.py`. No benchmark clear has a Bard, so our 62 clean pulls (four players) are the only check
(`calibrate.py --job brd --ours`; `--compare` has nothing to replay). Ranged Mastery (94) raises the main actions in
the guide; from the logs, scaled to Bloodletter (130): Burst Shot 200, Refulgent Arrow 260, Empyreal Arrow 240,
Sidewinder 320, Apex Arrow 5 a Soul Voice; DoT ticks 20 and 25 at base speed (the tooltips'; see DoT ticks below); auto-attacks 68 every 3.07 s;
Radiant Finale's damage status is 2964.

- Songs: every 3 s on the song's own clock (from its cast, not the server tick; no DoT needed) gives Repertoire 80% of
  the time; the search counts the expected 0.8 (Pitch Perfect stacks under the Minuet, 7.5 s off Bloodletter under the
  Ballad, 4% haste under the Paeon plus Army's Muse after it), also while Athena is away. The clock is
  xivintheshell's (songTick); in our logs Army's
  Paeon stacks are gained on it (a tick in 86% of the GCD pairs that gained one, 62-69% of those that didn't; the song
  status's own refresh clock shows no such contrast), and a Pitch Perfect went off with no DoT up. (A histogram of
  Pitch Perfects or Bloodletters by their phase on a 3 s clock is no evidence: Sidewinder, which no song touches, shows
  the same shape, six 2.5 s GCDs making 15 s.) In every P12S kill with a Bard (FFLogs, 9 kills in 10 logs, one pull
  uploaded twice; three players at levels 90 and 100) the first Apex Arrow after Palladion was at 80+ Soul Voice;
  targetable ticks and Empyreal Arrow could have paid only 45-75 by then, so the song ticks count while she is away
  (`scratch/brd`). Repertoire isn't logged, so the ~73 illegal casts left in
  replays (Bloodletters under the Ballad, Blast Arrows under 80 Soul Voice) are that expectation; on the server tick
  76, or 48 with calibrate.py fitting the tick's phase to each log (a free parameter the song clock doesn't need).
- Hawk's Eye (35% from Burst Shot, the bites and Iron Jaws) counts at its expected 0.35 x 60 / 1.35 per GCD; the search
  fires Refulgent Arrow only under Barrage.
- Own buffs: Raging Strikes, Radiant Finale and the Ballad are damage; Battle Voice and the songs' crit / direct hit
  count at their expected worth. `dps.py`'s replay-vs-logged check counts those twice (~2%); the ceiling doesn't.
- DoTs snapshot, tick on the server tick and count when applied; Iron Jaws refreshes late, or early under fresh buffs.
- Every action is instant and reaches 25 y, so R1, R2 and standing still give the same rotation.

Over the phase 84,780 (2026-10-25; 84,504 without the downtime ticks, 84,651 on the server tick: within the
search's noise of each other): Raging Strikes and Battle Voice on the Minuet, Ballad and Paeon in either order,
Blast Arrow after every Apex Arrow at 80+; Radiant Finale goes anywhere, since its worth to the party isn't counted.
These are near-ties at personal potency: the searches at 2.45, 2.49 and 2.50 s each pick a different song order and
Radiant Finale spot, so the site's Bard notes (`ROT_CHALLENGES` in `tools/scorecard/site/app.js`) say so and put
Radiant Finale with Battle Voice in a party; no single GCD's order is presented as the Bard rotation.

## Dragoon

`jobs/drg.py`, measured in the acts caches (our 311 pulls by six Dragoons, 11 benchmark clears) and replayed through
the full logs. Melee Mastery (94) raises most weaponskills in the guide; at level 90, scaled to High Jump (400):

- Raiden Thrust 280, Vorpal Thrust 130 / 280 in combo, Heavens' Thrust 100 / 400, Disembowel 140 / 250, Chaotic
  Spring, Fang and Claw and Wheeling Thrust 100 / 260 in combo +40 positional, Drakesbane 400, Wyrmwind Thrust 420,
  Stardiver 720, Nastrond 720, Mirage Dive 380, Geirskogul 280, Dragonfire Dive 500; DoT 45 a tick at base speed (the tooltip's);
  auto-attacks 86 every 2.81 s;
- statuses come with the cast, so Geirskogul's hit doesn't get the Life of the Dragon it grants; Lance Charge and
  Battle Litany land 0.63 s after; High Jump / Dragonfire Dive lock 0.87 s, Stardiver 1.58 s (single-weave), Elusive
  Jump 0.96 s; Piercing Talon doesn't break a combo.

Every cast in our pulls replays legal, and in the clears all but second tinctures.

- Combos: True Thrust -> Vorpal -> Heavens' Thrust -> Fang and Claw -> Drakesbane, and True Thrust -> Disembowel ->
  Chaotic Spring -> Wheeling Thrust -> Drakesbane; Draconian Fire turns the next True Thrust into Raiden Thrust.
- Life Surge and Battle Litany count at their expected worth for `--crit`; `dps.py` leaves Life Surge hits out of a
  player's crit gain (`sure_crits`).
- The DoT counts when applied, so an early refresh looks good for a while and a narrow beam dropped the Vorpal chain
  for it (-1.3% over the phase): Disembowel is offered only when the DoT would be nearly out by its Chaotic Spring, or Power Surge is low.
- Out of reach, Elusive Jump buys an Enhanced Piercing Talon (350).

Over the phase 127,315 in M1 and M2 (2026-10-25); standing still 127,909: six True Norths, three Piercing Talons.
Life Surge goes on seven Drakesbanes and five Heavens' Thrusts.

## Red Mage

`jobs/rdm.py`, measured in the acts caches (our 267 pulls by five Red Mages, 18 benchmark clears) and replayed through
the full logs. Enchanted Blade Mastery (94) raises nearly every potency in the guide; at level 90 they are Endwalker's,
scaled to Jolt III (360):

- Verthunder / Veraero III 380, Verfire / Verstone 340, Verflare / Verholy 600, Scorch 680, Resolution 750; Enchanted
  Riposte 280, Zwerchhau 150 / 340 in combo, Redoublement 130 / 500, Reprise 340; Fleche 460, Contre Sixte 380,
  Engagement 180, Corps-a-corps 130;
- Embolden: +10% on the Red Mage's own magic (the enchanted combo too, not the physical oGCDs), 0.67 s after the cast;
- MP: Jolt III, Verfire and Verstone 200, Verthunder / Veraero III 300, Verflare, Verholy, Scorch and Resolution 400 (the
  logs' MP between casts); +200 a tick, +550 more under Lucid Dreaming (21 s, 60 s recast). Without it a phase runs dry
  by ~190 s; every pull of ours lasting 200 s or more uses it (~every 77 s). The model's MP matches 96-97% of the
  logged snapshots;
- the enchanted combo recasts in a fixed 1.5 / 1.5 / 2.2 s; an instant Ver-III spends Acceleration before Dualcast and
  Swiftcast, and Dualcast survives it; a spell made instant never grants Dualcast; Sprint cancels Dualcast;
  Verthunder / Veraero III proc 49.4% (4,158 casts), 100% under Acceleration.

Every cast (24,041, ours and the clears) replays legal but one Verraise after a Super-Ether (MP potions aren't modelled).

- Procs count at their expected worth. At level 90 the search never spends them (Jolt III's 360 and 2 / 2 mana beat
  Verfire's 340 and 5); forcing them costs 0.4-1.1%, though our Red Mages spend them.
- The melee combo costs 20 / 15 / 15 of each mana (nothing under Manafication's Swordplay) and gives the stacks for
  Verflare / Verholy -> Scorch -> Resolution. Tested in game ([rdm-in-game-tests.md](rdm-in-game-tests.md), 2026-10-23):
  mana gains halve while a colour leads by more than 30 (searches never get there); each enchanted melee action adds a
  Mana Stack, any other GCD clears them (oGCDs don't), and they don't lapse (the search plays whole combos, started only
  with their mana and their three hits clear of far spots).
- Reach: the melee combo and Engagement need 14 y from Athena's centre (25 y under Manafication); at our plan's far
  spots (`p12s.FAR`) a ranged player is out of reach around the snapshot.
- Dashes (`engine.dash`): in R1, Corps-a-corps from Paradeigma I's wall to Athena's hitbox edge saves 1.3 s of the
  swap (+0.8%); R2's Displacement comes after the GCD it could have freed, so it gains nothing. P12S's arena edge is a
  drop (a 40 y square), so a backstep may only overshoot its stretch as far as the floor goes (`p12s.ARENA_HALF`).

Over the phase 93,948 in R1 and 92,856 in R2 (2026-10-25; MP costs nothing: three Lucid Dreamings go in free weave
slots); standing still 93,376 (R1 over standing still is search noise). What is left is Paradeigma I's swap through
the middle while the opener's cooldowns recharge, filled with Enchanted Reprise. The clears' rotations, replayed
standing still over 0:00-380 s, deal 93-97% of the best.

## Viper

`jobs/vpr.py`, measured in the acts caches (our 249 pulls by six Vipers, 24 benchmark clears) and replayed through the
full logs since 7.5. No Viper trait above level 90 raises a potency, so the guide's values hold (Death Rattle 280 as
the reference; Vicewinder 540 and the Coils 630 since 7.5, the Generations 680, the bites 170, Uncoiled Fury 680);
level 90 lacks Uncoiled Twinfang / Twinblood (92), the fifth Tribute and Ouroboros (96) and the Legacies (100).
Auto-attacks 80 potency.

- Recasts: Vicewinder and the Coils 3.0 s, Uncoiled Fury 3.5 s, Reawaken 2.2 s, the Generations 2.0 s, the rest 2.5 s,
  all by skill speed and Swiftscaled's 15% (the GCD granting it isn't hasted); Vicewinder's 40 s and Serpent's Ire's
  120 s are flat;
- statuses come after their hit (Honed Steel ends 61.27 s after Reaving Fangs: its 1.29 s hit delay plus the 60 s
  tooltip); Hunter's Instinct and Swiftscaled refresh to 40 s, so both lapse over Palladion;
- the Coils, Uncoiled Fury and the Generations don't break the dual-wield combo; Death Rattle and the bites are lost
  with the next weaponskill; Reawaken grants four Tributes at 90; Rattling Coils start at none.
- the Coils follow Vicewinder as the next weaponskills: any other but Uncoiled Fury or Writhing Snap ends the twinblade
  combo (1,225 logged Vicewinders with both Coils and only Uncoiled Fury between; no Coil ever after another weaponskill);

Every cast replays legal. Swiftscaled is up nearly all fight, so `calibrate.gcd_of` divides gaps under it by its haste
(`HASTED`) and scales gaps after longer GCDs (`GCD_BASE`).

- Dual-wield combo with Honed and venoms, twinblade combo with bites, Reawaken on 50 Offerings or Ready to Reawaken.
- Uncoiled Fury about ties the filler; offered at every step it filled the beam with orderings of one rotation, so it
  is offered at three Rattling Coils, out of reach or near it, before downtime, at the end and under raid buffs.
- Each held resource is valued at what it converts into less the time its GCDs take; at 1.5 times that the search held
  Coils and Offerings (-5%). Held values fade over the window's last 15 s. Rates below the filler's own (~275 a second)
  made time look cheap (-1.5%).

Over the phase 145,194 in M1 and M2 (2026-10-25); standing still 145,736 (-0.4%, the least of the melee jobs): six
True Norths cover ten positionals, Uncoiled Fury and the 3 s twinblade gaps cover the stretches out of reach.

## Samurai

`jobs/sam.py`, measured in the acts caches (our 199 pulls by four Samurais, 12 benchmark clears) and replayed through
the full logs. Way of the Samurai III (94) raises most potencies in the guide; at level 90, scaled to Hissatsu: Shinten
(250):

- Hakaze 200; Jinpu / Shifu 120 / 280 in combo; Gekko / Kasha 110 / 320 in combo +50 positional; Yukikaze 110 / 290;
  Higanbana 200 and 45 a tick at base speed for 60 s (the tooltip's); Shoha 560; Senei 800 on 120 s; auto-attacks 80; sure crits Midare Setsugekka
  and Kaeshi 620 (lowest cluster over each player's crit multiplier), Ogi and Kaeshi: Namikiri 860 (1.38 x Midare in
  the same pull under the same buffs).

From the logs:

- Gekko and Kasha give the guide's 10 Kenki (positionals give none; replays fell short only through the two status
  timings below);
- statuses logged at the cast run ~0.6 s past their tooltip: True North 10.5 s, Tengentsu 4.65 (its hits come up to
  4.60 s after the cast), Meikyo Shisui 20.7 (one expired at 20.76, spent up to 20.62), Ogi Namikiri Ready and
  Tsubame-gaeshi 30.6; Fugetsu and Fuka, applied with the hit, last their 40;
- Iaijutsu and Ogi Namikiri cast in 1.3 s flat; Fuka shortens the recast (2.40 -> 2.09 s) and autos, not the cast;
  Iaijutsu, Kaeshis, Ogi and Enpi don't break the combo; Kaeshis give no Meditation;
- every opener has a pre-pull Meikyo Shisui ~13 s ahead, often a pre-pull True North too (a replay reads both from
  their statuses coming off);
- Tengentsu's 10 Kenki needs a hit while it is up: 18 fight hits (`HITS`) where it paid off; a replay takes the log's own;
- the clears Meditate at Palladion's end until Athena returns, a Meditation stack per 3 s tick (its 10 Kenki a tick is
  the in-game value, not testable in logs).

Every cast in our pulls replays legal, and in the clears all but a second tincture.

- Sure crits (Midare, Kaeshis, Ogi) are weighed by a sure crit's gain over an average hit (`SURE_W`, x1.60 at 25%
  crit); the printed potency stays plain, `dps.py` converts them at each player's own (`AUTO_CRIT`). The weight isn't
  named `CRIT`: for a job with `CRIT`, `dps.py` searches each player at their own crit rate, which only Monk's chakra
  needs.
- While Athena is away the search takes one step: Tengentsu on the hits it catches, then a 0-5 tick Meditate ending
  at her return (separate steps made short Meditates look better under the rate).
- Held Tsubame-gaeshi Ready is valued at its Kaeshi less a 2.09 s GCD (valued whole, the beam held it 16 s and
  overwrote Sen).

Over the phase 130,980 in M1 and M2 (2026-10-25); standing still 132,418 (-1.1%), nearly all of it the stretches out of
reach, where Enpi fills in (the 6-10 y Iaijutsu and Shoha are assumed not to reach there; +0.3% if they do).

## Pictomancer

`jobs/pct.py`, checked against our 27 clean pulls and three benchmark clears (full logs with positions) and ~200 pulls
in the acts caches. Pictomancy Mastery IV (94) raises most potencies in the guide; the level-84 trait gives the level-90
values after the 7.2 / 7.3 notes, scaled to Pom Muse (800): Fire / Aero / Water in Blue 420 / 460 / 500, Blizzard /
Stone / Thunder in Magenta 750 / 790 / 830, Holy 500, Comet 830, Pom / Winged Muse 800, Mog of the Ages 1,000,
hammers 540 / 560 / 580 (always critical direct hits). Living Muse and Striking Muse have two charges at 90; every
canvas is painted at the pull.

From the logs:

- **Inspiration** takes 25% off the cast and recast of the colour spells, Holy and Comet, each taking a Hyperphantasia
  stack (hammers and motifs take neither); it starts 0.58 s after Starry Muse;
- **the landscape** is a ~8 y circle around where Starry Muse was cast (`LANDSCAPE`): Superchain I's 15 y run leaves it;
- motifs cast in a fixed 3.0 s on a fixed 4.0 s recast; Subtractive Palette and Monochrome Tones never lapse; MP never
  binds.

Every cast replays legal (a replay has no movement, so the 8 early GCDs all follow a player leaving the landscape).

- Hammers count plain in the printed potency and are weighed at `SURE_W` (x1.62), converted by `dps.py` per player.
- A canvas or the Moogle Portrait counts only if what renders it is back before the window ends, and a cooldown sitting
  at full charges is charged twice its share a second (`CAPPED`); each fixed a 0.2-1.5% loss.
- Smudge dashes 15 y along an open run, the way the player faces; `smudge_gain` banks the running it saves into the
  state's `acc` from inside the job, with no change to `engine.py`. It ties with no Smudge.

Over the phase 93,782 in R1 (103,194 weighted) and 93,146 in R2; standing still 94,243, about half the gap
Inspiration lost in Superchain I. Living Muse renders 13 times; Palladion repaints the canvases. Settings from
`tune.py` (values at 0.45-0.65 of the guesses).

## Machinist

`jobs/mch.py`, checked against our 38 clean pulls and seven benchmark clears (full logs) and ~186 pulls in the acts
caches (which alone hold the queen's hits). Marksman's Mastery II (94) and Enhanced Multiweapon raise the guide's
values; at level 90, scaled to Gauss Round (130): Heated Split Shot 200, Slug Shot 120 / 300 in combo, Clean Shot
120 / 380, Drill (one charge), Air Anchor and Chain Saw 620 (7.3), Blazing Shot 220 + Overheated's 20, Ricochet 130;
auto-attacks 60 every 2.67 s.

- The queen's hits grow linearly with the battery she was deployed with, ~0.9 x the tooltips: five Arm Punches at 2.2
  a battery point 6.4-12.6 s after the deploy, Pile Bunker 6.15 at 14.7 s, Crowned Collider 7.0 at 17.4 s, so ~24
  potency a battery point; deploys are at least 21.8 s apart.
- Wildfire detonates 10.6 s after its cast for 240 a weaponskill landed under it (six at most), logged as a tick.
  Whether it can direct hit is untested in game; the model, and `tools/gear/ceiling.py`'s luck spread, give it
  neither crit nor direct hit.
- The tools recast on skill speed (Drill 19.3 s at 2.41 s); Blazing Shot's 1.5 s doesn't, and takes 15 s off Gauss
  Round and Ricochet; nothing breaks the combo; Barrel Stabilizer gives only Hypercharged at 90.
- 37 of 45 logs open with a pre-pull Reassemble whose cast isn't logged: a replay reads it from the status falling off,
  the search presses one at -4.5 s. Reassemble went on a tool every time; its critical direct hits are weighed at
  `SURE_W` (x1.62) and converted per player (`AUTO_CRIT` names the tools).

Every cast in the clears since 7.3 replays legal, and in our pulls all but four Drills of one player (a GCD that reads
2.50 s to the hundredth). The queen and Wildfire are booked when deployed or cast. Whether the queen can be deployed
while Athena is away (her first hit comes 6.4 s later) isn't in the logs: the model says no, which scores the same. A
battery point is valued at two
thirds of what the queen makes of it: at the full 24, any VALUE scale above 1 held battery (-3.5%).

Every action is instant and reaches 25 y, so R1, R2 and standing still play the same. Over the phase 107,858 (111,688
weighted): 12 Hypercharges, eight queens (~15% of the potency), four Wildfires. The clears' rotations replayed standing
still over 0:00-370 s deal 96-98% of the best. FFLogs' full logs hold the player's own hits only, so `dps.py`'s
'logged' column misses the queen (~10%); the ceiling and the conversion count her.

## Ninja

`jobs/nin.py`. Our groups have no Ninja pulls, so the nine benchmark clears with one (Feb 2025 - Sep 2026, seven
players) are the only check: full logs for the player's own hits, the acts caches for the shadow's (pet hits). Melee
Mastery III (94) raises the combo, Fuma Shuriken, Raiton, Suiton, Bhavacakra and the Raijus in the guide, and Kunai's
Bane (92), Higi (96) and Tenri Jindo (100) lie above P12S. At level 90, scaled to Dream Within a Dream (180 a hit):

- Spinning Edge 220, Gust Slash 160 / 320 in combo, Aeolian Edge 140 / 320 in combo +60 from the rear +100 with
  Kazematoi, Armor Crush 140 / 340 in combo +60 from the flank (bonusPercent 50 / 42 / 65 / 58 fit only these), Trick
  Attack 300 / 400 from the rear, Bhavacakra 350 / 500 under Meisui, Fleeting Raiju 560, Raiton 650, Suiton 500, Fuma
  Shuriken 450 (466 on its 16 plain hits), Hyosho Ranryu 1,300, Dokumori 400 (300 before 7.3), auto-attacks 76 every
  2.18 s;
- Kassatsu's +30% isn't in FFLogs' multiplier (Hyosho Ranryu reads 1,300 x 1.3); Trick Attack (+10% the Ninja's
  damage) and Dokumori (+5%) are, as debuffs on Athena, from their own hit's landing for 15 / 20 s;
- the shadow: a copied weaponskill 148 (tooltip 160), Phantom Kamaitachi 665 since 7.3 (550 before), about 0.93 of
  the tooltips like the Machinist's queen; Bunshin's stacks go on weaponskills (the Raijus too), not on ninjutsu or
  Phantom Kamaitachi, each copy +5 Ninki.

From the logs:

- the GCD is 2.5 s x 0.85 (Increase Attack Speed, 45) x skill speed: 2.09-2.14 s; a mudra takes a flat 0.5 s and a
  ninjutsu 1.5 s before the next GCD, Ten Chi Jin's first two 1.0 s, whatever the skill speed;
- mudras, ninjutsu, the Raijus and Phantom Kamaitachi don't break the combo; a melee weaponskill ends Raiju Ready;
  Shadow Walker goes on Trick Attack or Meisui;
- eight of nine clears make the opener's three mudras before the pull (not logged) and open with Suiton at 0.6-1.2 s;
  the mudra charges fit only if those mudras began 1.5-4.5 s before it. A replay takes the earliest the 6 s Mudra
  status allows, the search makes them at -3.5 s;
- statuses outlast their tooltip by ~0.6 s (a Trick Attack 20.49 s after its Suiton).

Every cast in the nine clears replays legal but four second tinctures. A control with broken rules (each cooldown 1-3
s longer, less Ninki from the finishers, the shadow, Dokumori or Meisui, shorter Shadow Walker or Phantom Kamaitachi
Ready, slower mudras, ninjutsu or Ten Chi Jin, no haste trait) shows each as illegal or early casts
(`scratch/nin/tamper.py`); Raiju Ready's 30 s can't be tested (the clears spend it at once).

- **Ninjutsu**: the search makes mudras and their ninjutsu as one step: Raiton (a Raiju Ready), Suiton when Shadow
  Walker would be there for Trick Attack, Hyosho Ranryu right after Kassatsu, Fuma -> Raiton -> Suiton right after Ten
  Chi Jin (then Meisui). Mudra charges sitting full are charged to the rank (`CAPPED`). While Athena is away it can
  make the mudras so the ninjutsu goes off as she returns.
- **Movement**: as for the Reaper; Aeolian Edge, Armor Crush and Trick Attack are the positionals. The combo, Fleeting
  Raiju, Trick Attack, Dream Within a Dream, Bhavacakra and Dokumori (8 y, taken as melee) need reach; ninjutsu,
  Phantom Kamaitachi and Throwing Dagger reach 20 y, so the away stretches fill themselves. Forked Raiju (a gap closer)
  is left to replays. `check.py`'s melee control (a standing-still rotation must break an away window) can't fail a
  Ninja, whose ninjutsu leave 2.5-4 s without a melee action anyway, so it uses the windows at twice their length.

Over the phase 131,531 potency in M1 and M2 (2026-10-25); standing still 131,976, so our strategy costs a Ninja
about the search's noise: five True Norths cover the fixed spots and ninjutsu fill the stretches out of reach. It opens on
the pre-pull Suiton with Trick Attack, Dokumori and Ten Chi Jin (Meisui into Bhavacakra), then Raiton, Bunshin,
Kassatsu -> Hyosho Ranryu and the Raijus inside Trick Attack, and over the phase makes 22 Raitons, 10 Suitons, seven
Hyosho Ranryus, four Ten Chi Jins, five Bunshins and 27 Bhavacakras. Settings from `tune.py` (rates 300-340 at
values x1.0 tie, x0.5 is 0.4% lower); the sweep holds within 0.5% from width 1,000 to 8,000 and beats the beam by
1.5-3%. The clears' rotations, replayed standing still over 0:00-365 s, deal 94-98% of the best (a pull with a death
79%). A search takes ~50 s. With no Ninja in our groups, `dps.py --site` puts the rotations on the scorecard site at the
clears' Ninjas' GCDs since 7.3 (`CONVERT_SINCE`), converted to DPS at those four players (damage per potency: three
within 2%, one 13% lower, likely gear: the benchmark checks only the logging player's); no player page links there.
`logs.clears` divides an Echo kill's damage by 1.2: one of the four played with The Echo, which had shown as a 40% spread
and put the site's ceiling band for Ninja far above every other job's. `rotations.json` marks such a job
`converted_from: "clears"` with its `converted_since`, which the site's pages quote. If one of our players takes up
Ninja, `calibrate.py --job nin --ours` and `dps.py --job nin --site` make it a job of ours like the others.

## Summoner

`jobs/smn.py`, checked against our 15 clean pulls (two players) and the 11 benchmark clears with one (Mar-Dec 2025,
mostly one player) in the full logs, and our 77 pulls in the acts caches, which alone hold the pets' hits. Arcane
Mastery (94) raises nearly every potency in the guide; at level 90 they are Endwalker's, scaled to Fester (340):

- Ruin III 310, Ruin IV 430, Astral Impulse 440, Fountain of Fire 540, Ruby / Topaz / Emerald Rite 510 / 330 / 230,
  Energy Drain 200, Deathflare 500, Mountain Buster 150, Crimson Cyclone and Crimson Strike 430, Slipstream 430 and its
  windstorm six ticks of 30 at base speed (the tooltip's);
- the pets hit at 0.79 of their tooltips: Wyrmwave and Scarlet Flame 119, Akh Morn and Revelation 1,030, Inferno,
  Earthen Fury and Aerial Blast 600; Searing Light (+5%, 20 s) raises them as it does the Summoner's own hits.

From the logs:

- Summon Bahamut and Summon Phoenix are GCDs whose 60 s shrinks with spell speed (57 s at a 2.31 s GCD); the 15 s
  trance allows only Astral Impulse / Fountain of Fire (six at 2.45 s), Enkindle once and, under Bahamut, Deathflare;
  the primals come after it (16-22 s after the summon, any order);
- the demi hits four times on its own timer, 5.1 / 7.3 / 10.4 / 13.5 s after the summon, whatever is cast; Akh Morn and
  Revelation land 1.0 s after Enkindle but not before ~3 s after the summon; Inferno and Earthen Fury 4.06 s after
  their summon, Aerial Blast 3.39 s;
- Ruby Rite casts 2.8 s on a 3 s recast and Slipstream 3 s on 3.5 s, both shortened by spell speed; Emerald Rite's
  1.5 s isn't (1.47-1.51 s at a 2.31 s GCD); a demi-summon or a primal ends whatever favor is left (Ifrit's / Garuda's
  Favor and Crimson Strike Ready otherwise outlast 50 s); MP never binds (lowest 1,600).

Every cast in the clears replays legal but six second tinctures, and in our pulls all but one Astral Impulse after an
opener without the pre-cast Ruin III (a replay places the first GCD at 0:00). A control with broken rules (each
cooldown 1.5-2 s longer, the demi's recast unscaled, a 14.5 s trance, fewer attunement stacks, shorter attunement or
Further Ruin, slower Rites or Slipstream) shows each as illegal or early casts (`scratch/smn/tamper.py`).

- The pets are booked when summoned or Enkindled, at their landing's buffs.
- Crimson Cyclone rushes to Athena (`engine.dash`). While our plan holds the player to a spot (a mechanic's first cue
  to its last snapshot, as `p12s.plan_spans`) it may only be a dash along a stretch of the run straight to her
  (Paradeigma I's swap in R1), and as Red Mage's Corps-a-corps not off a far spot before its snapshot; Crimson Strike
  needs melee reach (`FAR`).
- Held values (each resource's conversion less Ruin III's rate over its GCDs) tie the filler exactly, so at their full
  scale the beam drifted holding Ruby stacks and Arcanum until the next demi-summon wiped them (-5.5%); `tune.py` puts
  the scale at 0.10-0.15. The search opens on a pre-cast Ruin III, as every clear does; this is set by policy, since
  the rank's charge for time made an instant Summon Bahamut at the pull look just as good.

Our runs cost a Summoner next to nothing: 94,559 potency over the phase in R1 and 94,556 in R2, against 94,602
standing still (Ruin III slidecasts, and all but Ruby Rite and Slipstream is instant); keeping Crimson Cyclone out of the
plan's mechanics only moves it to the stretches between them. Eight demi-summons, Searing
Light with each Summon Bahamut, Swiftcast on Slipstream, a Ruby Rite or Ruin III, and only eight Ruin IIIs: every Arcanum is
spent but Garuda's before Palladion (the 27 s after the 4:00 trance fit Titan and Ifrit). The primals' order changes
from cycle to cycle, a near-tie. Settings from `tune.py`; a search takes ~20 s and polish adds 0.2%. The clears'
rotations, replayed standing still over 0:00-370 s, deal 95-98% of the best (one pull 89%); our pulls over 0:00-130 s,
86-87%. FFLogs' full logs hold the Summoner's own hits only, so `dps.py`'s 'logged' column misses the pets (~20%); the
ceiling and the conversion count them.

## Dancer

`jobs/dnc.py`, checked against our 62 clean pulls (five players) and the 38 benchmark clears with one (Feb 2025 - Sep
2026, 13 players) in the full logs, and ~320 pulls in the acts caches for the rules. Dynamic Dancer (94) raises the main
potencies in the guide, and Last Dance (92), Finishing Move (96) and Dance of the Dawn (100) lie above P12S. At level 90,
scaled to Fan Dance (150):

- Cascade 200, Fountain 100 / 260 in combo, Reverse Cascade 260, Fountainfall 320, Saber Dance 500, Fan Dance III 200,
  Fan Dance IV 300, Double Standard Finish 800, Quadruple Technical Finish 1,200 (Triple 900), Tillana 600, Starfall
  Dance 600 (a sure critical direct hit), auto-attacks 80 every 3.12 s; Standard and Technical Finish +5% each.

From the logs:

- nothing breaks the combo (30 s); every proc is 50%; a Reverse Cascade / Fountainfall spends the silken proc before
  Flourish's; the Steps and finishes run on a fixed 1.5 s, the steps on 1.0 s; statuses outlast their tooltips (procs
  spent up to 30.7 s after their grant, dances finished up to 15.1 s after the Step);
- Standard Step goes before the pull (not logged; the opening Standard Finish comes at ~0.9 s, the second Step 16.4 s
  at the earliest): the search presses it at -14 s and opens on the finish at 0:00;
- FFLogs logs each Technical Finish twice, 0.5 s apart, the second `fake` (`calibrate.py` skips such casts; the second
  of a lesser finish isn't flagged, `prepare` marks it).

Randomness counts at its expectation, as Bard's Repertoire: a 50% proc, feather or Threefold is half a token, usable at
a whole one. A replay reads the procs from the log's statuses and counts every feather chance (feathers aren't logged).
Esprit isn't logged either: 5 / 10 from the Dancer's own GCDs, 50 from Tillana, and the party's chances at an expected
0.7 a second from the dance partner while Standard Finish is up, plus 4.2 from the six others in the Technical Finish
window (the same chance each). A regression on the pulls fixes only the total (~165 every two minutes); the split is the
one that balances, over every replayed log, the Esprit the model lacks at Saber Dances against what it overcaps (46 / 43
a pull). Every cast replays legal but five second tinctures, one clear's opener (a Technical Finish before the pull),
and 423 of ~3,000 Saber Dances short by ~10 Esprit each: players spend a lucky draw at once. A control with broken rules
(each cooldown 0.5-1.5 s longer, slower steps, Steps, finishes or GCD, shorter dances, procs, Flourishing Starfall or
Finish, half the Esprit or feathers) shows each as illegal or early casts (`scratch/dnc/tamper.py`).

- Devilment (+20% critical and direct-hit rate) counts on the Dancer's own hits at its expected worth (x1.155), as
  Bard's Battle Voice. Starfall Dance is weighed at a sure critical direct hit with Devilment's rates turned into damage
  (`STAR_W`, x1.88) and converted per player (`AUTO_CRIT`; `dps.py` measures it under Devilment, `OWN_CRIT_BUFFS`).
- A dance is one step of the search (Step, steps and finish): a state halfway through had dealt nothing, so states
  banking filler damage outranked it and the search danced Standard Step once a minute, just keeping its buff (-3%).
- While Athena is away the steps are danced so that the finish comes as she returns.

Every action is instant and reaches the plan's spots, so R1, R2 and standing still find the same 84,431 potency over the
phase (86,750 weighted; 2026-10-25): Technical Step every two minutes with Devilment, Starfall Dance and Tillana in
its window,
Standard Step every ~32 s (13 finishes), seven Flourishes, 29 Saber Dances. Devilment lands just before Technical Step
rather than after its finish, a near-tie for the Dancer's own damage (what it gives the partner isn't counted).
Settings from `tune.py` (scales 0.25-0.35 tie, as Summoner's); a search takes ~40 s. The clears' rotations, replayed
standing still over 0:00-370 s, deal 93-99% of the best (one pull 83%; two lucky ones just over 100%, as a replay takes
the log's procs). Our Dancers' logged 0:00-2:00 sits at ~97% of the ceiling (the opener is scripted); the ceiling isn't
under-searched: widths from 2,000 to 15,000 agree within 0.2%.

## The fight

`p12s.py` holds P12S P1 as the optimizer plays it; `p12s_p1.json` is built from six benchmark clears (`--build`).

- **Timeline**: every boss cast lands within ~0.2 s of its median, so it is fixed. Athena can't be hit from 281.6 s
  to 325.9 s (Palladion): nothing can be cast at her and DoTs don't tick.
- **Running**: each run is a window (a cue plus 1 s to react, to when its mechanic snapshots) and a distance at 6
  yalms a second. The player spends that long somewhere in the window not hard-casting: instants, weaves, the last
  0.46 s of a cast and the caster tax all count. A run takes the player out of Ley Lines; they run as late as they can.
- **Our plan**: Paradeigma I, II, III and Superchain Theory I follow our raidplan (Syncademy P12S P1), measured from
  Athena's centre. Paradeigma I depends on the slot; the others on a random assignment, where the default is the
  variant with the most running. Everything else takes its running from the benchmark clears' Black Mages (median path
  per window), and from Palladion on that is provisional. Our own pulls never set or check the runs (our groups prog
  blind); the benchmark clears' are used freely.
- **Melee**: melee actions need the player within ~14 y of Athena's centre (the clears' Reapers use them up to 13.5 y).
  Every spot of our plan is within that; where the clears' Reapers went longer than a GCD without a melee action, a
  melee is out of reach that long somewhere in the window (`away`: 13 s in five windows, all from 173 s on), with no
  melee actions or auto-attacks. While our plan fixes the spot (Paradeigma I-III, Superchain I: 77 s, `pinned`),
  positionals need True North, and the search decides where to spend it. Runs only block hard casts. The away windows
  come from `p12s._melee`; every melee job (M1 and M2 alike) shares this model through `jobs/_common.py` (`reach`,
  `flank_rear`, `away_soon`).
- **Far spots**: a ranged player is within melee reach everywhere but Paradeigma I's wall end and Superchain I's
  Heavensflame corner (`FAR`); a ranged job with melee actions is out of reach around those snapshots. A job opts in
  with `FAR = True` (Red Mage, Summoner).
- **Dashes**: where a run of our plan goes straight to or from Athena (`DASH`: Paradeigma I and II), a dash along that
  stretch saves its running (`engine.dash`): a gap closer down to her hitbox edge (`ATHENA_EDGE`, 10.5 y), a backstep
  its length. Red Mage (Corps-a-corps, Displacement) and Summoner (Crimson Cyclone) go through `engine.dash`;
  Pictomancer's Smudge banks its running job-locally. Other gap closers don't move the player: Reaper's Hell's Ingress
  and Dragoon's Elusive Jump are only valued for the enhanced ranged GCD they grant, and Ninja's Forked Raiju is left
  to replays. `pinned` is built for melee only, so a ranged job's gap closer finds the plan's fixed spots itself:
  Summoner's Crimson Cyclone rebuilds them from the move windows labelled "; plan" (`smn.plan_spans`, as
  `p12s.plan_spans`). Any other ranged gap closer needs the same, or it pulls the player off a spot.

`python tools/rotation/p12s.py` lists every window with its source and compares our plan's distances with the clears'
(within about ±30%: ours runs more in Paradeigma I-III, less in Superchain I).

## The search

A beam search, one GCD per step with the oGCDs woven before it. States compete with those at the same time
(`engine.sweep`: 0.5 s layers, 0.25 s for Black Mage), ranked by damage so far plus what the resources they hold are
worth, minus a rate per second of time (and, for Black Mage, minus the running ahead its instants won't cover). From
Viper on, each job values a held resource at what it converts into less `RATE` times the GCD time spending it takes
(inflated values made the beam hoard Viper's Coils), and fades held values to nothing over the window's last
`END_TAPER` seconds (15; 20 for Dancer and Machinist): without it a state that never spent its last 50 Offerings
ranked well to the end. Cooldowns sitting at full charges are charged what a second of their recharge is worth
(`CAPPED`, from the Pictomancer model, which charges twice its share; `jobs/_common.py`).

Over a whole phase the result moves by ~1% with these guesses, so `engine.search` runs several settings in parallel
(the job's `HEURISTICS`, from `tune.py`; a `multiprocessing.Pool`, one process per setting up to the core count) and
keeps the best. Under Windows' spawn start method the workers re-import `__main__` and the job module afresh: a
script that calls `engine.search` must be a file with an `if __name__ == "__main__":` guard (run from stdin or
`python -c`, the workers crash and respawn without end and the run looks hung), and a job model edited while its
searches run plays by the new rules in every pool started after the edit.

`polish.py` then improves the best by local search over the whole fight (another legal choice in one step's place,
neighbouring GCDs swapped, an oGCD moved, a step dropped), on any job through its `expand`; it found 0-0.7% more.
Polish replays a rotation by choosing each step's child by its action names, so children that differ only in timing
(waits while Athena is away) must log different names, as Ninja's `(boss away, until x s before)` do; otherwise the
replay rebuilds the wrong child and polish keeps the beam's rotation ("replays at X, not Y; kept as it was").
`--layers gcd` (the beam by GCD count) and `--no-polish` bring back the earlier search.

Differences between scenarios below ~0.4% are noise. The search is deterministic (the same rotation, polish included,
under any `PYTHONHASHSEED`) but chaotic in its inputs: a small change to a model or a setting moves the result by
about that much, so scenarios are compared by the portfolio's best, not by one setting's beam. `engine.sweep` moves a
child that gains no time on to the next layer; the beam by GCD count doesn't, so there a wait child of zero length
keeps its rank forever and the search never ends. A search running far longer than usual is such a hang, not
slowness: one worker's CPU time runs far ahead of the others'; run that setting alone to find the state.

Restarts (2026-10-25; solve.py by default, `--no-restarts` skips them; dps.py with `--restarts`): when single edits find nothing, polish searches the rest of the fight afresh from
the rotation's state every 15 s, at twice the job's width, and splices in what improves it. Over the whole phase in the
site's slot it found more for most jobs, at 2-15 minutes a job instead of seconds (`scratch/restarts`; times with other
searches running beside it, and some hit the 600 s budget):

| | NIN | DNC | BLM | MNK | SAM | RDM | DRG | RPR | BRD | VPR | SMN, PCT, MCH |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gain | +0.95% | +0.69% | +0.57% | +0.55% | +0.32% | +0.28% | +0.26% | +0.26% | +0.17% | +0.06% | 0 |

Re-planning only a window and rejoining the rotation's own steps doesn't work: a different window leaves the job in
another phase (Black Mage's fire or ice, Summoner's demi-summon) and the old steps no longer fit. Fitting the resource
values (`VALUE`) instead was tried too, by regression on sweep states (confounded, and its target mostly search noise)
and by tuning each entry against the search (within noise of the portfolio): `scratch/values`.

Procs (`montecarlo.py`, 2026-10-25): the search counts random procs at their expectation; `engine.DRAW` draws them
instead (Red Mage's Verfire / Verstone Ready, Bard's Repertoire and Hawk's Eye, Dancer's Silken procs, Threefold,
feathers and the party's Esprit, Monk's crits and party chakra). The party's Esprit is drawn as 10 or none on each
member's GCD, on a fixed 2.5 s grid at the chance that gives the expected rate (`dnc.party_drawn`; the table below
predates it; with it, a plan-following Dancer lost 2.21% on the current plan, 48 draws). `tools/gear/ceiling.py` uses the same replays
(`montecarlo.draws`) for the site ceiling's proc luck. Draw modes leave a normal search identical, and a job that
counts a new proc at its expectation needs a draw branch for it (`engine.drawn`), or `montecarlo.py` and the site's
proc-luck band treat it as certain. The site's whole-phase rotation, replayed
under drawn procs by a player who follows it (the planned step, else its oGCDs with another GCD in its place, a planned
oGCD not up yet woven in the next four steps) and by one who re-plans 20 s ahead before every step:

| | follows the plan | re-plans, nothing drawn | re-plans, procs drawn | its p5 / p95 |
|---|---|---|---|---|
| RDM | +0.00% (no draw matters) | +0.04% | -0.24% | -1.5% / +0.1% |
| DNC | -1.94% | -0.24% | -0.28% | -2.6% / +1.7% |
| MNK | -1.22% | -0.44% | -0.86% | -2.1% / +0.3% |
| BRD | -2.11% | -0.18% | -0.89% | -2.3% / +0.1% |

A player who reacts loses ~0.4-0.7% to luck at most (Monk's chakra, Bard's Repertoire; the rest is the 20 s horizon), so the expected-value
plan is a fair target; one who plays the published steps as they stand loses 1-2.5%. Red Mage's plan uses no proc:
at level 90 Jolt III (360) beats Verfire / Verstone (340) but for their mana.

DoT ticks: each model's `dot_tick()` is the tick's plain potency (no crit, no direct hit) at base speed, its level-90
tooltip's, times the speed bonus the game gives DoTs at the model's `SPEED` (1 + floor(130 x (speed stat - 400) / 1900)
/ 1000 = 2 - `SPEED`). The game sends one combined tick for every DoT on a target, and FFLogs splits it between players
by each one's simulated tick (its `S`, from its crit rate `C` and estimated direct-hit rate `D`), so a player's single
tick in the logs is no roll of theirs. FFLogs also keeps each tick's plain value (`T`, `expectedAmount`, from the game's
packet): measured from it (`scratch/gear/dot_t.py`, 2026-10-23), our players' and the clears' ticks deal the tooltip x
0.98-0.99 (Thunder III, both bites, Chaotic Spring, Higanbana). The crit and direct-hit gain on ticks is their sum over
the sum of `T` (`dps.tick_gain`), close to each player's gain on hits (1.25-1.31 against 1.24-1.31). Slipstream's ground
ticks are ordinary hits in the logs, with crit and direct-hit flags. (Read from the split amounts as if they were rolls,
ticks had looked 8-13% above their tooltips: the earlier Thunder III 63 and bites 25 / 31 were that, and the median.)

Timing: `engine.recast(base, SPEED, haste)` times a recast or cast as the game does (xivgear's `sksToGcd`): the speed
stat's per-mille factor (`SPEED`, e.g. 0.962) in whole milliseconds, then the haste in whole hundredths of a second.
Black Mage (Ley Lines), Samurai (Fuka), Viper (Swiftscaled), Monk and Ninja (their traits) go through it, so a 2.40 s
Samurai is 2.08 s or 2.09 s under Fuka by the factor; the other jobs still
scale continuously, exact at `SPEED` = GCD / 2.5. A job's own crit and direct-hit buffs and sure-hit weights are built
from its `CRIT_RATE` / `CRIT_DMG` / `DH_RATE` in `derive()`, which `engine.configure` reruns after `params` set them
(the gear model passes each set's own: `tools/gear`).

Speed: CPython 3.15 runs every search ~35% faster than 3.10, with identical rotations (`scratch/speed/`); PyPy 3.10
was 15-25% faster on the long searches but slower on short ones (Dancer twice as slow) at 2-3x the memory, and wasn't
adopted. cProfile overstates small functions: the gauge notes looked like 7% of a search, but formatting them lazily
gained nothing and cost 15-30% more memory, so it was reverted; a candidate is checked with `timeit` and whole-sweep
timings before anything is restructured for it. Cheaper rounding of the state keys would change which states dedupe,
so it can't leave the results identical (see Checks).

## From potency to DPS

`dps.py` converts per player, from their clean pulls (alive through 2:00) on the job:

- **damage per potency**: their plain hits with others' buffs divided out, over the model's potency; FFLogs' multiplier
  holds the player's own damage-ups too, so the job's `own_factor` puts them back (Death's Design, Arcane Circle, ...);
- **crit and direct hit**: their average hit over their plain hit, action by action, over the hits under no crit or
  direct-hit raid buff (rDPS credits those to whoever gave them); sure crits at their own gain;
- **DoT ticks** at their average over their plain level, DoT by DoT (`tick_gain`); **GCD** from back-to-back casts. Where the job model rounds as the game
  does (`engine.recast`: Black Mage, Samurai, Viper, Monk, Ninja) the speed factor within the GCD counts too
  (`calibrate.speed_for`): under Fuka or Swiftscaled the player's hasted GCD as played decides it (the fastest spacing
  holding a quarter as many gaps as the commonest, `hasted_gcd_of`: our Samurai 2.41 / 2.09, two Vipers whose few
  unhasted gaps read 2.49 play 2.09, so 2.47); Ley Lines only narrows the GCD's tier. A GCD whose tier holds two
  hasted GCDs gets both in its site key (`2.41-h2.09`).

Check: each pull's logged casts, replayed through the model and converted, land within ~1.5% of the damage logged for
Black Mages and Machinists, -2% to +4% for Reapers (the replay takes every positional).

The ceiling is the best rotation without raid buffs at the player's GCD over 0:00-2:00 (the scorecard's window), at
their worst slot and variants (`p12s.worst_slot`), so it holds whichever they are given. A job with a raid buff
(Reaper's Arcane Circle) also gets credit for what it added to others: the site adds each pull's FFLogs
totalRDPSGiven. `dps.py --job <job> --site` saves the ceilings (`.cache/ceilings.json`, git-ignored: it names players)
and one rotation per GCD for the site's Rotations pages (`.cache/rotations.json`; `--gcds` adds GCDs): the whole-phase
optimum, scored and shown until Palladion (`ROT_UNTIL`, 4:41; not a search for that window: a rotation that has to go
on holds resources one ending there would spend, and as our progress moves on the site shows more of the same
rotation, which players keep learning, rather than a new one), its runs placed in the longest stretches outside cast
bars (`placed_runs`). A rotation's expected DPS is the median of our players' conversions (for a job none of them plays, the benchmark
clears' players since the job's `CONVERT_SINCE`), each moved to its GCD first:
the speed points a faster GCD takes come out of crit, direct hit or determination (`SPEED_PTS`, `STAT_PT`: ~0.40%
damage per potency per 0.01 s), so GCDs from 2.18 s to 2.45 s come out within 0.7% for a Black Mage. Moved to one
GCD that way, our seven Black Mages' conversions span 3.4% instead of 10.5%: the price holds even 0.2 s away. A full
stat model per player isn't possible: FFLogs logs stats (CombatantInfo) only for the player who uploaded.

The ceiling's crit / direct-hit gain (`e0`, hits under no crit or direct-hit buff) pools the clean pulls' full logs with
each player's other pulls up to their own first death or Damage Down (`logs.ours_more`, the acts caches, `flag_hits`):
about three times the hits. On the same clean pulls the two sources agree within ~0.2% on average, but a player with
few clean pulls swung by up to 6% on luck alone (one Viper's 2 pulls read a 54% direct-hit rate).

`--offline` converts from the acts caches when FFLogs is down (`logs.ours_offline`): no crit flags, so `flag_hits`
reads crit and direct hit from each hit's size against its plain level (x1.12, 1.37, 1.73); hits under others' raid
buffs are left out, own damage-ups come from the player's statuses. On Black Mage it reads 0-3% higher than the full
logs. A target debuff (Death's Design) can't be divided out this way. The site says which jobs were converted so.

## Checks

`check.py` tests the movement accounting on hand-made windows, then replays quick searches for both slots and every
variant: each window gets its running time outside cast bars, and nothing is cast at Athena while she is away (a
standing-still rotation, as a control, breaks several windows). For the melee jobs it tests reach and positionals and
that every away window holds a stretch of its length without a melee action. Each job adds its own rules on hand-made
states (Reaper's positionals, Bard's Repertoire and Army's Muse, Red Mage's Dualcast, procs, far spots and dashes,
Pictomancer's Inspiration, landscape and capped charges, Machinist's heat, Blazing Shot, Wildfire and queen,
Summoner's trances, pets, attunement and favors, Dancer's dances, procs, feathers, Esprit and Devilment, ...).

A log replay only shows that a model is no stricter than the game. For the other direction each job's whole-phase plan
is replayed through [xivintheshell](https://github.com/xivintheshell/xivintheshell) at level 90 with every proc granted
(the most lenient case, so a refusal is a rule difference, not luck): the harness and how to run it are in the
repository's `scratch/xits/`. Each refusal is settled from our logs or the guide, and where the two disagree the logs
win (Machinist's Drill recast shortens with skill speed, xivintheshell's is a fixed 20 s; Red Mage's Verthunder /
Veraero III cost 300 MP, not its 400). The 2026-10-25 pass found the rules each job's section now states (Bard's song
clock, Monk's forms after Perfect Balance, Viper's twinblade combo, Samurai's 10 Kenki, statuses timed from their
landing). Bard (after its song-clock and downtime fixes), Dancer, Ninja, Dragoon and Summoner replay clean. Two
refusals are still unsettled: Samurai's Kaeshi: Namikiri after a combo weaponskill (the logs only show Higanbana
between them) and Pictomancer's Striking Muse before combat starts (only possible solo). Rerun the replay after
changing a job's rules.

`calibrate.py`'s status check (each job's `STATUSES`, model against log just before every cast) catches what a legality
replay can't: a damage buff that ends early or lands too soon. It found the status timings of the same pass (a status
timed from the cast at its tooltip ran 0.5-0.8 s short, True North's 10.5 s in every melee job among them), three
rules (Reaper's last reaping of an Enshroud grants no enhanced reaping, Monk's Form Shift takes the form, every
Machinist weaponskill under Overheated takes a stack) and that Red Mage's Manafication was six GCD stacks before 7.5
and a plain 30 s since (Red Mage's `LOGS_SINCE` reaches back to 7.05, so the older clears' Manafications show up as
disagreements). What it still shows is noted per job: pre-pull statuses a replay doesn't cast (Summoner's
Searing Light), Black Mages leaving their Ley Lines, Immortal Sacrifice coming with the party's hits.

A refactor or speed-up must change no result: every job's score, step count and history hash stay identical
(`scratch/speed/identity.py --save` / `--against`, all 13 jobs against a baseline of the old code;
`scratch/review/snapshot.py`, one narrow sweep per job, `--diff`).

## Adding a job

A new job follows the method above, starting from the last job's measuring scripts (`scratch/<job>/`) and the full
logs (`logs.clears(job)`, `logs.ours(job)`).

- **Search hooks** in `jobs/<job>.py`: `State` (an `engine.SlotState` with `__slots__`, which generates its `copy`;
  `initial`, `key` with the cooldowns through `engine.cd_key`, `log`, `history`), `expand`, `rank`, `final`, `VALUE`,
  `RATE`, `MOVE_WEIGHT`, `HEURISTICS`, `WIDTH`, `SWEEP_WIDTH`; where they apply `CAPPED`, `END_TAPER`, `FAR`,
  `MELEE`, `s.dashed` with `engine.dash`. A short GCD needs `WEAVE_SLACK` (a double weave in Monk's 1.94 s GCD clips
  it by 0.01 s).
- **Calibration and DPS hooks** (`calibrate.py`'s docstring has their contract): `LOG_NAME` (FFLogs' job name),
  `LOGS_SINCE`, `OGCDS`, `REFERENCE`, `cast_time`, `at`, `status`, `force`, `label`, `cast_label`, `STATUSES`;
  optional `cd_name`, `own_factor`, `prepare` / `unprepare` (what a replay reads from the log; `unprepare` must clear
  it, or it leaks into `dps.upto`), `force_ogcd` (leaves multi-charge cooldowns recharging), `HASTE` / `HASTED` /
  `GCD_BASE` / `HASTE_STATUSES` (`calibrate.gcd_of`), `AUTO_CRIT` with `s.critp` and `CRIT` (dps.py's sure crits),
  `sure_crits(p)`, `CONVERT_SINCE`.
- **Shared helpers** (`jobs/_common.py`): `wasted`, `cast_label`, `no_cast` (as `cast_time`), a melee's `reach`,
  `out_of_reach`, `away_soon` and `flank_rear`, and `charges, use_cd, full_since, capped, ready, at =
  cooldowns(__name__)` bound after `CDS` (and `recast_of`). A job writes its own only where it differs (Black Mage's
  `at`, Red Mage's charges for Sprint).
- **Tuning**: `SWEEP_WIDTH` is the width at which a sweep takes about as long as the beam at `WIDTH`; then
  `HEURISTICS` from `tune.py --job <job>` (mostly the `VALUE` scale matters). A rank ends in `- RATE * s.t`.
- **Registration**: `JOBS` in `jobs/__init__.py` (solve.py, dps.py and tune.py pick from it), `check.py` (`HARM`, the
  job's cases and searches) and `calibrate.py`'s `--job` help. Every search worker imports every registered job, so a
  job goes in only once `python -c "from jobs import <job>"` passes; until then `calibrate.py`, `engine.search` and
  `polish.py` load it by name.
- **On the site**: `dps.py --job <job> --site`, then the scorecard's `build_site.py --reanalyse`, and the job's notes
  in `ROT_CHALLENGES` (`tools/scorecard/site/app.js`). A `--site` run replaces the job's rotations in
  `rotations.json`, so extra GCDs are passed again with `--gcds` (a rotation with `players: 0` is an extra, e.g.
  Summoner's 2.41 and 2.49, except in a job converted from the clears, Ninja, where every rotation shows 0). Runs for
  different jobs may go in parallel: `rotations.json` is read only after the searches.

Ranking lessons, each of which cost a job 1-5% before it was found:

- held resources by the rules in The search (conversion less `RATE` times the GCD time, `END_TAPER`, `CAPPED`;
  inflated values hoard), and a cooldown-gated resource counts only if its cooldown is back before the window ends;
- a resource feeding delayed or pet damage is worth less than what it converts into (Machinist's battery);
- held values priced at the filler's own rate tie it exactly, and the beam drifts holding them (Summoner);
- an action that ties the filler, offered every step, floods the beam: offer it only where it matters (Monk's
  Six-Sided Star, Viper's Uncoiled Fury);
- a DoT counted when applied makes early refreshes look good: gate the refresh (Dragoon's Disembowel);
- a multi-GCD action that pays only at its end must be one search step, or the states partway through lose to fillers
  (Dancer's dances);
- a zero-length wait child hangs the beam (see The search), and a state with no GCD landing before downtime needs a
  wait child, or the beam (`--layers gcd`) dies at Palladion.

Supports aren't modelled yet: `p12s.PLAN` is written for the DPS slots; a tank or healer needs its role's assignments
from the raidplan's role slides, its own clears' runs, and room for healing and mitigation (the target stays personal
potency).

## Files

| File | Role |
|---|---|
| `engine.py` | timing (GCD, casts, slidecast, weaving), raid buffs, move windows and dashes, downtime, beam and sweep search |
| `jobs/<job>.py` | a job: its resources, actions, potencies, the search's choices and ranking, and the calibration hooks |
| `jobs/_common.py` | what the jobs share: cooldown charges and capped-charge costs, a melee's reach and positionals, trivial hooks |
| `jobs/__init__.py` | `JOBS`, the registry the command lines pick a job from |
| `p12s.py`, `p12s_p1.json` | the fight: timeline, downtime, our strategy's runs, the clears' runs elsewhere, melee reach |
| `solve.py` | command line |
| `polish.py` | local search on a found rotation (and restarts of the search along it) |
| `montecarlo.py` | a rotation under drawn procs: followed, or re-planned before every step |
| `tune.py` | picks a job's heuristic settings |
| `logs.py` | detailed per-player logs from the benchmark clears and our pulls, cached in `.cache/` |
| `calibrate.py` | replays logs through a job model and reports where they disagree |
| `check.py` | movement, downtime and job-rule checks |
| `dps.py` | potency to DPS per player; ceilings and rotations for the scorecard site |
| `patchnotes.py` | a job's PvE action changes from the official patch notes (level-100 values, like the job guide) |
| `rdm-in-game-tests.md` | what the Red Mage logs couldn't settle, to test in game |
