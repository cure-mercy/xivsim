# P12S P1 scorecard

Turns FFLogs reports of P12S phase 1 (Athena, Savage) progression into a website you can drill down from raid
days to a day's groups to a group's players. For every player it shows how many mistakes they make and how
many wipes they caused, how much damage their mistakes cost, and how their damage compares with players from
other groups' clears on the same job, overall and per phase of the fight.

## Usage

```
python tools/scorecard/build_site.py <report link> [<report link> ...]
python -m http.server -d tools/scorecard/site 8000          then open http://localhost:8000
```

To check a rendered page from a script, dump its DOM with headless Chrome while the server runs:
`chrome --headless=new --disable-gpu --virtual-time-budget=8000 --dump-dom "http://localhost:8000/index.html#/day/<day>/<group>/pulls/<n>"`
(the virtual-time budget lets the hash route render). The trainer works the same way from the repository root.

Each link is one raid group's report; full links (with or without `#fight=…`) and bare report codes both work.
Reports are grouped into raid days by the date they were logged, and new reports on a day are named G1, G2, …
in the order given. A report already on the site is analysed again and keeps its name.

`tools/logs.csv` lists our groups' reports: a row per raid day, a column per group (G1-G5). The site names groups after
those columns, so give a day's new links with their columns' names, `--names "G1,G3"`. The CSV's Date column is only a
label (it has had typos): the raid day is always FFLogs' log date. Copy `site/data.json` (git-ignored, see below) before
a run you may want to undo.

| Option | What it does |
|---|---|
| `--names "Static A,Static B"` | Group names for the links, in order, instead of G1, G2, … |
| `--refresh` | Downloads the reports again instead of using the cache. Use it for a log that was still being uploaded. |
| `--reanalyse` | Analyses every report already on the site again from the cache. Needed after the classifier or the cause labels change, since the site stores what it was built with. |
| `--remove CODE` | Removes a report from the site. |
| `--publish [DIR]` | Also writes the copy for public hosting: rotations and gear open, the rest in Supabase behind a login (or behind a passphrase without Supabase; see Publishing). |
| `--upload` | Sends the data to Supabase without writing the page files. |
| `--cached` | Uses the cache only: parts a cached report is missing (such as the rDPS raid buffs gave others) are left out instead of fetched. For when FFLogs is down; a normal run later fills them in. |

A report takes a few seconds the first time and is cached in `.cache/` afterwards. The page needs a web server
because it loads `data.json`; opening `index.html` straight from disk will not work. `site/data.json` holds
player names and who caused which mistake, so it is git-ignored, and `tools/` is left out of the GitHub Pages
deploy.

## Setup

- Python 3.10 or newer, no extra packages. Node, only for `--publish` without Supabase. For accounts: Supabase keys in
  `.supabase` and, for the admin page's builds, the worker in WSL (see Publishing).
- An FFLogs API client in `.fflogs_v2` at the repository root (it is git-excluded), two lines:

  ```
  FFLOGS_CLIENT_ID=<client id>
  FFLOGS_CLIENT_SECRET=<client secret>
  ```

  Create a client at <https://www.fflogs.com/api/clients/>. Any key names ending in `_ID` and `_SECRET` work.
  The access token is cached in `.cache/token.json` until it expires.

Deaths and other events are read with paged event queries (`fflogs.events` follows `nextPageTimestamp`); tables
(`fflogs.tables`) only over short windows with few entries. FFLogs can cut a table short without a warning: the v1
API's deaths table stopped at 200 entries, which once corrupted a "no death before 2:00" filter. A script that needs a
long table pages it itself (the next request starting at the last entry's timestamp, duplicates dropped by id and
timestamp).

### Archived reports

FFLogs archives reports after a while (in October 2026, everything logged before about July 2024). Their fight
list stays public, but their content is only readable by an account with an FFLogs subscription, through its
user API. To let the tools read them, register a redirect address on the API client (at
<https://www.fflogs.com/api/clients/>, for example `http://localhost:8765/fflogs-callback`) and log in once:

```
python tools/scorecard/fflogs.py --login [--redirect http://localhost:8765/fflogs-callback]
python tools/scorecard/fflogs.py --check      # confirms an archived report can be read
```

The login opens FFLogs' sign-in page in the browser and catches the reply on that address (authorization code
with PKCE). The user token is saved in `.cache/user_token.json` (git-ignored) and renewed automatically when
FFLogs gives a refresh token. From then on, a query that FFLogs refuses as archived is asked again through the
user API; everything else keeps using the app token.

## Publishing

GitHub Pages sites are public, so the published copy splits its data. The rotation and gear pages are open to
everyone. Everything else (progress, mistakes, player names, our players' figures) is for Syncademy staff only: staff
accounts on Supabase, which an admin approves (ACCESS_CONCEPT.md), or the staff passphrase (see the end of this
section).

```
python tools/scorecard/build_site.py [<report link> ...] --publish
```

This writes `stats/` at the repository root: the three page files, `public.json`, `config.json` and, with a
passphrase, `data.enc.json`. It also sends the rest to Supabase.

- `public.json` holds what the rotation and gear pages need, unencrypted: `rotations`, `gear` and the benchmark's
  clears (`benchmark.pools`, from public FFLogs reports). It is a whitelist, `PUBLIC_KEYS` in `build_site.py`: a new
  key in the data stays private until it is added there. Before writing anything, `--publish` looks for every
  player's name (each report's players and actors, as whole names) in `public.json` and publishes nothing if one is
  there.
- `config.json` tells the page where to log in: the project's address and its public (publishable) key, which is meant
  to be public, and whether `data.enc.json` is there. Row-level security in the database decides what a logged-in
  account may read.
- Supabase gets the private part (`build_site.fragments`, uploaded by `supa.py`). Staff and admins read all of it:

| Table | Holds |
|---|---|
| `progress` | Per report, what the pages load first (`PROGRESS_KEYS`, `PROGRESS_PULL_KEYS`): group-level figures, mistakes by mechanic, its players' names and its pulls |
| `report_full` | The report's whole record, as in `data.json`; a page loads it when it needs it (a group's, pull's or player's page) |
| `site_meta` | `strategies`, the whole benchmark, `ours` |
| `reports` | Which reports exist, with their day and group |

Only what changed since the last upload to that project is sent (hashes in `.cache/supabase_sent.json`). A report
removed with `--remove` is deleted from Supabase too, along with its progress and full record. `--upload` sends the
data without writing `stats/`, for example after `--reanalyse`.

`public.json`, `config.json` and `data.enc.json` go to Pages with a commit and push. The data in Supabase changes as
soon as it is uploaded. The published `index.html` loads `style.css` and `app.js` with a version stamp (`?v=` and a
hash of the file), so browsers fetch new page files after a deploy instead of mixing a cached stylesheet with a new
script. The page may be indexed by search engines (ACCESS_CONCEPT.md, decision 4); only the open pages have anything
to index.

### Accounts

| Who | Sees |
|---|---|
| Not logged in, or an account waiting for approval (`pending`) | The rotation and gear pages; a progress link shows the login, or that the account waits for approval, and the passphrase form |
| Staff (`staff`), or anyone with the staff passphrase | Everything: every report in full, mistakes included |
| Admin (`admin`) | Everything, plus the admin page |

Anyone with a Discord account can log in; the account is `pending` until an admin approves it as staff on the admin
page. The account page shows the role, what is stored, and lets users log out or delete their account.

The first admin is made from the command line, once they have logged in on the site:
`python tools/scorecard/supa.py admin <email or Discord name>` (`supa.py staff <who>` approves someone as staff the
same way). After that, admins approve and promote others on the admin page; nobody changes their own role there.
`supa.py status` counts rows and accounts by role, and `supa.py audit [N]` prints the audit log's last entries.
`supa.py probe` checks the access rules from outside: the public key alone must see nothing; a `pending` account only
its own profile; a `staff` account every report but none of the admin's tables; and neither may raise its own role,
remove accounts, add reports, start an FFLogs search or write the audit log. It uses a throwaway account and deletes
it afterwards (its entries stay in the audit log, as `probe-…`).

**The audit log** (`audit_log`, on the admin page) keeps who did what and when: logins, accounts created, approved,
promoted, revoked or removed, changes to the report list (added, renamed, rebuild or removal asked, live watching),
FFLogs searches, and what the worker built, removed or failed to build and what the command line uploaded or
published. The database writes the entries for what happens on the page itself, with triggers
(`supabase/migrations/20261029000000_staff.sql`); the worker and the command line write theirs with the service key.
Nobody can change or delete entries from the page. Opening the site with the passphrase leaves no entry: it happens in
the browser and never reaches the server.

### The admin page and the worker

`#/admin` (the Admin link in the header, shown to admins) has a note at the top while logins wait for approval, and:

- **Find a raid day's reports on FFLogs.** Pick the day, and optionally characters to look for (`First Last`, or
  `First Last@World`, comma-separated). The worker lists that day's public P12S Savage reports, each with its pulls,
  uploader and which of our players (anyone in a report on the site) were in its P12S pulls (of its players: FFLogs' Limit Break actor is left out); characters looked for are
  in bold, and those in none of them are named. A report already on the site or the list says so. One that repeats
  another's pulls (a second upload of the same night: half its pulls or more start within 5 seconds of the other's)
  says "same pulls as G3". The rest have a group field and an Add button, with Live ticked when the log's last pull is
  under 30 minutes old. Reports without our players are behind a button.
- **Reports.** Add a report by its FFLogs link or code, with its group name (G1, G2, …; empty takes the day's next
  free one). For each report there are buttons to rename its group, rebuild it from a fresh download, watch it live,
  or remove it. Each row shows the state the worker reports: queued, building, ok, or error with FFLogs' message.
  The list refreshes every 15 seconds, except while a field is being edited. The list and the search are tabs, the
  list open first. It shows the two newest raid days (and anything queued, building or failed), older ones behind a button, and links each
  built report to its page on the site.
- **Accounts.** Logins waiting for approval (approve as staff, or remove), and staff and admins (make or remove admin,
  revoke staff access, remove the account).
- **Audit log.** The newest hundred entries, with older ones a button away.

The analysis runs in Python, not in the browser or the database, so the page only edits a list (`report_sources`).
`worker.py` builds what the list asks for. It reads the list every 30 seconds, analyses new, renamed and rebuilt
reports with the same functions as `build_site.py`, removes what was removed, writes `data.json` and uploads. A
build from the command line also keeps the list in step: reports it adds appear there, and reports it removes leave.
`site_lock()` (`site/.build.lock`) keeps the worker and a command-line build from writing `data.json` at the same time.

**Finding reports.** The search (`report_searches`: the page inserts the day and names, the worker answers within a
few seconds, and keeps a week of searches) uses FFLogs' report listing for a time window: the reports FFLogs files
under Anabaseios, P12S's zone, plus every report the uploaders of our reports uploaded that day (a night that began
with other content can be filed under another zone; uploaders are cached in `.cache/uploaders.json`). It costs about
60 of the 18,000 points an hour. FFLogs never lists unlisted or private reports, so those (3 of our first 25) still
need their link. A character's own list on FFLogs (`recentReports`) would be the direct way, but it lags weeks behind:
for our players it had none of our P12S reports.

**Live reports.** FFLogs' API has no webhooks or subscriptions (its GraphQL schema has no subscription type), so a
live log is polled. Every 3 minutes the worker asks for the report's uploaded segments (`fflogs.report_state`, a
query of a few points). When the count has grown, it downloads and analyses the report again. Watching has a hard
limit: `live_until`, at most 12 hours after it was set (the database caps it). It also stops after 90 minutes with
nothing new in the log. A report that fails, for example a live log with no P12S pull yet, is tried again only when
the log grows or an admin changes it.

The worker runs in WSL (Ubuntu) as a systemd service. `worker.service` has the install commands. It needs the
`.supabase` keys and the FFLogs client (`.fflogs_v2`), which it reads from the Windows checkout through `/mnt/c`.
WSL stops its VM a little while after the last Windows-side process using it exits, and the worker and the local
database stop with it. To keep them running, keep a WSL process open, for example a task at logon that runs
`wsl.exe -d Ubuntu-26.04 --exec sleep infinity`.

### Setting up Supabase

`supabase/` holds the project for the Supabase CLI: `config.toml`, and the schema with its access rules in
`supabase/migrations/` (tables, row-level security, the roles, `remove_account`, `delete_my_account`, the audit
log's triggers, and the trigger that caps live watching and queues admin changes for the worker).

**Locally, in WSL** (Docker and the CLI are installed in Ubuntu-26.04), from `/mnt/c/Gitroot/xivsim/tools/scorecard`:
`supabase start` runs the stack: the API on <http://127.0.0.1:54321> and Studio on <http://127.0.0.1:54323>.
`supabase db reset` reapplies the migrations to an empty database. `supabase status -o env` prints the keys; they
go in `.supabase.local` at the repository root (git-ignored), and `SCORECARD_SUPABASE=.supabase.local` selects that
file. With `SCORECARD_EMAIL_LOGIN=1` in it, the page also offers email and password, for test accounts. To try it:

```
SCORECARD_SUPABASE=.supabase.local python tools/scorecard/build_site.py --publish scratch/access/site
python -m http.server -b 127.0.0.1 -d scratch/access/site 8000
```

Discord login works locally only once a Discord application is set up (below). Its id and secret then go in
`supabase/.env` (git-ignored), and the application also needs `http://127.0.0.1:54321/auth/v1/callback` as a redirect.

**For the published site**, one time:

1. Create a project at <https://supabase.com> (the free tier is enough). Free projects pause after about a week without
   activity.
2. Create a Discord application at <https://discord.com/developers/applications>. Under OAuth2, add the redirect
   `https://<project>.supabase.co/auth/v1/callback`.
3. In the Supabase dashboard, go to Authentication → Sign In / Providers, enable Discord, and enter the
   application's client id and secret. Under URL Configuration, set the Site URL to
   `https://cure-mercy.github.io/xivsim/stats/` and add `https://cure-mercy.github.io/xivsim/stats/**` as a redirect
   URL. Leave the Email provider on, with Confirm email: `supa.py probe` logs its throwaway account in by password,
   which turning the provider off stops (it also blocks password logins for accounts an admin made). Someone who
   signs up by email is like a new Discord user: they see nothing until an admin approves them as staff.
4. Apply the schema from WSL: `supabase login`, then `supabase link --project-ref <ref>`, then `supabase db push`.
5. Put the project's URL, publishable (anon) key and secret (service_role) key in `.supabase` at the repository root,
   in the format `supa.py` describes, and the staff passphrase in `.PUBLISH_KEY` (git-ignored). Then run
   `build_site.py --publish`, check with `supa.py probe`, and commit and push `stats/`.
6. Log in on the site once, then run `supa.py admin <you>`.
7. Install the worker in WSL (`worker.service`). It reads `.supabase` by default.

### The passphrase

The staff passphrase is the other way in: no account, staff's view, no admin page. With a passphrase,
`--publish` writes `data.enc.json` next to `config.json`. It holds the private part, compressed and encrypted with
AES-256-GCM under a key derived from the passphrase (PBKDF2-SHA256, 600,000 rounds), which goes to `encrypt_data.js`
(Node) on stdin, so no plaintext copy is written. The passphrase comes from `SCORECARD_PASSPHRASE`, else from
`.PUBLISH_KEY` at the repository root (git-ignored); with neither, a publish to Supabase leaves `data.enc.json` out
(and deletes an old one). It must be at least 12 characters. Anyone can download the file and try passphrases
offline, so several unrelated words are best.

The page offers the passphrase below the Discord login. Readers enter it once per browser session; Lock (or logging
out) forgets it. It opens the data as of the last publish: what the worker builds later reaches Supabase, and the
passphrase sees it only after the next `--publish`. Everyone shares one passphrase, so changing it (and publishing
again) is the only way to revoke it, and old encrypted files stay readable in git history to anyone who has it.
Without `.supabase` the passphrase is the only way in: `--publish` writes no `config.json` and asks for the passphrase
twice when it isn't set.

`ours` is our players' share of the rotation pages, without names: per job, every clean 0:00–2:00 pull's rDPS and the
buffs it gave others, how many players those come from, and each player's rotation ceiling (`ours_by_job` in
`build_site.py`). It stays private in both setups. Until it is available, the rotations overview hides its chart of
our players against the ceiling and the clears. rDPS then adds the clears' mean buff credit instead of our players'
median, and the notes under the tables say which one they use.

**Undoing or moving it.** Nothing outside `stats/` depends on the published copy: delete `stats/` and push to take
it down. The page doesn't depend on where it is hosted: on any static host, upload `stats/` as it is. On a host with
its own login, upload `site/` with the plaintext `data.json` instead; the page then needs neither login nor
passphrase (it only asks when `data.json` is missing).

## What the site shows

The header links the sections side by side, Raid days, Players, Rotations and Gear (plus Admin for admins, with the
number of logins waiting for approval), and marks the one the page is in; the breadcrumbs below start from that section.
Day, group, player and pull pages link to their neighbours (the day before and after, the day's other groups, the
player's other raid days, the pull before and after), group and player pages list their sections under the title
("On this page"), and group and pull pages link to the report and the pull on FFLogs.

Mechanics and phases no pull of ours has reached yet (Superchain II so far) are left out of the charts and tables that
list them, until a pull gets there (`seenCps`, `seenWindows` in `site/app.js`). The mistake and wipe heatmaps show the
15 most frequent causes, the rest behind a button (`CAUSE_ROWS`). "Top wipe cause" in the Days and Groups tables is the
most frequent blamed cause, with the wipes nobody is blamed for yet (no rules for the mechanic, no culprit found, the
wipe called) counted after it when there are more of them; Raid leader focus leaves those out.

| Page | What it shows |
|---|---|
| Players | Every player across the raid days, the most recent first, with a search box: jobs, nights, pulls, mistakes and wipes per pull over all of them, mistakes per pull on their latest night. On the hosted site it reads each report's `people` (`build_site.progress_of`), so it needs no full records. Each row opens the player's summary |
| Player summary | `#/player/<name>`, a player over every raid day (it loads all their reports). Tiles: pulls, nights and hours in combat, jobs with pulls on each, the furthest pull they have seen, mistakes per pull and per minute in pulls, wipes caused with their share of the blamed wipes in their pulls (a fair share is 12.5%). **Mechanics**: per mechanic, the pulls that reached it (still going when it began), their mistakes (their shares) and those per pull reaching it, the share of those pulls clean of their mistakes, the pulls lost on them there, their most common mistake in it, a trend (later nights against earlier, 20% apart) and Drill / Brief links; the mechanic with the most per pull is marked, and mechanics they never erred in are named in a line under it. **Pulls**: every pull they played, night by night, as a bar as long as the pull, coloured by how it ended for them (the kill, the wipe put on them, their death before the pull was lost by whose mistake it was, or alive when it was lost: dying in the collapse that lost it counts as alive); a bar opens its pull. **Deaths**: their deaths before each pull was lost by whose mistake (their own, someone else's, no culprit found) and the deaths of others their mistakes caused before it was lost, with the players most often involved; the deaths that lost a pull and the collapse after are left out, since a raidwide would put every death on one culprit. **Damage**: per job, rDPS on clean pulls night by night (median, best, their ceiling plus the buffs they gave) against the clearers' average, how far a night's clean pulls spread (standard deviation over the mean), and damage by phase against clearers night by night. **Rotation**: per job played on two nights or more, the costed rotation checks added up night by night with their two costliest on their own; opener damage against the clears; raid buff timing per burst and night. **Through the night** (from four nights, `THIRDS_NIGHTS`): their mistakes per minute in the first, middle and last third of their nights against their groups' per player. **Night by night**: their top issues by raid day, mistakes per pull and wipes over the nights, and a row per night and job (mistakes per pull and per minute, wipes, vs Clears, uptime, rotation loss, opener against clearers) linking to that night's page |
| Raid days | Tiles: pulls, best pull, furthest seen (the longest pull, the mechanic it reached, its day, group and pull), latest day, mistakes per pull; the burndown; trends across days (how far pulls got, pulls clean through each mechanic, mistakes per pull and per minute, damage lost to mistakes, party DPS against the clears, pull pacing), the night in thirds and a table of days |
| Day | The day's groups side by side, their boss HP checkpoints in one chart (a block of rows per mechanic, a row per group), and heatmaps of all mistakes and of what wiped each group (rows named by mechanic, see below) |
| Group | The player scorecard; every pull's length with its first mistake and what lost it; boss HP checkpoints; damage lost to deaths, by player and by cause; every player's damage per phase against clearers; heatmaps of mistakes and wipes by player |
| Rotations | The optimizer's rotations (`#/rotations`, linked in the header): a chart and a table of every job it covers, then each job's GCDs and each GCD's rotation on the fight timeline (see Rotation ceiling) |
| Gear | The best-in-slot sets (`#/gear`, linked in the header): a table of each job's set and, per job, the set drawn like the game's character window with its DPS per GCD tier (see Best-in-slot gear) |
| Player | Mistakes per pull and wipes (each counting the player's share of the mistake, with their counts by confidence), damage and opener damage against clearers, uptime, what one death of theirs costs (time dead plus the full Weakness at their rDPS, as boss HP, kill time and against the group's mistake budget); damage per phase; mistakes by cause (one bar each: dark red for the mistake that lost the pull, red for other deaths, orange for Damage Downs; wipes put on them without a recorded mistake of theirs count only in Wipes caused); rDPS on every clean pull, with the rotation ceiling for jobs the optimizer covers and how far their pulls are from it, linking to its rotation (see below); every mistake with its pull, time and confidence; every death with its pull and time, the hit that killed them, the classifier's cause and the culprit (self, another player, or none found) with its confidence, marked when it decided the wipe or came after it, or saved the pull: in green, a death before the pull was lost holding what would otherwise have lost it, so far a Superchain I tower held in its Strong Soul's place (`death_list` on each pull, `saved`), and a ↗ link to FFLogs' Deaths view for them over the whole mechanic it happened in, or on to the death when that came later (from the report's `start_ms` and `actors` and the benchmark's `mech_end`); a link to their summary over all raid days |

The player page's "What their mistakes cost" card (boss HP lost to deaths they caused, by cause) and the group page's "What each player's mistakes cost" are hidden for now: set `SHOW_MISTAKE_COST` in `site/app.js` to `true` to bring them back.

Wherever a mistake is named (the mistake and wipe heatmaps, Raid leader focus, a player's Work on this, Mistakes by cause and top issues), it starts with the major mechanic it happened in, in the short form of How far pulls get, then the mistake: "SC I: Orange cone overlap", "Para II: Soul tower in the wrong quadrant". A mistake that happens in several mechanics gets a row for each (Trinity of Souls in Para I, Dialogos and SC I). Labels that already name the mechanic don't repeat it. The stored labels are unchanged; the names are made when the page draws (`causeName` in `site/app.js`).

Jobs show as the game's job icons (`job_icons` in the data, every job's from XIVAPI via `gamedata.job_icon`, public like the rotations; FFLogs' "Unknown" job gets `job_unknown.png`, the game's "Any" icon with a question mark, drawn by `scratch/icons/draw_unknown.py`) in tables, tiles, titles and the lists of a player's jobs, with the job's name on hover; chart labels, tooltips and sentences keep the short name (MNK).

Every chart has a Table button for the same numbers as a table and shows details on hover or keyboard focus.
The theme follows the system and can be switched with the button (or `?theme=light` / `?theme=dark` in the
link).

### The scorecard

| Column | Meaning |
|---|---|
| Mistakes/pull | The player's mistakes per pull: every death or Damage Down they caused, not just a pull's first, and the few mistakes that count without either (both Superchain I lasers on one player). A mistake that kills several players counts once, and deaths that are only fallout of the player's own earlier mistake are not counted again. Being killed by someone else's error does not count. Mistakes are counted until the pull is lost; the collapse after that is not. Each counts the player's share of it (see Shares below): in full, ½ when the classifier could not tell them from one other player, ⅛ of a healing shortfall spread over the party. Deaths/pull and DD/pull split it the same way; a mistake with neither counts only in the total. |
| Wipes | Share of the player's pulls where their mistake is what lost the pull (see below), each wipe counted by the player's share of the entry that decided it, as mistakes are. |
| vs Clears | rDPS over 0:00–2:00, averaged over the player's best quarter of clean pulls, against the average player on the same job in the benchmark's clears without The Echo; * when only 1–2 clearers played the job. |
| Uptime | Active GCD time over 0:00–2:00, against clearers of the same role. |
| Pulls | The night's pulls. A player who changed jobs during the night has a row per job, showing the pulls on that job of the night's, "28 of 47": their mistakes and wipes per pull count over the whole night, vs Clears and uptime over the job's own pulls. The player summary's night table does the same. |

Grades are coloured dots: green good, yellow ok, red worth focusing on. `*` marks a comparison against only one
or two clearers, which is rough.

| Grade | Mistakes per pull | Wipes | Damage vs clears | Uptime vs clearers |
|---|---|---|---|---|
| green | 0.30 or fewer | 10% or less | within 5% | within 0.5 points |
| yellow | 0.60 or fewer | 20% or less | within 12% | within 1.5 points |
| red | more | more | more | more |

With eight players and one wipe a pull, a fair share of the wipes is 12.5%. The thresholds are constants at the
top of `scorecard.py` (`G_MIST`, `G_WIPE`, `G_DMG`, `G_UP`). The group and day pages' mistakes per pull count shares
the same way. Damage over 0:00–2:00 is only measured on pulls
with no death or Damage Down before 2:00, so every player is compared on the same opener and mechanics.

### Who lost the pull

Pulls run until the whole party is dead, so every pull that is not a kill is a wipe. A death without a hit in the
last 20 seconds of a pull (`JUMP_S`; above half HP after any hit in the 5 seconds before) is a player jumping off the
arena once the wipe is called: only deaths before the first jump count, and a pull with none before it was called
without one ("Wipe called", no culprit). 419 of the 427 deaths without a hit come that close to the end; the other
eight, single players mid-pull, stay ordinary deaths without a culprit. The collapse is the last run of deaths with
less than 15 seconds between them (`CASCADE_GAP`); earlier deaths the group recovered from do not count. One player
outliving the rest by more than that (an invulnerability, a late raise) does not make a collapse of their own unless
the wipe was called, and deaths after the whole party was dead (players raised after the wipe, dying again) belong to
the collapse before (`party_dead`, the user's rule, 2026-10-28: in dMvrn pull 7 a Paradeigma III explosion left no one
alive, and two raised players' deaths 17 s later had passed the wipe to a laser mistake 1:30 earlier). A mass death in the collapse (four or more players to one ability within 3 seconds, or two to a
tower explosion or Electrify, which kill everyone left, within 5 seconds of the collapse's start: `RAIDWIDE`) decides
the wipe; otherwise the collapse's first death does, or a death with a culprit within 1.5 seconds of it (the same
hit). Deaths within 0.6 seconds of the deciding one (`SIMULTANEOUS_S`: one step of a mechanic; its next step comes
0.8 s or more later), each to its own mistake, lost the pull with it, so their culprits share the wipe; so do the
culprits of a mass death's other deaths, except that an explosion or Electrify is its own cause's alone. When no rule
explains that first death and no mistake came before it in the pull, the wipe has no culprit ("No culprit found")
rather than going to a later death that may be its fallout; when it follows an earlier mistake, the collapse's first
death with a culprit decides. When a tower went unsoaked because its soaker was already dead, the wipe goes to
whoever caused that death. A collapse in a mechanic not blamed yet (see the rule book below) has no culprit ("Not
blamed yet"). A lone death does not start the collapse (`lone_start`, the user's rule, 2026-10-28: a Heavensflame
player's donut death 7 s before an unrelated laser cascade did not lose that pull): one with no other death within 1.5 s
(`LONE_S`) is passed over when nothing later in the pull follows from it (no death chains to it, none names its
victim, after the wipe call too: a dead tank shows up as auto-attacks then), every later death in the collapse has a
rule's culprit (an unexplained one may be its fallout), and the next step kills two or more. 16 of 898 wipes moved;
of the rest it could have moved, 12 are kept by a later death chained to them, 4 by one naming the victim, 44 by
unexplained deaths, 38 of them in mechanics not blamed yet on their day. Another rule was tried on 2026-10-26 and
reverted: the wipe falls when the last player able to Raise dies. It put six hand-checked wipes 7-20 s after the
collapse that had lost them.

### Boss HP checkpoints

For each major mechanic (Paradeigma II, Superchain I, Paradeigma III, Palladion and both Superchain II sets),
the chart shows how far the best and the median pull were ahead of or behind the pace for a kill at enrage when
the mechanic's cast began: Clear is on pace to kill exactly at enrage (~7:38), Comfy about 13 seconds earlier.
The dot after each best value is green at Comfy or better, yellow at Clear or better, red behind. The table view
has the exact HP.

### Damage lost to mistakes

Every death costs the time spent dead, from the lethal hit until a raise (or the end of the pull), and after a
raise 100 seconds of Weakness, which cuts a player's damage by 22% (Brink of Death taken as 50%). Every Damage Down
costs 38% of the player's damage until it wears off (or they die). These are measured from each player's own hits of
the same skill during and around the debuff: Damage Down x0.62 over 1,264 windows (an in-game combat log agrees),
Weakness x0.78 over 479; Brink of Death had too few samples. (An earlier regression on FFLogs' per-hit buff list read
Damage Down as costing nothing and Weakness as 5%: FFLogs does not list those debuffs reliably on hits.) The lost time
is valued at the player's own rDPS in that phase of the fight (from their clean pulls), so a dead buffer also costs
the buffs they would have given, and a death in a downtime phase costs less than one in the opener. Only time before
the pull was lost counts.

The cost goes to whoever caused the mistake, split when the classifier names several, and is shown as boss HP and
as seconds of kill time at the pace of a clear, combined and split into deaths and Damage Down. Mistakes without a
culprit are shown as "No culprit found".

**Mistake budget** (group and day pages): how much boss HP a group can lose to mistakes over a whole kill and still
kill before enrage, 1 - (minimum party DPS to clear / the group's 0:00-2:00 party DPS), also given as deaths or Damage
Downs. Those are priced at full length, since in a kill they are not cut short by a wipe: a death is the median time
dead until raised (10 s in our reports) plus the raise's Weakness, a Damage Down its median length (6.6 s) at -38%, both
at the group's average player DPS (party DPS / 8). The scorecard also splits each player's mistakes into Deaths/pull
(mistakes that killed someone) and DD/pull (those that only gave Damage Down).

### Rotation ceiling

For every DPS job the rotation optimizer covers (`tools/rotation`), the player page's rDPS-on-clean-pulls chart marks
each pull with a ceiling: the best rotation without raid buffs at the player's GCD over 0:00-2:00, with the runs our
strategy needs at their worst for the role (the Paradeigma I slot with the most running, R1 or M2, and each mechanic's
variant with the most), converted to their DPS (their damage per potency and crit / direct-hit gain from their own hits,
the same for every pull), plus what that pull's raid buffs added to the other players' damage (FFLogs' rDPS given: a
Reaper's Arcane Circle), which rDPS credits to them. The table view splits the two. The player page's "vs optimized
rotation" card, under Damage, gives their median clean pull's share of the ceiling (and the gap in DPS), their best
pull's and the ceiling itself (in rDPS, the median over their pulls, split into its nDPS and the buffs' credit), and
links to the rotation at their GCD.

**Which FFLogs metric is which.** FFLogs' fields relate exactly (checked on every player of the cached clears):
nDPS = raw damage − what others' buffs added to it (`totalRDPSTaken`); rDPS = nDPS + what the player's own buffs and
debuffs added to others' damage (`totalRDPSGiven`); aDPS = raw − only the single-target buffs received (Dance Partner,
cards); cDPS = aDPS + the credit given. A player's own buffs on themselves count as their damage in all four. On the site:
our players' pulls and the clears are rDPS, with tinctures taken out of both (ours: `fetch_pots` / `pot_gain`, the clears'
way); the optimizer's ceiling and the rotation pages' expected DPS are nDPS (no one's buffs, no credit given), labelled so;
the ceiling becomes rDPS on player pages by adding each pull's `given`, and the best rotation's expected rDPS (the
Rotations table and chart) adds the job's credit up to Palladion. Opener damage and damage by phase are nDPS.

**The Rotations pages** (`#/rotations`, the Rotations link in the header) list the jobs the optimizer covers, grouped by
role (melee, physical ranged, magical ranged) with job icons and ordered by expected rDPS:

- **The chart**, all of it over 0:00-2:00: a box over our players' clean rDPS (whiskers to 1.5 times the box's width),
  a tick at the job's ceiling with a band behind it, and a dot per clear player (`rdps_each`, each one's mean over their
  kills). The ceiling and band come from the gear model (`tools/gear`; `ceiling.py` writes `tools/gear/.cache/bis_site.json`,
  which `scorecard.rotations()` adds as each job's `bis`): the rotation searched for 0:00-2:00 with the job's best-in-slot
  gear, materia and food at the GCD where gear and rotation together do best over the phase, in nDPS, plus our median
  credit for buffs given; the band one standard deviation either side from crit and direct-hit luck alone (the rotation's
  hits one by one, at the set's rates; Reaper: ±427 on 13,577, 3.1%). A job without a `bis` entry keeps the older ceiling,
  the best of its rotations' own 0:00-2:00 searches at our players' median conversion, its band from the weakest to the
  strongest player's gear (each player's own ceiling over the median's at their GCD, players with 5+ clean pulls,
  `BAND_PULLS`; for a job none of ours plays, the clears' `dps_lo` / `dps_hi`); the chart's note names such jobs. A
  ceiling is an expected value (average crits, direct hits and procs), so single pulls beat it on luck: our best pulls
  reach 0.99-1.085 of their own ceiling, medians 0.87-0.98. Summoner's top clear sits ~3% over the band, whose top is our
  stronger Summoner's conversion (our two convert 21% apart): better gear than ours.
- **The table**: each job's best rotation (by expected nDPS) with its expected nDPS to Palladion plus what the job's
  raid buffs give the others over that stretch, which is our players' median 0:00-2:00 credit (the clears' `given` for a
  job none of ours plays) times the job's `given_ratio` in `benchmark.json` (the clears' credit rate up to Palladion over
  their 0:00-2:00 rate: three bursts against one and steady buffs like Dance Partner, from the clear players who used
  their raid buff in each burst as the optimized rotations do; `given_ratio_all` for a job without clears). Its 0:00-2:00
  ceiling column is the best of the job's rotations' own 0:00-2:00 searches (`ceiling_2min`, at the median conversion)
  plus our players' median 0:00-2:00 credit, no scaling needed. The rotation to Palladion is not the 0:00-2:00 one: it
  holds resources for after the downtime, and its stretch has three bursts against 0:00-2:00's one and pre-pull
  preparation, so it sits 7% under (Pictomancer) to 3% over (Dragoon) the 0:00-2:00 ceiling.
- **A job's page**: the same columns for each of its GCDs (every GCD it was searched at: our players' and any extra),
  under what P1 asks of the job with our strategy (`ROT_CHALLENGES` in `site/app.js`, from the optimizer's findings:
  update it when a job's rotation or our strategy changes), the fight timeline without a rotation (hovering or tapping a
  point marks the stretches it is about), and the set card of Best-in-slot gear; the GCD that is the set's carries a BiS
  tag. Monk's rotations also depend on the crit rate (its chakra), so its are per GCD and crit rate. A `--site` rerun can
  move what `ROT_CHALLENGES` states (True North counts, timings and GCD gaps drift between searches, and near-ties flip
  from one GCD to the next), so after one each claim is checked against every GCD's rotation of the job, not just one.
- **A GCD's page**: the rotation from the pull until Palladion takes Athena away (4:41) with its expected DPS over that
  stretch, its own 0:00-2:00 ceiling (a search over the scorecard's window, which is what players' ceilings use), its
  potency, casts per skill and any resources wasted. It is drawn compactly in the game's action icons, a line for each
  stretch between major mechanics: every GCD on the line with the oGCDs woven after it smaller and raised beside it (the
  table view has every GCD's start time, cast and running). The icons come from XIVAPI by action name (`gamedata.icons`,
  cached in `.cache/icons/`) and go into the site data as data URIs, so the published copy carries them encrypted like the
  rest. GCDs cast while running are marked (a green bar under an instant GCD the player runs through, a blue one under a
  hard cast whose run fits only in its slidecast and the gap after), with how much running falls before the next GCD:
  the optimizer only makes sure each run fits outside cast bars, so `dps.py` places them (longest stretches outside cast
  bars first, as late as they allow, which puts them on instant GCDs where it can). On top, the fight timeline it plays
  around: each major mechanic's start (its boss cast), the windows in which our strategy needs a run (the seconds needed;
  "movement" for the raidplan's mechanics, lighter "movement, pre-position" between them, where the clears' median path
  is used), a melee's stretches out of reach and spots the plan fixes (positionals need True North), and the rotation's
  GCDs and oGCDs. The timeline comes with the rotations (`dps.py --site`, from `p12s.py`).

**Expected DPS** converts the potency at our players' damage per potency and crit / direct-hit gain on the job, the
median of them, each player moved to the rotation's GCD first: Spell or Skill Speed comes out of the same gear budget as
critical hit, direct hit and determination, so a faster GCD costs about 0.4% damage per potency per 0.01 s (level-90
formulas; our Black Mages' gear falls 0.38% per 0.01 s). The range is the same over those players. A job none of our
players plays (Ninja) gets its rotations too, at the GCDs of the benchmark clears' players on it since the job's
`CONVERT_SINCE`, and expected DPS converts at theirs; the pages say so, and no player page links there.

**Refreshing them**: `python tools/rotation/dps.py --job blm --site` (and `--job rpr`, `--job drg`, ...; `--offline`
converts from the acts caches when FFLogs is down, and the pages say so; `--gcds 2.30,2.40` adds GCDs none of our
players has; `2.48/2.15` names the hasted GCD where a tier holds two, as Samurai's, Viper's and Black Mage's can, and
`-cNN` the crit rate in percent it is searched at, `2.45-c28`, for Monk, whose chakra comes from crits), then
`build_site.py --reanalyse` (the rotations themselves are picked up by any `build_site.py` run).

### Best-in-slot gear

The Gear pages (`#/gear`, `#/gear/<job>`) and the set card on each Rotations job page show the gear model's sets
(`tools/gear`, `sheets.py`; `scorecard.gear()` adds them to `data.json` as `gear`, with the item, materia and food
icons from XIVAPI, cached in `.cache/icons/`): the best searched GCD tier's set and, as tabs, the searched tiers within
0.4% of it. A job's Rotations table tags the GCD that is a set's (the rotations' GCDs are before a trait's haste, so
Monk's and Ninja's compare at that); the tag only shows where a rotation was searched at that GCD (`dps.py --bis-gcds`, with the hasted GCD for Samurai and Viper;
`scratch/gear/rerun_all.py` adds the missing ones). `--bis-gcds` takes the forms of `--gcds`, and the tag matches a set's
GCD, hasted GCD and crit rate (`bisAt` in `site/app.js`). Without them it lands on the wrong rotation: a plain GCD took
the middle speed factor's hasted GCD and missed Samurai's and Viper's sets, and Monk's BiS row, searched at the default
crit 0.25 against its set's 0.283, lost "best" to another GCD (2026-10-25). Such rotations are marked `bis_gcd`: once no set sits at their GCD and no
player plays it, the next `rerun_all.py` run drops them, while extras asked for with `--gcds` stay.
Any `build_site.py` run picks up new sets.

### Damage by phase

The fight is split at the HP checkpoints into seven phases (`WINDOWS` in `scorecard.py`). In each phase a
player's nDPS is compared with clearers on the same job in the same phase, pots removed. nDPS leaves out other
players' buffs, so a phase reads the player's own rotation whatever the party's buffers did. A phase is only
measured from pulls where the player was alive and unweakened through all of it before the pull was lost, and
needs two such pulls before it is compared; late phases rarely have them yet. The tooltip and table view add
uptime in the phase against clearers of the role.

### Progress

- **Burndown** (overview): every pull's boss HP at its end, all groups together in the order they were played (groups
  mix players, so there is one burndown), the best so far (steps) and dotted lines at the first pull that reached each
  mechanic, as on tomestone.gg; above it the pull count, hours in combat and best pull. Pulls with The Echo are drawn
  but not counted for the best.
- **How far pulls get** (overview): the share of each day's pulls that reached each mechanic.
- **Pull pacing** (overview, and an In combat tile on day and group pages): time in combat against the raid time (a
  group's first pull to the end of its last; a day adds its groups up), the median reset between pulls (one pull's end to
  the next one's start; breaks of 5 minutes or more, `BREAK_S`, left out of it and counted apart) and pulls per hour,
  from the pulls' start times (`at`). Our share went from 23-46% on the first raid day to 52-61% by 28 Oct.
- **Through the night** (overview): each group's pulls of a night in thirds by pull order, all nights together:
  mistakes per player per minute in pulls (counted as the trend charts count them), with the average pull and mistakes
  per pull. Over the first nine raid days the first third had the most (0.23 against 0.13 in the last), in the early
  and the later raid days alike: warming up costs pulls.
- **Where pulls ended** (group page): pulls that ended between each pair of mechanics, by pull length; the longest
  bar is the wall.
- **Their top issues** (player page, Across raid days): their three most frequent mistakes and their costliest
  rotation issues per minute, raid day by raid day. Mistakes are per pull that reached the mechanic they happen in
  (still going when it began; start times from `MECH` in `classifier.py`, passed on as `mech_start`), so getting
  further on later days doesn't read as more mistakes. Each row is one mistake in one mechanic (Trinity of Souls in
  Para I and in Dialogos are separate rows). Rotation issues are per minute alive, only on days with the same job. Trend:
  improving or worse when the later days differ from the earlier by 20% or more.

### Focus lists and practice links

**Raid leader focus** (group page) lists what to raise first: the mechanics that ended the most pulls and who failed
them, the most common mistake, the costliest rotation issues against the clearers, the latest raid buff and weak
openers. **Work on this** (player page) does the same for one player, at most five points: mechanics whose mistakes
lost pulls, their most frequent other mistake, the two costliest rotation issues, an opener 5% or more below clearers (with the skills cast fewer times than in the clears' opener and the cooldowns that went out late),
and a raid buff pressed 1.5 s late or skipped. Every point links to its section, and mistakes in a mechanic the trainer
has a drill for link to it: **Drill** opens the trainer on that mechanic (`index.html#<mechanic>`) and **Brief** its
brief (`briefs.html#<mechanic>`). The open drills are listed in `DRILLS` in `site/app.js` (Paradeigma I, Paradeigma II,
Superchain I, Paradeigma III); add a mechanic there when its drill opens. The links point one level up from the scorecard,
which is the trainer on GitHub Pages.

### Burst

On a group's page, each 2-minute burst: when every raid buff landed against the clears' median for that buff and burst
(seconds, + is late), from pulls that got through the burst; uses skipped while the buff's user was alive; and the
spread from the party's first raid buff to its last against the clears.

### Opener

On a player's page, their openers against the best opener the clears play (`opener_ref` in `checks.py`): GCDs,
damaging oGCDs, raid buffs and the other oGCDs planned into openers (`OPENER_ALSO`: Astrologian cards and draws,
Lightspeed, Swiftcast, Infuriate, Enshroud, Hypercharge and the like). Potions, Sprint, mitigation, movement, True North
and Lucid Dreaming are left out. A hard cast is timed from its begun cast, an instant (Swiftcast, Lightspeed, Dualcast,
procs) from the cast itself. Clears' openers run from before the pull to 0:22; openers within a few casts of each
other count as one variant. The reference is the variant most clears play, unless another one played by at least three
clears clearly does more opener damage: its median ahead by more than 1.5 standard errors of the difference. Within one
opener, gear and crits spread players by about 1,000 nDPS, more than most openers differ, so the highest median alone
would chase noise. Echo clears count with their damage divided by 1.2.

Compared is what matters, not the order:
- **Casts per skill**, over as many GCDs as the reference opener has (the player's casts are read to 0:30 and cut
  there), so a slower GCD from gear doesn't count as a missing filler. Flagged at half a cast or more per pull fewer or
  more than the reference.
- **First cast of each cooldown and raid buff** (oGCDs with a recast of 30 s or more, the job's cooldowns, raid buffs;
  not gauge spenders), median over their pulls against the median over the variant's clears. Flagged at 1.5 s or more
  either way.
- **GCD order is not compared.** Swapping two GCDs inside the opener changes nothing.

**Jobs with fewer than three clears** are compared within our own groups instead (`group_openers` in `checks.py`).
Every other player on the job counts like one clear, with their usual opener and median opener damage over all raid
days, so a regular on the job doesn't outweigh the others; the player themselves is left out. Bard has no clears at
all, so a BRD gets only this opener comparison, no rotation checks. With four BRDs the reference is thin (each is
compared with three others, often one other player's opener), and the card and tile say so below five players.
**Kit changes the clears predate** (`KIT_CHANGES`): only clears after the change count for the job's opener. White
Mage is the one so far: it now starts the pull with a Blood Lily (Afflatus Misery
right away, in 98% of our pulls), which none of the 12 WHM clears (2025-03 to 2025-12-12) had, so the change came after
2025-12-12. The card, the opener tile ("vs groups") and the focus lists say when a job is compared within our groups.

The card lists the flagged differences and shows the reference opener next to their usual one (red: a skill the other
doesn't have); its table view has the per-skill counts and first casts. Dancer steps count as one step, since they come
in a random order. Opener damage is nDPS over 0:00-0:20 (tinctures removed), from pulls the player was alive through,
against the clears playing the reference opener and against all clears on the job. The card's title carries the same colour dot as the opener tile, from the latter: green from −5%, yellow from −12%,
red below. For the latter, clears with The
Echo are left out; a job with fewer than three other samples includes them, damage divided by 1.2, and the card says so.

### Abilities

On a player's page, casts per minute of every damaging skill against clearers on the job, over the same stretches as
the rotation checks (0:00-0:55 against clears that move through Paradeigma I). GCD skills are compared at the player's
own GCD speed, since a slower GCD from gear fits fewer casts without any mistake. The difference is worth the player's
own average damage per cast (DoT ticks included). It overlaps with the GCD gaps: those say when time was lost, this
says which casts it cost.

**Grades on the Rotation and Abilities cards.** Each card's title carries a colour dot for the potential gain against
the clears as a share of the player's DPS: green under 5%, yellow under 15%, red from 15%.
- **Rotation:** the costed checks added up.
- **Abilities:** net, so extra casts of one skill offset missing casts of another (counting only shortfalls would
  inflate it: casting more of one skill usually means casting less of another).

The two overlap, so they are graded apart, never added. Over our 175 player-days, rotation splits 127 / 39 / 9
(green / yellow / red) and abilities 93 / 57 / 25. Healers come out highest (median 10.8% on abilities), partly from
healing GCDs our groups need.

### Pulls

Under each group, **Pulls** lists every pull: length, boss HP, how it ended and whose mistake decided it, mistakes,
deaths before the wipe, boss HP lost to deaths, and two party figures: the players' average nDPS against clearers on
their jobs (over the phases they were alive through) and their summed rotation loss against the clears. Each pull has
its own page with every player's mistakes, a death that came before the pull was lost, damage against clearers and that
pull's rotation loss with its biggest check, plus the pull's mistakes in time order and its deaths in time order (who,
the hit that killed them, the classifier's cause, the culprit with its confidence, marked when it decided the wipe or
came after it, or in green when it saved the pull, as on the player page). The group page's pull chart and the
pull numbers in a player's mistake list link there.

### Rotation

Simple, nameable rotation mistakes per player and job (`checks.py`), each against clearers on the job:

| Check | What counts |
|---|---|
| *Cooldown* held | an oGCD sat ready at full charges while the player was alive. Only oGCDs that deal damage or are damage buffs / resource generators, and that the clears use on cooldown (75-115% of possible uses) |
| GCD gaps | time between GCD starts (the begun cast for hard casts) beyond the player's usual GCD + 0.3 s, longer casts and GCDs with their own recast allowed for; split into *after an interrupted cast*, *weaving delayed the GCD* (the GCD started as an oGCD's animation lock ended) and *nothing cast* |
| Casts interrupted | a begun cast that never went off (its time is in the gap row) |
| Healing GCDs | healers: GCDs that never deal damage for the job; Eukrasia, raises, Esuna and White Mage's lily heals (they pay back through Afflatus Misery) aside |
| Combo broken / Positional missed | a hit with less bonus (FFLogs' `bonusPercent`, the share of its potency from combo and positional bonuses) than the clears usually get on that skill; no bonus after the wrong GCD is a broken combo. The damage lost is exact: hit x ((1 - got) / (1 - usual) - 1) |
| DoT ticks missed | ticks missing after the first one, for jobs whose clears keep a DoT up |
| *Proc* expired / overwritten | short self-buffs the clears spend with a cast (85%+ of them removed at a cast's own timestamp): run out unspent while alive, or refreshed while still up. Priced at the cast that normally spends it, less the filler when that cast is a GCD |
| *Buff* down | self-buffs the clears keep up (85%+): seconds down while alive after 0:15; damage buffs priced at their value (Surging Tempest, Power Surge, Hunter's Instinct +10%, Fugetsu +13%, Standard Finish +5%), haste buffs shown in seconds |
| GCDs in *buff* | GCDs started inside the player's own damage buff (20 s; Wildfire 10 s), per window, against the clears' average |
| *Gauge* overcapped | gauge wasted at the cap, replayed from casts with a table of gains and spends per job (`gauges.py`): Gunbreaker cartridges, Warrior Beast Gauge, Reaper Soul and Shroud, Dark Knight Blood (with Blood Weapon's +10 per weaponskill), Samurai Kenki (with Tengentsu's Foresight), Machinist Heat and Battery, Dragoon Firstminds' Focus. A table is used only when it replays the clears with under 6% of spenders unaffordable, which tests it. Priced per unit at the main spender's hit (less the filler for GCD spenders); gauges whose spender opens a sequence (Heat, Battery, Shroud) are not priced. Healer gauges buy healing, and Monk Chakra, Dancer Esprit and feathers, and Ninja Ninki come from crits, procs or shadow hits, so they are not replayed. Black Mage: Polyglot overcapped (`tools/rotation`) |

Every check runs from 0:00 until the player died or the pull was lost, skipping time dead, and the clears are
measured over the same stretch (0:00 to the same time), so movement and other mechanics that cost everyone uptime
cancel out. Level-90 cooldowns and charges come from how the clears use them (the game data's values are before
traits); whether an action is a GCD comes from the game data via XIVAPI (`gamedata.py`). The cost of the difference
uses the player's own hits: a held damaging oGCD at its average hit, a missed tick at their median tick, an idle GCD
second at their damage per second alive, a lost Polyglot at their average Xenoglossy. Buffs held get no cost, since
their value depends on what they would have covered. The idea list follows xivanalysis's modules, adapted to level 90 and to
comparison with the clears. Checks such as Thunderhead or Firestarter left unused were
tried and dropped: the clears let them lapse as often as we do, so they are not mistakes.

## How mistakes are attributed

`classifier.py` takes every Damage Down and lethal hit in a pull (`Pull.incidents`) and judges it against the strategy
in the trainer's mechanic briefs (`briefs.html`), mechanic by mechanic, with the rules the rule book (below) gives the
pull's raid day. The rules produce faults (who is to blame for which hits, how sure, and the rule's tag); each death or
Damage Down then goes to the fault about the hit behind it.

**How a rule decides.** Where the positions are cached (`fetch_wf`, `fetch_p2`, `fetch_sc1`, `fetch_p3`: damage events
only carry the hit players' positions at the hit, so these fetch every player's positions over the mechanic's window,
e.g. 35-47 s for White Flame, `WF_WINDOW`), a rule replays
the mechanic from them (whom an add's laser targets, where a line runs, where a tower dropped) and blames whoever's move
alone to their own spot would have prevented the hit (the user's rule, 2026-10-27). When either of two moves would have,
the one off their spot is blamed, both when both were off (medium); when neither was, the model cannot tell them apart
and says so: both, low, labelled "undecided (both blamed)" (the user's ruling: better to admit the model's limits than
pass a guess off as one player's mistake). Spots and tolerances come from clean pulls, mostly their 90th-99th
percentiles; the measurements behind each constant are in `classifier.py`'s comments and the audits in `scratch/`. Where
a replay does not reproduce what the log shows, or the positions are missing, an older rule judges from the hits alone.

| Mechanic | What is judged |
|---|---|
| Paradeigma I | White Flame: each add fires at its two nearest living players as the laser is cast. The baiting light party of each wave (or of each adds' side, `by_side`) and every baiter's line-up seat are learned from the group's clean waves (`infer_light_parties`, `line_up_seats`); non-baiters belong in the stack on the far side. A baiter is measured against the spot for their seat's rank (`SEAT_ALONG`, medians over clean waves), not against where that player habitually stands. The White Flame laser logs a stale position (Athena's spot) in about half the waves, so the adds' places then come from their own White Flame cast just before it, and each laser is matched to its add geometrically (`wf_pair`). The replay (`wf_replay`, 90% of waves reproduced) blames whoever's move to their spot alone spares a player hit more than they should be, else the fewest players who together would, all of the corrections with the fewest players inside their tolerance (when every one of them moves someone out of place, only those are blamed, not the players inside their tolerance); the label follows the culprit's role (missed bait, too close to an add, off their spot, in a laser line). Without the replay: a missing baiter is theirs unless someone out of place stood closer to their add (`wf_closer`); one as close within what the positions tell apart (the measured error of the two positions, `unc`; see Confidence) makes it a tie: the interloper's when clearly off their spot, else undecided. A player in a baiter's line is their own. Trinity of Souls is the victim's. Athena's auto-attack at ~50.5 s through wave 2's Magic Vulnerability (`para1_auto`): a provoke while carrying it, light party 1's tank taking a wave 2 laser, a shirk, else both tanks. |
| Paradeigma II | The quadrant sweep (supports clockwise from north-east, DPS counter-clockwise from north-west), read from where the tether holders stood, says where each Soul drops and who soaks it. Tether lasers replayed from their holders (`para2_tethers`): a holder dying to their own laser nearer than `P2_STRETCH`, a laser through someone else (`p2_tether_fix`: the holder off their line or the victim off their spot). Towers: a Soul in the wrong quadrant (the dropper), an unsoaked tower on its spot (the soaker), one off its spot (`p2_unsoaked`: out of the soaker's reach the dropper's, in reach undecided), two stacked, a soak with the same-colour Tilt (it explodes, 15 of 15) or while holding a Soul; a Soul dropped off the sweep is blamed with whoever soaked it with the same-colour Tilt, and for the quadrant's own tower going unsoaked when its soaker took the misplaced one instead. A Soul holder dead before dropping leaves the game to drop the tower on someone else, and with the party short a Soul holder gets a tether too: both are the deaths' fallout, that holder's own tower included. Ray of Light is the victim's. |
| Glaukopis | The tank swap (`glaukopis`): the second tank provokes during the cast, the first provokes back as the second hit lands; the boss picks its target 1.2 s after a hit (`SNAPSHOT`). Only a death counts: provoking back too early, not provoking, or provoking back too late for the heavy auto-attack after the second hit; both tanks when neither's casts explain it. Each hit is a 5 y line from Athena through its tank (game data): a non-tank in it is their own; with every tank dead, the hits are whoever killed the tanks'. |
| Superchain I | Orange cones and purple pairs at the first cluster, by each seat's angle around it (`spot_frame`, `cone_blame`, `pair_blame`; a party that fits its seats better mirrored is read mirrored). The lasers replayed from the centre through each Strong Soul (`sc1_laser_replay`, 88% reproduced; within the positions' error of a laser's edge a hit is as the log has it, and a move that decides it by less is undecided; a laser it cannot reproduce that hit a player at their group's spot is its Strong Soul's when they stood off theirs, else undecided, `sc1_misaim`): the wrong laser group, both lasers on one player (a mistake even when they live), a laser a sharer short; a death a full share would have spared goes to the dead sharers (`share_short`). Heavensflame (`flame`): a Strong Soul hit at their tower is the Heavensflame player's, anyone else whoever closed the distance. The bright Souls' drop: a Strong Soul stepping in early, a tower dropped on its waiting soaker (`sc1_dropped_on`), two Souls dropping together (`sc1_together`: whoever's tower dropped off its spot, undecided at its edge). Towers (`sc1_tower`) as in Paradeigma II, and: anyone with the tower's Tilt holds it, a player who dies holding it in its Strong Soul's place is the absent soaker's (`saved` on the site), and a Strong Soul with the wrong Tilt explodes it, blamed on what gave them that Tilt. Orbs and donuts are the victim's. |
| Dialogos | The tanks' hit is a 6 y circle (game data) on the closest player for Peridialogos and the farthest for Apodialogos, the party's stack the opposite: the tanks belong at the centre for Peridialogos and out for Apodialogos, the party the other way (`CENTRE_R`). A non-tank in the tanks' hit is theirs, unless it was aimed at a non-tank where the party belongs (then the tanks'); a tank leaving the hit to the other; a stack aimed at a tank; party members missing from the stack; a stack short of the dead (`share_short`). |
| Paradeigma III | Support towers (Electrify): a support not in their platform's tower, two in one (which of them belongs elsewhere by `BRIGHT_PRIORITY` from 2026-10-26), a DPS in one. DPS tether lasers, their holders from the adds' tethers and their seats from the simulator (`tether_lasers`, `tether_seats`): unstretched, through another DPS (`tether_cross`: whoever's seat clears it by more), clipping a support (`tether_clip`). Only 28 pulls were played under the strategy, all on one raid day, too few to fit spots as for the other mechanics, so the rest go by the plan's roles (2026-10-28, approved by the user; `scratch/review/p3_*.py`): the + and X (not stepping out of their own; one landing over 3 y from its spot, the north platform's outer corner or the south wall's middle, is its owner's whoever its arms hit: correct drops land within 1.6 y, `P3_CROSS_OFF`). White Flame per add (`p3_white_flame`): the + and X supports bait the add on their own platform's edge, of the matching DPS pair the straight tether the add in its own column and the crossed one the add across (16 of 16 clean baits); which add fired each laser comes from `p3_split` (each add fires two; a split within 2 y of the best, `P3_WF_TIE`, is undecided, low); an add's laser through anyone else is its missing baiter's, or a dead baiter's death's, else theirs for standing in its line. The bright towers: a tile whose DPS pair shares the Souls' colour sends its tower to the centre corner, the other stays mid-tile; the straight tether of the opposite pair soaks the centre tower and the crossed one the tile's. A centre tower has to reach 1 y past the arena centre to be humanly soaked from the other platform (a tower reaches 3 y, game data; a player is a point; the user's ruling: under 0.5 y it is out of reach and its dropper's, between undecided, `P3_ACROSS`; every soak from the other platform was of a tower within 2.0 y of the centre). An unsoaked tower is its soaker's by seat, or chained to them when dead, even where someone with the wrong Tilt stepped in (it explodes all the same). Falling with a destroyed tile (`Sample`) is the victim's. |
| Palladion | Not blamed yet (see the rule book). |
| Later mechanics | Generic rules only: standing in an avoidable AoE is the victim's mistake. |
| Any time | Athena's first auto-attack, in the first 15 s, on a non-tank: that player pulled her early (medium). Max HP under half the other non-tanks' median: broken gear (medium). A death with no hit mid-pull that is not a jump: fell off the arena (low). A death to a raidwide (`RAIDWIDES`: On the Soul, Ultima Blade) no rule explains, before the wipe is called: everyone alive, low, and the dead passed to whoever killed them (the user's rule, 2026-10-28). These count on days before a strategy too. |

**From faults to deaths.** A death goes to the faults about the very hit that killed it (several about one hit, like
two towers exploding together, are one cause with their culprits together), otherwise, unless the hit was avoidable, to
the earliest fault that hit the victim in the 4.5 s before. A death one step (`AT_ONCE_S`, 0.6 s) before a hit that kills
everyone left alive (`WIPE_HITS`: Electrify, Unmitigated Explosion), such as a tether laser just before Electrify, is two
failures at once, the faults about both hits as one cause (the user's rule, 2026-10-28). The site tells such a cause as
"N failures at once", each failure in the fold, and each culprit's mistake is counted as their own failure (`by_culprit`). A death within `STUNG_S` (1 s) of an avoidable hit on the same
player is their own, whatever else made it lethal. The 1 s comes from the gap histogram: across the caches these gaps
run 0-1.0 s, and a mechanic's next step comes 1.3 s or later. The rule does not apply when a rule already blames the
victim alone for the hit that killed them, such as their own wrong laser: that death stays a mistake of its own, next to
the avoidable hit. A later death from the same player's earlier mistake is fallout of it,
counted once. When a mechanic fails because the player who should have done it was already dead (an unsoaked tower, a
bait that found someone else, a share a sharer short), the blame passes to whoever caused that death; the site shows the
chain as a tree (`trace`), the immediate cause first and the earlier deaths folded under it. A player killed by a hit
that was theirs to take is marked as healing or mitigation, with no culprit. Anything no rule explains is left
unattributed rather than guessed.

**Rule tags.** Every rule's fault carries a tag, a stable id such as `p2.tower.undecided` or `sc1.laser.both` (`fault(...,
tag=)`, required), and every classifier entry the tag of the rule that decided it. Code decides by tags, never by a rule's
text, so wording can change freely: the summaries' labels come from `LABELS` in `scorecard.py` (a label, or a tower or
tether failure named with its mechanic), and an entry about several faults at once is named by the first of them in
`MAIN_ORDER` in `classifier.py`. A new rule needs a new tag and a label; an unknown tag stops the analysis.

**Confidence.** How sure the classifier's reading of the log is (the user's definition, 2026-10-28): every verdict that
rests on positions holds by a margin (how far past a laser's edge, a tower's reach, a spot's tolerance, how much nearer
an add), and the log's positions are only so exact. They are logged with events, not continuously, so one read between
samples is interpolated, and even one at a hit is the spot as logged, not as the game snapshotted it (the soft edge every
AoE shows). `POS_ERR` in `classifier.py` is that error, measured: 90% of positions read *g* seconds from the nearest sample
are within 0.38 y at *g* = 0, 0.63 y at 0.2 s, 1.36 y at 0.5 s and 2.78 y at 1 s (leave one out of 450,000 samples,
`scratch/review/pos_error.py`). A distance from two positions combines both errors (`unc`). A verdict is *high* when its
margin is at least twice that error, *medium* when at least once, *low* under it (`certainty`); where another player
could equally be the culprit, low is *undecided* and the players named share the mistake. The same holds for what is
not a position: a cast against the boss's snapshot (`TIME_ERR`, 0.1 s), a hit's damage roll (±5%, `SHARE_ROLL`). Facts the
log states (standing in an avoidable hit, a tower nobody stood in) are high. A tolerance learned from clean pulls (how
far off a spot still counts as on it, a tower's reach) stays a rule; only the confidence of the verdict comes from the
margin. A stale reading keeps a player a candidate: it is no proof they stood at their spot. At most medium where a
replay does not reproduce what the log shows. Blame passed on through an earlier death is as sure as the least sure
death behind it. Confidence is shown, not discounted (the user's call, 2026-10-28, after the measurement below found the
levels about equally right).

**Shares.** Apart from confidence, every culprit carries their share of the mistake (`shares` on the classifier's entries,
set by `fault(share=...)`): 1 when it is their own mistake, also when two players each stood off their spot; 1/n when it is
one mistake among n players the model cannot tell apart (every rule tagged `.undecided`, a Glaukopis swap or Athena's
auto-attack that neither tank's casts explain, a crowd in a purple pair whose joiner is unknown: all but two of them); and
1/8 each for a healing and mitigation shortfall spread over the party (raidwide deaths), a dead player's eighth passed to
whoever caused their death. Blame carried over from an earlier death takes that death's share times the slot's; a culprit
named twice in one hit keeps the larger. Mistakes per pull and Wipes add up shares (`mistakes_of`, `wipe_shares`); the site
shows a share under 1 beside the name ("½").

How often the verdicts are right was measured on 2026-10-28 on a held-out sample: 25 verdicts per level, drawn at random
from pulls not in the hand-checked suite, judged by their own raid day's rules and checked against the log and the cached
positions (`scratch/accuracy/`; a verdict naming only part of its culprits counts half, one the log cannot decide is left
out). The check was by hand, not blind, and the undecided verdicts were judged by the user's rulings.

| | High | Medium | Low |
|---|---|---|---|
| Counted mistakes | 92% (avoidable hits 25 of 25, rule-based 84%; weighted to their 1,503 and 1,583) | 88% | 94% |
| Wipes | 94% | 88% | 100% |

With 25 verdicts a level the 90% intervals span 10-25 points (rule-based high 69-93%, medium 73-95%). Confidence no longer tracks accuracy: medium
verdicts are as reliable as rule-based high ones, and low ones score well because the players they name do include the
culprit, so low's weight worked as a share of blame between candidates rather than a discount for doubt: hence the shares
above, and no discount. The errors found
were concentrated in the fallbacks; the first five were fixed the same day (approved by the user; the figures are from
before the fixes). The rules were then fixed against these very verdicts, so measuring again needs a fresh draw; this
one was `scratch/accuracy/sample.py --draw 25 1028`.

- Paradeigma I without the replay (`wf_closer`): a baiter at their seat is blamed (high) when someone out of place stood as
  close to the add, within half a yalm, or ran past it (3 of 175).
- Paradeigma II: a Soul dropped in the wrong quadrant is not blamed when the misplaced tower is then soaked with the
  same-colour Tilt or stacked on another, and an explosion of two towers both soaked with the same-colour Tilt goes to the
  first soaker only (4).
- Superchain I lasers the replay does not reproduce: the fallback blames the victim, standing at their spot, when the
  Strong Soul aimed from off theirs or before settling (2, a third the log cannot decide, and a wipe chained to one).
- A Soul holder given a tether too, the party short, is blamed directly for their tower (3).
- The White Flame replay blames a player inside their tolerance when its correction needs them alongside one far off (2).
- A death with no hit within `JUMP_S` of the end, followed by a mass death, counts as a jump and cut that collapse off (1).
  Left as it is: a death with no logged hit stems from a jump off the platform (the user, 2026-10-28); whether the jump
  was justified is the open question. 21 pulls have such a death followed within 6 s by three or more deaths to hits.

Several undecided towers had landed 12-18 y off their spot while their soaker waited at or near it; the ruling makes
those both players', where a stricter reading would blame the dropper alone.

**Testing a change.** `python tests/run.py blame` checks the classifier against the hand-checked pulls in the
git-ignored `tests/blame_cases.json`, and `python tools/scorecard/blame_diff.py` prints every attribution a change moved
over all cached pulls. The suite's pulls were used to fix the rules, so its passing is no measure of accuracy (see
above). The workflow, the case fields and the check that every rule has a guarding case:
[tests/README.md](../../tests/README.md#blame-suite-the-scorecards-mistake-classifier).

The classifier assumes the group plays the strategy in the briefs: the line-up for Paradeigma I rather than tank
invulnerabilities, the quadrant sweep, and the Paradeigma III placements. A group that plays a mechanic differently will
see players blamed wrongly for it.

**The rule book** (`RULEBOOK` in `classifier.py`) says which rules judge each mechanic from which raid day (the report's
date, as the site groups raid days). A pull is judged by the latest entry dated on or before its day, so a strategy
change is a new dated entry and older pulls keep the rules they were played under; run `build_site.py --reanalyse` after
changing it. An entry is a rule function, `GENERIC` (only the generic rules; also any mechanic not listed), `NOT_YET`
(blames no one in the mechanic, for one the groups are still learning: its deaths and Damage Downs are listed as "not
blamed") or `AVOIDABLE_ONLY` (for the days before a strategy: only standing in an avoidable hit, and a death within
`STUNG_S` of one). Fallout of an earlier mistake keeps its blame, and a collapse in a mechanic not blamed decides the wipe
with no culprit rather than passing it to an unrelated earlier mistake. The suite judges its pulls from before a strategy
by the strategies' rules all the same (`rules_day`, 2026-10-25), unless a case says `own_day`. The site draws each dated
entry on its raid-day charts as a dashed vertical line between the raid days around it, with a short note ("Para I/II,
Glaukopis strategy"; "changed" when a mechanic's rules change rather than start): `strategy_dates()`, passed on as
`strategies` in the site data.

| Mechanic | Entries |
|---|---|
| Paradeigma I, Paradeigma II, Glaukopis (both) | `AVOIDABLE_ONLY` until the group's strategies took effect on 2026-09-29 (Trinity of Souls and Ray of Light still blamed); their rules from then (the raid day of 2026-09-23 is before it). |
| Superchain I, Dialogos | `AVOIDABLE_ONLY` until the group's strategy was introduced on 2026-10-06; its rules from then (the raid days of 2026-09-23, 09-30 and 10-04 are before it; 10-04 had only two groups). |
| Paradeigma III | `AVOIDABLE_ONLY` until the original strategy arrived on 2026-10-25. From then, when two bright Souls soak one middle tower, the day's rule says which of them belongs on the other platform, and only they are blamed: on 2026-10-25 by light party (LP1 the northern middle platform, LP2 the southern; both in one, the healer keeps theirs and the tank takes the other: `bright_seat_lp`), from 2026-10-26 by the priority H1 > T1 > T2 > H2, east to west. The seats come from the light parties learned in Paradeigma I (light party 1 is T1, H1, M1, R1). |
| Palladion | `NOT_YET`. To start blaming it, add `("YYYY-MM-DD", GENERIC)` or a rule. |

## The benchmark

**Minimum party DPS to clear.** The Party DPS 0:00-2:00 views show the 0:00-2:00 party DPS that is on pace to kill
just before enrage (7:38): boss HP over the enrage time, times the clears' median ratio of their 0:00-2:00 party DPS
to their whole-fight average (about 1.11; they front-load opener and burst). Stored as `party_dps_min` in
`benchmark.json`; about 79.4k with the current clears.

**The Echo.** Some clears were played with The Echo turned on (+20% damage, HP and healing): 16 of the 45, all among the
faster kills (Echo is what made them fast). They still count for everything about casts and timing (rotation checks, openers, burst, cooldowns, gauges)
but not for damage, boss HP checkpoints or kill time. The exception is a job with fewer than three clear players without The Echo: its
Echo clears count too, damage divided by 1.2 (rDPS, damage by phase, opener damage), marked `echo_corrected`. That
fills Dragoon, Gunbreaker, White Mage, Summoner, Red Mage and others; the corrected values land within a few percent
of the few clean ones. `python tools/scorecard/build_benchmark.py --rebuild` recomputes
`benchmark.json` from the kills it already lists. Our own reports are checked the same way: pulls with The Echo are left
out of every damage figure (rDPS against clearers, damage by phase, opener damage, party DPS, boss HP checkpoints, damage
lost to deaths) and the group, day and player pages say so; mistakes, deaths and rotation checks still count.

`benchmark.json` holds what players in other groups' clears do, per job: Savage P1 clears from Dawntrail on
(28 June 2024, patch 7.0; jobs played differently before it, so no earlier clear is ever used) that took
5:30–7:50, played at level 90 in capped gear like ours. Level 100 runs and lower-gear runs are left
out, tincture damage is removed, and players who died are skipped. Each job's value is the average over
distinct players, over every clear without The Echo (29 clears; an earlier split into peer
and fast clears was dropped: without The Echo the faster ones were only 6:54-7:08 and within 1% in party DPS). It covers 0:00–2:00 (rDPS,
nDPS, the rDPS their buffs gave others, uptime, and each player's rDPS), the buffs' credit up to Palladion against
0:00-2:00 per job (`given_ratio`, over every clear, The Echo included since it changes both alike, and only players who
used their raid buff in each 2-minute burst: about half the clears' Reapers hold the second Arcane Circle to 2:56-3:12,
leaving two before Palladion) and every phase of the fight (nDPS, uptime; only phases a kill lived through, so Superchain IIB
comes from the slower clears alone).

It also holds the boss HP checkpoints. For each mechanic, a line is fitted through every benchmark kill: the
HP % left when the mechanic began against how long the kill took. Clear is that line at 7:38, Comfy at 7:25.

The file is a snapshot. To rebuild it:

```
python tools/scorecard/build_benchmark.py [--since 2025-01-01] [--until 2026-10-18] [--out FILE]
python tools/scorecard/build_benchmark.py --checkpoints-only     # only refit the HP checkpoints, same kills
python tools/scorecard/build_benchmark.py --windows-only         # only redo the per-phase values, same kills
python tools/scorecard/build_benchmark.py --add --since 2024-06-28 --until 2024-12-31   # add a period's clears
```

`--since` is never earlier than 28 June 2024. Clears in archived reports count only after `fflogs.py --login`.

A full rebuild reads several thousand report pages and can use an hour or more of the API's hourly budget; it
waits out the rate limit by itself and caches its progress in `.cache/benchmark/`, so it can be stopped and
resumed. Run `build_site.py --reanalyse` afterwards so the site picks up the new values.

## Files

| File | Purpose |
|---|---|
| `build_site.py` | The command: adds reports to the website's data (`site/data.json`); `--publish` writes the public copy to `stats/` (`public.json` open, the rest to Supabase and, with a passphrase, `data.enc.json`) |
| `supa.py` | Uploads to Supabase, writes audit entries; `status`, `admin`, `staff`, `audit`, `probe` |
| `worker.py`, `worker.service` | Builds what the admin page's report list asks for and watches live reports (runs in WSL) |
| `supabase/` | The Supabase project: `config.toml` and the schema with its access rules, roles and audit log (`migrations/`) |
| `scorecard.py` | The analysis: fetching, mistakes and wipes, damage against clearers, damage lost to deaths, damage per phase |
| `classifier.py` | Mistake attribution, and the rule book of which rules apply from which raid day |
| `blame_diff.py` | Every attribution that changes between two versions of the classifier, over every cached report |
| `checks.py` | Rotation checks against the clears |
| `acts.py` | Casts, begun casts and outgoing damage per pull, cached |
| `gamedata.py` | Action data (GCD or not, base recast, charges) and action icons from XIVAPI, cached |
| `fflogs.py` | FFLogs v2 client: token, rate-limit waits, paged events, batched tables, character ids, a report's upload state; `--login` for archived reports |
| `benchmark.json` | Benchmark snapshot used for the damage, uptime and HP checkpoint comparisons |
| `build_benchmark.py` | Rebuilds `benchmark.json` |
| `encrypt_data.js` | Encrypts the data for `--publish` without Supabase (Node) |
| `site/` | The website: `index.html`, `style.css`, `app.js`, and the generated `data.json` (git-ignored) |
| `.cache/` | Downloaded reports, the API token and benchmark progress (git-ignored) |

The folder is left out of the GitHub Pages site by the deploy workflow.
