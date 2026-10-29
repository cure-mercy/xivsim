-- Staff only (2026-10-29): the site is for Syncademy staff, not for every player. Anyone may log in with Discord, but an
-- account sees nothing until an admin approves it as staff; staff see every report in full, admins also get the admin
-- page. This replaces linking accounts to players (who saw only their own reports, and no mistakes by mechanic on the
-- latest raid day). Everything admins and the build do is kept in audit_log.
--
-- Roles: pending (logged in, not approved), staff, admin.

-- ---------- linking accounts to players goes ----------
drop policy read_reports  on reports;
drop policy read_progress on progress;
drop policy read_meta     on site_meta;
drop policy read_full     on report_full;
drop policy read_players  on players;          -- these two look at user_players
drop policy read_rp       on report_players;
drop function request_link(text, text);
drop table user_players;
drop table report_players;
drop table players;
drop function linked();
drop function my_report(text);

-- ---------- roles ----------
alter table profiles drop constraint profiles_role_check;
update profiles set role = 'pending' where role = 'member';
alter table profiles add constraint profiles_role_check check (role in ('pending', 'staff', 'admin'));
alter table profiles alter column role set default 'pending';

create function is_staff() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where user_id = auth.uid() and role in ('staff', 'admin')) $$;
revoke execute on function is_staff() from public, anon;
grant execute on function is_staff() to authenticated;

create policy read_reports  on reports     for select to authenticated using (is_staff());
create policy read_progress on progress    for select to authenticated using (is_staff());
create policy read_meta     on site_meta   for select to authenticated using (is_staff());
create policy read_full     on report_full for select to authenticated using (is_staff());

-- an admin changes other accounts' roles, never their own (no locking yourself out, no last admin gone by accident)
drop policy admin_role on profiles;
create policy admin_role on profiles for update to authenticated using (is_admin() and user_id <> auth.uid()) with check (is_admin() and user_id <> auth.uid());

-- an admin removes an account (a login that isn't staff, or someone who left), never their own
create function remove_account(p_user uuid) returns void language plpgsql security definer set search_path = public, auth as $$
begin
  if not is_admin() then raise exception 'only admins remove accounts'; end if;
  if p_user = auth.uid() then raise exception 'use Delete my account for your own'; end if;
  delete from auth.users where id = p_user;
end $$;
revoke execute on function remove_account(uuid) from public, anon;
grant execute on function remove_account(uuid) to authenticated;

-- ---------- the audit log ----------
-- Written only by the triggers below and by the build (build_site.py, worker.py, with the service key); admins read it.
-- actor is the account that did it, null for the command line and the worker; actor_name is its name at the time.
create table audit_log (
  id         bigint generated always as identity primary key,
  at         timestamptz not null default now(),
  actor      uuid,
  actor_name text,
  action     text not null,
  target     text,
  detail     jsonb
);
create index on audit_log (at desc);
alter table audit_log enable row level security;
revoke all on audit_log from anon, authenticated;
grant select on audit_log to authenticated;
create policy admin_audit on audit_log for select to authenticated using (is_admin());

create function audit(p_action text, p_target text, p_detail jsonb default null, p_actor uuid default auth.uid(), p_name text default null)
returns void language sql security definer set search_path = public as $$
  insert into audit_log (actor, actor_name, action, target, detail)
  values (p_actor, coalesce(p_name, (select display_name from profiles where user_id = p_actor)), p_action, p_target, p_detail) $$;
revoke execute on function audit(text, text, jsonb, uuid, text) from public, anon, authenticated;
-- who is asking, inside these SECURITY DEFINER functions (where current_user is their owner): the request's role
create function by_service_key() returns boolean language sql stable set search_path = public as $$
  select coalesce(auth.role(), '') = 'service_role' or coalesce(current_setting('role', true), '') = 'service_role' $$;

-- accounts: created (the first login), roles, removed
create function audit_profiles() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' then
    perform audit('account created', new.display_name, null, new.user_id);
  elsif tg_op = 'UPDATE' and new.role <> old.role then
    perform audit(case when old.role = 'pending' and new.role = 'staff' then 'approved as staff'
                       when new.role = 'admin' then 'made admin'
                       when old.role = 'admin' and new.role = 'staff' then 'admin rights removed'
                       when new.role = 'pending' then 'staff access revoked'
                       else 'role changed' end,
                  new.display_name, jsonb_build_object('from', old.role, 'to', new.role));
  elsif tg_op = 'DELETE' then
    perform audit(case when old.user_id = auth.uid() then 'deleted own account' else 'account removed' end, old.display_name,
                  jsonb_build_object('role', old.role), auth.uid(),
                  case when old.user_id = auth.uid() then old.display_name end);   -- their profile is gone by now
  end if;
  return null;
end $$;
create trigger audit_profiles after insert or update or delete on profiles for each row execute function audit_profiles();

-- logins: GoTrue sets last_sign_in_at at each login (not when a session is merely refreshed)
create function audit_login() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.last_sign_in_at is distinct from old.last_sign_in_at then
    perform audit('logged in', (select display_name from profiles where user_id = new.id),
                  jsonb_build_object('provider', new.raw_app_meta_data->>'provider'), new.id);
  end if;
  return null;
end $$;
create trigger audit_login after update of last_sign_in_at on auth.users for each row execute function audit_login();

-- the report list, as admins change it on the admin page (the worker's own updates are its business: it writes what
-- it built itself)
create function audit_sources() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if by_service_key() then return null; end if;
  if tg_op = 'INSERT' then
    perform audit('report added', new.code, jsonb_strip_nulls(jsonb_build_object('group', new.group_name, 'live_until', new.live_until)));
  else
    if new.group_name is distinct from old.group_name then
      perform audit('report renamed', new.code, jsonb_build_object('from', old.group_name, 'to', new.group_name)); end if;
    if new.want <> old.want then perform audit(case when new.want = 'absent' then 'report removal asked' else 'report kept' end, new.code,
                                               jsonb_build_object('group', new.group_name)); end if;
    if new.rebuild_at is distinct from old.rebuild_at then perform audit('rebuild asked', new.code, jsonb_build_object('group', new.group_name)); end if;
    if new.live_until is distinct from old.live_until then
      perform audit(case when new.live_until > now() then 'live watch started' else 'live watch stopped' end, new.code,
                    jsonb_build_object('group', new.group_name, 'until', new.live_until)); end if;
  end if;
  return null;
end $$;
create trigger audit_sources after insert or update on report_sources for each row execute function audit_sources();

create function audit_searches() returns trigger language plpgsql security definer set search_path = public as $$
begin
  perform audit('FFLogs searched', new.day::text, jsonb_strip_nulls(jsonb_build_object('names', nullif(new.names, ''))));
  return null;
end $$;
create trigger audit_searches after insert on report_searches for each row execute function audit_searches();
