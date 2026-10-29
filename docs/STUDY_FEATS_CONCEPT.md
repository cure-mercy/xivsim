# Concept: study feats

Status: draft, 2026-10-29. Staff named the monthly study feats update as the part they most want streamlined, so this
concept takes it out of the "later" pile of [SETUPS_CONCEPT.md](SETUPS_CONCEPT.md) (decision 20). Nothing is built yet.
The rules below come from the Course Credits workbook's formulas, the Study Feats, Study Groups and Cleanup guides in
the staff archive server, the staff Drive's templates and finalization guide, and the monthly update posts. They were
checked against the workbook's data (section "Checked against the data"); names of members and staff stay out of this
document because the repository is public.

## Goal

Once a month, on Promotion Monday, staff work out every member's study feats: raid activity, raid streaks and streak
freezes, study badges, cakedays, study level, promotions and demotions. They then update the workbook, update the
members' Discord roles, and post the Study Feats thread and the Promotion Monday part of the monthly update.

Almost all of it follows from data that already exists: who took part on which day, who cleared which duty, when they
joined, and the member's rank. The goal is that the site works the month out, staff check it, and then the site produces
everything that has to happen in Discord. That means the posts, the role changes and the messages. Later the bot can carry
them out too.

## The chain today

One member's month, from input to output:

```
participations per raid night ─┐
raid days of the month ────────┴─► monthly count ─► activity tier (+1…+6 Exp)
                                         │
                                         └─► active month (≥ 2) ─► raid streak (+3…+9 Exp) ─► streak freezes
clears (study history sheet) ─► study badges (+6/+12/+6, story arc, BLU) ─► unique streak freezes
#campus join date ─► cakeday (+3 Exp per year)
study group kills ─► study group Exp
rank ─► rank Exp (+3…+48 per promotion)
                     all of the above ─► Study Exp ─► Study Level
participations of the last 2–36 months + badges + months since the last promotion ─► promotion (Promotion Monday)
no participation for 6 months ─► demotion to Visitor
```

### Inputs, and who types them

| Input | Where | Kept by |
|---|---|---|
| Participations per month | Credits workbook, one column per Syncademy month; a number, `-` (none), `SG` (study group only), `B`/`BT` (rare, meaning unknown) | Staff, after each night's participation run |
| Raid days per month | Row 2 of the same column ("without Sprout Monday or other events") | Staff, by hand |
| The last month to count | Cell `AI2` (a column letter, read by every formula with `INDIRECT`) | Staff, monthly |
| Rank, date of the last promotion | Columns `L`, `M` | Staff |
| Badges | Per expansion: number of Expansion badges, `x` for the Extreme and the Savage badge of the current tier; story arc, Dawntrail, BLU blocks the same way | Staff, from the study history sheet |
| Raid streaks | `S1`–`S6` (how often each streak length was reached), `CS` (current streak, e.g. `6-21`), cells coloured by streak | Staff, by hand |
| Streak freezes | `SF` (regular), `UF` (unique) | Staff and the `!raidstreak_sf` / `!consume_sf` commands |
| Study group Exp | `SG` | Staff, at a study group's finalization |
| Cakeday | `BD`, the date of the member's first post in `#campus` (`01.01.1970` = unknown) | Staff, by searching Discord |

### The formulas

| Column | What it computes |
|---|---|
| `Total` | Months with at least 2 participations |
| `A1`–`A6` | How many months fell into each activity tier. A month's ratio is participations ÷ raid days. Tier 1 is at least 2 participations, tier 2 ≥ 25%, tier 3 ≥ 37.5%, tier 4 ≥ 50%, tier 5 ≥ 62.5% and tier 6 ≥ 75%. Tier *n* is worth *n* Exp |
| `CP` | Cakeday points: with *y* = whole 365-day years since the cakeday, `1.5·y·(y+1)` (3 Exp for the 1st year, 6 for the 2nd, …) |
| `Study Exp.` | Rank Exp (Disciple 3, Adept 9, Magister 21, Archon 45, Prime 81, Eternal 129: the sums of +3, +6, +12, +24, +36, +48) + 24 per Expansion badge + 6 per Extreme badge + 12 per Savage badge (the same for story arc and Dawntrail) + 24 per BLU combo badge + 9 per BLU expansion badge (ARR, HW) + Σ tier × months + streaks (3, 4, 5, 6, 7, 9 per `S1`…`S6`) + `SG` + `CP` |
| `Study Level` | Bands of 8 levels with a growing step: 6 Exp per level up to 48 Exp (level 8), then 12 up to 144 (16), 18 up to 288 (24), 24 up to 480 (32), 30 up to 720 (40), 36 up to 1008 (48), 42 up to 1344 (56) |

Everything else is decided by hand: streaks, freezes, cakedays, badges, promotions, demotions. Conditional formatting
helps by highlighting cakedays in the update range, months without enough participations, and Exp that changed. Some of
those rules now point at `#REF!` and no longer work.

### The rules the formulas don't hold

| Part | Rule (from the guides and templates) |
|---|---|
| Syncademy month | From a calendar month's second Monday to the day before the next one's |
| Raid streak | Every 3 months in a row with at least 2 participations: 3 months +3, 6 +4, 9 +5, 12 +6, 15 +7, then +9 for every further 3 months (the post counts the "nth time"). Every 6 months of an ongoing streak add a streak freeze |
| Streak freeze | A month with 0 or 1 participation uses one (regular before unique); the streak only ends when none are left |
| Unique streak freeze | +1 for a promotion to Adept, Magister or Archon (the workflow says "Adept or higher", the template gives none for Prime and Eternal) and for each story-arc badge |
| Badges | All Extremes of an expansion: +6. All its Savage: +12. Both: an Expansion badge (+6), and the two reset to be earned again in the next tier. Story arc: Zodiark (all ARR–EW Extremes, +6), Hydaelyn (all ARR–EW Savage, +12), Starbird (both, +6), each with a unique freeze. BLU: a mask badge per expansion (+9) and the Morbol combo for ARR and HW (+6). Earned in the course or in a study group |
| Cakeday | The *n*th anniversary of the first `#campus` post gives 3·*n* Exp ("active players") |
| Promotions | See below |
| Demotion | A student inactive for more than half a year becomes a Visitor and gets the old rank back on returning; a DM explains it |
| Inactive | No participation for 9 months and no study group points: marked inactive |
| Alumni cleanup | The `@Alumni` role is removed by rank and months away (Cleanup guide) |
| Study group Exp | Decision 24 in SETUPS_CONCEPT.md: the Drive guide's per-expansion amounts or the archive guide's 2/4/6 for 2–4/5–8/9–12 kills |

Promotion criteria (Promotion Monday template):

| To | Exp | Needs |
|---|---|---|
| Disciple | +3 | ≥ 5 participations in total and ≥ 3 in the current month, or ≥ 10 study group Exp |
| Adept | +6, unique freeze | ≥ 20 participations in the last 3 months, over 33% in the last 2 months, 2 months since the last promotion; or ≥ 20 study group Exp |
| Magister | +12, unique freeze | ≥ 45 participations in the last 6 months, over 33% in at least 4 of them, over 50% in the last 2 months, ≥ 2 badges |
| Archon | +24, unique freeze | ≥ 100 participations in the last 12 months, over 33% in at least 8 of them, over 50% in the last 2 months, ≥ 3 badges with ≥ 1 Savage |
| Prime | +36 | ≥ 8 badges with ≥ 2 Savage, ≥ 15 months in tier 3 or higher averaging tier 4, 18 months since the last promotion, over 33% in the last 2 months |
| Eternal | +48 | ≥ 16 badges with ≥ 4 Savage, ≥ 30 such months, 36 months since the last promotion, over 33% in the last 2 months |
| Staff ranks | | A simulated student rank plus months on staff (two ranks) |

Staff get their student ranks "simulated": staff are assessed by the same rules, and the post marks them so.

### The monthly workflow

The Study Feats Workflow guide (August 2025, partly replaced by a "new workflow" in November 2025 that uses a Django
application and bot commands) has these steps. The last column is what the site would make of each step.

| # | Step | Today | With the site |
|---|---|---|---|
| 0 | Preparation | Fill missing Discord and Lodestone IDs and cakedays by command, copy the sheet, reload the Django application | Not needed: the member register is the database |
| 1 | Study badges | Mark badges in the sheet from the study history; collect the IDs for the post | Computed from the recorded clears; staff confirm |
| 2 | Cakedays | Search each player's first `#campus` post, update points, freezes and Exp roles, mark long-inactive players | Computed; the date is entered once per member, or taken from Discord's join date (question 6) |
| 3 | Raid streaks | Colour cells, raise `S1`–`S6`, add freezes, add roles for new streaks | Computed |
| 4 | Promotions | Check the criteria by eye with filters, set rank, colour rows, add unique freezes | Candidates computed; staff confirm each |
| 5 | Raid activity | Edit the column limit in formulas and the ranges of conditional formatting rules, collect IDs by colour | Computed; nothing to edit |
| 6 | Update profiles | Look up each member in Server Settings → Members and change their roles (Exp, level, badges, freezes) | A list of role changes per member (phase 1); the bot makes them (phase 2) |
| 7 | Consume streak freezes | Filter, `!consume_sf`, end streaks without freezes | Computed |
| 8 | Post the monthly update | Write the Study Feats thread and Promotion Monday from templates | Generated text, split to Discord's length limit; posted by staff, later by the bot |
| 9 | Mark insufficient participation | Grey out months with one participation | Not needed |
| 10 | Add a new month | Drag the last column, clear it, copy statistics, fix the weekly average | Not needed |

Steps 3 to 7 change the same member's roles one after another, and the June 2026 level-up list alone had 77 members.
Step 6 is likely the largest share of the time. Two earlier automation attempts exist: a 2024 development copy of the
sheet with one tab per step, which generated the ID lists but left streaks, freezes and column upkeep manual, and the
Django application of the new workflow. Both stayed inside the spreadsheet, so the monthly upkeep of columns,
formulas and colours remained.

## Checked against the data

Run on the workbook export of 29 October 2026 (1,224 members, 80 months) with the scripts in `scratch/setups/feats/`:

- **Activity tiers**: recomputed from the monthly counts and raid days, `A1`–`A6` match for every member.
- **Study level**: the level table above reproduces `Study Level` for every member except one (see below).
- **Raid streaks**: the streak rule above (2+ participations, freezes every 6 months, a freeze bridges a weak month)
  reproduces `S1`–`S6` for 1,169 members (95.5%). Without freezes it's 1,125. The other 55 have long streaks across
  months with one participation, or counts that predate the sheet's months. These are the cases staff would check once
  when the site takes over; they may be hand corrections or older rules.
- **Promotions**: on the Promotion Mondays of March, April, May and June 2026, all 37 members promoted that day meet
  the criteria above, evaluated with the months up to that day. Only a handful of members who were not promoted meet
  them too (0–3 per rank and month; some may be staff, whose ranks are simulated).
  - The promotion is checked as if the member had the rank below until that day.
  - An Expansion badge counts as three badges: its Extreme badge, its Savage badge, and itself.
  - Whether "over 33% in the last 2 months" means both months together or each month made no difference here.

Found along the way, each worth fixing whatever happens to the site:

| Finding | Effect |
|---|---|
| One member's cakeday is `31.12.1969` instead of the placeholder `01.01.1970` | Cakeday points count 56 years: 4,788 Exp, and the level shows `#N/A` |
| The tier 6 threshold is `≥ 75%`, the post says "over 75%" | 210 month cells sit at exactly 75% (12 of 16 raid days, for example), and the sheet gives +6 |
| Cakeday years are 365-day blocks, not anniversaries | 3 members currently count a year early; the highlighting rules use 365, 730, 1095, 1460, 1826 days |
| The BLU block has columns for the ARR and HW mask badges only | The SB (Red Mask) and ShB (Purple Mask) badges of the template aren't counted in Exp |
| The level table ends at 1344 Exp (level 56) | Fine for now (the highest real Exp is 1,035) |
| The newest promotion date in the sheet is 8 June 2026 | Either nobody was promoted since, or the dates stopped being kept; promotions after June can't be checked |

## The concept

### One rule set, run from the start

The site computes study feats with one function: give it a member's history (participations by day, clears with
dates, badges, join date, rank changes, study group awards) and a month, and it returns that month's feats. The
thresholds sit in a table, not in code, so a rule change by staff is a change of a number. The rules are applied
from each member's first month every time. So the result never depends on someone having coloured a cell, and a
corrected participation from three months ago shows up in this month's figures.

The function lives in `site/setups_core.js` next to the setup proposal (on the MVP branch) and has tests on made-up
members. The
checks above become those tests: the activity tiers, the level table, the streak and freeze rule, and a promotion of
each rank.

### The month close (`#/feats/<month>`)

On or after Promotion Monday, a staff member opens the month:

1. **Readiness.** The page lists what's missing: nights of the month without a confirmed participation run, members
   without a join date, study groups awaiting finalization. The raid days come from the calendar: nights of the
   counted series, without Sprout Monday and special events. Staff can override that number.
2. **The draft.** For every member, the month's feats with the reason for each:
   - "tier 4: 9 of 16"
   - "streak 12 months, freeze +1"
   - "freeze used: 1 participation"
   - "Savage badge: all ShB Savage cleared"
   - "3rd cakeday"
   - "level 23 → 24"
3. **Decisions.** Promotion candidates are listed with the criteria they meet; staff tick who gets promoted. Ranks that
   need judgement are left unticked, as are staff ranks (simulated) and anything flagged. Demotion and inactivity
   candidates work the same way.
4. **Close.** Closing saves the month as a snapshot: the feats, the decisions, and who closed it. The month's data can
   still be corrected afterwards; the page then shows what changed against the snapshot and what that means in Discord
   (for example "role Level 24 to add").
5. **The texts.**
   - The Study Feats thread, the Promotion Monday part and the level-up list, each in the exact template layout and
     split at Discord's 2,000-character limit.
   - The monthly statistics: unique players, average participations per week.
   - The demotion DMs.
   Each has a copy button.
6. **Discord changes.** A list per member of the roles to add and remove: rank, level, badges, the streak freeze
   count. Staff tick each change as done; the next month starts from what was ticked. With the bot (phase 2), one click
   applies them, and the bot reads each member's current roles first, so it only changes what differs.

### Study groups

A study group's finalization gets a page too. Staff enter the kills (duty, date, members, backups), which go into the
study history like any other clear and may complete badges. The page computes each member's study group Exp by the
rule staff settle (decision 24), offers Initiate promotion to Visitors, and writes the finalization message with each
member's rewards and level change.

### What stays with staff

- Confirming promotions, demotions and anything flagged. The site proposes and never promotes on its own.
- Posting, until the bot does it.
- Judgement calls the rules don't cover, entered as a manual Exp correction with a note. That replaces editing a sum by
  hand.
- The anniversary event's badge and medal tiers, which are outside the monthly rules.

## Phases

| Phase | What | Needs |
|---|---|---|
| 0 | **Credits checker**: a staff page that reads a credits workbook export (a file chosen on the staff member's own computer and processed in the browser, so nothing is uploaded or stored) and produces the month: the lists, the posts, the role changes, and the cells to change in the sheet. The sheet stays the record | Neither the bot nor the database; it holds no member data, so it can be built before the site is approved |
| 1 | **The site keeps the record**: members, participations from the participation run, clears, badges and credits in the database; the month close above; the sheet becomes an archive | Steps 2 and 4 of SETUPS_CONCEPT.md (bookkeeping, the participation run) |
| 2 | **The bot**: posts the Study Feats thread, applies role changes, sends the demotion DMs after a staff click | The bot application with Manage Roles and permission to post (decisions 5, 6, 17) |

Phase 0 removes most of the monthly work without changing where the data lives, and shows staff the computed results
next to their own before anything depends on them. It replays the whole history from the monthly columns, as the
checks above did. The streak counters in the sheet stay the record; where the replay differs, the page says so instead
of overwriting.

Phase 1 changes the data model of SETUPS_CONCEPT.md a little:

- `credits` stops being typed in and becomes a monthly snapshot (`feats_months`: member, month, participations, tier,
  streak, freezes, badges earned, cakeday, Exp, level, rank before and after).
- `badges` gets the story-arc, BLU and Dawntrail kinds.
- `members` keeps the rank before a demotion.
- A `feat_rules` table holds the thresholds.
- A `feat_roles` table maps each feat to its Discord role.

## Questions for staff

1. **Exactly 75%**: tier 6 (as the sheet computes) or tier 5 (as the post says, "over 75%")? It happens about 3 times a
   month (210 month cells over 80 months).
2. **"Over 33% in the last 2 months"**: both months together, or each month? The data so far can't tell them apart.
3. **Badge count for promotions**: does an Expansion badge count as three (its two badges and itself)? That reading
   matches all 37 promotions checked.
4. **Streaks**: does a month with 1 participation use a freeze (as the new workflow's filter says), and do `SG`, `B`
   and `BT` months count as active, as weak, or not at all? What do `B` and `BT` mean?
5. **Cakeday**: only for members active that month ("all the following active players") or for everyone, as the
   formula does?
6. **The join date**: is the first post in `#campus` the cakeday on purpose, or would Discord's server join date (which
   the bot can read) do? It's the one input that needs a manual search today.
7. **Profiles**: which Discord roles make up a profile? Rank, level, badges, the streak freeze count and the separator
   roles; is that the full list? This becomes the `feat_roles` table.
8. **Promotion dates after June 2026**: were there promotions on the Promotion Mondays since July, and where are their
   dates kept?
9. **The Django application**: does it still run, and does it compute anything this concept should match (its
   streak list, for example)? This is part of decision 19.
10. **Phase 0 first?** It helps with the next Promotion Monday, before anything else of the site exists.
