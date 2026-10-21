# Rotation optimizer

Searches for the highest-potency rotation of a job over P12S phase 1 (level 90), from the pull to the kill, with the
fight's fixed timeline: when Athena can't be hit, and where the player has to run under our groups' strategy. So far:
Black Mage.

```
python tools/rotation/solve.py                                # R1, 2.32 s GCD, no raid buffs, 0:00 to the median kill (449 s)
python tools/rotation/solve.py --slot R2 --var para2=debuff --var para3=cross
python tools/rotation/solve.py --still                        # no forced movement: what running costs
python tools/rotation/solve.py --gcd 2.14 --party RPR,SCH,RDM --until 120 --compare
python tools/rotation/p12s.py [--slot R2]                     # the move windows; --build refetches the timeline
python tools/rotation/check.py                                # movement and downtime checks
python tools/rotation/calibrate.py                            # check the job model against the clears' logs
python tools/rotation/dps.py                                  # our players: ceiling in DPS next to their scorecard rDPS
```

| Option | Meaning |
|---|---|
| `--gcd` | the player's GCD without haste (spell speed); `--compare` prints each clear's |
| `--slot` | Paradeigma I: `R1` lines up for the first lasers, `R2` for the second (our groups' BLMs play both) |
| `--var` | a mechanic's variant: `para2=tether/debuff`, `sc1=spread/laser`, `para3=straight/cross`; default: the one with the most running |
| `--still` | no forced movement |
| `--party` | jobs whose raid buffs are present (default none: the job's own potency); they land at the median times of the benchmark clears |
| `--move` | extra windows in which nothing may be hard-cast (the last 0.46 s of a cast can be slid) |
| `--pot` | allow one tincture (off by default: the scorecard strips tinctures) |
| `--carry` | also value resources still held at the end, instead of dumping everything |
| `--until` | end of the scored window, seconds (default: the clears' median kill, 449 s; enrage is 458 s) |
| `--width` | beam width per heuristic setting (default 1,000) |
| `--compare` | replay every benchmark clear's logged rotation under the same buffs, downtime and window |

Damage is in potency (Xenoglossy 890) times the raid buffs active when each hit lands; crit and direct-hit buffs count
at their expected value. Over the whole phase (R1, no buffs) the best rotation found deals 101,361 potency; standing
still it would be 101,596, so our strategy's ~59 s of running costs about 0.2%: the rotation covers nearly all of it
with instants, slidecasts and weaves.

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
- **crit and direct hit**: the share of their hits that crit / direct-hit; crit damage is 1.35 + crit rate (same stat);
- **DoT ticks**: FFLogs reports ticks without crit flags, so they count at the player's average tick;
- **GCD**: their unhasted GCD from back-to-back casts.

Check: each pull's logged casts, replayed through the model and converted, land within ~0.5% of the damage the pull
logged (one player +1.7%). The ceiling is the best rotation *without* raid buffs: FFLogs' rDPS credits a buff's gain to
the job that gave it, so a job without raid buffs gets no rDPS from alignment, and the unbuffed optimum is its rDPS
ceiling. It covers 0:00-2:00 standing still, like the scorecard's window.

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
so the level-90 ones are taken from the logs where they differ. The kit changed in 7.2 (Fire IV and Despair 2.0 s
casts, 20 s Ley Lines), so only clears since April 2025 are used. Later changes the model follows:

- Thunderhead and Firestarter no longer expire; they are only lost by being granted again while held;
- Fire III and Blizzard III deal 290 potency (280 before; the clears since July 2026 agree).

Two rules come from the logs alone, as the full-pull replays need them: a hard-cast Fire III from Umbral Ice III costs
no MP (4 of 4 such casts), and the Polyglot timer starts when the first fire or ice spell lands, not when it resolves
(only a 1.0-1.5 s lag makes every Xenoglossy legal; Fire III's flight is 1.29 s).

`check.py` tests the movement accounting on hand-made windows, then replays quick searches for both slots and every
variant from their history: each window gets its running time outside cast bars, and nothing is cast at Athena while
she is away. A standing-still rotation, as a control, breaks several windows.

## Files

| File | Role |
|---|---|
| `engine.py` | timing (GCD, casts, slidecast, weaving), raid buffs, move windows, downtime, beam search |
| `jobs/blm.py` | Black Mage: gauge, MP, procs, cooldowns, potencies, Ley Lines' circle |
| `p12s.py`, `p12s_p1.json` | the fight: timeline, downtime, our strategy's runs, the clears' runs elsewhere |
| `solve.py` | command line |
| `logs.py` | detailed per-player logs from the benchmark clears, cached in `.cache/` |
| `calibrate.py` | replays logs through a job model and reports where they disagree |
| `check.py` | movement and downtime checks |
| `dps.py` | potency to DPS per player; ceiling next to the scorecard's rDPS |
