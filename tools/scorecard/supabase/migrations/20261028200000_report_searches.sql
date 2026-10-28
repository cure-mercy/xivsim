-- Searches for P12S reports on FFLogs, from the admin page: an admin asks for a raid day (and names to look for),
-- the worker answers (worker.py, fflogs.find_reports) and keeps a week of them. Only admins read or ask.
create table report_searches (
  id        bigint generated always as identity primary key,
  day       date not null,
  names     text not null default '' check (length(names) <= 300),   -- comma-separated characters, "Name" or "Name@World"
  asked_by  uuid default auth.uid() references auth.users on delete set null,
  asked_at  timestamptz not null default now(),
  state     text not null default 'queued' check (state in ('queued', 'running', 'done', 'error')),
  message   text,
  results   jsonb,   -- {reports: [...], listed: n}, see worker.search
  done_at   timestamptz
);
alter table report_searches enable row level security;

revoke all on report_searches from anon, authenticated;
grant select on report_searches to authenticated;
grant insert (day, names) on report_searches to authenticated;   -- who asked, when and the answer are set for them
create policy admin_searches on report_searches for select to authenticated using (is_admin());
create policy admin_search   on report_searches for insert to authenticated with check (is_admin());
