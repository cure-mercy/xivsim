# Concept: course calendar, raid setups and bookkeeping

Status: draft, 2026-10-29. Nothing built yet. Most decisions are answered (see the end); the bot, the hosting and
the pitch to the server owner come first.

## Goal

The site takes over what Syncademy does today in Google Sheets, by hand in Discord, and with the bot:

1. **Calendar entries.** Staff write the entries for `#course-calendar` on the site, and the site posts them to Discord,
   adds the signup reactions, and removes them the day after the event. Entries that follow a plan (the Friday and
   Saturday rotations, Sprout Monday, the Wednesday and Sunday progression series) can be prepared and posted
   automatically.
2. **Bookkeeping.** Who has cleared which duty, how (MIL, synced, Echo), how often (reclears), and how often each member
   took part in an event.
3. **Setup creation.** For each event, turn the Discord signups into groups of 8 that follow the priority rules,
   let a setup creator adjust them, and produce the setup announcement.
4. **Closing the loop.** After the raid, the setup creator or raid lead records who played and who got the kill, which
   updates the bookkeeping that the next setup reads.

It is for staff, like the rest of the site: everything here sits behind the staff login (ACCESS_CONCEPT.md, "Change:
staff only"). Members don't log in for it; they keep signing up on Discord.

## Where things stand

| Source | Holds | How it's kept |
|---|---|---|
| Participation sheet (public link) | Tabs Extreme Trials (61 duties), Raids (75), Blue Mage (80). One row per player (about 1,200, 1,100 and 150), one column per duty. A letter per cell: `M` MIL, `m` MIL + Echo, `S` synced, `E` synced + Echo, `N` normal MIL, `-` progress, `x` eligible for reclear. The letter's font colour is the member's tier (1st to 6th) for that expansion: completing both badges of an expansion moves them to the next tier, and its duties become `x`. | By hand after each raid, following the participation cheat sheet (a staff Google Doc) |
| Course Credits workbook | The member register on `Participation` (about 1,250 rows): character name, Discord ID, Lodestone ID, data center, world, rank (Visitor to Eternal), promotion date, cakeday, expansion progress, monthly participation counts, and formulas for study experience and level. `Rotation`: the plan of each Friday and Saturday rotation season, by weekslot and timeslot. `Templates`: setup announcement layouts. | By hand, formulas |
| Setup Creation Helper | `Staff-Duties (e)`: staff availability per weekday (`0`, `1`/`2` timeslot priority, `b` backup, `x` not available, `?` signs up as player) and a trainee flag. `Bot_Setup`: the signups the bot wrote. `Setup (e)`: up to 4 groups of 8 plus backups per destination, a letter per player (`P`, `K`, `-`, `?`), raid lead icons, missing signups. `Template (e)`: the announcement. | The bot fills `Bot_Setup`; setup creators move rows with ✂️/📋 (Apps Script) |
| Discord `#course-calendar` | Information posts at the top (raiding procedure, knowledge markers such as Semi-Blind or Clear Attempt, star rankings, duty groupings), then the overviews: Sprout Monday (a dated list), Friday and Saturday Rotation Overview per season part (completed, current weekslot, upcoming), the Wed+Sun progression status, break times. Below them, one entry per event night: a header message (`#1420: Friday Rotation Season 11 Part 3: Weekslot 6`, date, Server Time window, destinations with star difficulty, notes) and one message per destination. | Staff write each post by hand and send it to the bot with a Discord command; the bot posts it as "Syncademy" |
| Signups | Reactions on each destination message: ✅ signed up; `tank_role`, `pure_healer_role`, `barrier_healer_role`, `melee_role`, `ranged_role`, `caster_role` (BLU nights: `healer_role`, `dps_role`) for the roles a member can play; `:online:` for "okay with being backup", or the less preferred of two parallel destinations. | The bot reads the reactions when a setup creator runs its command |

Kinds of event night:

- **Parallel**: two destinations at the same time (the Wednesday and Sunday progression series). A member plays at most
  one of them.
- **Sequential**: two timeslots one after the other (Friday and Saturday rotation, 18:00 then 20:00 ST). A member can
  play both.
- **Single**: one destination (Sprout Monday, every other Monday).
- **Special**: Community Choice weekends, the anniversary week; breaks (spring, summer, winter) have no entries.

Raid times are given in Server Time (UTC). They follow European local time, so they move by an hour when the clocks
change. The entries of the first week after a change carry a Wintertime or Summertime warning, and a reminder post goes
out before it.

**The current bot is "Crystal Exarch"**, not the 2021 `syncademybot` (which had a database with students,
participation and kill history, a Discord login, `add_reactions` and the reaction parsing). What the staff guides show
of it:

| Command | Does | Needs |
|---|---|---|
| `/send channel_link:…` | Posts the text it is given as the bot; the first line becomes the title of a new thread; keeps a backup of the text and its images on its server | the `@Send` role |
| `/edit message_link:…` | Edits one of its posts, with the same backup | the `@Edit` role |
| `!parse_reactions [link 1] [link 2]` | Reads the signups of two calendar messages into the Setup Creation Helper | |
| `!template participation / Fellowship / initiate / badges / strike removal / player strike / visitor` | Writes the participation run's messages for the names given | the `@Send` role |
| `/channel_to_text` | Archives a channel as a text file (study groups) | |
| `!fill_empty_ids`, `!fill_empty_cakedays`, `!raidstreak_sf`, `!consume_sf` | Study feats upkeep in the credits sheet | |

The study feats workflow also mentions a Django application that reloads its data from the credits sheet
(`…/reload/`, `…/studyfeats/`). Both are run by the new server owner. The previous owner and their developer have left,
so nobody maintains the code, and Syncademy is looking at alternatives; this concept is one. The site therefore talks
to Discord itself and takes over Crystal Exarch's jobs one area at a time (decision 19).

**The staff guides** live in the "Syncademy's Archive" Discord server: per area (Course Calendar, Setup Creation,
Participation, Linkshell Network, Study Feats, Onboarding Process, Study Groups, Cleanup, Community Finder) a
`templates`, a `guides` and a `links` forum, plus `bot-commands` and `other-guides`. The Linkshell, Onboarding and
Community Finder forums were empty when read on 2026-10-29.

## What the site adds

| Page | For | Replaces |
|---|---|---|
| `#/calendar` | Every entry: drafts, scheduled, posted, removed. Create, edit, preview, publish, remove. Upcoming entries show signup counts and setup status | Writing posts by hand, the bot's posting command |
| `#/event/<id>` | One entry: its text and Discord status; signups (fetched from Discord); the proposed setup, editing, warnings, the setup announcement; after the raid, attendance and kills | `Bot_Setup`, `Setup (e)`, `Template (e)` |
| `#/seasons` | The plans behind the series: rotation seasons by weekslot, Sprout Monday's list, the progression series' current status, breaks. They generate entries and the overview posts | Credits `Rotation`, the overview posts kept by hand |
| `#/members` | Search members by character or Discord name; a member's page shows their characters, rank, participation count, and their clears and progress per duty | Credits `Participation`, a row of the participation sheet |
| `#/duties` | The matrix as in the participation sheet, one tab per kind (Extreme Trials, Raids, Blue Mage), filtered by expansion or member; one duty's column: who needs it, who has it, how often | Participation sheet |
| `#/staff` | Staff availability per weekday, trainee flag; the couples and friends list; the strength weights | `Staff-Duties (e)`, the friends sheet |

(`#/rotations` is taken by the job rotations, hence `#/seasons`.)

## Calendar entries

### Writing an entry

An entry is a form, not free text, so the site can post it, read its signups and build setups from it:

- **Series and number**: the series (Wednesday progression, Friday rotation, Sprout Monday, …) fills in the defaults;
  the number (`#1423`) continues from the last entry.
- **Date and time**: start and end in Server Time. The form shows the local time next to it and adds the Wintertime or
  Summertime warning on its own to the entries of the first week after a clock change in Europe/Berlin (decision 12).
- **Destinations** (one or two): the duty (from `duties`, which gives its name, expansion emoji and star difficulty),
  MIL or SYNC, the knowledge marker (Full Blind … Last Call), the start time for a sequential night, and a note
  (for example how far a Partial-Progress goes, with raidplan slides).
- **Notes**: free lines under the header (the P12S warning, the BLU spell rule, the channel to discuss in), with
  saved snippets per series so they don't have to be typed each time.
- **Signup reactions**: six roles, three roles (BLU), or none (information posts). Sprout Monday and Raiding Seminars
  add `:pve_mentor:`, for members who want to try raid leading with a staff member at their side.

The preview shows the post as Discord will: the custom emojis come from the server's emoji list (cached from Discord,
`emojis`).

**The layouts are the staff templates** (Course Calendar → templates), one per kind of entry, each in a winter and a
summer version. The site keeps them as they are, with their placeholders (`DAY`, `MONTH`, `DUTY_1`, `ACRONYM_1`,
`DIFFICULTY_1`, `RAID_KNOWLEDGE`, …) filled from the form:

| Template | Winter (ST) | Summer (ST) | Shape |
|---|---|---|---|
| Wednesday Progression Raid Series | 19:00–22:00 | 18:00–21:00 | Two parallel raid series (`:marker_1:`, `:marker_2:`), up to three notes (`:chain_1:`–`:chain_3:`), the `:online:` hint |
| Sunday Progression Raid Series | 18:00–21:00 | 17:00–20:00 | As Wednesday |
| Friday / Saturday Rotation Season `##` Part `#`: Weekslot `#` | 18:00–22:00 | 17:00–21:00 | Two timeslots, 18:00 and 20:00 (summer 17:00 and 19:00), the second with the current content's minimum item level |
| BLU additions | | | `:blue_mage:` destination, the spell rule with its link |
| Sprout Monday Season `##` Part `#`: Weekslot `#` | 19:00–21:00 | 18:00–20:00 | One destination; synced first, then MIL + Echo or MIL; semi-blind; `:pve_mentor:` |
| Raiding Seminars Season `#` – Day `#`: `TOPIC` | 18:00–22:00 | | Like a rotation day with a details line and a presentation note; pre-filled entries per seminar day |
| Special events: Unreal trial, Alliance raid, Normal raid ("(Bonus) #xxxx: …") | weekday times | | Tuesday or Thursday; quest requirement, quest start and duty start lines for new content |
| Raid breaks: Spring, Summer, Holiday | | | Posted in the last raiding week before the break: last and first raiding day |
| Daylight saving: reminder post, first-week additions | | | The warning in the Date line and a note |
| Common additions | | | Raid guide note, raidplan note, (partial-)progress note, links to the duty groupings, spoiler tags |

So the site doesn't invent a layout: an entry from the site is the template, filled in.

### Publishing, editing, removing

Publishing (a button, or at the scheduled time) posts the header and one message per destination to
`#course-calendar`, then adds the signup reactions to each destination message in a fixed order (✅, the roles,
`:online:`), as the old `add_reactions` did. The site stores each message's ID, so signups are read from exactly those
messages, without parsing the channel.

- **Editing** a posted entry edits its messages in place; reactions stay.
- **Removing** happens at 06:00 ST the day after the event, on its own: the site takes a last copy of the signups,
  then deletes the Discord messages. Only the messages go; the site keeps the full history of every entry, with its
  signups, setup and attendance. A removal by hand is possible at any time, with a confirmation.
- **Status**: `draft` → `scheduled` (has a publish time) → `posted` → `removed`. Failures (a missing permission, an
  emoji that no longer exists) show on the entry and in the audit log.

### Plans and automatic entries

A **series** knows its weekday, its time window in local time, its layout, its notes, and when its entries go out:
7 days before the event. For each upcoming date, the series takes its content from its plan:

| Series | Plan | An entry's destinations come from |
|---|---|---|
| Friday rotation, Saturday rotation | A season part (`Season 11 (Part 3)`): numbered weekslots, each with a 1st and 2nd timeslot duty, plus markers for breaks, the anniversary and Community Choice | The next weekslot; the plan's markers skip or replace dates |
| Sprout Monday | A dated list (17.08. Byakko, 31.08. T8, …, "Sprout's Choice!") | The list entry for that date |
| Wednesday, Sunday progression | Two raid series running in parallel, each with its current duty and how far the progress goes | The current duty of each series; the progress note is written per evening |
| Breaks | Date ranges (summer, holiday, spring) | No entries during a break |

The site creates the entry as a draft a day before it is due, and it goes out when a staff member publishes it. Fully
automatic posting (publish at its time unless someone holds it) is a switch per series for later; it starts off.

**Overview posts.** The Rotation Overview of a season part is the plan rendered as a post: completed weekslots,
the current one, the upcoming ones. After each weekend the site can move the current weekslot to completed and edit the
overview in place. The Sprout Monday overview and the progression status work the same way. The site's bot posts these
overviews once anew, since it can't edit Crystal Exarch's.

### The bot

The site talks to Discord through a bot token, never through someone's user account. **A bot application of its own**
is recommended, created by the server owner in the Discord Developer Portal under a **Team** with at least one other
admin. A bot's token can only be reset by whoever owns its application; with a team, it no longer depends on one
person, which is what went wrong with Crystal Exarch's developer leaving. Who creates it is decided after the site has
been pitched to the server owner (decision 5).

What a new bot can and can't do with Crystal Exarch's posts:

- It can't edit them: a bot edits only its own messages. The overview posts (rotation seasons, Sprout Monday,
  progression status, breaks) are posted once anew by the site's bot, and the old ones removed.
- It can delete them with Manage Messages in `#course-calendar`, so the entries Crystal Exarch posted are still removed
  the day after their event.
- It can read their reactions, so signups of entries posted before the switch still reach the site.

Both bots can run side by side while the areas move over: the site uses Discord's HTTP API only and holds no gateway
connection, and staff keep using Crystal Exarch's commands for whatever hasn't moved yet. Using Crystal Exarch's own
token instead is possible only if the server owner owns its application in the Developer Portal.

| Needs | For |
|---|---|
| View Channel, Read Message History, Add Reactions in `#roster-history` | Reading the screenshots; the ✅ under a confirmed one |
| View Channel, Read Message History in `#course-calendar` | Reading reactions |
| Send Messages, Add Reactions | Posting entries and their signup reactions |
| (editing and deleting its own messages needs nothing more) | Editing, removing its own entries |
| Manage Messages in `#course-calendar` | Removing the entries and overviews Crystal Exarch posted |
| Send Messages, Create Public Threads, Send Messages in Threads in `#course-organization` | Posting the setup and its course thread |

The bot doesn't send DMs, change roles or lock threads: the participation run only prepares those texts for staff
(decision 17), so it needs no Manage Roles or Manage Threads.

**Where it runs: a dedicated server** (decision 6; the hosting provider is still open). Calendar posting and removal run
on a schedule, and signups and screenshots are fetched when staff ask, so none of it may depend on your PC being on.
The server runs one service for all of it: the Discord jobs (posting, editing, removing, reading reactions and
screenshots) and the scheduler. The scorecard's analysis worker (`worker.py`, now in WSL) can move there too, so the
site needs no PC of yours at all. The database and the logins stay on Supabase; the server talks to it with the
service key, which lives only on the server, like the bot token.

A server also allows a gateway connection later: the bot would then see a reaction or a screenshot the moment it
happens instead of on the next poll. Polling every few minutes is enough to start with.

## Data model (Supabase)

New tables next to the existing ones. Every table gets row-level security: staff read and write (all staff, as all of
them have the Google files today; decision 7), the server writes with the service key, and every change goes to
`audit_log`.

```sql
-- members and bookkeeping
members        (id bigint pk generated, discord_id text unique, discord_name text, rank text, promoted date,
                cakeday date, joined date, visitor boolean, fellowship boolean, linkshell text /* N, Inv, Y, Inact, Decl */,
                cwls text, badges_opt_out boolean, note text)
participations (member_id bigint, day date, event_id bigint null, primary key (member_id, day))   -- one per day
participation_before (member_id bigint, month text /* Syncademy month */, n int, primary key (member_id, month))
revokes        (id bigint pk generated, member_id bigint, event_id bigint, at timestamptz, note text)
strikes        (id bigint pk generated, member_id bigint, event_id bigint null, at timestamptz, severe boolean,
                removed_at timestamptz null, warning boolean /* a visitor's warning, not a strike */)
badges         (member_id bigint, badge text /* 'shb-trials' */, tier int, awarded date, primary key (member_id, badge, tier))
tiers          (member_id bigint, expansion text, tier int, primary key (member_id, expansion))
characters     (id bigint pk generated, member_id bigint references members, name text, world text,
                lodestone_id bigint unique, main boolean)          -- alts and renames: several per member
duties         (id text pk /* 'o7s', 'p12s', 'hades-ex' */, name text, short text, kind text /* trial, raid, blu, ... */,
                expansion text, stars int, sort int, aliases text[])   -- names as Discord and the sheets write them
clears         (id bigint pk generated, member_id bigint references members, duty_id text references duties,
                mode text check (mode in ('M','m','S','E','N')), tier int, day date, event_id bigint null, source text /* sheet, site */)
progress_marks (member_id bigint, duty_id text, since date, source text, primary key (member_id, duty_id))  -- '-' in the sheet
staff_days     (member_id bigint, weekday int, code text check (code in ('0','1','2','b','x','?')), trainee boolean,
                primary key (member_id, weekday))
friends        (id bigint pk generated, members bigint[], note text)    -- couples and friends who play together
credits        (member_id bigint pk, exp int, level int, sg_exp int, streak text, streak_freezes int,
                unique_freezes int, cakeday_points int, raid_activity jsonb, updated date)   -- credits columns, edited by
                                                                                             -- staff until study feats are computed

-- calendar
series         (id text pk /* 'fri-rotation' */, name text, weekday int, local_start time, local_end time,
                kind text check (kind in ('parallel','sequential','single','special')), role_set text,
                notes text[], publish_days_before int, publish_at time, auto boolean)
plans          (id bigint pk generated, series_id text references series, title text /* 'Season 11 (Part 3)' */,
                overview_message_id text, active boolean)
plan_slots     (plan_id bigint references plans, pos int, label text /* '6', '🎉', 'CC' */, kind text /* weekslot, break, special */,
                duties jsonb /* [{duty, sync, mode, label}] per timeslot */, day date null, status text /* done, current, upcoming */,
                primary key (plan_id, pos))
breaks         (id bigint pk generated, name text, first date, last date)
events         (id bigint pk generated, number int unique /* #1419 */, series_id text, plan_id bigint null, plan_pos int null,
                title text, kind text, starts timestamptz, ends timestamptz, notes text[], warning text,
                status text check (status in ('draft','scheduled','posted','removed')), publish_at timestamptz,
                remove_at timestamptz, header_message_id text, error text, created_by uuid)
destinations   (id bigint pk generated, event_id bigint references events, slot int, duty_id text references duties,
                sync text /* MIL, SYNC */, mode text /* Semi-Blind, Partial-Progress, Clear Attempt, ... */, note text,
                starts timestamptz, message_id text, role_set text check (role_set in ('six','three','none')))
emojis         (name text pk, id text, animated boolean)          -- the server's custom emojis, refreshed from Discord

-- signups, setups, attendance
signups        (destination_id bigint, member_id bigint, discord_id text, confirmed boolean /* ✅ */, roles text[],
                backup boolean /* :online: */, fetched timestamptz, primary key (destination_id, discord_id))
setups         (destination_id bigint pk, status text check (status in ('draft','posted','done')), proposed jsonb,
                edited_by uuid, edited timestamptz)
setup_slots    (destination_id bigint, grp int /* 1..4, 0 = backup */, pos int, member_id bigint, role text,
                lead boolean, primary key (destination_id, grp, pos))
attendance     (destination_id bigint, member_id bigint, grp int, played boolean, result text check (result in ('kill','progress','none')),
                job text, source text /* screenshot, manual, fflogs */, recorded_by uuid, primary key (destination_id, member_id))
screenshots    (message_id text pk, channel_id text, posted timestamptz, poster_discord_id text, attachment text,
                destination_id bigint null, grp int null, status text /* new, read, confirmed, ignored */, read jsonb /* OCR rows */)

-- strength
ratings        (id bigint pk generated, member_id bigint, role text /* tank, healer, dps */, score int, note text,
                destination_id bigint null, by uuid, at timestamptz)
strength_parts (member_id bigint, role text, source text /* clears, speed, rating */, value real /* 0..1 */,
                confidence real, updated timestamptz, primary key (member_id, role, source))
```

- **The matrix is derived**, not stored: a member's cell for a duty is their best letter among the `clears` of their
  current tier for that expansion; `x` if they cleared it only in an earlier tier; `-` if there is a `progress_marks`
  row and no clear. A view (`duty_status`) gives the matrix the pages and the setup proposal read.
- **History from the sheets has no dates.** Imported clears get `day = null`, `source = 'sheet'`, the letter as
  `mode`, and the colour as `tier`. New clears come from the participation run with the event's date.
- **Participation** is the `participations` days, plus the credits workbook's monthly totals for the months before the
  site, imported once (`participation_before`).
- **Identity:** a signup carries a Discord user ID; the credits register has the Discord ID for most members, so
  signups match members directly. A signup from someone not in `members` yet creates a new member with their Discord
  name, marked as new. Character names (sheets, FFLogs) match through `characters`. Names that match nothing go to an
  import report for staff to resolve once, not to guesses.

## Signups from Discord

For an entry the site posted, it knows the destination messages. For each message and each signup emoji it lists who
reacted (`GET /channels/{id}/messages/{msg}/reactions/{emoji}`, 100 per page) and combines per person: ✅, roles,
`:online:`. It replaces that destination's `signups` rows and keeps `fetched`. Someone with roles but no ✅ is an
incomplete signup, shown as "Missing signup" as the sheet does now.

When it runs: on a button on the event page, every 15 minutes for entries in the next 7 days, and once more at the
event's start, which is the copy kept after the messages are removed.

Entries posted by hand before the switch have no stored message IDs. For those, the event page takes a message link,
or the site reads the channel and matches the header (`#<number>:`) and the destination messages under it.

## The setup process today

From the Setup Creation guide and templates (the day before the raid):

1. Post "Setup Started" in `#course-organization` (`@Student I've started with the setup creation…`) and make a thread
   of it named like `Course 814 - Wed. 03.01.2024`.
2. Copy the links of the two calendar posts and run `!parse_reactions` with them.
3. Message every incomplete signup (roles but no confirmation; the confirmation is ✅ or a clock emoji for a specific
   time) with the "Incomplete Signup" template.
4. Build balanced groups, **each with a raid leader in the first spot**, and copy them into the setup template.
5. Screenshot the preliminary setup and post it in `#roster-history` as `03.01.2024 (BLU A1-4S & O12S)`.
6. Edit the "Setup Started" message into the "Setup Template": time, both destinations with their knowledge
   expectations, the image link, the notes.
7. Post "Setup Completed" in the thread: a reminder that mentions the signed-up Initiates (or everyone), how late
   signups and absences work, and that staff track late signups with reactions (`:marker_1:`/`:marker_2:` for the
   series, 1️⃣–9️⃣ for the order).

The couples and friends list is kept in a sheet of its own and pasted into the helper's setup part. It moves to the
site (`friends`, edited on `#/staff`).

On the site, steps 2 to 4 are the proposal and the editing below. The site posts the rest itself (decision 13):

| Step | On the site |
|---|---|
| 1 | "Start setup" on the event page posts "Setup Started" and opens the course thread, named from the event |
| 3 | The incomplete signups are listed with the "Incomplete Signup" text ready to copy (DMs stay with staff, decision 17) |
| 5, 6 | "Post setup" draws the groups as an image, posts it in `#roster-history` with its title, and edits the "Setup Started" message into the setup template with the image |
| 7 | "Setup Completed" goes to the thread, mentioning the signed-up Initiates |

Late signups in the thread are read from its messages and the staff reactions (marker and order numbers) and shown on
the event page as a list in signup order.

## The setup proposal

For one event night, the site proposes groups; the setup creator edits them. The rules, in order:

**Hard constraints**

- A group is 8: 2 tanks, 2 healers (one pure, one barrier, where the destination has six roles), 4 DPS. A member only
  plays a role they reacted with.
- On a parallel night, a member is in at most one group across both destinations. On a sequential night, each timeslot
  is separate.
- Each group has a raid lead from staff who is available that weekday (`staff_days`), as one of the 8, in the first
  spot.
- Trainees, and members who reacted `:pve_mentor:` to try raid leading, go into a group whose lead is staff, where
  possible (decision 3). The page warns when one isn't, or when their staff lead isn't available.

**Priority** (who gets a spot when there are more signups than spots)

1. `P`: has progressed this duty (a `-`) and still needs the clear.
2. New: has no record for this duty at all, neither progress nor a clear.
3. `K`: has the clear, including `x` (cleared in an earlier tier).
4. Anyone who reacted `:online:` ("okay with being backup"), whatever their tier would be otherwise.
5. Tiebreaker inside a tier: fewer participations first, so spots spread.

Members with three strikes come after tier 4. The page shows each member's tier where the sheet showed `P`/`K`.

`:online:` also decides between two parallel destinations: someone with ✅ on both and `:online:` on one is placed in the
other first.

**How it's computed.** Taking players in priority order and checking roles one by one can lock a group: a flexible
player fills a tank spot early and the only healer-only player is left out. The proposal instead picks, tier by tier,
the largest set of players that still fits the role slots (a matching problem: players on one side, role slots on the
other, solved as a max-flow). Each tier is fixed before the next one is added, so a lower tier never pushes out a higher
one. Ties inside a tier go by participation, then by signup time. It runs in the browser, since 80 signups and 32 slots
take milliseconds.

Then:

- The number of groups is the number of full groups the role counts allow, at most 4 per destination, and at most the
  number of available raid leads.
- Friends who signed up together stay in one group where the roles allow it (`friends`, the old couples and friends
  list).
- Everyone not placed goes to the backup list, in priority order, with their roles.

**Balanced groups.** Priority decides who gets a spot; balancing decides who plays with whom. With two or more groups
on a destination, the proposal moves the chosen players between groups, swapping players of the same role, until the
groups are as even as it can get them. It never swaps a player out for someone on the backup list, so balancing can't
undo the priority. In this order:

1. **Support pairs.** The two tanks of a group together should be about as strong as the two tanks of every other
   group, and the same for the two healers: a veteran healer goes with a new one, not two veterans in one group and two
   new healers in the next. Who tanks or heals is only settled at the raid, so the proposal uses each player's strength
   in the role of their slot; for a flexible player, the page also shows their strength in their other roles, so the
   lead sees what a switch on the night does to the pairs.
2. **DPS.** The four DPS of each group add up to about the same.
3. **Experience.** The members with the kill (`K`, `x`) are spread over the groups rather than stacked in one.

The friends rule, the raid leads and the staff-lead rule for trainees stay as they are. The search swaps two players of
the same role between groups while that makes the spread smaller, in the order above (a few thousand tries in the
browser, instant). The page shows each group's tank pair, healer pair, DPS and `K` count next to it, so a setup creator
sees what a manual move does.

**The strength score**, per member and role (tank, healer, DPS). Detailed data such as the P12S scorecard exists for
one fight only, so the score is built from what the bookkeeping has for everyone:

| Source | What it gives | Starting weight |
|---|---|---|
| Clears | Hardest star difficulty cleared; how many clears at this duty's star level or above | 0.4 |
| Progress speed | Nights of progress before the kill, against others who progressed the same duty | 0.3 |
| Staff rating | A raid lead's rating after a night, per role: 1 to 5 with an optional note | 0.3 |

- Each source becomes a number between 0 and 1. It is pulled towards the middle (0.5) by how little it rests on:
  `0.5 + (value − 0.5) · n / (n + 3)`, with `n` the nights, clears or ratings behind it. One rating moves the score a
  quarter of the way, ten ratings almost all of it.
- The score is the weighted mean of the sources a member has. With none, it is 0.5, so new members don't count as weak.
- Clears and progress speed apply to every role a member plays, unless the job they played is known (from a
  screenshot's job icon, later); the staff rating is per role. So a strong tank who is new to healing gets their own
  healer score once rated or recorded as a healer.
- The weights are a first guess, set on a settings page. Staff can see what a member's score is made of and override
  it.

**Ratings** are optional: nobody rates today, but the event page offers it after a night (decision 15), per member
and role, seen by staff.

**Editing** replaces ✂️/📋: drag a player to another slot or group, or to and from backups. While editing, the page
warns, as the sheet's icons do now:

| Warning | When |
|---|---|
| Role short | A group lacks a tank, a pure or barrier healer, or DPS |
| Twice | A member is in two groups of a parallel night |
| Not signed up | The member has no ✅ for this destination |
| Wrong role | The member didn't react with the role of their slot |
| Lead | The raid lead isn't available that day, prefers the other timeslot (`1`/`2`), is backup-only (`b`), or is a trainee without a lead in the group |
| Skipped | A higher-priority member is on the backup list while a lower one has a spot |

**The setup announcement.** "Preliminary Setup", the time window, each destination with its groups and backups, as
`Template (e)` and the Setup Template have it. The site posts it to `#course-organization` the day before, with its
thread (see "The setup process today").

## After the raid

Today a staff member works through the participation cheat sheet (a staff Google Doc) after each raid day: participation, revokes,
strikes and warnings, new members, linkshell invites, the study history with its badges, messages to players and to
`#finished-tasks`, and the in-game fellowship. On the site this becomes the **participation run** of an event (below):
the site reads who played, works out what the cheat sheet's rules say should happen, and a staff member reviews and
confirms the list. Saving writes `attendance`, the participation, the study history (`clears`, `progress_marks`) and
the strike records. For a rotation entry, the plan's weekslot is marked done, which updates the overview post.

### Attendance from a screenshot

Today the raid lead takes a screenshot of the Party tab of the in-game Contacts window and posts it in
`#roster-history`, with the group's difficulty (MIL, synced, …). The bot watches that channel and reads the names off
the image with OCR. Each row has the job icon,
the character's name, the home world, and the duty. The person who takes the screenshot isn't on it, so it shows 7 of
the 8.

The raid leads keep doing exactly that. The site reads the channel with the same bot (Read Message History; no gateway
connection), every few minutes from an event's start until the end of the next day, and on a button on the event page.
Each new image is assigned to its event and group: the post's time falls in the event's window, the poster is the
group's raid lead in the setup, and the duty line on the image names the destination. The setup creators' preliminary
setup images go to the same channel, titled like `03.01.2024 (BLU A1-4S & O12S)`; those are told apart by that title
and by not having the Contacts window's rows. An image that fits no group waits on the event page for staff to place
it. Discord's attachment links are signed and expire, so the server fetches the image and hands it to the page. Today
the bot's OCR writes the names into a Google sheet and a staff member counts them in by hand; that sheet is no longer
needed. Once a screenshot is confirmed, the bot reacts ✅ under it, so the raid lead sees it was counted.

Pasting or dropping a screenshot onto a group on the event page does the same, for a lead who didn't post it.

The page reads the image in the browser with Tesseract.js when a staff member opens the event, so nothing depends on
your PC, and the image itself isn't stored:

1. **Prepare**: crop off the job-icon column, convert to grey, enlarge 3×.
2. **Read** each row: name and home world, and the duty line.
3. **Match** each name against the characters on that home world (`characters`), allowing for small reading errors.
   A match below about 0.8 counts as unknown.
4. **Check** the duty line against the event's duty, and the names against the group's setup.
5. **Show** the result as the checklist, filled in: matched members ticked; the uploader added as the 8th; backups who
   played instead marked as swapped; unknown names offered as "new member" or "link to an existing member". The raid
   lead confirms, then picks kill or progress.

Tried on three of your screenshots (21 names, 3 duties, light and dark window themes), with Node and Tesseract.js 5:

| | Read exactly | Matched to the register | Unknown |
|---|---|---|---|
| As taken | 13 of 21 (the icon gets read as a letter: `{@)2guarnot`, `Bristle`) | 20, scores 0.90 to 1.00 | 1 |
| Icons cropped, 3× | 18 of 21 (one image lost a first letter to the crop) | 20, scores 0.93 to 1.00 | 1 |

The one unknown was read correctly but isn't in the credits register: a new member, or one listed under another
name. The home world matters: matching the name among about 60 characters on one world instead of all 1,226 is what
makes misreadings such as `Aviis` or `hzi` safe. The crop should follow where the icon column ends in each image, not
a fixed width. The job icons could also be recognised, which would record the job each member played.

The screenshots are only read, not stored. The scripts of the trial are in `scratch/setups/ocr/` (git-ignored, as the
screenshots show real names).

### The participation run

Once the screenshots of an event are confirmed, the event page offers its participation run: every step of the cheat
sheet that follows from the data, as a list of proposed actions, each with what it is based on. Staff untick what
shouldn't happen, then confirm. Confirming writes the records on the site; messages to members and role changes stay
with staff (below).

**Who gets what.** From the setup (the preliminary roster with its backups), the confirmed screenshots, and two things
only staff know: who revoked in the event's `#course-organization` thread (the page lists the thread's messages next to
the names), and which unused backups were in voice chat on time.

| Case | Result |
|---|---|
| Played (on a screenshot, or the raid lead) | Participation |
| Backup, not needed, on the preliminary roster, in voice on time | Participation |
| Revoked in the thread | Revoke (`RVK` + 1) |
| Backup needed, absent, told us before the run | Revoke |
| Backup needed, absent, didn't tell us | Strike |
| Signed up and in the setup, didn't show (MIA), visitor without participations | Warning |
| MIA, anyone else | Strike |

**Participation** is one per member and day, counted in Syncademy months, which start on the second Monday of a
calendar month. The site keeps the days themselves (`participations`), so the month totals, "Participations (total)",
and the monthly columns of the credits sheet are views, not cells to increment.

**Strikes** follow the cheat sheet's rule: a strike is normal or severe, and successful participations since the last
strike wipe one off. The site stores each strike and computes the count and the progress towards removal:

| Strikes | Participations to remove one (normal) | (severe) |
|---|---|---|
| 1 | 3 | 5 |
| 2 | 5 | 10 |
| 3 | 10 | 15 |

Three strikes put a member on the backup bench by default: the setup proposal places them after tier 4, and the event
page says why.

**Follow-ups.** The run writes on the site what it can (participation, revokes, strikes, new members, linkshell status,
study history, badges, tiers). Everything that touches Discord or the game is a **text prepared for staff**, from the
staff templates with the name, Discord mention and numbers filled in, each with a copy button and a "done" tick that
the site remembers (decision 17):

| When | On the site | Prepared for staff |
|---|---|---|
| Warning | Warning recorded | DM to the player; post for `#finished-tasks` |
| Strike, or strikes removed | Strike recorded or removed | DM (the wording for a first, second or third strike); post for `#finished-tasks` |
| First participation of someone not in the register | New member, rank Initiate | Roles to change (`@Initiate` and `@Student` added, `@Visitor` removed); DM; post for `#finished-tasks` |
| Third participation, linkshell `N` | Linkshell status `Inv` | Post for `#linkshell-network`; the in-game invite |
| All trials or all raids of an expansion cleared | Badge recorded | Roles to add (the badge unless opted out, `Study Feats`, `Base Level 🌑`, `Study Trophy` where missing); DM; post for `#finished-tasks` |
| Both badges of an expansion | Its duties become `x` on the next tier | |
| After the run | Run marked done | Lock and close the course thread; `Participation & encounter history updated` for `#finished-tasks`; the fellowship message of the day with the next calendar entry, the recruitment text and a recap, in-game |

**The study history** keeps the sheet's rules: a member's letter for a duty is only upgraded, never lowered (savage
the order is `N` < `-` < `E` < `S` < `m` < `M`), and different groups of one event can
have done different duties. The **tier** is what the sheet shows as the letter's colour: completing both badges of an
expansion moves the member to the next tier for that expansion, and their duties there show `x` until they clear them
again. So the import reads the colour as the tier, not as a count of clears, and `clears` gets a `tier` column.

**What becomes unnecessary**: the duplicate checker (the site counts one participation per member and day), copying
template rows for new players, checking that formulas still work, the highlighting (it becomes filters on `#/members`:
"three participations, not in the linkshell", "has strikes", "Chaos: CWLS and linkshell differ"), sorting, and the named
version history (the database keeps every change, and the audit log who made it).

Sending these through the bot later would need Send Messages in `#finished-tasks` and `#linkshell-network`, direct
messages, Manage Roles and Manage Threads; for now the bot needs none of them.

Filling in attendance and kills from FFLogs reports is left out for now, perhaps for good (decision 8).

## Monthly study feats

Staff named this the most pressing part (2026-10-29), so it has a concept of its own:
[STUDY_FEATS_CONCEPT.md](STUDY_FEATS_CONCEPT.md), with the full chain of rules, checks against the workbook, and a
first phase that works on a workbook export before the rest of the site exists. The summary below is from the first
reading of the guides.

The credits move to the site (decision 9): rank, Exp, level, study group Exp, streaks and freezes, cakeday points and
raid activity are imported into `credits` and shown on a member's page.

The credits workbook's formulas and the Study Feats, Study Groups and Cleanup guides describe that monthly update. All
of it follows from data the site would already hold (participation days, clears, badges, members' dates):

| Part | Rule (from the guides) |
|---|---|
| Syncademy month | Starts on the second Monday of a calendar month ("Promotion Monday") |
| Raid activity | Per month: participations against the month's raid days; a month with one or no participation counts as insufficient |
| Raid streaks | Every 3 months of uninterrupted activity: +3, +4, +5, +6, +7, +9 Exp for 3 to 18+ months; every 6 months a Streak Freeze, which a month without activity consumes |
| Cakedays | Exp for the server anniversary, from the `#campus` join date |
| Study badges | Per expansion: an Extreme Trials badge and a Savage Raid badge; both make an Expansion badge, reset the two to "-", and start the next tier |
| Study level | Exp thresholds in tiers: 6 Exp per level (to 48), then 12 (to 144), 18 (to 288), 24 (to 480), 30 (to 720), 36 (to 1008) |
| Promotions | On Promotion Monday, by rank: badges (with how many Savage), months of high raid activity, months since the last promotion, activity over the last 2 months; `@Disciple` and `@Adept` also from study group Exp (10 and 20) |
| Demotion | An Initiate with at most one participation in the last six months becomes a Visitor (unless promoted through a study group) |
| Alumni cleanup | The `@Alumni` role is capped by Discord's thread mentions (~100): remove it from Visitors after 6 months, Initiates and Disciples by participations against months away (<10 & 3, <20 & 6, >20 & 12) |
| Study groups | Kills reported by the group update the study history; bonus Exp for 2–4, 5–8, 9–12 kills (2, 4, 6) |

Each of these ends in the same kinds of follow-up as the participation run: a list for staff to confirm, messages from
the staff templates, role changes, and the monthly update post.

## Moving over

1. **Import, once**, with a script next to `build_site.py` (`setups_import.py`): members and characters from the
   credits workbook, clears and progress from the participation sheet (with the font colours as tiers), strikes and revokes from the credits `MIA` and `RVK` columns,
   staff availability from `Staff-Duties (e)`, the current season plans from the credits `Rotation` tab and the
   overview posts. It prints an import report: rows whose names match nothing, members without a Discord ID, duty
   columns and plan entries without a duty. Nothing is published from the workbooks themselves: they hold member data
   and stay out of git (`scratch/setups/`).
2. **Side by side**: the sheets stay the record for a few weeks while the site runs alongside them; the import can be
   run again to catch up. The site can export the matrix as CSV in the sheet's layout, so the sheet can be pasted over
   if needed. Calendar entries can move first: the bot's own posting command keeps working until staff stop using it.
3. **Switch**: setup creators use the site; the sheets become read-only archives.

## Building it, step by step

| Step | What | Depends on |
|---|---|---|
| 0 | The pitch to the server owner; then the bot application and its team, the server and its hosting provider | Open decisions 5, 6 |
| 1 | Calendar: `#/calendar`, the staff templates, preview, publishing with reactions, editing, removal at 06:00 ST the day after; signups read from the posted messages | Step 0 |
| 2 | Members and bookkeeping: tables, import (members, characters, credits, study history, strikes, friends), `#/members`, `#/duties` | |
| 3 | Setups: proposal with priority and balancing (pairs, DPS, `K`), editing, warnings, `#/staff`, posting the setup and its thread | Steps 1, 2 |
| 4 | After the raid: screenshots from `#roster-history`, the participation run, its follow-ups as texts for staff, ratings | Step 3 |
| 5 | Plans: `#/seasons`, drafts 7 days ahead published by a staff click, overview posts kept up to date | Step 1 |
| later | Study feats computed; fully automatic posting; follow-ups sent by the bot; perhaps FFLogs | Decisions 8, 10, 17, 20 |

Each step works on its own: after step 1 staff post entries from the site, after step 2 they look things up there.
Step 5 could come right after step 1 if prepared entries matter more than setups.

## From the staff Drive (2026-10-29)

The staff Google Drive (about 40 documents read: events, staff meetings, difficulty rankings, the staff members'
folders) adds the following. The file ids are in the git-ignored `scratch/setups/drive-survey.md`.

**Infrastructure.** A handover sheet (May 2026) assigns the bot's GitHub repository, its rented server, Ko-fi, the
Discord server and the Drive to new owners. A second code base exists as well: a repository with a server, a database
and a bot that imports both sheets, calculates badges and writes the badge roles, last used for a sheet integrity
check in September 2026. A PostgreSQL dump of its database from February 2026 is in the Drive. The archive server's
bot hosting ended in August 2026, and the `sync.guide` domain with its link shortener in October 2026, so links in the
staff guides may be dead. The rented server could be where the site's server runs (decision 6).

**Data the import can use** (from the live sheets; the Drive also holds about a dozen dev copies and snapshots,
which the import ignores):

| Source | Gives the site |
|---|---|
| Kills logs, one sheet per progression season, a tab per duty, a column per raid date (`K` kill, `-` progress, `0` absent) | Dated clears and progress nights for the Wednesday/Sunday series: the history the study history sheet lacks, and the input for the progress-speed part of the strength score |
| Duty star ratings: a staff survey (2025; 26 Extreme and 24 Savage answers, votes 0–5) turned into 1–5 stars (0.8 × mean + 1) for 117 duties | The history behind the stars and the decimal means, which can rank "hardest cleared" finer. `duties.stars` itself comes from the published "Star Ranking Overview" thread in `#course-calendar` (last edited April 2026), which supersedes the sheets; duties not listed there have no stars |
| The rotation working sheet, seasons 1–11 | The rotation plans, with planned against actual weeks |
| Community Choice vote sheets (four voting days per weekend; votes and unique voters per category) | What a Community Choice slot became |
| The duplicate checker's duty list | Name aliases for `duties` |
| The credits sheet's hidden `Setup` tab | The couples and friends list |

The Drive connector can read these sheets directly, so later imports can pull from Drive instead of `.xlsx` exports
(read-only, through a Google service account or the staff account; not in the MVP).

**Calendar and plans.**
- A weekslot can be extended (`4(e)`, `2(2xe)`: the same duties another week) or split (`3.1`, `3.2`: one duty over
  several weeks), and each season part gives each day a theme (for example "Friday: ARR & ShB"). `plan_slots` needs an
  "extend" action besides "done", and the plan keeps planned and actual weeks.
- Community Choice weekends follow a four-day vote; a CC slot can link to its vote sheet.
- Raiding Seminars run six days over three weekends with fixed topics (fundamentals, basic mechanics, callouts,
  positioning, timelines, modern savage), which can pre-fill the seminar entries.
- The anniversary is around 27 November: an extended weekend with community events and a 24-hour raiding marathon
  (duties earn medals, the medal total unlocks tiers of an anniversary badge). Special series, outside the plans.
- Staff meeting, October 2025: current-content Extremes start synced and move to MIL if the group clears easily.

**Setups and raid leading.**
- Setups are made the day before (Tuesday for Wednesday, Thursday for Friday), by named setup creators with backups.
- The staff meeting of October 2025 discussed an "anchor list" of players who need a strong group around them, a
  raid-leader avoidance list, and a review of the couples and friends list. None of it is decided (decision 21).
- The same meeting proposed that only active raiders make setups and calendar posts, which narrows decision 7
  (decision 22).
- The raid lead opens a private Party Finder named like `Syncademy <duty> Group N` 10–15 minutes before the start and
  says so in the course thread; the site can prepare that line per group.
- The screenshot post names the group number and difficulty, and leads sometimes note weak or exceptional players.
  So informal ratings already happen; the rating option on the event page gives them a place.
- A trainee is briefed before their first night on what they do (lead, explain, open the party, post the screenshot).
  A separate Mentor role for staff who support weaker players is planned.

**Participation and linkshells.**
- Confirmed: backups present at the start count; three active strikes bench a member; 3 participations remove the
  first strike, 5 the second.
- The per-world linkshells are to be retired; only the cross-world linkshell stays. The "third participation →
  linkshell invite" follow-up may then apply to the cross-world linkshell only, or go (decision 23).
- How revokes are handled was on the agenda for a later meeting (October 2025) and may change.

**Study feats** (the deferred project) gets its missing numbers:

| Part | Rule |
|---|---|
| Raid activity | Per Syncademy month, against the month's raid days (without Sprout Monday and other events): over 75% +6 Exp, ≥ 62.5% +5, ≥ 50% +4, ≥ 37.5% +3, ≥ 25% +2, at least 2 participations +1 |
| Cakeday | +3 Exp per year of membership |
| Badges | Extreme Trials +6, Savage +12, Expansion +6; story-arc badges for all ARR–EW Extremes, all ARR–EW Savage, and both; BLU expansion badges and a BLU combo badge; Dawntrail badges for its trials and its raid tier. Ultimates, BLU and Dawntrail Extremes are not yet counted by the badge script |
| Promotions | Six student ranks above Initiate with their own thresholds (participations over 3, 6 or 12 months, activity, badges with Savage ones, months since the last promotion, study group Exp), and two staff ranks |
| Demotion | Any student rank inactive for more than half a year is demoted, and gets the old rank back on returning |
| Study groups | The Drive guide gives up to +3 Exp for all Extremes of an expansion and up to +6 for a whole Savage tier, with smaller amounts for at least a third of the bosses; the archive guide gives 2/4/6 Exp for 2–4/5–8/9–12 kills. Which one is current is decision 24 |
| Profiles | Exp and level are shown in members' Discord profiles; a monthly list says whose to update |

`badges` needs kinds for story-arc, BLU and Dawntrail badges, and `members` keeps the previous rank for a demotion
that is undone.

## MVP (started 2026-10-29)

While the server owner considers the site, the first build covers what needs neither the bot nor the server:
**bookkeeping and setups**, on the local Supabase stack in WSL only. Real member data stays local until the site is
approved: nothing of it goes to the cloud project, `stats/`, or git.

1. **Schema**: a migration in `tools/scorecard/supabase/migrations/` for the tables of this concept that the MVP uses
   (members, characters, duties, clears, progress marks, tiers, badges, participations, participation_before, strikes,
   revokes, credits, staff_days, friends, events, destinations, signups, setups, setup_slots, ratings, strength_parts),
   with row-level security for staff and audit triggers as in `20261029000000_staff.sql`.
2. **Import** (`setups_import.py`): the credits register, the study history sheet (letters, tiers from the font
   colours), staff availability, the friends list where available, with the import report. Re-runnable.
3. **Pages**: `#/members` (search, a member's page with clears per duty, tier, participation, strikes, credits) and
   `#/duties` (the matrix per tab and expansion), staff only.
4. **Signups without the bot**: an event is created by hand on the site (series, date, destinations) and its signups
   come from the Setup Creation Helper's `Bot_Setup` tab (an `.xlsx` export, uploaded or imported), where each role is a
   formula pointing at a `Bot_DB` icon cell (`tank` `A1`, `healer` `B1`, `melee` `C1`, `ranged` `D1`, `caster` `E1`,
   `backup` `F1` in the 2021 bot; the newer cells `D2`, `E2`, `F2`, `G1` still need mapping).
5. **The setup proposal**: priority tiers, role matching, raid leads, staff leads for trainees, friends, balancing
   (pairs, DPS, `K`), the warnings, manual editing, and the announcement text to copy.

Done means: the import runs on the real files with a readable report; the pages show real members locally; a past
event night (for example #1419, 28 October) gets a proposal that a setup creator would accept with few changes; the
proposal and the import have tests on made-up data; the README and this concept say what was built.

## Things to keep in mind

- **More personal data than before.** The scorecard knows about 70 players by character name. This knows about 1,250
  members with Discord IDs, Lodestone IDs and their history. It stays staff-only behind row-level security, the audit
  log records changes, and the import files stay out of git. The repository is public, so test data in it must be
  made up.
- **The site posts in Syncademy's name.** A mistake in an entry or a setup reaches every member. Nothing goes out
  without a staff click for now, the preview matches the post, and every post, edit and removal is in the audit log.
- **Removing an entry removes its reactions.** The last signup copy is taken at the event's start; a removal by hand
  before that takes one first.
- **Name matching is the risky part of the import.** The sheets have alts in one cell ("A/B"), free-text notes in
  brackets and spelling drift. The import reports what it can't match instead of guessing.
- **Free Supabase projects pause** after a week without traffic. The server's scheduled jobs count as traffic, so they
  keep the project awake, breaks included.
- **The server is one more thing to run.** Updates, backups of its configuration, and someone besides you who can
  reach it, for the same reason as the bot's team.
- **Ratings are personal data about people.** A strength score or a lead's rating is an opinion about a member, kept
  for staff only. Under the GDPR members may ask what is stored about them, ratings included, so ratings should be
  written as the member could read them. The score is a guide for spreading groups, never a reason on its own to leave
  someone out: it doesn't enter the priority.
- **Strikes, warnings and revokes** are records about members' conduct. Like ratings, they are staff-only, and a member
  can ask to see them. A strike that was removed stays in the history with its removal date, so the site can still
  answer "why was I benched".
- **OCR misreads.** A misread name either matches the right member on that world or none; it never silently becomes
  someone else, because a weak match counts as unknown and the raid lead confirms the list before it is saved.
- **Testing against Discord.** Posting can't be tried on the real channel. A test server with a copy of the emojis
  and a test channel, selected in the configuration, is where publishing and removal get tried first.

## Decisions

Answered on 2026-10-29; the sections above follow them.

| # | Question | Decision |
|---|---|---|
| 1 | Status letters | `x` counts as `K`; upgrade order `N` < `-` < `E` < `S` < `m` < `M` |
| 2 | "New people", tiebreaker, `:online:` | New means new to the duty; fewer participations first; `:online:` lowers everyone to tier 4 |
| 3 | Raid leads | The lead is one of the 8, in the first spot; trainees and `:pve_mentor:` members go with a staff lead where possible, with a warning otherwise |
| 4 | Friends together | The list moves to the site |
| 6 | Where the Discord part runs | A dedicated server |
| 7 | Who may edit | All staff, as all of them have the Google files today |
| 8 | FFLogs prefill | Later, if at all |
| 9 | Credits | They move to the site |
| 10 | Automatic entries | Drafts 7 days before, published by a staff click; fully automatic posting as a later option |
| 11 | Removal | The Discord messages at 06:00 ST the day after; the site keeps the full history |
| 12 | Time zone | Europe/Berlin (CET/CEST) |
| 13 | Setup posts | The site posts them |
| 14 | Strength | Clears, progress speed and staff rating, starting weights a best guess; per role; spread `K` players; balance the tank and healer pairs first |
| 15 | Staff ratings | Not done today; the option is built |
| 16 | The screenshot channel | `#roster-history`; today the bot's OCR fills a Google sheet and staff count by hand; the site's bot reacts ✅ under a screenshot once it is confirmed |
| 17 | Follow-ups | Prepared texts only |
| 18 | The cheat sheet's other duties | In-game tasks stay manual; the site writes their texts |
| 20 | Study feats | A deferred project; since 2026-10-29 staff's first priority, see STUDY_FEATS_CONCEPT.md |

### Still open

- **5. The bot application** and who is on its team: after the site has been pitched to the server owner.
- **6. The hosting provider** for the server. The bots' rented server from the handover is a candidate. Options
  compared on 2026-10-29, for one host with the site, the database (self-hosted Supabase: 4 GB RAM minimum, 8 GB
  recommended), the worker and the Discord jobs:

  | Host | Plan | Per month | Notes |
  |---|---|---|---|
  | Strato (where the bots' VM already is) | VPS L: 4 vCores, 8 GB, 240 GB NVMe | €20 incl. VAT | German provider; root and Docker; same account and Ko-fi payment as the bots' VM |
  | netcup | VPS 1000 G12.5: 4 vCores, 8 GB, 128 GB | about €17 incl. VAT (12-month term) | German provider, data centres in Nuremberg, Vienna, Amsterdam |
  | Hetzner Cloud | CPX32: 4 vCPU, 8 GB | €36 excl. VAT | EU plans not orderable at the time; prices rose up to threefold in 2026 |
  | Supabase Pro (Frankfurt) plus a small VPS | managed database, auth, daily backups, no pausing | about €23 plus about €10 | No database upkeep; two providers |

  On one host, the backups have to leave the machine: a nightly dump to separate storage.
- **19. The existing data**: Crystal Exarch's saved texts and images, the Django application's database, and the other
  code base's database (a dump from February 2026 is in the Drive). Who owns that code now, per the handover sheet,
  and is any of it still maintained?
- **21. Anchor and avoidance lists**: should the setup proposal know players who need a strong group around them, or
  pairs a raid lead shouldn't get? Only if staff decide to keep such lists; they are personal data.
- **22. Who may make setups and calendar posts**: all staff (decision 7), or only staff who raid actively, as proposed
  in October 2025?
- **23. Linkshell invites**: with the per-world linkshells retired, does the third participation still lead to an
  invite (to the cross-world linkshell), or does the follow-up go?
- **24. Study group Exp**: the Drive guide (per expansion and Savage tier) or the archive guide (per kill count)?
