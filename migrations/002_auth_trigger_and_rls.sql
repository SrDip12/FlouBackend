-- Migration: Setup Auth Triggers and RLS for Profiles

-- 1. Create a function to handle new user signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, avatar_url, role)
  values (
    new.id,
    new.raw_user_meta_data ->> 'full_name',
    new.raw_user_meta_data ->> 'avatar_url',
    coalesce((new.raw_user_meta_data ->> 'role')::user_role, 'student')
  );
  return new;
end;
$$;

-- 2. Create the trigger
-- Drop the trigger first if it exists to avoid errors on replacement
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- 3. Enable Row Level Security (RLS) on profiles
alter table public.profiles enable row level security;

-- 4. Create Policies
-- Drop policies if they exist before creating them
drop policy if exists "Users can view own profile" on public.profiles;
create policy "Users can view own profile"
on public.profiles for select
using ( auth.uid() = id );

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile"
on public.profiles for update
using ( auth.uid() = id );

-- Optional: Public profiles
-- drop policy if exists "Public profiles are viewable by everyone" on public.profiles;
-- create policy "Public profiles are viewable by everyone"
-- on public.profiles for select
-- using ( true );
