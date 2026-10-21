# Red Mage: things to test in game

The Red Mage model (`jobs/rdm.py`) was built from logs while FFLogs was down. The logs can't settle the points
below, or settle them only indirectly. Each test says what the model assumes now and what to change if the game
disagrees. The most important ones come first.

Where to test:
- **Gauge, status and movement rules** (tests 2 to 10) are the same at any level: a striking dummy is fine. Start each
  test in combat. The Balance Gauge shows both mana values as numbers.
- **Potencies** (test 1) must be read at **level 90**. Hover the actions inside a duty that
  syncs you to 90, e.g. P12S itself or a level-90 dungeon. The tooltips then show level-90 values.

## 1. Level-90 potencies (most important)

The search never spends Verfire / Verstone procs, because at level 90 Jolt III (360) out-damages them (340). Our
players spend procs on most hard casts, so this is the result most worth confirming.

Synced to 90, read these tooltips. The model uses:

| Action | Model | Action | Model |
|---|---|---|---|
| Jolt III | 360 | Enchanted Riposte | 280 |
| Verfire / Verstone | 340 | Enchanted Zwerchhau | 150, combo 340 |
| Verthunder III / Veraero III | 380 | Enchanted Redoublement | 130, combo 500 |
| Verflare / Verholy | 600 | Enchanted Reprise | 340 |
| Scorch | 680 | Fleche | 460 |
| Resolution | 750 | Contre Sixte | 380 |
| Engagement | 180 | Corps-a-corps | 130 |

If a tooltip differs: change `POTENCY` in `jobs/rdm.py`. If Verfire is 360 or more, the proc result goes away.

## 2. Mana imbalance

Older versions of the job halved a colour's mana gains while it led the other by more than 30. The model has no such
rule (`IMBALANCE_HALVES = False`).

1. From 0 / 0, cast Verthunder III (or Verfire) until Black Mana leads White Mana by more than 30, e.g. 36 / 0.
2. Cast one more Verthunder III (+6 Black) and note the gauge.

- +6: no halving, the model is right.
- +3: halving exists. Set `IMBALANCE_HALVES = True`. The searched rotations never pass a 30-point lead, so the
  results should barely move.

## 3. Mana Stacks after a broken combo

The search only plays whole melee combos. The model lets stacks persist, but nobody knows whether they do.

1. With 50 / 50 mana or more, cast Enchanted Riposte (1 stack shows), then Jolt III.
   Is the stack still there?
2. If it is, wait 30 s or more. Is it still there?
3. If it survives a broken combo, try Enchanted Riposte -> Jolt III -> Enchanted Riposte -> Enchanted Zwerchhau.
   Does Verflare / Verholy light up after that?

If stacks vanish when the combo breaks, add that rule to `do_gcd` in `jobs/rdm.py`. The search results won't change.

## 4. Swiftcast and Dualcast together

Assumed, never seen in the logs: when both are up, the next spell uses Dualcast and Swiftcast stays.

Hard-cast Jolt III (Dualcast comes up), press Swiftcast, then cast Verthunder III. Which status disappears?

If Swiftcast is spent instead, swap the order of the two checks in `cast_time` (`jobs/rdm.py`).

## 5. Manafication

The model assumes:
- Manafication gives no mana.
- Its Magicked Swordplay stacks are spent even when you have enough mana.
- It doesn't remove existing Mana Stacks.

1. With about 60 / 60 mana, press Manafication. Does the gauge change?
2. Cast Enchanted Riposte. Does the mana drop by 20 / 20, or does a Magicked Swordplay stack go instead?
3. Cast Enchanted Riposte (1 stack), Jolt III, then Manafication. Is the Mana Stack still there? (Only possible if
   test 3 shows stacks survive a broken combo.)

## 6. Verflare / Verholy at equal mana

The model assumes:
- Verflare surely grants Verfire Ready when White Mana leads.
- Otherwise the chance is 20%, and that includes a tie.

At exactly equal mana (e.g. 50 / 50), cast Verflare a few times. Does Verfire Ready come up every time, or only now
and then?

## 7. Enchanted Reprise recast

The model gives Enchanted Reprise a normal 2.5 s GCD. Our logs hold a single use, so its recast is unmeasured.

Cast Enchanted Reprise and read the GCD timer. Is it 2.5 s, or 1.5 s like Enchanted Riposte?

If it is 1.5 s, add `"Enchanted Reprise": 1.5` to `RECAST` in `jobs/rdm.py`. It would then cover our runs better.

## 8. Displacement's backstep

The optimizer now models dashes. Corps-a-corps is settled by the logs: from anywhere 11-19 y out, it lands you at
Athena's hitbox edge, 10.5 y from her centre. Displacement has only 3 uses in our logs, so the model takes its tooltip
on trust:
- It jumps 15 y straight back, away from the target.
- It works from inside the boss's hitbox. Our plan uses it from beside Athena, heading out to the wall in Paradeigma I
  and out across the arena in Paradeigma II.

1. On a striking dummy, stand inside its ring, use Displacement and count the floor tiles you travel. Is it 15 y?
2. Turn your character away from the dummy first, then use it. Do you still jump away from the dummy, or backwards
   from where you face?
3. In P12S, if you get the chance: use Displacement next to Athena with the wall behind you. Do you stop at the wall?

- **Not 15 y:** change `BACKSTEP` in `jobs/rdm.py`.
- **It goes by your facing:** nothing changes. The model assumes you face Athena when you use it.
- **It can't be used from inside the ring:** the "out" stretches in `p12s.DASH` must start at the ring (10.5 y), not
  at Athena's centre.

## 9. Sprint cancels Dualcast (quick)

The logs show it, and the model now assumes it. Hard-cast Jolt III, press Sprint. Is Dualcast gone?

## 10. Melee reach under Manafication (quick)

Assumed from the tooltip: under Manafication the three enchanted combo actions reach 25 y. Engagement and Enchanted
Riposte without Manafication need melee range.

Stand about 10 y from a dummy, press Manafication, then try Enchanted Riposte. Without Manafication it shouldn't work.
