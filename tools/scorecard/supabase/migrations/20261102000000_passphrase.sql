-- The staff passphrase (2026-11-02): the password of one shared staff account, so the passphrase reads the same live
-- tables as a staff login instead of an encrypted copy of the last publish (data.enc.json, gone). supa.py passphrase
-- makes the account; changing the passphrase deletes it and makes a new one, which also ends every session it had.
-- Everyone who has the passphrase shares the account, so none of them may delete it or change its password or email.

alter table profiles add column shared boolean not null default false;   -- authenticated may update only role

create or replace function delete_my_account() returns void language plpgsql security definer set search_path = public, auth as $$
begin
  if exists (select 1 from profiles where user_id = auth.uid() and shared) then
    raise exception 'the staff passphrase account is shared; an admin removes it'; end if;
  delete from auth.users where id = auth.uid();
end $$;

-- GoTrue writes auth.users as its own database role whoever asks, so the rule is on the row: the shared account's
-- password, email and phone stay as supa.py made them (it replaces the account instead of changing them)
create function shared_account_fixed() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from profiles where user_id = new.id and shared)
     and (new.encrypted_password is distinct from old.encrypted_password or new.email is distinct from old.email
          or new.email_change is distinct from old.email_change or new.phone is distinct from old.phone
          or new.phone_change is distinct from old.phone_change) then
    raise exception 'the staff passphrase account cannot be changed; supa.py passphrase replaces it';
  end if;
  return new;
end $$;
create trigger shared_account_fixed before update on auth.users for each row execute function shared_account_fixed();
