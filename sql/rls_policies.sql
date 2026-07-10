-- =============================================================================
-- Row-Level Security policies (defense-in-depth).
--
-- The FastAPI backend is the primary data path and connects with the Supabase
-- SERVICE ROLE, which BYPASSES RLS — so these policies do NOT constrain the
-- API. They exist to protect against *direct* Supabase access (anon /
-- authenticated roles), e.g. if the frontend ever queries Supabase directly.
--
-- They rely on two JWT claims injected by the custom access-token hook
-- (see access_token_hook.sql): `user_role` and `shop_id`.
--
-- Apply this in the Supabase SQL editor AFTER running `alembic upgrade head`.
-- =============================================================================

-- Helper expressions:
--   auth.jwt() ->> 'user_role'  -> 'super_admin' | 'shop_admin' | 'staff'
--   auth.jwt() ->> 'shop_id'    -> the caller's shop UUID (text) or NULL

-- ---- shops -----------------------------------------------------------------
alter table public.shops enable row level security;
create policy shops_tenant on public.shops
  for all to authenticated
  using (
    (auth.jwt() ->> 'user_role') = 'super_admin'
    or id = nullif(auth.jwt() ->> 'shop_id', '')::uuid
  )
  with check (
    (auth.jwt() ->> 'user_role') = 'super_admin'
    or id = nullif(auth.jwt() ->> 'shop_id', '')::uuid
  );

-- ---- profiles --------------------------------------------------------------
alter table public.profiles enable row level security;
create policy profiles_self_or_tenant on public.profiles
  for all to authenticated
  using (
    id = auth.uid()
    or (auth.jwt() ->> 'user_role') = 'super_admin'
    or shop_id = nullif(auth.jwt() ->> 'shop_id', '')::uuid
  )
  with check (
    (auth.jwt() ->> 'user_role') = 'super_admin'
    or shop_id = nullif(auth.jwt() ->> 'shop_id', '')::uuid
  );

-- ---- tenant tables (same shape) --------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array[
    'customers', 'games', 'prize_tiers',
    'play_sessions', 'coupons', 'analytics_events'
  ]
  loop
    execute format('alter table public.%I enable row level security;', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (
          (auth.jwt() ->> 'user_role') = 'super_admin'
          or shop_id = nullif(auth.jwt() ->> 'shop_id', '')::uuid
        )
        with check (
          (auth.jwt() ->> 'user_role') = 'super_admin'
          or shop_id = nullif(auth.jwt() ->> 'shop_id', '')::uuid
        );
    $f$, t || '_tenant', t);
  end loop;
end $$;

-- Note: the `anon` role has NO policies here, so RLS denies it by default.
