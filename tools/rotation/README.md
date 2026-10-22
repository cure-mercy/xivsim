# Rotation optimizer

Searches for the highest-potency rotation of a job over P12S phase 1 (level 90), from the pull to the kill, against
the fight's fixed timeline: when Athena can't be hit, and where our groups' strategy makes the player run.

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
python tools/rotation/patchnotes.py Reaper                    # the job's PvE changes in the official patch notes
python tools/rotation/dps.py [--job rpr]                      # our players: ceiling in DPS next to their scorecard rDPS
python tools/rotation/dps.py --job rpr --site [--gcds 2.40]   # ...and save ceilings and rotations for the scorecard site
python tools/rotation/dps.py --job drg --site --offline       # ...from the scorecard's cached events, when FFLogs is down
```

| `--job` | Job | Default GCD | Slot | Best over the phase | Standing still | Search |
|---|---|---|---|---|---|---|
| `blm` | Black Mage | 2.32 s | R1 | 101,361 | 101,596 | ~70 s |
| `rpr` | Reaper | 2.49 s | M1 = M2 | 131,628 | 133,399 | |
| `mnk` | Monk | 1.94 s (2.43 s before Greased Lightning) | M1 / M2 | 133,997 / 133,392 | 135,805 | ~2.5 min |
| `brd` | Bard | 2.49 s | R1 = R2 = still | 85,922 | | |
| `drg` | Dragoon | 2.49 s | M1 = M2 | 126,632 | 127,736 | ~70 s |
| `rdm` | Red Mage | 2.50 s | R1 / R2 | 93,149 / 92,056 | 93,613 | ~35 s |
| `vpr` | Viper | 2.49 s (2.12 s under Swiftscaled) | M1 = M2 | 145,130 | 145,714 | ~55 s |
| `sam` | Samurai | 2.40 s (2.09 s under Fuka) | M1 = M2 | 133,863 (148,419 \*) | 134,948 (149,505 \*) | ~2 min |
| `pct` | Pictomancer | 2.45 s | R1 / R2 | 93,782 / 93,146 (103,194 / 102,558 \*) | 94,243 (103,725 \*) | ~30 s |
| `mch` | Machinist | 2.45 s | R1 = R2 = still | 107,858 (111,688 \*) | | ~30 s |
| `nin` | Ninja | 2.09 s (2.46 s before Increase Attack Speed) | M1 = M2 | 131,340 | 131,525 | ~50 s |
| `smn` | Summoner | 2.45 s | R1 = R2 = still | 94,536 | | ~20 s |

Potency without raid buffs, over 0:00-449 s, as each job's section last recorded it. \* with sure critical (direct)
hits at their expected worth, which is what the search ranks by.

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
| `--compare` | replay every benchmark clear's logged rotation under the same buffs, downtime and window |

Damage is potency times the raid buffs active when each hit lands; crit and direct-hit buffs count at their expected
value.

## How a job model is built

Each `jobs/<job>.py` starts from the official job guide and the patch notes since 7.0 (`patchnotes.py`). Both show
level-100 values, and most jobs have a trait between 91 and 100 that raises their potencies, so the level-90 values
are measured from logs: per player and action, the plain-hit cluster (no crit, no direct hit, own and others' damage
buffs divided out), scaled to a reference action that no trait or patch touches; FFLogs' `bonusPercent` (a hit's share
of potency from its combo or positional) confirms each split. Two sources: the full FFLogs logs (`logs.py`, cached in
`.cache/`: crit flags, multipliers, buffs on each hit, positions) and the scorecard's acts caches
(`tools/scorecard/.cache/acts_*`: every pull of ours and the benchmark kills, pet hits, no crit flags). The measuring
scripts live in the repo's git-ignored `scratch/<job>/`.

`calibrate.py` then replays every logged cast through the model at its logged time, over the whole pull up to the
player's first death (`report_<code>.json` deaths for our pulls): every cast should be legal, cast times should match
begin-cast to cast, and each action's plain hits should match the model's potency. Each job's replay is legal but for
the casts its section notes (in most jobs only second tinctures, which the model doesn't allow). A tamper control
(`scratch/<job>/tamper.py`: rules broken on purpose) shows each broken rule as illegal or early casts. Rules the logs
need and the guide doesn't give are listed per job.

## Black Mage

`jobs/blm.py`, checked against the 11 Black Mage clears since patch 7.2 (April 2025, when the kit changed):

- every cast is legal except a second tincture; cast times match within 0.02 s at each player's own GCD (2.14-2.45 s);
  each spell's plain hits match within ~2-3%; MP matches 1,846 of 1,911 logged snapshots (most of the rest predate a
  refill);
- a spell resolves (its logged cast event: damage, gauge, MP) 0.52 s before its bar ends, for every cast length; the
  player may move for the last 0.46 s (the slidecast), so the two are kept apart;
- since 7.2: Fire IV, Despair and Blizzard IV cast in 2.0 s, Ley Lines lasts 20 s, Thunderhead and Firestarter never
  expire (only lost by being granted again), Fire III and Blizzard III deal 290;
- from the logs alone: a hard-cast Fire III from Umbral Ice III costs no MP (4 of 4 casts), and the Polyglot timer
  starts when the first fire or ice spell lands (Fire III's 1.29 s flight), not when it resolves.

Over the whole phase in R1 the best rotation deals 101,361 potency; standing still 101,596, so our strategy's ~59 s of
running costs about 0.2%: instants, slidecasts and weaves cover nearly all of it. The best clear's own rotation,
replayed at the same 2.32 s GCD with its own movement (`--compare`), deals 101,033.

## Reaper

`jobs/rpr.py`. Melee Mastery III (94) raises most potencies in the guide; at level 90 they are Endwalker's, scaled to
Communio (1,100): Slice 320, Waxing / Infernal 400 / 500 in combo, Soul Slice 460, Void / Cross Reaping 460 (+60
enhanced), Lemure's Slice 240, Unveiled 400, Harvest Moon 600, Gluttony 560 (7.5 raised it: 520 in older clears).

- Gibbet and Gallows: 400, +60 from the flank / rear, +60 enhanced;
- Plentiful Harvest grants Ideal Host (one Enshroud without gauge) and no Shroud gauge; Gluttony two Soul Reaver
  (Executioner 96, Sacrificium 92, Perfectio 100 lie above P12S);
- Void and Cross Reaping run on a fixed 1.5 s GCD; Communio casts in 1.3 s like a spell; combos aren't broken by
  other GCDs; auto-attacks 96 potency every 3.2 s; Plentiful Harvest assumes a full party's eight stacks.

Every cast in the 15 benchmark logs and our 79 clean pulls replays legal. The search needs width 3,000 (at 1,000 the
settings spread 3%); its ranking gives no credit for running banked toward a run (`move_credit`), which made it burn
Enshroud early. Over the phase 131,628 in M1 and M2; standing still 133,399 (-1.3%): five True Norths for the fixed
spots, ranged GCDs in the stretches out of reach. Over 0:00-380 s standing still the clears' own rotations replay at
79-93% of the best (they hold Soul Slice and Enshroud for raid buffs, lose uptime, some die).

## Monk

`jobs/mnk.py`, checked against the 19 benchmark clears with a Monk and our 64 clean pulls. Melee Mastery (84) sets the
level-90 values: Bootshine 220, True Strike 300, Snap Punch 270, Twin Snakes 380, Demolish 320, Dragon Kick 280, The
Forbidden Chakra 400 (the reference); from the logs Phantom Rush 1,400, Six-Sided Star 710 (the logs' spelling).

- auto-attacks 78 potency every 2.05 s (1.03 s under Riddle of Wind); hit delays 0.40 s (Phantom Rush) to 1.60 s
  (Demolish); the meditations recast in a fixed 1 s; Six-Sided Star's 4 s shrinks with skill speed, not Greased
  Lightning;
- every Bootshine under Perfect Balance or Formless Fist crits, as in opo-opo form;
- forms and Fury: Dragon Kick, Twin Snakes and Demolish bank +200 / +200 / 2 x +150 for Bootshine, True Strike and the
  Snap Punches; Perfect Balance makes the beast chakra for Elixir Field, Rising Phoenix and Phantom Rush;
- chakra is random: the search counts the expected `--crit` per weaponskill, one per opo-opo Bootshine, one more under
  Meditative Brotherhood, and the party's 20% chances (0.57 a second in our windows, 0.51 in the clears); a replay takes
  the log's own crits. One window's party share swings 0.4-0.7 a second, so ~55 of 1,500 replayed Forbidden Chakras
  come out a chakra short: luck, not a rule;
- Bootshine's sure crits are kept apart (`critp`) and `dps.py` converts them at the player's own sure crit, searching
  each player's ceiling at their crit rate.

Six-Sided Star about ties the rotation per second, so it is only offered before Palladion and at the window's end.
Over the phase 133,997 in M1 and 133,392 in M2 (tuned settings, 2026-10-22; within the search's noise of each other);
standing still 135,805 (-1.3% / -1.8%): the fixed spots' positionals take True Norths and the
away stretches can't be filled (out of reach a Monk can only meditate, Form Shift or use Enlightenment).

## Bard

`jobs/brd.py`. No benchmark clear has a Bard, so our 62 clean pulls (four players) are the only check
(`calibrate.py --job brd --ours`; `--compare` has nothing to replay). Ranged Mastery (94) raises the main actions in
the guide; from the logs, scaled to Bloodletter (130): Burst Shot 200, Refulgent Arrow 260, Empyreal Arrow 240,
Sidewinder 320, Apex Arrow 5 a Soul Voice; DoT ticks 25 and 31 (1.25 x the tooltips); auto-attacks 68 every 3.07 s;
Radiant Finale's damage status is 2964.

- Songs: each 3 s tick with a bite up gives Repertoire 80% of the time; the search counts the expected 0.8 (Pitch
  Perfect stacks under the Minuet, 7.5 s off Bloodletter under the Ballad, 4% haste under the Paeon plus Army's Muse
  after it). Repertoire isn't logged, so the ~48 illegal casts left in replays (Bloodletters under the Ballad, Blast
  Arrows under 80 Soul Voice) are that expectation.
- Hawk's Eye (35% from Burst Shot, the bites and Iron Jaws) counts at its expected 0.35 x 60 / 1.35 per GCD; the search
  fires Refulgent Arrow only under Barrage.
- Own buffs: Raging Strikes, Radiant Finale and the Ballad are damage; Battle Voice and the songs' crit / direct hit
  count at their expected worth. `dps.py`'s replay-vs-logged check counts those twice (~2%); the ceiling doesn't.
- DoTs snapshot, tick on the server tick and count when applied; Iron Jaws refreshes late, or early under fresh buffs.
- Every action is instant and reaches 25 y, so R1, R2 and standing still give the same rotation.

Over the phase 85,922: Raging Strikes and Battle Voice on the Minuet, Minuet -> Ballad -> Paeon, Blast Arrow after
every Apex Arrow at 80+; Radiant Finale lands in the Ballad, since its worth to the party isn't counted.

## Dragoon

`jobs/drg.py`, measured in the acts caches (our 311 pulls by six Dragoons, 11 benchmark clears) and replayed through
the full logs. Melee Mastery (94) raises most weaponskills in the guide; at level 90, scaled to High Jump (400):

- Raiden Thrust 280, Vorpal Thrust 130 / 280 in combo, Heavens' Thrust 100 / 400, Disembowel 140 / 250, Chaotic
  Spring, Fang and Claw and Wheeling Thrust 100 / 260 in combo +40 positional, Drakesbane 400, Wyrmwind Thrust 420,
  Stardiver 720, Nastrond 720, Mirage Dive 380, Geirskogul 280, Dragonfire Dive 500; DoT ~50 a tick (tooltip 45);
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
  for it: Disembowel is offered only when the DoT would be nearly out by its Chaotic Spring, or Power Surge is low.
- Out of reach, Elusive Jump buys an Enhanced Piercing Talon (350).

Over the phase 126,632 in M1 and M2; standing still 127,736 (-0.9%): six True Norths, four Piercing Talons. Life Surge
goes on eight Drakesbanes and four Heavens' Thrusts.

## Red Mage

`jobs/rdm.py`, measured in the acts caches (our 267 pulls by five Red Mages, 18 benchmark clears) and replayed through
the full logs. Enchanted Blade Mastery (94) raises nearly every potency in the guide; at level 90 they are Endwalker's,
scaled to Jolt III (360):

- Verthunder / Veraero III 380, Verfire / Verstone 340, Verflare / Verholy 600, Scorch 680, Resolution 750; Enchanted
  Riposte 280, Zwerchhau 150 / 340 in combo, Redoublement 130 / 500, Reprise 340; Fleche 460, Contre Sixte 380,
  Engagement 180, Corps-a-corps 130;
- Embolden: +10% on the Red Mage's own magic (the enchanted combo too, not the physical oGCDs), 0.67 s after the cast;
- the enchanted combo recasts in a fixed 1.5 / 1.5 / 2.2 s; an instant Ver-III spends Acceleration before Dualcast and
  Swiftcast, and Dualcast survives it; a spell made instant never grants Dualcast; Sprint cancels Dualcast;
  Verthunder / Veraero III proc 49.4% (4,158 casts), 100% under Acceleration.

Every cast (24,041, ours and the clears) replays legal.

- Procs count at their expected worth. At level 90 the search never spends them (Jolt III's 360 and 2 / 2 mana beat
  Verfire's 340 and 5); forcing them costs 0.4-1.1%, though our Red Mages spend them.
- The melee combo costs 20 / 15 / 15 of each mana (nothing under Manafication's Swordplay) and gives the stacks for
  Verflare / Verholy -> Scorch -> Resolution. Open in the logs, to test in game ([rdm-in-game-tests.md](rdm-in-game-tests.md)):
  whether mana gains halve past a 30-point imbalance (left out; searches never pass 30) and whether stacks outlive a
  broken combo (the search plays whole combos, started only with their mana and their three hits clear of far spots).
- Reach: the melee combo and Engagement need 14 y from Athena's centre (25 y under Manafication); at our plan's far
  spots (`p12s.FAR`) a ranged player is out of reach around the snapshot.
- Dashes (`engine.dash`): in R1, Corps-a-corps from Paradeigma I's wall to Athena's hitbox edge saves 1.3 s of the
  swap (+0.8%); R2's Displacement comes after the GCD it could have freed, so it gains nothing.

Over the phase 93,149 in R1 and 92,056 in R2; standing still 93,613. What is left is Paradeigma I's swap through the
middle while the opener's cooldowns recharge, filled with Enchanted Reprise. The clears' rotations, replayed standing
still over 0:00-380 s, deal 93-97% of the best.

## Viper

`jobs/vpr.py`, measured in the acts caches (our 249 pulls by six Vipers, 24 benchmark clears) and replayed through the
full logs since 7.5. No Viper trait above level 90 raises a potency, so the guide's values hold (Death Rattle 280 as
the reference; Vicewinder 540 and the Coils 630 since 7.5, the Generations 680, the bites 170, Uncoiled Fury 680);
level 90 lacks Uncoiled Twinfang / Twinblood (92), the fifth Tribute and Ouroboros (96) and the Legacies (100).
Auto-attacks 80 potency.

- Recasts: Vicewinder and the Coils 3.0 s, Uncoiled Fury 3.5 s, Reawaken 2.2 s, the Generations 2.0 s, the rest 2.5 s,
  all by skill speed and Swiftscaled's 15% (the GCD granting it isn't hasted); Vicewinder's 40 s and Serpent's Ire's
  120 s are flat;
- statuses come after their hit; Hunter's Instinct and Swiftscaled refresh to 40 s, so both lapse over Palladion;
- the Coils, Uncoiled Fury and the Generations don't break the dual-wield combo; Death Rattle and the bites are lost
  with the next weaponskill; Reawaken grants four Tributes at 90; Rattling Coils start at none.

Every cast replays legal. Swiftscaled is up nearly all fight, so `calibrate.gcd_of` divides gaps under it by its haste
(`HASTED`) and scales gaps after longer GCDs (`GCD_BASE`).

- Dual-wield combo with Honed and venoms, twinblade combo with bites, Reawaken on 50 Offerings or Ready to Reawaken.
- Uncoiled Fury about ties the filler; offered at every step it filled the beam with orderings of one rotation, so it
  is offered at three Rattling Coils, out of reach or near it, before downtime, at the end and under raid buffs.
- Each held resource is valued at what it converts into less the time its GCDs take; at 1.5 times that the search held
  Coils and Offerings (-5%). Held values fade over the window's last 15 s. Rates below the filler's own (~275 a second)
  made time look cheap (-1.5%).

Over the phase 145,130 in M1 and M2; standing still 145,714 (-0.4%, the least of the melee jobs): six True Norths
cover ten positionals, Uncoiled Fury and the 3 s twinblade gaps cover the stretches out of reach.

## Samurai

`jobs/sam.py`, measured in the acts caches (our 199 pulls by four Samurais, 12 benchmark clears) and replayed through
the full logs. Way of the Samurai III (94) raises most potencies in the guide; at level 90, scaled to Hissatsu: Shinten
(250):

- Hakaze 200; Jinpu / Shifu 120 / 280 in combo; Gekko / Kasha 110 / 320 in combo +50 positional; Yukikaze 110 / 290;
  Higanbana 200 and ~50 a tick for 60 s; Shoha 560; Senei 800 on 120 s; auto-attacks 80; sure crits Midare Setsugekka
  and Kaeshi 620 (lowest cluster over each player's crit multiplier), Ogi and Kaeshi: Namikiri 860 (1.38 x Midare in
  the same pull under the same buffs).

From the logs:

- **Gekko and Kasha give 15 Kenki**, not 10: at 10, 246 Hissatsu casts come up short, at 15 two (whether 5 of it needs
  the positional can't be told);
- Iaijutsu and Ogi Namikiri cast in 1.3 s flat; Fuka shortens the recast (2.40 -> 2.09 s) and autos, not the cast;
  Iaijutsu, Kaeshis, Ogi and Enpi don't break the combo; Kaeshis give no Meditation;
- every opener has a pre-pull Meikyo Shisui ~13 s ahead (a replay reads it from the log);
- Tengentsu's 10 Kenki needs a hit within 4 s: 18 fight hits (`HITS`) where it paid off; a replay takes the log's own;
- the clears Meditate at Palladion's end until Athena returns, a Meditation stack per 3 s tick (its 10 Kenki a tick is
  the in-game value, not testable in logs).

Every cast but one in our pulls replays legal, and in the clears all but a Midare and a second tincture.

- Sure crits (Midare, Kaeshis, Ogi) are weighed by a sure crit's gain over an average hit (`SURE_W`, x1.60 at 25%
  crit); the printed potency stays plain, `dps.py` converts them at each player's own (`AUTO_CRIT`).
- While Athena is away the search takes one step: Tengentsu on the hits it catches, then a 0-5 tick Meditate ending
  at her return (separate steps made short Meditates look better under the rate).
- Held Tsubame-gaeshi Ready is valued at its Kaeshi less a 2.09 s GCD (valued whole, the beam held it 16 s and
  overwrote Sen).

Over the phase 133,863 in M1 and M2 (148,419 weighted); standing still 134,948 (-0.7%), nearly all of it the stretches
out of reach, where Enpi fills in (the 6-10 y Iaijutsu and Shoha are assumed not to reach there; +0.3% if they do).

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
- Smudge dashes 15 y along an open run (job-local, banking the running); it ties with no Smudge.

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
- The tools recast on skill speed (Drill 19.3 s at 2.41 s); Blazing Shot's 1.5 s doesn't, and takes 15 s off Gauss
  Round and Ricochet; nothing breaks the combo; Barrel Stabilizer gives only Hypercharged at 90.
- 37 of 45 logs open with a pre-pull Reassemble whose cast isn't logged: a replay reads it from the status falling off,
  the search presses one at -4.5 s. Reassemble went on a tool every time; its critical direct hits are weighed at
  `SURE_W` (x1.62) and converted per player (`AUTO_CRIT` names the tools).

Every cast in the clears since 7.3 replays legal, and in our pulls all but four Drills of one player (a GCD that reads
2.50 s to the hundredth). The queen and Wildfire are booked when deployed or cast. A battery point is valued at two
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

Over the phase 131,340 potency in M1 and M2; standing still 131,525, so our strategy costs a Ninja ~0.1%, within
the search's noise: six True Norths cover the fixed spots and ninjutsu fill the stretches out of reach. It opens on
the pre-pull Suiton with Trick Attack, Dokumori and Ten Chi Jin (Meisui into Bhavacakra), then Raiton, Bunshin,
Kassatsu -> Hyosho Ranryu and the Raijus inside Trick Attack, and over the phase makes 22 Raitons, 10 Suitons, seven
Hyosho Ranryus, four Ten Chi Jins, five Bunshins and 27 Bhavacakras. Settings from `tune.py` (rates 300-340 at
values x1.0 tie, x0.5 is 0.4% lower); the sweep holds within 0.5% from width 1,000 to 8,000 and beats the beam by
1.5-3%. The clears' rotations, replayed standing still over 0:00-365 s, deal 94-98% of the best (a pull with a death
79%). A search takes ~50 s. With no Ninja in our groups, `dps.py --site` puts the rotations on the scorecard site at the
clears' Ninjas' GCDs since 7.3 (`CONVERT_SINCE`), converted to DPS at those four players (whose damage per potency
differs by up to 40%); no player page links there.

## Summoner

`jobs/smn.py`, checked against our 15 clean pulls (two players) and the 11 benchmark clears with one (Mar-Dec 2025,
mostly one player) in the full logs, and our 77 pulls in the acts caches, which alone hold the pets' hits. Arcane
Mastery (94) raises nearly every potency in the guide; at level 90 they are Endwalker's, scaled to Fester (340):

- Ruin III 310, Ruin IV 430, Astral Impulse 440, Fountain of Fire 540, Ruby / Topaz / Emerald Rite 510 / 330 / 230,
  Energy Drain 200, Deathflare 500, Mountain Buster 150, Crimson Cyclone and Crimson Strike 430, Slipstream 430 and its
  windstorm six ticks of 30;
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
- Crimson Cyclone rushes to Athena (`engine.dash`; as Red Mage's Corps-a-corps not off a far spot before its
  snapshot) and Crimson Strike needs melee reach (`FAR`).
- Held values (each resource's conversion less Ruin III's rate over its GCDs) tie the filler exactly, so at their full
  scale the beam drifted holding Ruby stacks and Arcanum until the next demi-summon wiped them (-5.5%); `tune.py` puts
  the scale at 0.10-0.15. The search opens on a pre-cast Ruin III, as every clear does.

Our runs cost a Summoner nothing: R1, R2 and standing still find the same 94,536 potency over the phase (Ruin III
slidecasts, and all but Ruby Rite and Slipstream is instant; no Crimson Cyclone dash pays). Eight demi-summons, Searing
Light with each Summon Bahamut, Swiftcast on Slipstream or a Ruby Rite, and only eight Ruin IIIs: every Arcanum is
spent but Garuda's before Palladion (the 27 s after the 4:00 trance fit Titan and Ifrit). The primals' order changes
from cycle to cycle, a near-tie. Settings from `tune.py`; a search takes ~20 s and polish adds 0.2%. The clears'
rotations, replayed standing still over 0:00-370 s, deal 95-98% of the best (one pull 89%); our pulls over 0:00-130 s,
86-87%.

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
  per window), and from Palladion on that is provisional.
- **Melee**: melee actions need the player within ~14 y of Athena's centre (the clears' Reapers use them up to 13.5 y).
  Every spot of our plan is within that; where the clears' Reapers went longer than a GCD without a melee action, a
  melee is out of reach that long somewhere in the window (`away`: 13 s in five windows, all from 173 s on), with no
  melee actions or auto-attacks. While our plan fixes the spot (Paradeigma I-III, Superchain I: 77 s, `pinned`),
  positionals need True North, and the search decides where to spend it. Runs only block hard casts.
- **Far spots**: a ranged player is within melee reach everywhere but Paradeigma I's wall end and Superchain I's
  Heavensflame corner (`FAR`); a ranged job with melee actions is out of reach around those snapshots.
- **Dashes**: where a run of our plan goes straight to or from Athena (`DASH`: Paradeigma I and II), a dash along that
  stretch saves its running (`engine.dash`): a gap closer down to her hitbox edge (`ATHENA_EDGE`, 10.5 y), a backstep
  its length.

`python tools/rotation/p12s.py` lists every window with its source and compares our plan's distances with the clears'
(within about ±30%: ours runs more in Paradeigma I-III, less in Superchain I).

## The search

A beam search, one GCD per step with the oGCDs woven before it. States compete with those at the same time
(`engine.sweep`: 0.5 s layers, 0.25 s for Black Mage), ranked by damage so far plus what the resources they hold are
worth, minus a rate per second of time (and, for Black Mage, minus the running ahead its instants won't cover). Over a
whole phase the result moves by ~1% with these guesses, so `engine.search` runs several settings in parallel (the job's
`HEURISTICS`, from `tune.py`) and keeps the best. `polish.py` then improves it by local search over the whole fight
(another legal choice in one step's place, neighbouring GCDs swapped, an oGCD moved, a step dropped), on any job
through its `expand`; it found 0-0.7% more. Differences between scenarios below ~0.4% are noise. `--layers gcd` (the
beam by GCD count) and `--no-polish` bring back the earlier search.

## From potency to DPS

`dps.py` converts per player, from their clean pulls (alive through 2:00) on the job:

- **damage per potency**: their plain hits with others' buffs divided out, over the model's potency; FFLogs' multiplier
  holds the player's own damage-ups too, so the job's `own_factor` puts them back (Death's Design, Arcane Circle, ...);
- **crit and direct hit**: their average hit over their plain hit, action by action, over the hits under no crit or
  direct-hit raid buff (rDPS credits those to whoever gave them); sure crits at their own gain;
- **DoT ticks** at the player's average tick; **GCD** from back-to-back casts.

Check: each pull's logged casts, replayed through the model and converted, land within ~1.5% of the damage logged for
Black Mages and Machinists, -2% to +4% for Reapers (the replay takes every positional).

The ceiling is the best rotation without raid buffs at the player's GCD over 0:00-2:00 (the scorecard's window), at
their worst slot and variants (`p12s.worst_slot`), so it holds whichever they are given. A job with a raid buff
(Reaper's Arcane Circle) also gets credit for what it added to others: the site adds each pull's FFLogs
totalRDPSGiven. `dps.py --job <job> --site` saves the ceilings (`.cache/ceilings.json`, git-ignored: it names players)
and one rotation per GCD for the site's Rotations pages (`.cache/rotations.json`; `--gcds` adds GCDs): the whole-phase
optimum, scored and shown until Palladion (`ROT_UNTIL`, 4:41), its runs placed in the longest stretches outside cast
bars (`placed_runs`). A rotation's expected DPS is the median of our players' conversions (for a job none of them plays, the benchmark
clears' players since the job's `CONVERT_SINCE`), each moved to its GCD first:
the speed points a faster GCD takes come out of crit, direct hit or determination (`SPEED_PTS`, `STAT_PT`: ~0.40%
damage per potency per 0.01 s), so GCDs from 2.18 s to 2.45 s come out within 0.7% for a Black Mage.

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
Summoner's trances, pets, attunement and favors, ...).

## Files

| File | Role |
|---|---|
| `engine.py` | timing (GCD, casts, slidecast, weaving), raid buffs, move windows and dashes, downtime, beam and sweep search |
| `jobs/<job>.py` | a job: its resources, actions, potencies, the search's choices and ranking, and the calibration hooks |
| `p12s.py`, `p12s_p1.json` | the fight: timeline, downtime, our strategy's runs, the clears' runs elsewhere, melee reach |
| `solve.py` | command line |
| `polish.py` | local search on a found rotation |
| `tune.py` | picks a job's heuristic settings |
| `logs.py` | detailed per-player logs from the benchmark clears and our pulls, cached in `.cache/` |
| `calibrate.py` | replays logs through a job model and reports where they disagree |
| `check.py` | movement, downtime and job-rule checks |
| `dps.py` | potency to DPS per player; ceilings and rotations for the scorecard site |
| `patchnotes.py` | a job's PvE action changes from the official patch notes (level-100 values, like the job guide) |
| `rdm-in-game-tests.md` | what the Red Mage logs couldn't settle, to test in game |
