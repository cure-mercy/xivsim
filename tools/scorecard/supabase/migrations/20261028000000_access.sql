-- Step 2 of ACCESS_CONCEPT.md: accounts linked to players.
--
-- The build (build_site.py, worker.py) writes the data with the service key, which bypasses row-level security.
-- Everyone else reads through these policies: progress for linked users, a report's full record for the users whose
-- player is in it, everything for admins. Admins also manage link requests and the list of reports (report_sources)
-- from the site's admin page; the worker builds what that list asks for.

create table players (
  id bigint primary key,            -- FFLogs character id; negative for a character FFLogs could not find (a hash)
  name text not null,
  world text
);

create table reports (
  code text primary key,
  day date not null,
  group_name text not null,
  built timestamptz not null default now()
);

create table report_players (
  report_code text references reports on delete cascade,
  player_id bigint references players on delete cascade,
  primary key (report_code, player_id)
);
create index on report_players (player_id);

create table progress (code text primary key references reports on delete cascade, doc jsonb not null);   -- the whitelisted fragment
create table report_full (code text primary key references reports on delete cascade, doc jsonb not null); -- the full record
create table site_meta (key text primary key, doc jsonb not null);   -- strategies, the private benchmark, ours

create table profiles (
  user_id uuid primary key references auth.users on delete cascade,
  display_name text,
  role text not null default 'member' check (role in ('member', 'admin')),
  created_at timestamptz not null default now()
);

create table user_players (
  player_id bigint primary key references players on delete cascade,   -- each player belongs to at most one user
  user_id uuid not null references auth.users on delete cascade,
  status text not null default 'requested' check (status in ('requested', 'approved')),
  requested_at timestamptz not null default now(),
  approved_by uuid references auth.users on delete set null,
  approved_at timestamptz
);
create index on user_players (user_id);

-- the reports the site should have, managed on the admin page. The worker (worker.py) adds, renames, rebuilds and
-- removes reports to match, and keeps re-reading a live one until live_until
create table report_sources (
  code text primary key check (code ~ '^[A-Za-z0-9]{16}$'),
  group_name text check (group_name ~ '^[A-Za-z0-9][A-Za-z0-9 _.-]{0,23}$'),   -- null: the day's next free G1, G2, ...
  want text not null default 'present' check (want in ('present', 'absent')),
  live_until timestamptz,             -- keep checking FFLogs for new pulls until then (at most 12 h ahead)
  rebuild_at timestamptz,             -- an admin asked for a fresh download at this time
  state text not null default 'queued' check (state in ('queued', 'building', 'ok', 'error')),
  message text,
  day date,
  pulls int,
  segments int,                       -- FFLogs' uploaded segments when last built, to notice new pulls
  report_end timestamptz,             -- the report's last event when last checked
  checked_at timestamptz,
  built_at timestamptz,
  added_by uuid references auth.users on delete set null,
  added_at timestamptz not null default now()
);

-- ---------- who may read what ----------
create function is_admin() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where user_id = auth.uid() and role = 'admin') $$;
create function linked() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from user_players where user_id = auth.uid() and status = 'approved') $$;
create function my_report(c text) returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from report_players rp join user_players up on up.player_id = rp.player_id
                 where rp.report_code = c and up.user_id = auth.uid() and up.status = 'approved') $$;

alter table players        enable row level security;
alter table reports        enable row level security;
alter table report_players enable row level security;
alter table progress       enable row level security;
alter table report_full    enable row level security;
alter table site_meta      enable row level security;
alter table profiles       enable row level security;
alter table user_players   enable row level security;
alter table report_sources enable row level security;

-- nothing is open to anonymous visitors; logged-in users get only what the policies below let through
revoke all on players, reports, report_players, progress, report_full, site_meta, profiles, user_players, report_sources from anon;
revoke all on players, reports, report_players, progress, report_full, site_meta, profiles, user_players, report_sources from authenticated;
grant select on players, reports, report_players, progress, report_full, site_meta, profiles, user_players, report_sources to authenticated;
grant update (status, approved_by, approved_at) on user_players to authenticated;
grant delete on user_players to authenticated;
grant update (role) on profiles to authenticated;
grant insert (code, group_name, live_until) on report_sources to authenticated;
grant update (group_name, want, live_until, rebuild_at) on report_sources to authenticated;

create policy read_reports   on reports        for select to authenticated using (linked() or is_admin());
create policy read_progress  on progress       for select to authenticated using (linked() or is_admin());
create policy read_meta      on site_meta      for select to authenticated using (linked() or is_admin());
create policy read_full      on report_full    for select to authenticated using (is_admin() or my_report(code));
create policy read_rp        on report_players for select to authenticated using (is_admin() or exists (
  select 1 from user_players up where up.player_id = report_players.player_id and up.user_id = auth.uid() and up.status = 'approved'));
create policy read_players   on players        for select to authenticated using (is_admin() or exists (
  select 1 from user_players up where up.player_id = players.id and up.user_id = auth.uid()));
create policy read_profiles  on profiles       for select to authenticated using (user_id = auth.uid() or is_admin());
create policy admin_role     on profiles       for update to authenticated using (is_admin()) with check (is_admin());
create policy read_links     on user_players   for select to authenticated using (user_id = auth.uid() or is_admin());
create policy admin_approve  on user_players   for update to authenticated using (is_admin()) with check (is_admin());
create policy drop_link      on user_players   for delete to authenticated using (user_id = auth.uid() or is_admin());   -- unlinking yourself, or an admin rejecting
create policy admin_sources  on report_sources for select to authenticated using (is_admin());
create policy admin_add      on report_sources for insert to authenticated with check (is_admin());
create policy admin_change   on report_sources for update to authenticated using (is_admin()) with check (is_admin());

-- ---------- profiles follow auth.users ----------
create function new_profile() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (user_id, display_name) values (new.id, coalesce(new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'name', new.raw_user_meta_data->>'user_name', split_part(new.email, '@', 1)));
  return new;
end $$;
create trigger new_profile after insert on auth.users for each row execute function new_profile();

-- ---------- report_sources: admin changes queue a build, live watching has a hard limit ----------
create function source_rules() returns trigger language plpgsql set search_path = public as $$
begin
  if new.live_until > now() + interval '12 hours' then new.live_until := now() + interval '12 hours'; end if;
  if current_user <> 'service_role' then   -- the worker sets state itself
    if tg_op = 'INSERT' then new.added_by := auth.uid(); new.state := 'queued'; new.message := null;
    elsif new.group_name is distinct from old.group_name or new.want <> old.want or new.rebuild_at is distinct from old.rebuild_at
       or (new.live_until is distinct from old.live_until and new.live_until > now()) then
      new.state := 'queued'; new.message := null;
    end if;
  end if;
  return new;
end $$;
create trigger source_rules before insert or update on report_sources for each row execute function source_rules();

-- ---------- what users do themselves ----------
-- ask to be linked to a character, by its name (and world when the name is not unique). Answers 'requested',
-- 'already' (yours already), 'taken' (someone else's), 'not_found', 'ambiguous' or 'too_many'
create function request_link(p_name text, p_world text default null) returns text
language plpgsql security definer set search_path = public as $$
declare pid bigint; n int; owner uuid;
begin
  if auth.uid() is null then raise exception 'not logged in'; end if;
  select count(*), min(id) into n, pid from players
   where lower(name) = lower(trim(p_name)) and (p_world is null or trim(p_world) = '' or lower(world) = lower(trim(p_world)));
  if n = 0 then return 'not_found'; end if;
  if n > 1 then return 'ambiguous'; end if;
  select user_id into owner from user_players where player_id = pid;
  if owner = auth.uid() then return 'already'; end if;
  if owner is not null then return 'taken'; end if;
  if (select count(*) from user_players where user_id = auth.uid() and status = 'requested') >= 3 then return 'too_many'; end if;
  insert into user_players (player_id, user_id) values (pid, auth.uid());
  return 'requested';
end $$;

-- delete your account: your profile and links go with it (on delete cascade)
create function delete_my_account() returns void language sql security definer set search_path = public, auth as $$
  delete from auth.users where id = auth.uid() $$;

revoke execute on function request_link(text, text), delete_my_account() from public, anon;
grant execute on function request_link(text, text), delete_my_account() to authenticated;
revoke execute on function is_admin(), linked(), my_report(text) from public, anon;
grant execute on function is_admin(), linked(), my_report(text) to authenticated;
