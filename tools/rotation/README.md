# Rotation optimizer

Searches for the highest-potency rotation of a job over P12S phase 1 (level 90), from the pull to the kill, with the
fight's fixed timeline: when Athena can't be hit, and where the player has to run under our groups' strategy. So far:
Black Mage, Reaper, Monk, Bard, Dragoon, Red Mage, Viper, Samurai and Pictomancer (Dragoon, Red Mage, Viper and Samurai checked only
against the scorecard's cached events: see their sections).

```
python tools/rotation/solve.py                                # R1, 2.32 s GCD, no raid buffs, 0:00 to the median kill (449 s)
python tools/rotation/solve.py --slot R2 --var para2=debuff --var para3=cross
python tools/rotation/solve.py --still                        # no forced movement: what running costs
python tools/rotation/solve.py --gcd 2.14 --party RPR,SCH,RDM --until 120 --compare
python tools/rotation/solve.py --job rpr [--slot M2]          # Reaper, 2.49 s GCD, M1 by default
python tools/rotation/solve.py --job mnk [--crit 0.25]        # Monk, a 1.94 s GCD (2.43 s before Greased Lightning)
python tools/rotation/solve.py --job brd                      # Bard, 2.49 s GCD, R1 (R2 and standing still come out the same)
python tools/rotation/solve.py --job drg [--slot M2]          # Dragoon, 2.49 s GCD, M1 by default
python tools/rotation/solve.py --job rdm [--slot R2]          # Red Mage, 2.50 s GCD, R1 by default
python tools/rotation/solve.py --job vpr [--slot M2]          # Viper, 2.49 s GCD (2.12 s under Swiftscaled), M1 by default
python tools/rotation/solve.py --job sam [--slot M2]          # Samurai, 2.40 s GCD (2.09 s under Fuka), M1 by default
python tools/rotation/solve.py --job pct [--slot R2]          # Pictomancer, 2.45 s GCD, R1 by default
python tools/rotation/p12s.py [--slot R2]                     # the move windows; --build refetches the timeline
python tools/rotation/check.py                                # movement and downtime checks
python tools/rotation/calibrate.py [--job rpr] [--ours]       # check the job model against the clears' (or our) logs
python tools/rotation/patchnotes.py Reaper                    # the job's PvE changes in the official patch notes
python tools/rotation/dps.py                                  # our players: ceiling in DPS next to their scorecard rDPS
python tools/rotation/dps.py --job rpr --site [--gcds 2.40]   # ...and save ceilings and rotations for the scorecard site
python tools/rotation/dps.py --job drg --site --offline      # ...from the scorecard's cached events, when FFLogs is down
```

| Option | Meaning |
|---|---|
| `--job` | `blm` (default), `rpr`, `mnk`, `brd`, `drg`, `rdm`, `vpr`, `sam` or `pct` |
| `--gcd` | the player's GCD without haste (spell or skill speed; default the clears' median); `--compare` prints each clear's. Monk's Greased Lightning takes 20% off it |
| `--crit` | critical-hit rate, for a job whose resources or buffs turn on crits (Monk's chakra, Dragoon's Life Surge and Battle Litany; default 0.25) |
| `--slot` | Paradeigma I: `R1` / `M1` line up for the first lasers, `R2` / `M2` for the second (our BLMs play both R slots; the melee slot varies with the lineup). Default `R1`, or `M1` for a melee |
| `--var` | a mechanic's variant: `para2=tether/debuff`, `sc1=spread/laser`, `para3=straight/cross`; default: the one with the most running |
| `--still` | no forced movement |
| `--party` | jobs whose raid buffs are present (default none: the job's own potency); they land at the median times of the benchmark clears |
| `--move` | extra windows in which nothing may be hard-cast (the last 0.46 s of a cast can be slid) |
| `--pot` | allow one tincture (off by default: the scorecard strips tinctures) |
| `--carry` | also value resources still held at the end, instead of dumping everything |
| `--until` | end of the scored window, seconds (default: the clears' median kill, 449 s; enrage is 458 s) |
| `--width` | search width per heuristic setting (default: the job's `SWEEP_WIDTH`, from 1,000 for BLM and RDM to 15,000 for DRG; `WIDTH` with `--layers gcd`) |
| `--layers` | `time` (default): states compete with others at the same time (`engine.sweep`); `gcd`: after the same number of GCDs (`engine.beam`, the search before 2026-10-22) |
| `--no-polish` | skip the local search on the search's best rotation (`polish.py`) |
| `--compare` | replay every benchmark clear's logged rotation under the same buffs, downtime and window |

Damage is in potency (Xenoglossy 890) times the raid buffs active when each hit lands; crit and direct-hit buffs count
at their expected value. Over the whole phase (R1, no buffs) the best rotation found deals 101,361 potency; standing
still it would be 101,596, so our strategy's ~59 s of running costs about 0.2%: the rotation covers nearly all of it
with instants, slidecasts and weaves.

## Reaper

`jobs/rpr.py`, from the job guide and the patch notes since 7.0. Both show level-100 values, and Melee Mastery III
(level 94) raises most of Reaper's potencies there, so the level-90 ones are measured from the logs' plain hits, scaled
to Communio (1,100, untouched by traits and patches). The benchmark clears (2025) and our groups' pulls (Sep-Oct 2026)
agree on every potency within ~1%, except Gluttony: 520 in the clears, 560 in ours (7.5 raised it). Rules the guide
alone would get wrong at level 90:

- Gibbet and Gallows are 400, +60 from the flank / rear, +60 enhanced (520 for both): under True North the enhanced
  hits cluster at 520, without it they mix 460 and 520;
- Plentiful Harvest grants Ideal Host (one Enshroud without Shroud Gauge) but no gauge, and Gluttony two stacks of Soul
  Reaver (Executioner is level 96, Sacrificium 92, Perfectio 100);
- Void and Cross Reaping run on a fixed 1.5 s GCD; Communio casts in 1.3 s like a spell (resolving 0.52 s early);
- auto-attacks: 96 potency every 3.2 s, and Plentiful Harvest assumes the eight stacks of a full party.

`calibrate.py --job rpr` replays every cast of the 15 benchmark Reaper logs and our 79 clean pulls (to the player's
first death) as legal; Communio and Harpe cast times match within 0.02 s.

**Movement.** A melee loses nothing to running as such (its actions are instants) but three things:

- *runs* (as for the Black Mage) block hard casts: Communio, Harpe, Soulsow;
- *out of reach*: melee actions need the player within ~14 y of Athena's centre (the clears' Reapers use them up to
  13.5 y, 99th percentile: a ~11 y hitbox plus 3 y). Every spot of our plan is within that, so only the stretches our
  plan doesn't cover have any: where the clears' Reapers went longer than a GCD without a melee action, the melee is
  away that much longer, somewhere in the window (13 s in five windows, all from On the Soul at 173 s on). No melee
  action may break that stretch and auto-attacks stop; Harvest Moon, Communio, Plentiful Harvest, Gluttony and Harpe
  reach from anywhere;
- *positionals*: while our plan fixes the player's spot (Paradeigma I-III and Superchain I, 77 s), Gibbet and Gallows
  only get theirs under True North, and the search decides where to spend its two charges.

The slots' Paradeigma I runs (`M1` baits the first lasers next to the tank, `M2` the second) differ, but neither run
blocks anything, so both come out the same. Over the whole phase the best rotation deals 131,628 potency; standing still
133,399, so our strategy costs a melee 1.3%: True North covers every Gibbet and Gallows left in a fixed spot (five
uses), the away stretches are filled with ranged GCDs, and the rest is the order the rotation has to bend into.
Running from Palladion on comes from the clears and is provisional, as for the Black Mage.

The search needs width 3,000 for Reaper (at 1,000 the heuristic settings spread 3%; at 3,000 they agree within 0.02%
standing still, 0.5% with the movement). The ranking gives no credit for running banked toward a run (the caster's
`move_credit`): for a Reaper that was noise of up to 600 potency per state, enough to make it burn Enshroud early.
Scenario differences under ~1% are not meaningful: a small delay can push the last Enshroud past the end of the window.

Over 0:00-380 s standing still the best rotation deals 112,097 potency; the clears' own rotations replay at 79-93% of
it (94.6% for the best two under their party's raid buffs, where the search's settings spread 3.4%). They hold Soul
Slice and Enshroud for raid buffs, lose uptime in mechanics, and some die.

## Monk

`jobs/mnk.py`, from the job guide and the patch notes since 7.0, checked against the logs of the 19 benchmark clears
with a Monk and our groups' 64 clean pulls (`calibrate.py --job mnk [--ours]`; the measuring scripts are in
`scratch/mnk/`). The guide's traits give most level-90 values: Melee Mastery (84) sets Bootshine 220, True Strike 300,
Snap Punch 270, Twin Snakes 380, Demolish 320, Dragon Kick 280 and The Forbidden Chakra 400 (the reference action);
Melee Mastery II (94) and the level-92 upgrades (Leaping Opo, Rising Raptor, Pouncing Coeurl, Elixir Burst) lie above
P12S. No single-target potency has changed since 7.05, so every Dawntrail clear will do. Every action's plain hits
match the model within 3% (Snap Punch and Demolish with their positional: the players take it nearly always). From the
logs:

- **Phantom Rush is 1,400** at level 90 (plain hits 1,400-1,415; Endwalker's 1,150 was assumed), **Six-Sided Star 710**
  (695 with no chakra open, 874 with two).
- **Auto-attacks**: 78 potency every 2.05 s, 1.03 s under Riddle of Wind. **GCD**: 1.92-1.96 s (1.94 s by default).
- **Hit delays** run from 0.40 s (Phantom Rush) to 1.60 s (Demolish).
- **Recasts**: the meditations take a fixed 1 s, not a GCD; Six-Sided Star's 4 s is shortened by skill speed but not by
  Greased Lightning (3.9 s between it and the next GCD).
- **Forms**: every Bootshine under Perfect Balance or Formless Fist crits, as in opo-opo form.
- **Party chakra** under Meditative Brotherhood: 0.57 a second in our windows, 0.51 in the clears, as the model's
  expected 20% of seven party members' GCDs. One window's share swings from about 0.4 to 0.7, so a replay at the
  expected rate finds 50-60 Forbidden Chakras (of 1,500) a chakra or two short: luck, not a rule.

The logs spell it Six-Sided Star (the model now does too: before, a replay skipped it).

- **Forms and Fury**: Dragon Kick, Twin Snakes and Demolish bank +200 / +200 / 2 x +150 for the next Bootshine, True
  Strike and Snap Punches; Perfect Balance's three GCDs make the beast chakra for Elixir Field, Rising Phoenix and then
  Phantom Rush once both Nadi are open.
- **Chakra** is random: a critical weaponskill opens one. The search counts the expected `--crit` (default 0.25) per
  weaponskill, one for Bootshine in opo-opo form (always a crit), one more under Meditative Brotherhood, and a full
  party's 20% chances; a log replay takes the log's own crits. Brotherhood lets ten be open.
- **Damage to DPS**: Bootshine's sure crits are kept apart (`critp`), and `dps.py` converts them at the player's own
  average sure crit, not their average hit; each player's ceiling is searched at their own crit rate.
- **Movement**: as for the Reaper (the away windows are the clears' Reapers'), with Snap Punch (flank) and Demolish
  (rear) as the positionals. Every weaponskill and The Forbidden Chakra need reach; out of reach a Monk can only
  meditate, Form Shift, or spend chakra on Enlightenment (a 10 y line).

Over the whole phase the best rotation deals 132,942 potency in `M1` (131,432 before the logs' values); standing still
136,209, so our strategy costs a Monk ~2.4%: the pinned spots' positionals take True Norths, and the away stretches
can't be filled. Six-Sided Star is only offered before Palladion and at the end of the window (elsewhere it about ties
the rotation per second, and the search drifted into chaining it); the search fires it just before Palladion and
meditates back up in the downtime, as the benchmark Monks do.

## Bard

`jobs/brd.py`, from the job guide and the patch notes since 7.0, checked against the logs. No benchmark clear has a
Bard, so `calibrate.py --job brd --ours` (our groups' 62 clean pulls, four players) is the only check, and
`solve.py --compare` has nothing to replay; the measuring scripts are in `scratch/brd/`. Since 7.0 the patch notes only
touch AoE potencies and actions above level 90 (Resonant Arrow 96, Radiant Encore 100). Ranged Mastery (level 94) raises
Burst Shot, Refulgent Arrow, Empyreal Arrow, Sidewinder and Apex Arrow to the guide's values, and the guide doesn't say
from what. From the logs (plain hits scaled to Bloodletter, 130, the reference action):

- **Burst Shot 200, Refulgent Arrow 260, Empyreal Arrow 240** (as guessed), **Sidewinder 320** (not 360), **Apex Arrow
  5 a Soul Voice** (~400 at 80, ~500 at 100; not 6). Pitch Perfect, the bites, Iron Jaws and Blast Arrow (700) are the
  guide's, within 1%.
- **DoT ticks**: 25 and 31, 1.25x the tooltips' 20 and 25 (as Black Mage's Thunder III).
- **Auto-attacks**: 68 potency every 3.07 s (not 80 per 3.04 s). **GCD**: 2.45-2.50 s (2.49 s by default).
- **Hit delays** run from 0.53 s (Sidewinder) to 1.65 s (Blast Arrow).
- The logs spell it The Wanderer's Minuet. Radiant Finale's damage status is 2964 (`own_factor` read 2722, its other
  status, which is never on a hit).

Repertoire isn't logged (the songs' statuses refresh every tick, proc or not), so a replay counts the expected 0.8 a
tick: of 48 illegal casts left, the Bloodletters under the Ballad and the Blast Arrows (Soul Voice under 80 in the model)
are that. A forced cast in a replay used to leave a multi-charge action without its recharge, which made every later
Bloodletter illegal (309 before the fix). Dragoon, Red Mage, Viper, Reaper and Monk had the same line and are fixed too;
their replays of today's logs come out the same (none had an illegal multi-charge cast to set it off).

- **Songs and Repertoire**: each server tick (3 s) with a bite on Athena gives Repertoire with an 80% chance while a song
  plays, and the search counts the expected 0.8 per tick. Under the Minuet that means Pitch Perfect stacks, under the
  Ballad 7.5 s off Bloodletter, and under the Paeon 4% haste a stack, plus Army's Muse (up to 12% for 10 s) when the
  next song comes in. Empyreal Arrow gives one surely, and each Repertoire is 5 Soul Voice. Singing over a song is
  allowed in its last 15 s, in any order.
- **Hawk's Eye** (35% from Burst Shot, the bites and Iron Jaws) also counts at its expected worth, as Monk's chakra does.
  A proc turns the next Burst Shot into a Refulgent Arrow, which can't proc, so each of those GCDs gains
  0.35 x 60 / 1.35 potency. The search only fires Refulgent Arrow under Barrage (three hits); a log replay fires it
  wherever the log does.
- **Own buffs**: Raging Strikes, Radiant Finale (2% a Coda) and the Ballad's 1% are damage. Battle Voice and the
  Minuet's and Paeon's crit and direct-hit rates count at their expected worth for typical rates. `dps.py` measures a
  player's crit/direct-hit gain on hits under none of those, so a ceiling counts them once. Its replay-vs-logged check
  counts them twice (~2%).
- **DoTs** snapshot buffs when they land, tick on the server tick, and are counted when applied. A refresh loses the old
  one's remaining ticks, so the search refreshes with Iron Jaws late, or early under fresh buffs.
- **Movement** costs a Bard nothing: every action is instant and reaches 25 y. R1, R2 and standing still give the same
  rotation; only Palladion's downtime matters.

Over the whole phase the best rotation deals 85,922 potency (87,790 with the guessed values: Sidewinder, Apex Arrow
and the autos came out lower, the DoTs higher; the settings spread 0.3%). It keeps Raging Strikes and Battle Voice on
the Minuet, refreshes Iron Jaws under them, and fires Blast Arrow after every Apex Arrow at 80+. With the measured
values it sings the usual Minuet -> Ballad -> Paeon (the guessed ones had Minuet -> Paeon -> Ballad). Radiant Finale
lands in the Ballad, not the 2-minute burst: the search counts only the Bard's own potency, and Radiant Finale's worth
to the party isn't in it.

## Dragoon

`jobs/drg.py`, from the job guide and the patch notes since 7.0. FFLogs was down when it was written, so instead of
guesses its level-90 values were **measured in the scorecard's cached damage events** (`tools/scorecard/.cache/acts_*`:
our groups' 311 pulls by six Dragoons, Sep-Oct 2026, and the 11 benchmark clears with one). Per player, each action's
plain-hit cluster with Power Surge, Lance Charge and Life of the Dragon divided out and others' raid buffs left out,
scaled to High Jump (400, untouched by traits and patches); FFLogs' `bonusPercent` (the share of a hit's potency from its
combo or positional) confirms each split. Both data sets agree within ~2%. Melee Mastery (level 94) raises most
weaponskills in the guide; at level 90:

- Raiden Thrust 280, Vorpal Thrust 130 / 280 in combo, Heavens' Thrust 100 / 400, Disembowel 140 / 250, Chaotic
  Spring, Fang and Claw and Wheeling Thrust 100 / 260 in combo, +40 from the rear / flank, Drakesbane 400, Wyrmwind
  Thrust 420; Stardiver 720, Nastrond 720 and Mirage Dive 380 (set by 7.1), Geirskogul 280;
- Chaotic Spring's DoT ticks for ~50 (tooltip 45: DoTs log above their tooltip, like the Black Mage's Thunder);
  auto-attacks 86 potency every 2.81 s;
- statuses come on with the cast, so Geirskogul's own hit doesn't get the Life of the Dragon it grants; Lance Charge
  and Battle Litany land 0.63 s after theirs;
- High Jump and Dragonfire Dive lock the player 0.87 s, Stardiver 1.58 s (so it is single-woven), Elusive Jump 0.96 s;
- Piercing Talon doesn't break a combo.

Every cast in our 309 pulls (24,001 casts, to each player's first death) replays as legal through the model, and in the
benchmark clears all but a second tincture. That replay went through `calibrate.replay` on records built from the same
caches; `calibrate.py --job drg` itself, the damage check by crit flag and `dps.py --job drg` need FFLogs' full logs.

- **Combos**: True Thrust -> Vorpal Thrust -> Heavens' Thrust -> Fang and Claw -> Drakesbane, and True Thrust ->
  Disembowel (Power Surge) -> Chaotic Spring (DoT) -> Wheeling Thrust -> Drakesbane. Drakesbane's Draconian Fire turns
  the next True Thrust into Raiden Thrust (one Firstminds' Focus; Wyrmwind Thrust spends two).
- **Crits**: Life Surge (a sure crit on the next weaponskill) and Battle Litany (+10% crit rate, which a sure crit gains
  as crit damage) count at their expected worth for `--crit`. The search spends Life Surge on Heavens' Thrust and
  Drakesbane (both 400). `dps.py` leaves the Life Surge hits out when it measures a player's crit gain (`sure_crits`).
- **DoT refresh**: the DoT is counted when applied, so an early Chaotic Spring refresh looks good for a while, and a
  narrow beam dropped the Vorpal chain before it caught up (1.3% lower over 2 minutes). The search offers Disembowel only
  when the DoT would be nearly out by the time its Chaotic Spring lands, or Power Surge is low.
- **Movement**: as for the Reaper. The melee weaponskills need reach; Piercing Talon, the jumps and the 15 y lines
  reach from anywhere. Out of reach, Elusive Jump buys an Enhanced Piercing Talon (350).

Over the whole phase the best rotation deals 126,632 potency in both `M1` and `M2` (all four settings agree); standing
still 127,736, so our strategy costs a Dragoon 0.9%: six True Norths for the pinned spots' positionals, and four
Piercing Talons (three enhanced) for the stretches out of reach. It alternates the two combos and puts Life Surge on
eight Drakesbanes and four Heavens' Thrusts. A search takes ~70 s.

## Red Mage

`jobs/rdm.py`, from the job guide and the patch notes since 7.0, with its level-90 values **measured in the scorecard's
cached damage events** as for the Dragoon (FFLogs was down): our groups' 267 pulls by five Red Mages (Sep-Oct 2026) and
the 18 benchmark clears with one. Enchanted Blade Mastery (level 94) raises nearly every potency in the guide; the patch
notes since 7.0 only change those level-94+ values and Manafication's durations (30 s since 7.05). Per player, each
action's plain-hit cluster with others' damage buffs and their own Embolden divided out, scaled to Jolt III (360, set at
level 84 and untouched since). At level 90 they are Endwalker's values:

- Jolt III 360, Verthunder / Veraero III 380, Verfire / Verstone 340, Verflare / Verholy 600, Scorch 680, Resolution
  750; Enchanted Riposte 280, Zwerchhau 150 / 340 in combo, Redoublement 130 / 500 (bonusPercent 74% = 370 / 500),
  Enchanted Reprise 340; Fleche 460, Contre Sixte 380, Engagement 180, Corps-a-corps 130; auto-attacks are negligible;
- Embolden adds 10% to the Red Mage's own magic damage (the enchanted combo included); Fleche, Contre Sixte,
  Corps-a-corps and Engagement are physical and get nothing. Its status lands 0.67 s after the cast;
- the enchanted combo's recasts are fixed at 1.5 / 1.5 / 2.2 s, even at a 2.23 s GCD; the 2 s spells resolve 1.47 s
  into the bar (0.52 s before its end, as for the Black Mage);
- an instant Verthunder / Veraero III spends Acceleration before Dualcast and Swiftcast, and Dualcast survives it (18 of
  18 casts); Dualcast goes before Swiftcast; a spell made instant never grants Dualcast; Sprint cancels Dualcast;
- Verthunder / Veraero III proc their colour 49.4% of the time (4,158 casts), 100% under Acceleration.

Every cast in our 267 pulls and the 18 clears (24,041 casts, to each player's first death) replays as legal through
`calibrate.replay`, on records built from the same caches; the hard casts' times match within 0.01 s. Nine GCDs start
"early" in the replay, all after a cancelled hard cast whose stale begin-cast the harness takes as the start. A control
with broken rules (Riposte costing 25, Jolt III giving 1 / 1 mana, Fleche on 27 s, Dualcast lasting 1 s) shows each as
illegal or early casts. `calibrate.py --job rdm`, `dps.py --job rdm` and `solve.py --compare` need FFLogs' full logs.

- **Dualcast loop**: a hard-cast 2 s spell grants Dualcast, so the 5 s Verthunder / Veraero III comes out instant.
  The search only offers the 5 s spells under Dualcast, Acceleration or Swiftcast.
- **Procs** are random: the search counts them at their expected worth (as the Bard's Repertoire). A Verthunder III
  raises the chance Verfire Ready is up by half of what is left (the part already up counts as overwritten), and
  "Verfire" means Verfire if it is up, else Verstone if that is, else Jolt III (all 2 s casts), at the mixture's
  potency and mana. A log replay knows the spell, so there a proc is only "possibly up" once granted. At level 90 the
  search never spends procs: Jolt III's 360 and 2 / 2 mana beat Verfire's 340 and 5. Forcing procs whenever one is
  likely up costs 0.4% standing still and 1.1% with our runs, though our Red Mages spend them on most hard casts.
- **Mana**: 0-100 of each colour; the melee combo costs 20 / 15 / 15 of each (nothing under Manafication's three
  Magicked Swordplay stacks) and gives the three Mana Stacks for Verflare / Verholy -> Scorch -> Resolution. Whether
  mana gains still halve past a 30-point imbalance can't be told from the logs (players pass 30 in 22 of ~10,000
  gains); the model leaves it out, and the searched rotations never pass 30 (27 at most).
- **Whole combos only**: whether Mana Stacks outlive a broken combo can't be told either (the replays are legal both
  ways), and 939 of 943 logged finishers follow one unbroken combo. The search starts a combo only with mana or
  Swordplay for all of it and no stacks left over; replays allow anything.
- **Reach**: the melee combo and Engagement need the player within 14 y of Athena's centre, the combo not under
  Manafication (25 y). A ranged player stands within that except at our plan's far spots (`p12s.FAR`: Paradeigma I's
  wall end, 18.3 y, and the Heavensflame corner of Superchain I, ~21.5 y), where they are out of reach around the
  snapshot (`away` windows: 1.4 s and 2.5 s).

Over the whole phase the best rotation deals 93,149 potency in `R1` and 92,056 in `R2` (width 1,000); standing still
93,613, so our strategy costs a Red Mage 0.5% in R1 and ~1.3% in R2. What is left is Paradeigma I's swap through the
middle (4.7 s of running in 5.3 s for R1, 4.4 s in 5.0 s for R2), when Manafication, Swiftcast and Acceleration are
still cooling down from the opener, so the rotation fills it with Enchanted Reprise.

- **Dashes** recover most of R1's: right after the bait (37.6 s) Corps-a-corps rushes from the wall to Athena's hitbox
  edge, saving 7.8 y (1.3 s) of the swap, room for a hard cast (+0.8% over the phase; the opener's charge is back by
  then without being held). R2 crosses the middle first and only then heads out, so Displacement (2.5 s saved) comes
  after the GCD it could have turned into a hard cast. With it and without, R2 scores within the search's noise
  (92,195 and 92,242 at width 3,000).
- **What didn't help**: a look-ahead at upcoming runs like the Black Mage's, and a value on dash charges kept for coming
  runs, never found a better rotation, so the ranking has neither.
- **A fix**: a combo that ran into a far spot (Superchain I's Heavensflame corner) used to break mid-way, and the stacks
  it left blocked every later combo (whole combos only) until the end of the phase. Combos now start only if their
  three hits stay clear of far spots, and left-over stacks get topped up.

The opener spends Manafication's free combo under Embolden, both Acceleration charges and Swiftcast on Verthunder III,
and the rotation makes 11 combos (four of them free) in the phase. The clears' own rotations, replayed standing still
over 0:00-380 s, deal 93-97% of the search's best (our pulls over 0:00-2:00: 91-95%). A search takes ~35 s.

What the logs couldn't settle, to be tested in game: [rdm-in-game-tests.md](rdm-in-game-tests.md).

## Viper

`jobs/vpr.py`, from the job guide and the patch notes since 7.0, checked like the Dragoon and Red Mage **in the
scorecard's cached damage events** (FFLogs was down): our groups' 249 pulls by six Vipers (Sep-Oct 2026) and the 24
benchmark clears with one. Unlike the other jobs, no Viper trait above level 90 raises a potency (Melee Mastery is level
74, Melee Mastery II 84), so the guide's numbers hold at level 90 as they stand; what level 90 lacks is Uncoiled
Twinfang and Twinblood (92), the fifth Anguine Tribute and Ouroboros (96) and the Legacies (100). Each action's plain-hit
cluster, Hunter's Instinct divided out and others' raid buffs left out, scaled to Death Rattle (280), matches the guide
within ~1%: Vicewinder 543 (540 since 7.5), the Coils 686 / 626 (680 / 630), Reawaken 758 (750), the Generations 680,
the bites 170, Uncoiled Fury 684 (680). Auto-attacks are 80 potency. FFLogs' bonusPercent tells the positionals apart:
a Coil's +50 shows as 7%, a finisher with its venom as 48% from the right side and 40% from the wrong one.

Rules from the logs the guide doesn't give:

- GCD recasts: the twinblade GCDs (Vicewinder, the Coils) 3.0 s, Uncoiled Fury 3.5 s, Reawaken 2.2 s, the Generations
  2.0 s, the rest 2.5 s, all scaled by skill speed and by Swiftscaled's 15%. The GCD that grants Swiftscaled isn't
  hasted by it. Vicewinder's 40 s and Serpent's Ire's 120 s are not scaled;
- statuses come on with the cast, after its hit: a Hunter's Sting doesn't get the Hunter's Instinct it grants. Hunter's
  Instinct and Swiftscaled are refreshed to 40 s (not extended), so both lapse over Palladion's 44 s;
- the Coils, Uncoiled Fury and the Generations don't break the dual-wield combo, and other GCDs don't end Vicewinder's
  Coils; Death Rattle and the bites are lost with the next weaponskill (no log uses one later);
- Reawaken grants four Anguine Tribute at level 90 (717 windows of four Generations, none of five); other GCDs may come
  inside Reawakened (two logs fit Uncoiled Fury in before the First Generation);
- Rattling Coils start at none: every first Uncoiled Fury follows a Vicewinder and Serpent's Ire.

Every cast in our 248 pulls (19,899 casts, to each player's first death) replays as legal through `calibrate.replay`,
and in the benchmark clears all but a second tincture; 6 GCDs start more than 0.15 s early in all. A control with
broken rules (Reawaken at 60 Offerings, Vicewinder on 45 s, Serpent's Ire on 125 s, three Tribute, Swiftscaled 10%,
Generations on 2.2 s) shows each as illegal or early casts; the first confirms the gauge (+10 a finisher, +5 a Coil).
`calibrate.py --job vpr` itself and `dps.py --job vpr` need FFLogs' full logs. Swiftscaled is up nearly all fight, so
`calibrate.gcd_of` takes the job's `HASTED` statuses' gaps divided by their haste and scales the gaps after the longer
GCDs (`GCD_BASE`) instead of leaving them out; our Vipers' unhasted GCDs come out at 2.43-2.49 s.

- **Dual-wield combo**: Steel or Reaving Fangs (the Honed one 300) -> Hunter's Sting (Hunter's Instinct, +10%) or
  Swiftskin's Sting (Swiftscaled) -> a flank or rear finisher, whose venom makes the next in the cycle Flanksting ->
  Hindsting -> Flanksbane -> Hindsbane 500 from its side. Each finisher gives Death Rattle and 10 Serpent Offerings.
- **Twinblade**: Vicewinder -> both Coils in either order (680 from the side), each followed by its two bites (170 in
  the right order); Uncoiled Fury (20 y) spends the Rattling Coils Vicewinder and Serpent's Ire grant. Reawaken spends 50
  Offerings or Serpent's Ire's Ready to Reawaken for four Generations at 680.
- **Search policy**: Death Rattle and the bites are always woven when they fit; under Reawakened only the next
  Generation is offered. Uncoiled Fury (~250 potency a second) about ties the filler (~275), and offering it at every
  step filled the beam with orderings of one rotation; it's offered at three Rattling Coils, out of reach or close to it,
  before downtime, near the window's end and under raid buffs. That alone took the best rotation at width 3,000 to width
  8,000's.
- **Ranking**: each held resource is valued at what it converts into, less the time its GCDs take, so spending it leaves
  the rank where it was; values 1.5 times those lose ~5% (the beam holds Coils and Offerings). Held values fade over
  the window's last 15 s: a state that never spent its last 50 Offerings otherwise ranked well to the end. Rates below
  the filler's own (~275 a second) make time look cheap and lose ~1.5%.
- **Movement**: as for the Reaper. Melee actions (3 y), and Death Rattle, the bites and Reawaken (5 y), need reach;
  Uncoiled Fury and Writhing Snap reach from anywhere.

Over the whole phase the best rotation deals 145,130 potency in both `M1` and `M2` (the six settings within 0.5%);
standing still 145,714, so our strategy costs a Viper 0.4%, within the search's noise and the least of the melee jobs.
Six True Norths cover all ten positionals in the fixed spots, and Uncoiled Fury and the twinblade GCDs' 3 s gaps cover
every stretch out of reach. It opens with Vicewinder, Serpent's Ire, both Coils and Reawaken on Ready to Reawaken, and
makes 12 Reawakens in the phase. The clears' own rotations, replayed standing still over 0:00-380 s, deal 90-96% of the
search's best (our pulls over 0:00-2:00: 92-99%). A search takes ~55 s.

## Samurai

`jobs/sam.py`, from the job guide and the patch notes since 7.0, checked like the Viper **in the scorecard's cached
damage events** (FFLogs was down): our groups' 199 pulls by four Samurais (Sep-Oct 2026) and the 12 benchmark clears
with one. Way of the Samurai III (level 94) raises most potencies in the guide, and Enhanced Hissatsu (94) halves
Senei's recast; Gyofu (92), Zanshin (96) and Tendo (100) lie above P12S. Each action's plain-hit cluster, Fugetsu divided
out and others' raid buffs left out, scaled to Hissatsu: Shinten (250, untouched by traits and patches); bonusPercent
confirms each split (Gekko 70% = (370 - 110) / 370 from the rear in combo). At level 90:

- Hakaze 200; Jinpu and Shifu 120 / 280 in combo; Gekko and Kasha 110 / 320 in combo, +50 from the rear / flank;
  Yukikaze 110 / 290; Higanbana 200 and ~50 a tick for 60 s; Shoha 560; Senei 800 on 120 s; auto-attacks 80;
- the sure crits have no plain hits. Midare Setsugekka's lowest cluster over each player's crit multiplier (Shinten's
  crit cluster over its plain one) is 620, and Kaeshi: Setsugekka matches it hit for hit. Ogi Namikiri and Kaeshi:
  Namikiri are only used under raid buffs, so they were measured against Midare in the same pull under the same buffs
  (a crit-rate buff raises every sure crit alike): 1.38 times, 860 (Endwalker's; the 7.2 notes' 900 -> 1,000 is level 94).

Rules from the logs the guide doesn't give:

- **Gekko and Kasha give 15 Kenki**, not the guide's 10: at 10, 246 Hissatsu casts in our pulls come up short, at 15
  two, and no other source (Hakaze, Jinpu / Shifu, Yukikaze, Shoha, out-of-combo steps) fits. Whether 5 of it needs the
  positional can't be told: 430 missed positionals never left a spender short. The model gives 15 flat;
- Iaijutsu and Ogi Namikiri cast in 1.3 s flat (begin -> cast 0.76 s at every skill speed, with Fuka or without): Fuka
  shortens the recast (2.40 s -> 2.09 s) and auto-attacks, not the cast;
- Iaijutsu, the Kaeshis, Ogi Namikiri and Enpi don't break the combo; Iaijutsu and Ogi Namikiri give Meditation, the
  Kaeshis don't (Shohas follow exactly three); Higanbana doesn't use up Tsubame-gaeshi Ready;
- every opener starts with a pre-pull Meikyo Shisui (Gekko or Kasha at 0 s without a Hakaze), pressed ~13 s ahead: its
  charge comes back at 42.2-42.7 s in the clears. A replay reads it from the log (its status ending before the first
  Meikyo cast; none means both charges were there);
- Tengentsu's 10 Kenki needs a hit within its 4 s. Our pulls' Foresights cluster on the raidwides and shared hits (On
  the Soul, Searing Radiance, Trinity of Souls, Superchain Burst, Dialogos, Ultima Blade, Palladion's shockwaves, Theos's
  Ultima): 18 times (`HITS`) where it paid off 70-100% of the times it was up. A replay takes the log's own Foresights;
- the clears Meditate at the end of Palladion, standing until Athena returns: each 3 s tick gives a Meditation stack
  (their Shohas right after need exactly the ticks their Meditate status lasted). Its Kenki (10 a tick) is the in-game
  value: the logs can't confirm it.

Every cast in our 199 pulls but one (15,101 casts, to each player's first death) replays as legal through
`calibrate.replay`, and in the benchmark clears all but a Midare and a second tincture. A control with broken rules
(Gekko / Kasha at 10 Kenki, Shinten at 30, Senei on 125 s, Meikyo on 60 s or lasting 15 s, Ikishoten on 125 s) shows
each as illegal casts. `calibrate.py --job sam` and `dps.py --job sam` need FFLogs' full logs.

- **Sen and Iaijutsu**: Gekko (Getsu), Kasha (Ka) and Yukikaze (Setsu) end the three combos; three Sen make Midare
  Setsugekka (then Kaeshi: Setsugekka), one Higanbana. Meikyo Shisui's three stacks make any finisher count as a combo.
  The search offers Midare at three Sen unless a Kaeshi is pending (it would be lost), Higanbana at one Sen when the DoT
  is nearly out, and a combo's middle step only for a missing Sen or a buff running low.
- **Sure crits**: Midare, the Kaeshis and Ogi Namikiri always crit, a large share of the job's damage. The search
  weighs their potency by a sure crit's gain over an average hit (1.39 at 25% crit, x1.60), so trading them against
  other hits is fair; the potency printed stays plain potency, and `dps.py` converts the sure crits at the player's own
  average sure crit (`AUTO_CRIT`, as for Monk's Bootshine).
- **Downtime**: while Athena is away the search takes one step: Tengentsu on the hits it can catch, then Meditate for
  0-5 ticks ending as she returns, standing between the runs. The ranking charges time (potency a second), so separate
  steps made a 3 s Meditate look better than a 15 s one.
- **Ranking**: as for the Viper, each held resource is valued at what it converts into less the GCD time it takes
  (Tsubame-gaeshi Ready its Kaeshi over a 2.09 s GCD, not the whole hit: valued whole, the beam held a Kaeshi for 16 s
  and overwrote Sen meanwhile; fixing that and the Midare policy above gained 2.6% over two minutes).
- **Movement**: as for the Reaper. Every weaponskill, Iaijutsu and Hissatsu needs reach, only Enpi (20 y) reaches from
  anywhere; Hissatsu: Yaten buys an Enhanced Enpi. Iaijutsu, Kaeshi: Setsugekka, Ogi Namikiri and Shoha reach 6-10 y,
  so a Samurai might use them a little farther out than the 3 y actions; the clears' Reapers' positions can't tell how
  far out they stood (they cast nothing then), so the model takes the strict rule.

Over the whole phase the best rotation deals 133,863 potency in both `M1` and `M2` (148,419 with the sure crits at their
expected worth; the six settings within 0.5%); standing still 134,948 (149,505), so our strategy costs a Samurai ~0.7%.
Searched one part at a time, the runs and the fixed spots cost nothing (the 1.3 s Iaijutsu fit around the runs; four
True Norths take all seven positionals in the fixed spots) and the stretches out of reach ~0.5%: Enpi fills them. If
the 6-10 y actions reached out there, the phase would come to 148,882 (+0.3%). It opens with Kasha, Ikishoten, Gekko,
Senei, Yukikaze, Meikyo Shisui, Midare, Higanbana, Ogi Namikiri, Shoha and Kaeshi: Namikiri, lets Higanbana run out
before Palladion rather than refresh it into the downtime, and spends Palladion on a Tengentsu and a 15 s Meditate.
The clears' own rotations, replayed standing still over 0:00-380 s, deal 90-95% of the search's best (our pulls over
0:00-2:00: 91-94%). A search takes ~2 minutes.

## Pictomancer

`jobs/pct.py`, from the job guide and the patch notes since 7.0, checked against our groups' logs: the scorecard's
cached events (~200 pulls by three Pictomancers, Sep-Oct 2026) and the full FFLogs logs of our 27 clean pulls and the
benchmark clears with one (three; two since 7.3); the measuring scripts are in `scratch/pct/`. Pictomancy Mastery IV
(level 94) raises most potencies in the guide, and Rainbow Drip (92), the Claw / Maw motifs, a third Living Muse charge
and Retribution of the Madeen (96) and Star Prism (100) lie above P12S. The guide's level-84 trait gives the level-90
values, as the 7.2 and 7.3 notes left them, and the logs' plain hits (own Starry Muse and others' buffs divided out,
scaled to Pom Muse, 800) match within ~2%:

- Fire / Aero / Water in Blue 420 / 460 / 500, Blizzard / Stone / Thunder in Magenta 750 / 790 / 830, Holy in White 500,
  Comet in Black 830, Pom and Winged Muse 800, Mog of the Ages 1,000; the hammers (always critical direct hits) 540 /
  560 / 580, from 7.3's base values for Brush and Polishing Hammer (no level-84 step);
- Living Muse has two charges at level 90, Striking Muse two; every canvas is painted at the pull (7.1).

Rules from the logs the guide doesn't give:

- **Inspiration** takes 25% off the cast and recast of the six colour spells and of Holy and Comet (Comet's 3.3 s too),
  and each of those takes a Hyperphantasia stack; the hammers and motifs take neither. It comes on 0.58 s after Starry
  Muse and ends when the stacks run out or the landscape does (~22 s);
- **the landscape** is a circle of ~8 y around where Starry Muse was cast: players keep Inspiration at up to 8.4 y from
  it and lose it from 6.5 y (positions on casts in the full logs, blurred by the 3 s tick). Our runs longer than that
  take the player out (`LANDSCAPE`); Superchain I's 15 y run into the second doughnut is where our Pictomancers and the
  benchmark ones lose it;
- motifs cast in a fixed 3.0 s on a fixed 4.0 s recast, whatever the spell speed or Inspiration;
- the Aetherhues step is shared: after Fire in Red, Subtractive Palette opens Stone in Yellow. Aetherhues lapses after
  30 s; Subtractive Palette's stacks and Monochrome Tones stay until spent. Subtractive Spectrum is spent before gauge;
- MP never binds (2,000 at the lowest), so the model leaves it out.

Every cast in our 27 clean pulls (to each player's first death) and in the clears' whole pulls replays as legal
(`calibrate.py --job pct [--ours]`); cast times match within 0.04 s. A log replay has no movement, so it takes every
Starry Muse window as spent in the landscape: the 8 GCDs that start "early" all follow a player leaving it. A control
with broken rules (Living Muse on 45 s, Striking Muse on 65 s, Starry Muse on 125 s, motifs on 4.4 s, four Hyperphantasia
stacks, a 10% Inspiration, Hammer Time or Aetherhues on 20 s, three White Paint) shows each as illegal or early casts
(`scratch/pct/tamper.py`); Mog of the Ages on 35 s doesn't, as Winged Muse gates it every ~40 s anyway.

- **Loop**: Fire -> Aero -> Water in Blue (25 gauge, a White Paint for Holy), Subtractive Palette (50 gauge) for Blizzard
  -> Stone -> Thunder in Magenta (a paint) and Monochrome Tones, under which a paint goes to Comet in Black instead. The
  canvases are painted by motifs and rendered by Pom / Winged Muse (Winged paints the Moogle Portrait for Mog of the
  Ages), Striking Muse (three hammers) and Starry Muse (+5% for 20.5 s on the Pictomancer, Subtractive Spectrum, five
  Hyperphantasia). Motifs need no target, so Palladion repaints them.
- **Hammers**: their potency counts plain in the printed potency; the search weighs them at a sure critical direct
  hit's gain over an average hit (`SURE_W`, x1.62 at 25% crit and 30% direct hit) and `dps.py` converts them at each
  player's own (`AUTO_CRIT`, as Samurai's sure crits).
- **Ranking**: as for the Viper, each held resource at what it converts into less the GCD time it takes. Two additions:
  a canvas or the Moogle Portrait counts only if what renders it is back before the window ends (without it the search
  painted a starry sky it could never use over a Comet, and polish found 0.9-1.5% at the end), and a cooldown sitting
  at full charges is charged twice its share of a use for each second (`CAPPED`: Living Muse was left full for ~30 s
  after the opener; 1.5-2 times the share did best, +0.2-0.6%).
- **Movement**: hard casts as for the Black Mage; most GCDs are 1.5 s casts on a 2.45 s recast or instants, so a
  standing-still rotation happens to fit all our runs. What running costs is mostly Inspiration lost in the landscape.
  **Smudge** dashes 15 y along whatever run is open (any direction: the player faces the way they dash) and banks
  that running; its 5 s of faster running is left out. It ties with no Smudge (the search uses it once, in Paradeigma
  I's swap).

Over the whole phase the best rotation deals 93,782 potency in `R1` (103,194 with the hammers at their expected worth)
and 93,146 in `R2` (102,558); standing still 94,243 (103,725), so our strategy costs a Pictomancer ~0.5% in R1 and up
to ~1% in R2, about half of it Inspiration lost in Superchain I's runs (102,936 if the landscape were never left). It
opens with Striking Muse, Starry Muse, Pom Muse, Wing Motif and Winged Muse into the inspired subtractive burst, covers
Paradeigma I's runs with hammers and Holy, renders Living Muse 13 times (all its charges allow) and repaints the
canvases in Palladion. The search's settings come from `tune.py` (values at 0.45-0.65 of the guesses); the sweep holds
within 0.1% from width 1,000 to 3,000, the beam drops with width. A search takes ~30 s.

## The fight

`p12s.py` holds P12S P1 as the optimizer plays it; `p12s_p1.json` is built from six benchmark clears (`--build`).

- **Timeline**: every boss cast lands within ~0.2 s of its median from pull to pull, so it is fixed. Athena can't be
  hit from 281.6 s to 325.9 s (Palladion): nothing can be cast at her and DoTs don't tick (the clears log no hits).
- **Running**: each run is a window (from a cue plus 1 s to react, to when its mechanic snapshots) and a distance in
  yalms at 6 yalms a second. The player has to spend that long somewhere in the window not hard-casting: instants,
  weaves, the last 0.46 s of a cast and the caster tax all count, split however the rotation likes. A run takes the
  player out of Ley Lines (the search runs as late as it can, so they keep it while the rest of the run still fits);
  Between the Lines brings them back once the mechanic is done.
- **Paradeigma I, II, III and Superchain Theory I** follow our raidplan (Syncademy P12S P1) and the trainer's
  geometry for it, measured from Athena's centre, where Black Mages stand between mechanics. Paradeigma I depends on
  the slot; the others on a random assignment, where the default is the variant with the most running, since the
  rotation is planned before the assignment shows.
- **Everything else** (Trinity of Souls, Dialogos, Glaukopis, and from Palladion to the end) takes its running from
  the benchmark clears' Black Mages: the median path they ran in each window, from their position at every cast. From
  Palladion on that is marked provisional: our strategy there may still change.
- **Far spots**: a ranged player stands within a melee action's reach of Athena (14 y from her centre) everywhere but
  Paradeigma I's wall end and Superchain I's Heavensflame corner (`FAR`); a ranged job with melee actions (Red Mage)
  is out of reach around those snapshots (`far`).
- **Dashes**: where a run of our plan goes straight to or from Athena (`DASH`: Paradeigma I and II), the run carries
  that stretch (`engine.Move.dash`), and a dash along it saves its running (`engine.dash`): a gap closer down to her
  hitbox edge (`ATHENA_EDGE`, 10.5 y: every Red Mage's Corps-a-corps from 11-19 y out lands there in our pulls), a
  backstep from beside her its length (a shorter stretch it overshoots, and the walk back counts). Free time already in
  the window counts as run along the path first. Superchain I's paths depend on the spheres' layout and Paradeigma
  III's floor falls, so they have none; the clears' windows have no geometry.

`python tools/rotation/p12s.py` lists every window with its source and compares our plan's distances with what the
clears ran (within about ±30%: ours runs more in Paradeigma I-III, less in Superchain I).

## The search

A beam search, one GCD per step with the oGCDs woven before it, whose states compete with those at the same time
(`engine.sweep`: 0.5 s layers, 0.25 s for BLM) rather than with those after as many GCDs (`engine.beam`, before
2026-10-22): a state that spent its time on long casts no longer has to be weighed against one that didn't by a guessed
potency per second. It ranks states by damage so far, plus a guess at
what the resources they hold are worth, minus the time used, minus the running in the next 25 s that their instants
won't cover. That last term counts what a held Triplecast or Swiftcast charge is worth before a run: hard casts leave
~40% of a window free anyway, each instant in hand (Triplecast stacks and charges, Swiftcast, Polyglot, Paradox,
Firestarter, Thunderhead) frees ~1.4 s more, and whatever is left has to be stood idle.

Over a whole phase the result moves by ~1% with these guesses and no single setting is best (the running term helps
under some settings and costs under others), so `solve.py` runs eight settings in parallel, four tunings each with
and without the running term (about 70 s), and keeps the best rotation. Differences between scenarios below ~0.4%
are within that noise: R2, which runs less than R1, comes out 0.35% lower.

`polish.py` then improves that rotation by local search, scoring each edit over the whole fight: another legal
choice in one step's place, two neighbouring GCDs swapped, an oGCD moved up to three steps, a step dropped. It works
on any job through its `expand`, takes 1-60 s, and found 0-0.7% more (2026-10-22). `--layers gcd` and `--no-polish`
bring back the earlier search.

The best clear's own rotation, replayed at the same 2.32 s GCD with its own movement (`--compare`), deals 101,033:
0.3% below the search's best under our (heavier) strategy, 0.6% below its best standing still.

## From potency to DPS

`dps.py` converts per player, from their clean pulls (alive through 2:00) on the job:

- **damage per potency**: their plain hits (no crit, no direct hit) with others' buffs divided out, over the model's potency;
- **crit and direct hit**: their average hit over their plain hit, action by action, weighted by hits. Over all hits
  for the replay check, since the log's hits carry others' crit and direct-hit buffs; over the hits under none of those
  buffs (Battle Voice, Battle Litany, Chain Stratagem, Devilment, the Wanderer's Minuet, Army's Paeon) for the ceiling,
  since rDPS credits them to whoever gave them. That takes 1.5-4.5% off the ceilings compared with all hits; the earlier
  formula from the crit rate (crit damage 1.35 + crit rate) overshot by up to 3% when others' buffs raised the rate;
- **DoT ticks**: FFLogs reports ticks without crit flags, so they count at the player's average tick;
- **GCD**: their unhasted GCD from back-to-back casts.

FFLogs' multiplier on a hit holds every damage-up on it, the player's own included: a Reaper's Death's Design and their
own Arcane Circle are put back (the job's `own_factor`) when the logged damage is compared.

Check: each pull's logged casts, replayed through the model and converted, land within ~1.5% of the damage the pull
logged for Black Mages, and within -2% to +4% for Reapers (the replay takes every positional). The ceiling is the best
rotation *without* raid buffs, at the player's GCD, over 0:00-2:00 like the scorecard's window, and the same for every
pull. It plays our strategy's runs at their worst for the role (`p12s.worst_slot`): the Paradeigma I slot with the most
running before 2:00 (R1 of R1 / R2 for ranged, M2 of M1 / M2 for melee) and each mechanic's variant with the most (the
default), so it holds whichever the player is given. FFLogs' rDPS credits a buff's gain to the job that gave it, so a job without raid buffs gets no
rDPS from alignment, and the unbuffed optimum is its rDPS ceiling. A job with one (Reaper's Arcane Circle) also gets
credit for what its buff added to the others' damage; the scorecard site adds each pull's own credit (FFLogs'
totalRDPSGiven) to the ceiling, pull by pull. `dps.py --job <job> --site` saves the ceilings for it
(`.cache/ceilings.json`, git-ignored: it names players) and, for the site's Rotations pages, one rotation per GCD (and
crit rate, for Monk) in `.cache/rotations.json`; `--gcds 2.30,2.40` adds GCDs none of our players has. Those run on from
the pull until Palladion takes Athena away (`ROT_UNTIL`, 4:41): a second search per GCD, since the engine scores a
whole window and the 0:00-2:00 optimum spends what a longer rotation would hold. Each keeps its 0:00-2:00 ceiling too.
Each rotation's runs are placed for the site (`placed_runs`): the search only checks that a window has the running time
it needs outside cast bars, so they go in its longest stretches outside cast bars first, as late as they allow, and
each GCD carries the running that falls before the next one.
There a rotation's expected DPS is the median of our players' conversions on the job, each player moved to its GCD
first (`SPEED_PTS`, `STAT_PT`): the speed points a faster GCD takes come out of critical hit, direct hit or
determination, 58.5 points and about 0.40% damage per potency per 0.01 s at the level-90 formulas (our Black Mages'
conversions fall 0.38% per 0.01 s of GCD), and DoT ticks gain as much per point as the GCD shortens. Without it a
2.18 s GCD read 10% ahead of 2.45 s for a Black Mage; with it every GCD from 2.18 s to 2.45 s comes out within 0.7%
(the search's noise), and for a Reaper 2.49 s leads 2.41 s by 1.2%. Not modelled: whether Skill Speed also raises a
melee's auto-attacks.

`--offline` takes our players' pulls from the scorecard's acts caches instead of FFLogs (`logs.ours_offline`, for
when FFLogs is down; Dragoon, Red Mage, Viper and Samurai went on the site this way on 2026-10-22, and were rerun from
the full logs the same day once FFLogs was back: ceilings moved -4.6% to +6.4%, most within 2%). Those have no crit
or direct-hit flags, no FFLogs multiplier and no record of others' buffs on a hit, so `logs.from_acts` leaves out the
hits under others' raid buffs (`acts.buff_uses`, 20 s each) and in tinctures, takes the player's own damage-ups from
their own statuses (the job's `own_factor`, which reads the same status ids), and `flag_hits` reads crit and direct hit
from the size of each hit against its plain level: hits of one action and bonusPercent at one model potency form a
group, and its plain level is the median of the hits within 13% of its lowest tenth; above it by 1.12, 1.37 and 1.73
a hit is a direct hit, a crit, and both (`PLAIN`, `DH`, `CRIT`). A target debuff (Reaper's Death's Design) can't be
divided out this way. Against the full logs, on Black Mage (`scratch/offline/measure.py blm`): the GCD comes out the
same for all seven players, damage per potency within 0.5% for six of them, crit gain within 2.2%, so the conversion
reads 0-3% higher (about 1% at the median; one player 3%, likely a Dancer partner or Astrologian card the caches can't
show). The replay check against the scorecard's rDPS gives the same picture: 0.97-1.00 offline, 1.00-1.02 from the full
logs. 'logged' in the printed table misses the hits left out. The site says which jobs were converted this way; a
rerun without `--offline` clears the note.

## How the job model was checked

`logs.py` fetches each clear's casts (with begin-casts, MP and position), hits (with the buffs on them) and the
player's own statuses. `calibrate.py` replays every logged cast through the model at its logged time, over the whole
pull up to the player's first death (2 of the 11 logs end at a death late in the pull):

- every cast in the 11 Black Mage logs since patch 7.2 is legal, except a second tincture (the model allows one);
- cast times match within 0.02 s, each log replayed at its player's own GCD (2.14 to 2.45 s). A spell resolves (its
  logged cast event: damage, gauge, MP) 0.52 s before its cast bar ends, for every cast length in and out of Ley
  Lines; the player may move for the last 0.46 s (the slidecast), so the two are kept apart;
- each spell's plain hits (no crit, no direct hit, buffs divided out) match the model's potency within ~2-3%;
- MP matches the logged snapshots in 1,846 of 1,911 casts (most of the rest are snapshots FFLogs takes just before a
  refill shows).

Rules come from the official job guide's tooltips, which show level-100 values (an instant Despair, a 40 s Swiftcast),
so the level-90 ones are taken from the logs where they differ. The kit changed in 7.2 (its patch notes, from
`patchnotes.py`), so only clears since April 2025 are used. Of its changes, ones a reading of the guide alone could miss:

- Fire IV, Despair and Blizzard IV cast in 2.0 s, and Ley Lines lasts 20 s;
- Thunderhead and Firestarter no longer expire; they are only lost by being granted again while held;
- Fire III and Blizzard III deal 290 potency (280 before).

Two rules come from the logs alone, as the full-pull replays need them: a hard-cast Fire III from Umbral Ice III costs
no MP (4 of 4 such casts), and the Polyglot timer starts when the first fire or ice spell lands, not when it resolves
(only a 1.0-1.5 s lag makes every Xenoglossy legal; Fire III's flight is 1.29 s).

`check.py` tests the movement accounting on hand-made windows, then replays quick searches for both slots and every
variant from their history: each window gets its running time outside cast bars, and nothing is cast at Athena while
she is away. A standing-still rotation, as a control, breaks several windows. For the Reaper it also tests the reach
rule and positionals on hand-made windows, and replays quick M1 and M2 searches: every away window must hold a stretch
of its length without a melee action (the standing-still rotation breaks one); the same for Monk, Dragoon, Viper and
Samurai (whose Iaijutsu are hard casts the runs must leave room for, and whose Meditate counts as standing). For the
Bard it tests Repertoire under each song and Army's Muse on hand-made states, and that quick R1 and R2 searches cast
nothing at Athena while she is away and score the same as standing still. For the Red Mage it tests Dualcast,
Acceleration's priority, the expected procs and reach at a far spot (with and without Manafication) on hand-made states,
and replays quick R1 and R2 searches like the Black Mage's, plus no melee action at a far spot without Manafication.
Dashes: Corps-a-corps waits for its run to open and saves the stretch, saves nothing once the free time has covered it,
and waits at a far spot for the snapshot; Displacement only once the path before its stretch is behind, and overshooting
a short stretch; in the searches no dash saves more than its stretch allows, and the replay counts what they saved. For the
Pictomancer it tests Inspiration's haste and stacks, the landscape after a 15 y and a 6 y run, the shared Aetherhues step,
Monochrome Tones, motifs while Athena is away and the capped muse charges on hand-made states, and replays quick R1 and
R2 searches like the Black Mage's, plus no inspired GCD after a run past the landscape since Starry Muse. Its controls
differ (a standing-still Pictomancer rotation fits our runs): the R1 rotation against the same runs at twice their
length, and the standing-still one against R1's landscape.

## Files

| File | Role |
|---|---|
| `engine.py` | timing (GCD, casts, slidecast, weaving), raid buffs, move windows and the dashes along them, downtime, beam search |
| `jobs/blm.py` | Black Mage: gauge, MP, procs, cooldowns, potencies, Ley Lines' circle |
| `jobs/rpr.py` | Reaper: Soul and Shroud gauges, Enshroud, combos, positionals, Death's Design, auto-attacks |
| `jobs/mnk.py` | Monk: forms, Fury, Perfect Balance, beast chakra and Nadi, chakra, positionals, auto-attacks |
| `jobs/brd.py` | Bard: songs, Repertoire, Soul Voice, Coda and Radiant Finale, Army's Muse, DoTs, Hawk's Eye, auto-attacks |
| `jobs/drg.py` | Dragoon: the two combos, Draconian Fire and Focus, Life of the Dragon, jumps, Life Surge, DoT, positionals, auto-attacks |
| `jobs/rdm.py` | Red Mage: Dualcast, mana, the melee combo and finishers, Manafication, Acceleration, expected procs, reach at far spots |
| `jobs/vpr.py` | Viper: the dual-wield combo, Honed and venoms, Vicewinder's Coils and bites, Rattling Coils, Serpent Offerings, Reawaken, Swiftscaled haste, positionals, auto-attacks |
| `jobs/pct.py` | Pictomancer: the colour loop and Aetherhues, Palette Gauge and Subtractive Palette, White Paint, Monochrome Tones and Comet, the canvases and motifs, Living / Striking / Starry Muse, Mog of the Ages, hammers, Inspiration and Hyperphantasia in Starry Muse's landscape, Smudge |
| `jobs/sam.py` | Samurai: the three combos, Sen and Iaijutsu, Tsubame-gaeshi, Meikyo Shisui, Kenki, Meditation and Shoha, Ogi Namikiri, Fugetsu and Fuka, Higanbana's DoT, Tengentsu on the fight's hits, Meditate in downtime, positionals, auto-attacks |
| `p12s.py`, `p12s_p1.json` | the fight: timeline, downtime, our strategy's runs, the clears' runs elsewhere |
| `solve.py` | command line |
| `logs.py` | detailed per-player logs from the benchmark clears, cached in `.cache/` |
| `calibrate.py` | replays logs through a job model and reports where they disagree |
| `check.py` | movement and downtime checks |
| `dps.py` | potency to DPS per player; ceiling next to the scorecard's rDPS |
| `patchnotes.py` | a job's PvE action changes from the official patch notes, patch by patch (level-100 values, like the job guide) |
