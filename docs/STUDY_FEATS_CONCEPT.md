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
| Participations per month | Credits workbook, one column per Syncademy month; a number, `-` (none), `SG` (took part only in a study group), `B` ("Visitor backup after start", the sheet's legend), `BT` (5 cells, not in the legend) | Staff, after each night's participation run |
| Raid days per month | Row 2 of the same column ("without Sprout Monday or other events") | Staff, by hand |
| The last month to count | Cell `AI2` (a column letter, read by every formula with `INDIRECT`) | Staff, monthly |
| Rank, date of the last promotion | Columns `L`, `M` | Staff |
| Badges | Per expansion: number of Expansion badges, `x` for the Extreme and the Savage badge of the current tier; story arc, Dawntrail, BLU blocks the same way | Staff, from the study history sheet |
| Raid streaks | `S1`–`S6` (how often each streak length was reached), `CS` (current streak, e.g. `6-21`), cells coloured by streak | Staff, by hand |
| Streak freezes | `SF` (regular), `UF` (unique) | Staff and the `!raidstreak_sf` / `!consume_sf` commands |
| Study group Exp | `SG` | Staff, at a study group's finalization |
| Cakeday | `BD`, the day the member became a Visitor, found as their first post in `#campus` (`01.01.1970` = unknown) | Staff, by searching Discord |

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
| Streak freeze | A month with 0 or 1 participation uses one (regular before unique); the streak only ends when none are left. `SG`, `B` and `BT` months aren't active months (from the data, see below). A cakeday while a streak runs adds a regular freeze, and regular freezes stop at 6; unique ones have no cap (the April 2022 announcement, confirmed by the sheet) |
| Unique streak freeze | +1 for a promotion to Adept, Magister or Archon (the workflow says "Adept or higher", the template gives none for Prime and Eternal) and for each story-arc badge |
| Badges | All Extremes of an expansion: +6. All its Savage: +12. Both: an Expansion badge (+6), and the two reset to be earned again in the next tier. Story arc: Zodiark (all ARR–EW Extremes, +6), Hydaelyn (all ARR–EW Savage, +12), Starbird (both, +6), each with a unique freeze. BLU: a mask badge per expansion (+9) and the Morbol combo for ARR and HW (+6). Earned in the course or in a study group |
| Cakeday | The *n*th anniversary of becoming a Visitor gives 3·*n* Exp ("active players"). Not the server join: the time before finishing onboarding doesn't count (staff, 30 October 2026). Leaving and rejoining the server starts the count again (April 2022). Members marked inactive get no cakeday post and no profile update (staff, 30 October 2026), and neither do demotion candidates. The posts go by calendar anniversaries, from the Promotion Monday up to the day before the next one; an anniversary on the next Promotion Monday is next month's (the October 2026 post) |
| Promotions | See below |
| Demotion | An Initiate with at most one participation in the last six months and no study group Exp becomes a Visitor (the Demotion Guide, May 2026); a DM explains it, and the old rank comes back on returning. An older helper sheet (2023) applied it to every student rank. An Initiate whose first participation falls in those six months is new, not inactive: the October 2026 post lists such an Initiate's cakeday and level-up (question 15) |
| Inactive | No participation and no study group month in the last 9 months: marked inactive (the October 2026 post lists exactly the members with a participation in that window). The June 2026 update neither listed their cakedays nor updated their profiles, though the sheet still adds their cakeday Exp |
| Alumni cleanup | The `@Alumni` role is removed by rank and months away (Cleanup guide) |
| Study group Exp | Decision 24 in SETUPS_CONCEPT.md: the Drive guide's per-expansion amounts or the archive guide's 2/4/6 for 2–4/5–8/9–12 kills. The April 2022 announcement gives the Drive guide's version: Extremes 1/2/3 and Savage 2/4/6 Exp for taking part in up to a third, two thirds or all of the bosses killed, an Ultimate 4 |

Promotion criteria (Promotion Monday template):

| To | Exp | Needs |
|---|---|---|
| Disciple | +3 | ≥ 5 participations in total and ≥ 3 in the current month, or ≥ 10 study group Exp |
| Adept | +6, unique freeze | ≥ 20 participations in the last 3 months, over 33% in each of the last 2 months, 2 months since the last promotion; or ≥ 20 study group Exp |
| Magister | +12, unique freeze | ≥ 45 participations in the last 6 months, over 33% in at least 4 of them, over 50% in each of the last 2 months, ≥ 2 badges |
| Archon | +24, unique freeze | ≥ 100 participations in the last 12 months, over 33% in at least 8 of them, over 50% in each of the last 2 months, ≥ 3 badges with ≥ 1 Savage |
| Prime | +36 | ≥ 8 badges with ≥ 2 Savage, ≥ 15 months in tier 3 or higher averaging tier 4, 18 months since the last promotion, over 33% in each of the last 2 months |
| Eternal | +48 | ≥ 16 badges with ≥ 4 Savage, ≥ 30 such months, 36 months since the last promotion, over 33% in each of the last 2 months |
| Staff ranks | | A simulated student rank until Prime and Eternal, which also need 24 and 60 months as a full staff member |

Staff get their student ranks "simulated": staff are assessed by the same rules, and the post marks them so. A badge
count includes Expansion badges as three: ARR's Extreme badge, its Coils badge and the full ARR badge make 3, not 2
(staff, 30 October 2026). "Each of the last 2 months" holds for the 50% criteria too, read the same way as the 33%
answer.

### The monthly workflow

The Study Feats Workflow guide (August 2025, partly replaced by a "new workflow" in November 2025 that uses a Django
application and bot commands) has these steps. The last column is what the site would make of each step.

| # | Step | Today | With the site |
|---|---|---|---|
| 0 | Preparation | Fill missing Discord and Lodestone IDs and cakedays by command, copy the sheet, reload the Django application | Not needed: the member register is the database |
| 1 | Study badges | Mark badges in the sheet from the study history; collect the IDs for the post | Computed from the recorded clears; staff confirm |
| 2 | Cakedays | Search each player's first `#campus` post, update points, freezes and Exp roles, mark long-inactive players | Computed; the date is entered once per member, or recorded when the member gets the Visitor role (question 6) |
| 3 | Raid streaks | Colour cells, raise `S1`–`S6`, add freezes, add roles for new streaks | Computed |
| 4 | Promotions | Check the criteria by eye with filters, set rank, colour rows, add unique freezes | Candidates computed; staff confirm each |
| 5 | Raid activity | Edit the column limit in formulas and the ranges of conditional formatting rules, collect IDs by colour | Computed; nothing to edit |
| 6 | Update profiles | Look up each member in Server Settings → Members and change their roles (level, badges, cakeday, rank; Exp and freezes had roles until recently) | A list of role changes per member (phase 1); the bot makes them (phase 2) |
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
- **Streak freezes** (added 30 October): with the two freeze rules of the April 2022 announcement (a regular freeze
  for a cakeday while a streak runs, at most 6 regular freezes), the replay gives the sheet's `SF` for 1,210 members
  instead of 1,149, and for 148 of the 162 with a streak going instead of 84. `S1`–`S6` then match for 1,178. No
  member has more than 6 regular freezes in the sheet, and 25 have exactly 6. Giving the cakeday freeze without a
  running streak matches worse (1,130). In the checker the members whose streak counts differ from the replay drop
  from 55 to 45.
- **Promotions**: on the Promotion Mondays of March, April, May and June 2026, all 37 members promoted that day meet
  the criteria above, evaluated with the months up to that day. Only a handful of members who were not promoted meet
  them too (0–3 per rank and month; some may be staff, whose ranks are simulated).
  - The promotion is checked as if the member had the rank below until that day.
  - An Expansion badge counts as three badges: its Extreme badge, its Savage badge, and itself.
  - Reading "over 33% in the last 2 months" as each month (staff's answer) keeps every promotion; it only drops two
    members who would have met the criteria with both months together but weren't promoted (rerun 30 October).

Found along the way, each worth fixing whatever happens to the site:

| Finding | Effect |
|---|---|
| One member's cakeday is `31.12.1969` instead of the placeholder `01.01.1970` | Cakeday points count 56 years: 4,788 Exp, and the level shows `#N/A` |
| The tier 6 threshold is `≥ 75%`, the post says "over 75%" | 210 month cells sit at exactly 75% (12 of 16 raid days, for example). Staff confirmed the sheet: exactly 75% is tier 6, so the post's wording is what's off |
| Cakeday years are 365-day blocks, not anniversaries | 3 members currently count a year early; the highlighting rules use 365, 730, 1095, 1460, 1826 days. The posts use calendar anniversaries, so the sheet's cakeday Exp runs a day or two ahead of them for some members (7 in the export of 29 October) |
| The BLU block has columns for the ARR and HW mask badges only | The SB (Red Mask) and ShB (Purple Mask) badges of the template, listed in the current post too, aren't counted in Exp |
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
6. **Discord changes.** A list per member of the roles to add and remove: rank, level, badges, cakeday. Staff tick each change as done; the next month starts from what was ticked. With the bot (phase 2), one click
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
- `rank_changes` keeps every promotion and demotion with its date and who confirmed it (question 8).
- A `feat_rules` table holds the thresholds.
- A `feat_roles` table maps each feat to its Discord role by role id: the badge roles share names ("x 1", "x 2"), so a name can't find them.

## Phase 0 as built (2026-10-29)

`#/feats` on the MVP branch (`claude/setups-mvp-712822`, not merged), described in `tools/scorecard/README.md` under
"Study feats (phase 0)". A staff member picks a credits workbook export; the browser reads it and shows the month's
posts, promotion candidates with each criterion, the members' month, the cells to change in the sheet, the role
changes per member, and the rows that don't add up. Each question still open below is a setting on the page,
defaulting to what the sheet does today; the answered ones are fixed rules.

Checked on real data:

- **The export of 29 October.** Exp is recomputed from its parts, and it equals the sheet's for every member. The
  exception is the one with the 1969 cakeday.
- **The copy staff made on 8 June 2026.** Its month was replayed:
  - Every member promoted that day meets the criteria for their new rank.
  - 61 of the 76 members on that update's profile list come out as level-ups, and 12 of the other 15 had badges or
    study group Exp entered during the update.
- **Dormant members.** The June update skipped the cakedays and profiles of members away for over a year (83 that
  month). So the page leaves out members without a participation for 9 months, the workflow's "inactive", and still
  counts their Exp.

What the earlier code left behind:

- **The Django application and the other code base aren't reachable.** Neither repository is public any more.
- **The February 2026 database dump.** It holds the sheets' data, not study feats: members, characters, monthly
  credits, duty clears with a reclear tier. Its duty list says which duties count toward a badge:
  - All Extremes and Savage turns of each expansion count, the Second Coil included.
  - Unreals, Urth's Fount, Cape Westwind and The Great Hunt (Extreme) don't.
  - Clear kinds: MIL, MIL Echo, Sync, Sync Echo, Normal MIL, Progress, eligible for reclear.

  That is the list phase 1 needs to find badges from clears. The dump also holds an API keys table, and like the
  service account file it sits in a shared Drive folder.
- **A role list from December 2024** in the same Drive folder, since replaced (see "The server's roles" below):
  - a role per study level ("[Level 24] Natural Snake"; past 48 "[Level Cap] Sun" and "Star");
  - Exp as digit roles ("x 1k", "x 600", "x 10", "x 3");
  - regular and unique streak freeze count roles;
  - badge roles per expansion with a count (Extremes, Raid, Composite);
  - story arc, BLU, cakeday (1–5) and anniversary roles.

Not in phase 0:

- Badges, which the export can't show as new. Staff add them to the post by hand.
- Staff ranks.
- The anniversary event.

## The April 2022 announcement

"The Long Read - Study Trophies Rework" (a locked thread on the Syncademy server, 8 April 2022) introduced Study Exp,
monthly activity tiers, raid streaks, streak freezes and Expansion badges. Read on 30 October 2026, against the sheet:

Still true, and new to this concept:

- **Cakeday freezes**: every cakeday gives a regular streak freeze. The sheet's `SF` shows it counts only while a
  streak runs (see "Checked against the data"). The checker adds it.
- **The freeze cap**: regular freezes stop at 6, unique ones have no cap. The sheet agrees, and the checker caps them.
- **Rejoining**: a member who leaves and rejoins the server starts their cakeday count again.
- **Study group Exp** as the Drive guide has it, plus 4 Exp for an Ultimate (see the rules table).
- **Badge names**: ARR Comet (Extremes) and Dragon (Savage), HW Ishgard and Robot, SB Blood and Omega, ShB Wave and
  Galaxy; Expansion badges use the MSQ symbols. Useful for question 7.
- **Profiles**: the freeze count roles show only while a streak runs. These roles are gone today.

Superseded since (the current post below and the sheet agree):

- **Levels** were then 6 per moon tier at 6, 12, 18, 24, 30 Exp each. Today's tiers have 8 levels each.
- **Activity tiers** were labelled 25/33/50/66/75% with "~4/~6/~8/~10/~12 of 16". Today they read 37.5% and 62.5%,
  which are those counts.

## The current post (September 2026)

"Community Benefits - Details" (a thread on the Syncademy server, posted 15 September 2026) is the public description
in force. It agrees with this concept on the month (2nd Monday to 2nd Monday), the activity tiers (25, 37.5, 50, 62.5,
75%+), the raid streaks, and the freeze rules including the cakeday freeze and the cap of 6. It adds or settles:

- **The level table**: tiers of 8 levels at 6, 12, 18, 24, 30, 36 Exp per level, up to level 48 at 1,008 Exp. These
  are the thresholds the checker uses (its tests check 6, 48, 60, 144, 162, 288 and 1,008).
- **Backups**: a member benched in a backup group of the preliminary setup who is still on voice at raid start gets
  the participation.
- **Badges**: EW is Moon (Extremes) and Panda (Savage). The story-arc badges each give a unique freeze. A study group
  can earn badges for one expansion. BLU has badges for ARR, HW, SB and ShB: ARR and HW make the Morbol badge, SB and
  ShB a combination badge not yet named. No Dawntrail badges are listed (question 7).
- **Study group Exp**: for clearing at least two bosses and up to a third, two thirds or all of them, Extremes 1/2/3,
  Savage 2/4/6, an Ultimate 4. This is the public rule for decision 24.
- **Ranks**: the same criteria in short form ("2 months of high participation" for Adept). The role names are
  "Archon Prime" and "Archon Eternal". An Initiate is made after the first participation.
- **Staff ranks**: staff ranks are simulated until Prime and Eternal. Those also need 24 months as a full staff member
  for Prime, and 60 in total for Eternal.
- **Cakedays**: still "as a @Student" (question 13).
- **The cross-world linkshell**: entry needs an active raid streak, more than one participation a week on average
  over the last three months, and the top place on the waiting list (highest average over those three months). Each
  linkshell has 64 slots, and members are checked periodically (decision 23 in SETUPS_CONCEPT.md).

## The monthly updates in `#announcements`

Every month's update (read on 30 October 2026, back to 2019) gives the month's statistics, the Promotion Monday post,
and since 2025 a link to a Study Feats thread. Compared with the export of 29 October:

- **The statistics** (question 10): "participations on average per week" is the month's participations ÷ (raid days ÷
  4), and "unique players" the members with at least one participation. For August, September and October 2026 both
  match the sheet exactly; older months drift as the sheet was corrected and cleaned since. The checker now shows the
  weekly figure on its Players tile.
- **Promotion Monday, 12 October 2026**: the 12 members promoted (1 Magister, 2 Adepts, 9 Disciples) all meet the
  criteria as the checker reads them, with "each of the last 2 months".
- **The Study Feats thread of October 2026**, against the checker's month (matched by name; 11 of the 146 names in
  the activity tiers aren't found in the sheet under that name):
  - Activity tiers: the same number of members in each tier (13, 12, 12, 27, 27, 55).
  - Cakedays: all 17 the same, after three changes the post showed: calendar anniversaries, the next Promotion
    Monday counted as next month, and no cakeday for demotion candidates or for members without a participation or
    study group month in 9 months (the checker had counted any study group Exp ever).
  - Raid streaks: the same for most members. The post has six streak awards the replay doesn't: members whose
    history the checker already flags as differing from the sheet's streak counts. The September case of question 14
    is in the checker only.
  - Level-ups: 73 of the post's 83 matched names agree. The other 10 are profiles one level behind: the post's "from"
    level is lower than the Exp before the month gives, so staff caught up an earlier missed level. The checker can't
    see the level a profile shows; phase 1 keeps it, and the bot can read it in phase 2.

The thread and the comparison scripts are in `scratch/setups/feats/` (the thread holds real names and stays local).

## The server's roles (30 October 2026)

Server Settings → Roles lists 226 roles. For study feats (a copy with role ids is in
`scratch/setups/drive/roles_2026-10-30.json`):

- **Levels**: "[Base Level] Grey Portal", then "[Level 1] Green Portal" to "[Level 8] Green Portal", and on in tiers of
  eight: Yellow, Orange, Red, Purple, Blue up to "[Level 48] Blue Portal", then "[Level Cap] Star" and "[Level Cap]
  Sun". The December 2024 names ("Natural Snake") are gone. The checker now writes these names.
- **No Exp and no freeze roles.** The digit roles for Exp and the streak freeze count roles no longer exist; the
  monthly update now points members to `/syncplate` in `#sync-plates` to see their achievements. The checker no
  longer lists changes to them; the freeze counts still go into the sheet.
- **Badges**: one role per badge and count, all named "x 1", "x 2", and so on, told apart by their icon and their
  place under the section headers ("[DO NOT USE] HW Badges" and so on). Per expansion the order is Expansion badge
  (MSQ symbol), Extremes, Savage. ARR goes up to x 4 (Expansion), x 5 (Comet), x 4 (Dragon); HW to x 4 each; SB to
  x 3; ShB and EW to x 2. The story arc roles (Starbird, Zodiark, Hydaelyn) and the cakeday and anniversary roles
  have no names at all.
- **Dawntrail badges exist**: an Expansion role and two badge roles (Extremes: 24 members, Savage: none yet). Their
  names don't show in the role list.
- **BLU**: three roles, a combination badge and two masks; none for SB and ShB yet.
- **Cakedays**: six roles, 1st to 6th year (230, 107, 74, 54, 23 and 12 members).
- **Ranks**: each student and staff rank has a "(Supporter)" twin for server supporters, so a promotion swaps
  "Adept (Supporter)" rather than "Adept" for them. Staff ranks have Prime and Eternal roles of their own ("Tutor
  Prime"), as do the student ranks ("Archon Prime", "Archon Eternal").
- **The staff tools** have roles too: "Feats Calculator", "Setup Creation", "Raid Participation", "Calendar
  Maintenance", and bots per task ("Plates Bot", "Linkshell Bot" and others).

## Answers from staff (30 October 2026)

| Question | Answer | What it changes |
|---|---|---|
| 1. Tier 6 at exactly 75%? | Yes, exactly 75% gets the top tier | Nothing: the sheet already does this. The post's "over 75%" is the wording to fix |
| 2. "Over 33% in the last 2 months": together or each? | Each month on its own | The checker tests each month. Taken to hold for "over 50%" (Magister, Archon) as well |
| 3. An Expansion badge counts as three? | Yes: ARR's Extreme, Coils and the full ARR badge are 3 badges, not 2 | Nothing: the checker already counts this way |
| 4. `SG`, `B`, `BT` months in streaks | `SG` means the member took part only in a study group that month. `B` and `BT`: not known, deduce them if possible | See below |
| 5. Cakedays only for members not marked inactive? | Yes | The checker leaves members without a participation for 9 months out of the cakeday post and the profile updates as a fixed rule. Their Exp still counts their cakedays, as the sheet does |
| 6. Is the `#campus` post the cakeday on purpose? | Yes: the cakeday counts from joining as a Visitor, not from joining the server, so the time before finishing onboarding doesn't count | See below |
| 8. Keep each promotion with its date? | Yes | Phase 1 keeps a `rank_changes` table instead of one date column |
| 11. Run phase 0 next to the update on 9 November? | Yes | See below |

**Question 4, from the data.** The export of 29 October holds 21 `B` and 5 `BT` cells:

- **`B`**: the sheet's own legend (below the member rows, next to "SG = Study Group") says "B = Visitor backup after
  start". 20 members have one. For 19 of them it's their first entry (13 have nothing else), and none sits next to an
  active month. So a `B` never changed a streak, and it doesn't add to participations or activity tiers either.
- **`BT`**: not in the legend. It occurs for two Magisters, once in the middle of an active stretch (spring 2022) and
  four months in a row (late 2022 to early 2023), and not since.
- **For streaks**, the sheet's `S1`–`S6` of those two members rule out counting `BT` as an active month: that would give
  one of them a 9-month streak the sheet doesn't have. Whether a `BT` month bridges a streak or uses a freeze can't be
  told: both readings give the sheet's numbers.
- **`SG` months** aren't active months either: counted as active, the streak replay matches the sheet for 1,129 members
  instead of 1,169.

So for the rules: `SG`, `B` and `BT` are months without course participations. `SG` and `B` simply aren't active;
`BT` stays a setting ("neither extend nor end a streak", the default, or "a weak month") until someone remembers what
it stood for. With no `BT` since early 2023, it only matters when replaying old history.

**Question 6, the join date.** Discord doesn't keep the date a member got a role: the member data has only the server
join date, and the audit log keeps role changes for 45 days. So:

- the dates in the `Cakeday` column are imported once, as they are;
- in phase 1, the site records the date when staff make a new member a Visitor, and staff can correct it;
- in phase 2, the bot records the day it sees the Visitor role given, and on its monthly run it can fill gaps from
  the audit log, which still covers the month (this needs the View Audit Log permission).

The manual search in `#campus` then ends for new members.

**Question 11, 9 November.** Staff run the usual update, and phase 0 runs on a fresh export of the workbook taken
before they change it. Then compare the results:

- the level-up list;
- the streak awards and freezes;
- the cakedays;
- the promotion candidates;
- the post texts.

Every difference is either a rule to settle or a slip in the sheet. Remember to export before the update: phase 0
reads the month from the workbook as it stands, and an export taken afterwards already holds the update.

## Questions still open

7. **Profiles**: the server's roles answer most of this (see "The server's roles"). Still open: what the Dawntrail
   badges are called, and when a member gets "[Level Cap] Star" or "[Level Cap] Sun" past level 48.
9. **The Django application**: does it still run, and who has its code? This is part of decision 19.
12. **`BT`**: does anyone remember what it stood for (perhaps from the time of the Azure & Omega chapter, 2022), and
    did such a month keep a streak going?
13. **Cakedays for Visitors**: the public posts (2022 and September 2026) give cakedays to Students. The sheet counts cakeday Exp for
    Visitors too (421 of them), and the checker lists an active Visitor's cakeday. Should Visitors get it?
14. **One September streak** (row 124 of the export): a cakeday freeze would have carried this member's streak to 9
    months in September, and the sheet ended it instead. Was the freeze missed, or does it not apply there?
15. **New Initiates and demotion**: the checker no longer counts an Initiate whose first participation falls in the
    last six months as a demotion candidate (the October post lists one such Initiate's cakeday). Is that the rule?
    It removes 21 to 42 candidates a month from the strict reading.
