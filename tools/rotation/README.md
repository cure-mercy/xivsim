# Rotation optimizer

Searches for the highest-damage rotation of a job over the first two minutes of P12S P1 (level 90), against the raid
buffs the party brings. So far: Black Mage.

```
python tools/rotation/solve.py --job blm                      # 2.32 s GCD, AST/SCH/DRG/DNC buffs, 0:00-2:00
python tools/rotation/solve.py --gcd 2.14 --party RPR,SCH,RDM --compare
python tools/rotation/solve.py --move 30-34,40-42             # no hard casts in these windows (e.g. Paradeigma I)
python tools/rotation/calibrate.py                            # check the job model against the clears' logs
python tools/rotation/dps.py                                  # our players: ceiling in DPS next to their scorecard rDPS
```

| Option | Meaning |
|---|---|
| `--gcd` | the player's GCD without haste (spell speed); `--compare` prints each clear's |
| `--party` | jobs whose raid buffs are present; they land at the median times of the benchmark clears |
| `--move` | windows in which nothing may be hard-cast (the last 0.46 s of a cast can be slid) |
| `--pot` | allow one tincture (off by default: the scorecard strips tinctures) |
| `--carry` | also value resources still held at the end, instead of dumping everything before 2:00 |
| `--until` | end of the scored window, seconds |
| `--width` | beam width; 1,000 and 4,000 give the same result for Black Mage |
| `--compare` | replay every benchmark clear's logged rotation under the same buffs and window |

Damage is in potency (Xenoglossy 890) times the raid buffs active when each hit lands; crit and direct-hit buffs count
at their expected value.

## From potency to DPS

`dps.py` converts per player, from their clean pulls (alive through 2:00) on the job:

- **damage per potency**: their plain hits (no crit, no direct hit) with others' buffs divided out, over the model's potency;
- **crit and direct hit**: the share of their hits that crit / direct-hit; crit damage is 1.35 + crit rate (same stat);
- **DoT ticks**: FFLogs reports ticks without crit flags, so they count at the player's average tick;
- **GCD**: their unhasted GCD from back-to-back casts.

Check: each pull's logged casts, replayed through the model and converted, land within ~0.5% of the damage the pull
logged (one player +1.7%). The ceiling is the best rotation *without* raid buffs: FFLogs' rDPS credits a buff's gain to
the job that gave it, so a job without raid buffs gets no rDPS from alignment, and the unbuffed optimum is its rDPS
ceiling. It assumes standing still through Paradeigma I; use `--move` in `solve.py` to see what movement costs.

## How the job model was checked

`logs.py` fetches each clear's casts (with begin-casts and MP), hits (with the buffs on them) and the player's own
statuses. `calibrate.py` replays every logged cast through the model at its logged time:

- every cast in the 11 Black Mage logs since patch 7.2 is legal;
- cast times match begin-cast -> cast within 0.03 s;
- each spell's plain hits (no crit, no direct hit, buffs divided out) match the model's potency within ~2-3%;
- MP matches the logged snapshots in 596 of 619 casts (the rest are snapshots FFLogs takes just before a refill shows).

Rules not visible in logs come from the official job guide's level-90 tooltips (Aspect Mastery, Enochian, Paradox).
The kit changed in 7.2 (Fire IV and Despair 2.0 s casts, 20 s Ley Lines), so only clears since April 2025 are used.

## Files

| File | Role |
|---|---|
| `engine.py` | timing (GCD, casts, slidecast, weaving), raid buffs on a timeline, beam search |
| `jobs/blm.py` | Black Mage: gauge, MP, procs, cooldowns, potencies |
| `solve.py` | command line |
| `logs.py` | detailed per-player logs from the benchmark clears, cached in `.cache/` |
| `calibrate.py` | replays logs through a job model and reports where they disagree |
| `dps.py` | potency to DPS per player; ceiling next to the scorecard's rDPS |
