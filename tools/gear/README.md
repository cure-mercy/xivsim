# Gear model and best in slot

Finds each DPS job's best gear, materia and food for P12S phase 1, together with the rotation optimizer
(`tools/rotation`): a set is worth what the job's whole-phase rotation deals with it.

```
python tools/gear/fetch.py [--refresh]         # gear_db.json from xivgear.app's data API (downloads cached in .cache/)
python tools/gear/gear.py --caps               # which synced items reach the cap in every stat
python tools/gear/gear.py --job blm --items weapon
python tools/gear/bis.py --job blm             # the best set per GCD tier, the rotation's mix at the job's GCD
python tools/gear/bis.py --job blm --combined  # gear and rotation together (a whole-phase search per tier)
python tools/gear/check.py                     # the model's rules and formulas, and the site's sets
python tools/gear/sheets.py [--job sam]        # the sets as the site shows them (build_site.py reads them)
```

## The fight's sync

P12S syncs the player to level 90 without an item-level sync. Gear above level 90 is synced down to level 90's item
level, **660, weapons included**: each stat is cut to the slot's cap at 660 and its materia is off. Level-90 gear is
never synced, so the level-90 665 weapons (savage, Criterion, Mandervillous) keep their stats and materia.

- Our groups' logs say so: every DPS and healer uploader's main stat is 3514-3540, capped gear at 660 throughout; a
  665 weapon would give 3544 or more (FFLogs logs stats for the uploader only, and no gear at all).
- xivgear's in-instance tests (its issue 317) say the same for a level-90 instance without item-level sync.
- Every armour piece from item level 780 on reaches the 660 cap in all its stats (weapons from 780 too); the
  level 91-96 gear at 650-669 is synced as well, so it only loses its materia.

## Data (`fetch.py`, `gear_db.json`)

From data.xivgear.app: the DPS jobs' gear at item level 640-669 and 780 up, the Mandervillous weapons (665) and the
newest Phantom weapons (Occultum, 795); the ItemLevel rows (stat values per item level) and BaseParams (each stat's
share per slot and meld parameter) the caps come from; job stat multipliers; substat materia; food (HQ).

## The model (`gear.py`)

After xivgear's rules and formulas (github.com/xiv-gear-planner/gear-planner: `packages/xivmath`,
`core/src/datamanager_new.ts`, `core/src/relicstats`):

- **caps**: `round(floor(floor(ilvl value x meld param / 100) x slot share / 100) / 10)`; every unsynced item's larger
  substat sits exactly at it (396 items);
- **materia**: a meld adds up to the item's own cap for that stat. Level-90 gear takes Materia X (36) and IX (12) only
  (XI and XII need item level 690). Crafted gear that allows overmelding: X, X, X, IX, IX;
- **relics**: Mandervillous two substats at the cap (306) and one at 72; Occultum two at its cap and one at 108, then
  synced (303 / 303 / 108), with main stat and weapon damage at 660 (409, 131) against the 665 weapons' 416 and 132;
- **stats**: base main stat 390 x the job's modifier, +3 clan, substats 400 (determination 390), gear, food (10% of
  gear and base, up to its max; food isn't synced), +5% main stat for a full party;
- **damage** per potency at level 90: main stat (195 / 390), determination, weapon damage, expected crit and direct hit,
  the speed stat on DoT ticks and autos; sure crits and sure critical direct hits (direct hit's bonus on determination).

Checked against our groups' logs: each DPS uploader's logged stats predict their measured damage per potency on plain
hits (dps.py's `k`) within 1.4% (Machinist, Dancer, Red Mage, Reaper, Viper; `scratch/gear/kcheck.py`). Black Mage
measures 1.216 x the prediction: its model's potencies leave Enochian out, a constant that doesn't change the set.

## Best in slot (`bis.py`)

The rotation's potency over the whole phase (0:00 to the clears' median kill, 449 s, no raid buffs, our strategy's
runs at the role's worst slot) split by how each part scales: normal hits (pets too), DoT ticks, sure crits, autos
(replayed without them). A set's value is that mix times its multipliers.

The GCD tiers: the speed stat sets the GCD in 0.01 s steps (after a trait's haste for Monk and Ninja, as the game
rounds it; under Fuka, Swiftscaled or Ley Lines the game rounds the hasted GCD again, so there a tier is the pair:
Samurai's 2.40 s is 2.08 s or 2.09 s under Fuka by the speed factor). Within a tier the rotation is
the same, so each tier gets its own best set: a dynamic program over the slots keyed by the gear's total speed, on
stat weights from the set's own gradient, then a local search on the exact, floored formulas (one or two slots
changed), repeated until the set stops changing. Rings go as pairs (a unique ring once); foods another beats in every
stat are left out.

`--combined` first finds every tier's set at the job's own rotation, then searches the whole-phase rotation on a grid
of GCDs, slowest first (every 0.03 s; Samurai and Viper on their hasted GCD; Black Mage every tier, `GRID_STEP`), fits
the potency over the grid (quadratic, as the search moves ~0.4% between runs, `tools/rotation/README.md`; Black Mage
takes each tier's own) and interpolates the mix, finds each tier's set at its fitted mix, and searches the top three
tiers again, and every grid tier whose own grid search came within 0.4% of them or above (`TIE`: a lucky grid point
lifts the fit's peak, but it is a searched set and rotation: Monk's 1.94 s grid point beat the fit's best three by
1.1%). The site's chart shows all three against the fit's peak, with the search's noise as a band around the fit. The
grid covers the tiers that could still win (`span_of`): a set's multipliers times the most a faster GCD can add to the
potency, the GCDs' ratio plus 2% (`SLACK`), at least the best set's. It stops once 0.05 s of it in a row stayed 1.5%
under its best grid point (`STOP`, `STOP_SPAN`), each priced at its tier's set (a flat cut by the sets' multipliers
alone stopped Black Mage at 2.31 s, while its 2.18-2.24 s rotations gain 8-9% potency over 2.38 s). Each search takes
the set's own:

- **speed factor** where the job model times everything through `engine.recast` (Black Mage, Samurai, Viper, Monk,
  Ninja): within a tier a Black Mage's 2.0 s casts are 1.85 s at 0.928 and 1.86 s at 0.930. The other models scale
  continuously, and the tier's smallest factor (GCD / 2.5) gives the game's GCD exactly;
- **rates** the job model takes as constants (crit rate, crit damage, direct-hit rate; its `derive()` recomputes what
  it builds from them): Monk's chakra, Dragoon's Life Surge and Battle Litany, Bard's songs and Battle Voice, Dancer's
  Devilment and Starfall, the sure-hit weights of Machinist, Pictomancer and Samurai.

A tier's search repeats while its set's speed factor and rates move. Tiers closer than ~0.4% are ties.

## The site's ceilings (`ceiling.py`)

`python tools/gear/ceiling.py [--job X]` turns each job's combined optimum (`bis.py --combined` saves it to
`.cache/bis_<job>.json`) into the scorecard's 0:00-2:00 ceiling (`.cache/bis_site.json`, read by
`scorecard.rotations()` for the Rotations chart):

- the rotation searched over 0:00-2:00 alone at the set's speed factor and rates (our strategy's runs at the role's
  worst slot, as `dps.py`'s ceilings), priced at the set (`bis.value`), in nDPS;
- in the job model's potency unit: the gear formula takes game potency, and the Black Mage model's potencies
  include Enochian (x1.22, `blm.ENOCHIAN`, which the game applies to every spell in an element); every other model's
  are game potency (`UNIT`). `--factors` checks it against every uploader at capped gear whose stats FFLogs logs (our
  reports and the benchmark clears' 45 kills), their plain hits over 0:00-2:00 against their stats' prediction:
  Black Mage -0.3%, the others -0.9% to +2.1% (one to six uploaders each, weapon damage inferred from main stat); none
  for Bard, Dragoon, Pictomancer and Ninja;
- the **spread**: one standard deviation of the window's damage from crit and direct-hit rolls alone, from the
  rotation's hits one by one. A replay sets `s.dmg` (and `dotp`, `critp`) to `Acc`, a float that keeps its increments
  as a persistent chain, tags `AUTO` so auto-attacks are known, and pairs each DoT and sure-crit increment with its
  channel. A hit of potency b varies by b² K² v (K: damage per potency, v: the variance of crit x direct hit at the
  set's rates); sure crits vary by their direct hit only, sure critical direct hits and Wildfire not at all; a DoT's
  share counts as ticks of the model's tick potency. Not in it: the ±5% damage roll and the extra spread own crit
  buffs (Devilment, Battle Voice, Battle Litany) give their hits;
- **proc luck** for the jobs whose models draw their procs (`DRAWN`: Monk, Bard, Dancer, Red Mage; `engine.DRAW`):
  the rotation played 400 times under drawn procs by a player who re-plans 20 s ahead before every step
  (`montecarlo.draws`, sweep width 3000: at 300 the sweep's pruning, not the procs, made a quarter of Red Mage's
  draws lose 3.1%), measured against the same player with nothing drawn (the short horizon's own cost is no luck).
  Each draw's hits are recorded and priced as above (`record(draw=seed)`); a Monk weaponskill's drawn crit (which
  opens its chakra) is booked as a sure crit or a plain hit (`plainp`), so its crit luck and its chakra's go
  together. The band (`lo` / `hi`) is p16-p84 of the draws, each spread by its own crit and direct-hit SD: as many
  pulls as one SD either side, but lopsided like proc luck. Other jobs: ceiling ± spread. Draws cached in
  `.cache/procs/` (delete after a job model changes).

## The site's sets (`sheets.py`)

`build_site.py` puts each job's set on the scorecard's Gear pages (`#/gear`, `#/gear/<job>`) and on its Rotations
job page: `sheets.py` rebuilds the set in `.cache/bis_<job>.json` from `gear_db.json` with the model's own rules, so
every item comes with its stats after sync and melds, its materia slot by slot (what each meld adds under the item's
cap) and its source, and the set with its final stats, rates and food. Nothing is searched. `scorecard.gear()` adds
the item, materia and food icons (XIVAPI, cached in the scorecard's `.cache/icons/`).

A job shows the best searched tier's set and, as tabs, the other searched tiers within 0.4% of it (`TIE`: the search's
noise). `bis.py --combined` saves every searched tier's set as `sets`. The same grade's melds are shown in a fixed order (crit, DH,
Det, speed): the search keeps an arbitrary one of the equivalent orders, which changes between runs. The rotations' GCDs are before a trait's haste,
so Monk's and Ninja's sets carry that GCD too (`base_gcd`) for the Rotations pages' BiS tag.

## Results

DPS over the whole phase without raid buffs, the job's own constant multipliers left out (Black Mage's Enochian), so
compare tiers within a job, not across jobs. Logs in `.cache/<job>_combined.log`, sets in `.cache/bis_<job>.json`
(2026-10-25). The rest of each set is 660 savage and
tomestone gear melded to the tier. Pictomancer and Viper have no Mandervillous weapon (Dawntrail jobs): their
relic is the synced Phantom Occultum. The site ceiling (`ceiling.py`) is in each job's potency unit (Black Mage x1.22).

| Job | Best tier (searched) | Tied within 0.4% | Weapon (relic substats) | Armour and accessories | Food | Site ceiling 0:00-2:00, nDPS +- luck (with procs: p16 / p84) |
|---|---|---|---|---|---|---|
| BLM | 2.13/1.81 | 2.12/1.80, 2.17/1.85, 2.15/1.83, 2.21/1.88, 2.20/1.87 | Mandervillous Rod (det/sps +dh) | 2 synced (780, 790) | Rroneek au Gratin | 15,608 +-280 (1.8%) |
| BRD | 2.47 | 2.50 | Mandervillous Compound Bow (crit/dh +sks) | 2 synced (780, 780) | Caramel Popcorn | 10,053 +-280 (2.8%); with procs -3.8% / +2.8% |
| DNC | 2.50 | - | Mandervillous Chakrams (crit/dh +det) | 2 synced (780, 780) | Caramel Popcorn | 10,354 +-373 (3.6%); with procs -4.3% / +4.7% |
| DRG | 2.50 | 2.49 | Mandervillous Trident (crit/det +dh) | 2 synced (780, 790) | Caramel Popcorn | 12,923 +-383 (3.0%) |
| MCH | 2.49 | 2.47 | Mandervillous Revolver (crit/dh +det) | 2 synced (780, 780) | Caramel Popcorn | 13,230 +-309 (2.3%) |
| MNK | 1.94 | - | Mandervillous Fists (crit/dh +sks) | 2 synced (780, 780) | Caramel Popcorn | 14,141 +-386 (2.7%); with procs -3.3% / +3.1% |
| NIN | 2.12 | - | Mandervillous Knives (crit/dh +det) | 2 synced (780, 780) | Caramel Popcorn | 13,364 +-431 (3.2%) |
| PCT | 2.49 | 2.47, 2.50 | Phantom Round Brush Occultum (crit/det +dh) | 4 synced (780, 780, 790, 795) | Caramel Popcorn | 14,335 +-483 (3.4%) |
| RDM | 2.50 | 2.49 | Mandervillous Rapier (crit/det +dh) | 3 synced (780, 780, 790) | Caramel Popcorn | 12,622 +-424 (3.4%); with procs -3.4% / +3.4% |
| RPR | 2.47 | 2.44, 2.49 | Mandervillous Zaghnal (crit/dh +sks) | 2 synced (780, 780) | Caramel Popcorn | 13,579 +-427 (3.1%) |
| SAM | 2.50/2.17 | 2.49/2.16, 2.48/2.15 | Mandervillous Samurai Blade (crit/dh +det) | 2 synced (780, 780) | Caramel Popcorn | 14,374 +-306 (2.1%) |
| SMN | 2.12 | 2.14, 2.11, 2.10 | Mandervillous Index (det/sps +dh) | 2 synced (780, 790) | Rroneek au Gratin | 12,837 +-217 (1.7%) |
| VPR | 2.48/2.10 | 2.50/2.12, 2.47/2.09 | Phantom Twinfangs Occultum (crit/det +dh) | 3 synced (780, 780, 795) | Caramel Popcorn | 14,523 +-432 (3.0%) |

Not modelled: cast and recast times other than the GCD in the continuously scaled job models (round to 0.01 s in
game); pets use the owner's weapon-damage job modifier.
