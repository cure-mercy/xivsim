# Concept: public rotations and gear, then accounts linked to players

Status: draft, 2026-10-26. Step 1 built 2026-10-28 (see the scorecard README, "Publishing with a passphrase"); step 2
not started.

## Goal

1. **Step 1.** Anyone can open the rotation and gear pages without logging in. Progress and mistakes stay locked
   behind the passphrase, as they are now.
2. **Step 2.** The site has user accounts. A user linked to a player can see:
   - global progress: every day and every group, with no player names, and
   - full data, mistakes included, for the groups their player played in.

   A user who isn't linked yet sees only the public pages.

## Where things stand

`build_site.py` writes one `site/data.json` (13.1 MB). `--publish` gzips and encrypts all of it into
`stats/data.enc.json` (6.1 MB), using AES-256-GCM with one shared passphrase. The browser has to download and decrypt
the whole file before it can draw any page.

| Part of data.json | Size | Contains player names or mistakes? | Read by |
|---|---|---|---|
| `rotations` | 5.7 MB | No. It has counts of our players per job (`players`, `conv_players`), and the conversions come from their median gear. | Rotations pages, plus a link from the player page |
| `gear` | 0.6 MB | No | Gear pages |
| `benchmark` | 18 kB | No. `pools` and `windows` come from public FFLogs clears. `mistake_times` holds counts over our pulls. | Rotations (`pools`), every progress page |
| `strategies` | <1 kB | No, but it shows when each strategy started, which is part of our progress timeline | Progress charts |
| `reports` | 7.6 MB | Yes: `players`, `pulls[].wipe.culprits`, `death_list`, `light_parties`, `burst`, … | Every progress page |

A script found none of the 71 player names anywhere outside `reports`. Splitting the data by access level is
therefore mostly a matter of moving keys around. The one part that needs real work is `reports`, which mixes
group-level progress with per-player data.

Players are identified only by their name string (`"Mafboss Falafell"`). There is no home world and no ID.
Step 2 needs a stable player ID.

## Data split (shared by both steps)

The build writes the data as three kinds of fragment instead of one file. Step 1 and step 2 differ only in how
the fragments are protected.

| Fragment | Content | Step 1 | Step 2 |
|---|---|---|---|
| `public.json` | `rotations`, `gear`, `benchmark.pools`, `benchmark.windows`, `hp_checkpoints` | Plaintext file on Pages | Same |
| `progress` | Per report: `code, group, day, start, pulls_total, kills, best, longest, clean2, party, hp, causes, wipe_causes, lost_*` (by cause, no names), and per pull `n, dur, boss, kill, first, deaths, wipe.{t, mechanic, label}`. Also `strategies` and the rest of `benchmark` | Encrypted | Any linked user |
| `report/<code>` | The report's full record: `players`, full `pulls`, `light_parties`, `burst`, `echo` | Encrypted | Users whose player is in that report, and admins |

- The `progress` fragment is a **whitelist**. A new field stays private until someone adds it to the list on
  purpose. `wipe.label` names the cause only ("Paradeigma II: Soul tower in the wrong quadrant"). `wipe.cause` is
  left out because it is the sentence that names players.
- The day page and the raid-days page must work from `progress` alone. Right now they only use group-level
  figures, but they read them from the full report objects, so they need to be checked one by one.
- On the client, `DATA.reports[code]` becomes `progress` merged with `report/<code>` when the user has access to
  it, and `progress` alone when they don't. The group, pull and player pages check for `r.players`. When it is
  missing, they show "Not your group" (with the group's progress figures) instead of failing.
- The player page's section on how the player did across raid days only uses reports that player was in. A user
  can read all of those, so it needs no fragment of its own.

## Step 1: public rotations and gear on GitHub Pages

No server and no accounts.

- `build_site.py --publish` writes `stats/public.json` (plaintext) and `stats/data.enc.json`. The encrypted file
  now holds only `progress` and the reports, so it shrinks from about 6.1 MB to under 3 MB.
- `boot()` loads `public.json` first and draws `#/rotations` and `#/gear` right away. The passphrase form appears
  only when someone opens a progress route (`#/`, `#/day/…`), and the data is decrypted only then. The Rotations and
  Gear links in the header work while the data is still locked.
- When the site is locked, a visitor to `#/` sees the passphrase form with links to Rotations and Gear next to it.
- Local development keeps working. If `site/data.json` exists, the page loads it and everything is visible, as
  it is now.
- `public.json` is uncompressed, but GitHub Pages serves JSON with gzip, so the download is close to what
  `data.enc.json` is now. Most of its size is icons stored as data URIs. If it ever matters, those can move to a
  cached `icons.json`.
- `index.html` stays `noindex` unless decision 4 says otherwise. Every route uses the same `index.html`, so
  indexing can't be allowed for the public pages alone.

As built:

- The rotation pages turned out to read `reports` too. The job chart's boxes are our players' clean-pull rDPS, and
  the rDPS columns add our players' median buff credit. The build now writes those figures as an anonymous per-job
  aggregate (`ours`), which stays locked. While the site is locked, the overview hides that chart, and rDPS falls
  back to the clears' buff credit, which the notes under the tables say.
- The locked site doesn't mention mistakes. The lock screen reads "The raid's progress is encrypted."
- The per-GCD counts of our players ("N of our players play at this GCD", and the "Our players" columns) were
  removed from the rotation pages, at your request.
- The name check runs inside `--publish` itself, not as a probe in `tests/run.py`, so a leaking `public.json` is
  never written. It matches whole names, because the actor "Chi Ji" appears inside "Ten Chi Jin".

### Optional bridge: one key per group, still static

Each `report/<code>` could be encrypted with its own random key. That key would in turn be encrypted ("wrapped")
under the passphrase of each group allowed to read it. A group would then see only its own reports, still on
GitHub Pages. This doesn't give real accounts, though. Revoking access means re-encrypting, and anyone who
downloaded a file earlier can keep trying passphrases on it offline. **I recommend skipping this** and going straight
to step 2.

## Step 2: accounts linked to players

### Access rules

| Who | Public pages | Global progress | Full reports, mistakes included |
|---|---|---|---|
| Anonymous | yes | no | no |
| Logged in, not linked | yes | no | no |
| Linked to player P | yes | yes | every report P is in (P's own data across days is a subset of this) |
| Admin | yes | yes | all |

A user can link to more than one player, for alts or a character that has been renamed. Each player belongs to at
most one user. Unlinking takes effect on the user's next request.

### Player identity

- The build saves each player's FFLogs character ID along with their name and home world. FFLogs report data has
  both, and the ID doesn't change when a character is renamed or moves worlds. The site keeps showing names, but
  access rules and links use the ID.
- Players get a `players` table with `id`, `name`, `world` and `fflogs_id`, plus a `report_players` table listing
  which players were in which report. The build fills both.

### Login and linking

- **Login: Discord OAuth** (recommended). The groups already organise there, nobody needs a new password, and the
  user ID is stable. Email magic links can be added later.
- **Linking, first version:** the user picks "I am …" from the list of players who aren't linked yet. An admin
  approves the request on a small admin page, or with a CLI command next to `build_site.py`. With about 70 people
  who know each other, that is enough.
- **Linking, later:** the user logs in with FFLogs and is linked automatically to the characters they have claimed
  there. `fflogs.py` already runs the user OAuth flow (PKCE). The `currentUser.characters` field in the user API
  needs to be checked before relying on this.

### Backend options

The build stays offline in Python as it is now. The backend only stores fragments, checks who may read which ones,
and serves them. Nothing is computed on the server.

| Option | Front end | Auth | Access enforced by | Upkeep | Notes |
|---|---|---|---|---|---|
| **A. Supabase** (recommended) | Stays on GitHub Pages | Built in, Discord provider | Postgres row-level security | Almost none, no server code | Free tier is enough for this size. Free projects pause after about a week without traffic. Open source, so it can be self-hosted later. |
| B. Cloudflare Pages + Worker + D1 | Moves to Cloudflare Pages | Hand-written OAuth and sessions in the Worker | Worker code | Low | Cheapest at scale, but you maintain the auth code yourself |
| C. Own server (Python FastAPI/Flask + SQLite on a VPS) | Served by the server | Library (Authlib) | Server code | Most: OS updates, TLS, backups | Same language as the tools, and no third party |

**Why A:** step 1's static site carries over unchanged. The access rules are about 15 lines of SQL instead of
auth code we write ourselves. The upload is an HTTP call from `build_site.py` with a service key that stays local
in a git-ignored file, like `.fflogs_v2` does.

### Schema (option A)

```sql
players         (id bigint pk /* FFLogs character id */, name text, world text)
reports         (code text pk, day date, group_name text, built timestamptz)
report_players  (report_code text references reports, player_id bigint references players, primary key (report_code, player_id))
progress        (code text pk references reports, doc jsonb)        -- the whitelisted fragment
report_full     (code text pk references reports, doc jsonb)        -- the full record
site_meta       (key text pk, doc jsonb)                            -- strategies, private benchmark parts
profiles        (user_id uuid pk references auth.users, role text check (role in ('member','admin')) default 'member')
user_players    (player_id bigint pk references players, user_id uuid references auth.users,
                 status text check (status in ('requested','approved')), approved_by uuid, approved_at timestamptz)
```

Row-level security only filters rows, not columns, so progress and full data go in separate tables:

```sql
create function linked() returns boolean language sql stable security definer as $$
  select exists (select 1 from user_players where user_id = auth.uid() and status = 'approved') $$;
create function is_admin() returns boolean language sql stable security definer as $$
  select exists (select 1 from profiles where user_id = auth.uid() and role = 'admin') $$;

alter table progress    enable row level security;
alter table report_full enable row level security;
create policy read_progress on progress    for select using (linked() or is_admin());
create policy read_full     on report_full for select using (is_admin() or exists (
  select 1 from report_players rp join user_players up on up.player_id = rp.player_id
  where rp.report_code = report_full.code and up.user_id = auth.uid() and up.status = 'approved'));
```

Every table gets row-level security. There are no insert or update policies, so writes happen only with the
service key from the build or the admin page. A test probe logs in with the public anon key and with an unlinked
test account and checks that `report_full` returns no rows to either.

### Client flow

1. Load `public.json` from Pages, as in step 1.
2. When a progress route is opened, show "Log in with Discord" if the user isn't logged in, or "Waiting for
   approval / pick your player" if they are logged in but not linked.
3. If the user is linked, fetch all `progress` rows (25 reports, a few hundred kB) and fetch `report_full` rows
   one at a time, only when a group or player page is opened (about 300 kB each). Pages draw as they do now, from
   `DATA.reports`.
4. The Lock button becomes Log out.

### Publishing

`build_site.py --publish` keeps writing `stats/public.json` for Pages. It upserts `players`, `reports`,
`report_players`, `progress` and `report_full`, then removes rows for reports that `--remove` took off the site.
`stats/data.enc.json` and the passphrase go away once step 2 is live.

## Things to keep in mind

- **The old encrypted file stays in git history.** Anyone who has the passphrase now, or guesses it later, can
  read the data as it was when it was published. Deleting `stats/data.enc.json` doesn't change that. Accept it, or
  rewrite the history once the move is done.
- **Small groups give people away.** Group-level progress has no names, but in a pull with a single Damage Down,
  the rest of the group can often tell who it was. This seems acceptable to me. If it isn't, global progress could
  show only boss HP and pull lengths, not mistakes by cause.
- **Rotations are built from our players' gear.** For a job only one of our players plays, the conversion
  reflects that player's substats. This is harmless, but it is the only player-derived value in `public.json`.
- **Personal data.** Step 2 stores Discord IDs, and it links them to characters and their mistakes. The site needs a
  short privacy note, plus a way for users to unlink themselves and delete their account. An admin should also be
  able to remove a player completely.

## Decisions for you

1. **What counts as "the group they played in"?** Either (a) the reports their player was in (recommended, and the
   rules above assume it) or (b) every report of the group they were in, such as all of G1's days, including days
   they missed. (b) only works if groups are fixed teams. It is a one-line change to the policy that joins on
   `group_name`.
2. **Login provider:** Discord (recommended), FFLogs, or email.
3. **Backend:** A Supabase (recommended), B Cloudflare, or C own server.
4. **Search indexing for the public pages:** keep `noindex` (recommended until step 2) or allow it.
5. ~~Rotation timelines use our raidplan positions.~~ Decided 2026-10-28: the raidplans are public, so these can
   be too.
6. **Can other groups' mistakes by mechanic count as global progress?** These are heatmaps by mechanic with no
   names. Yes is recommended. No limits global progress to boss HP and pull lengths.
7. **Should `ours` go public?** These are our players' anonymous rDPS spread and buff credit per job on the
   rotation pages. For a job only one or two of our players play, the figures are close to personal. They stay
   locked for now. Making them public means adding `"ours": None` to `PUBLIC_KEYS`.
