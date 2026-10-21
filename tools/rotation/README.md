# Rotation optimizer

Searches for the highest-potency rotation of a job over P12S phase 1 (level 90), from the pull to the kill, with the
fight's fixed timeline: when Athena can't be hit, and where the player has to run under our groups' strategy. So far:
Black Mage, Reaper, Monk, Bard and Dragoon (Monk and Bard not yet checked against logs, Dragoon only against the
scorecard's cached events: see their sections).

```
python tools/rotation/solve.py                                # R1, 2.32 s GCD, no raid buffs, 0:00 to the median kill (449 s)
python tools/rotation/solve.py --slot R2 --var para2=debuff --var para3=cross
python tools/rotation/solve.py --still                        # no forced movement: what running costs
python tools/rotation/solve.py --gcd 2.14 --party RPR,SCH,RDM --until 120 --compare
python tools/rotation/solve.py --job rpr [--slot M2]          # Reaper, 2.49 s GCD, M1 by default
python tools/rotation/solve.py --job mnk [--crit 0.25]        # Monk, a 1.94 s GCD (2.43 s before Greased Lightning)
python tools/rotation/solve.py --job brd                      # Bard, 2.49 s GCD, R1 (R2 and standing still come out the same)
python tools/rotation/solve.py --job drg [--slot M2]          # Dragoon, 2.49 s GCD, M1 by default
python tools/rotation/p12s.py [--slot R2]                     # the move windows; --build refetches the timeline
python tools/rotation/check.py                                # movement and downtime checks
python tools/rotation/calibrate.py [--job rpr] [--ours]       # check the job model against the clears' (or our) logs
python tools/rotation/patchnotes.py Reaper                    # the job's PvE changes in the official patch notes
python tools/rotation/dps.py                                  # our players: ceiling in DPS next to their scorecard rDPS
python tools/rotation/dps.py --job rpr --site [--gcds 2.40]   # ...and save ceilings and rotations for the scorecard site
```

| Option | Meaning |
|---|---|
| `--job` | `blm` (default), `rpr`, `mnk`, `brd` or `drg` |
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
| `--width` | beam width per heuristic setting (default: the job's, 1,000 for BLM, 3,000 for RPR, MNK, BRD and DRG) |
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

`jobs/mnk.py`, from the job guide and the patch notes since 7.0 only: **not yet checked against any log** (FFLogs was
down when it was written; `calibrate.py --job mnk [--ours]` fetches them: 19 benchmark clears have a Monk, our groups
64 clean pulls). The guide's traits give most level-90 values: Melee Mastery (84) sets Bootshine 220, True Strike 300,
Snap Punch 270, Twin Snakes 380, Demolish 320, Dragon Kick 280 and The Forbidden Chakra 400 (the reference action);
Melee Mastery II (94) and the level-92 upgrades (Leaping Opo, Rising Raptor, Pouncing Coeurl, Elixir Burst) lie above
P12S. No single-target potency has changed since 7.05, so every Dawntrail clear will do. Marked PENDING in the code,
to be measured: Phantom Rush (1,150 assumed) and Six-sided Star (710) at level 90, auto-attacks (77 potency every
2.05 s), the default GCD (1.94 s), the party's chakra under Meditative Brotherhood, and whether Perfect Balance and
Formless Fist count as opo-opo form for Bootshine's sure crit and Dragon Kick's Fury.

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

Over the whole phase the best rotation deals 131,432 potency in `M1` and 131,825 in `M2` (equal within the search's
noise: the settings spread up to 1.2% in `M2`); standing still 134,306, so our strategy costs a Monk ~2%: the
pinned spots' positionals take 11 True Norths, and the away stretches can't be filled. Six-sided Star is only offered
before Palladion and at the end of the window: elsewhere its assumed potency about ties the rotation per second, and
the search drifted into chaining it.

## Bard

`jobs/brd.py`, from the job guide and the patch notes since 7.0 only: **not yet checked against any log** (FFLogs was
down when it was written). No benchmark clear has a Bard, so `calibrate.py --job brd --ours` (our groups' 62 clean pulls,
four players) is the only check, and `solve.py --compare` has nothing to replay. Since 7.0 the patch notes only touch AoE
potencies and actions above level 90 (Resonant Arrow 96, Radiant Encore 100). But Ranged Mastery (level 94) raises
Burst Shot, Refulgent Arrow, Empyreal Arrow, Sidewinder and Apex Arrow to the guide's values, and the guide doesn't
say from what. Marked PENDING in the code, to be measured: those five (assumed 200, 260, 240, 360 and 6 per Soul Voice),
the DoT ticks (the tooltips' 20 and 25), auto-attacks (80 potency per 3.04 s), the default GCD (2.49 s), the logs'
spelling of the Minuet and the status ids `own_factor` reads. Bloodletter (130, the reference action), Pitch Perfect,
the bites, Iron Jaws and Blast Arrow (700) are the guide's: no trait touches them.

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

Over the whole phase the best rotation deals 87,790 potency (at width 3,000: the settings spread 0.5%, and width 1,000
finds 0.3% less). It keeps the 2-minute burst on the Minuet (Raging Strikes, Battle Voice, Barrage, Radiant Finale at
three Coda), refreshes Iron Jaws under it, and fires Blast Arrow after every Apex Arrow at 80+. It sings Minuet ->
Paeon -> Ballad, not the usual Minuet -> Ballad -> Paeon. That may come from the guessed values, so check it again once
they are measured.

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

`python tools/rotation/p12s.py` lists every window with its source and compares our plan's distances with what the
clears ran (within about ±30%: ours runs more in Paradeigma I-III, less in Superchain I).

## The search

A beam search, one GCD per step with the oGCDs woven before it. It ranks states by damage so far, plus a guess at
what the resources they hold are worth, minus the time used, minus the running in the next 25 s that their instants
won't cover. That last term counts what a held Triplecast or Swiftcast charge is worth before a run: hard casts leave
~40% of a window free anyway, each instant in hand (Triplecast stacks and charges, Swiftcast, Polyglot, Paradox,
Firestarter, Thunderhead) frees ~1.4 s more, and whatever is left has to be stood idle.

Over a whole phase the result moves by ~1% with these guesses and no single setting is best (the running term helps
under some settings and costs under others), so `solve.py` runs eight settings in parallel, four tunings each with
and without the running term (about 70 s), and keeps the best rotation. Differences between scenarios below ~0.4%
are within that noise: R2, which runs less than R1, comes out 0.35% lower.

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
There a rotation's expected DPS is at the median of our players' conversions on the job, so GCDs compare.

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
of its length without a melee action (the standing-still rotation breaks one); the same for Monk and Dragoon. For the
Bard it tests Repertoire under each song and Army's Muse on hand-made states, and that quick R1 and R2 searches cast
nothing at Athena while she is away and score the same as standing still.

## Files

| File | Role |
|---|---|
| `engine.py` | timing (GCD, casts, slidecast, weaving), raid buffs, move windows, downtime, beam search |
| `jobs/blm.py` | Black Mage: gauge, MP, procs, cooldowns, potencies, Ley Lines' circle |
| `jobs/rpr.py` | Reaper: Soul and Shroud gauges, Enshroud, combos, positionals, Death's Design, auto-attacks |
| `jobs/mnk.py` | Monk: forms, Fury, Perfect Balance, beast chakra and Nadi, chakra, positionals, auto-attacks |
| `jobs/brd.py` | Bard: songs, Repertoire, Soul Voice, Coda and Radiant Finale, Army's Muse, DoTs, Hawk's Eye, auto-attacks |
| `jobs/drg.py` | Dragoon: the two combos, Draconian Fire and Focus, Life of the Dragon, jumps, Life Surge, DoT, positionals, auto-attacks |
| `p12s.py`, `p12s_p1.json` | the fight: timeline, downtime, our strategy's runs, the clears' runs elsewhere |
| `solve.py` | command line |
| `logs.py` | detailed per-player logs from the benchmark clears, cached in `.cache/` |
| `calibrate.py` | replays logs through a job model and reports where they disagree |
| `check.py` | movement and downtime checks |
| `dps.py` | potency to DPS per player; ceiling next to the scorecard's rDPS |
| `patchnotes.py` | a job's PvE action changes from the official patch notes, patch by patch (level-100 values, like the job guide) |
