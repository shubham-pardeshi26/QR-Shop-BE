-- =============================================================================
-- Supabase custom access-token hook.
--
-- Mirrors each user's role + shop_id (from public.profiles) into their JWT as
-- `user_role` and `shop_id` claims. The RLS policies (rls_policies.sql) and the
-- FastAPI RBAC layer both read these claims.
--
-- Setup:
--   1) Run this in the Supabase SQL editor.
--   2) Dashboard -> Authentication -> Hooks -> "Custom Access Token" ->
--      enable and select public.custom_access_token_hook.
-- =============================================================================

create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
as $$
declare
  claims jsonb;
  v_role text;
  v_shop uuid;
begin
  select role, shop_id
    into v_role, v_shop
    from public.profiles
   where id = (event ->> 'user_id')::uuid;

  claims := coalesce(event -> 'claims', '{}'::jsonb);

  if v_role is not null then
    claims := jsonb_set(claims, '{user_role}', to_jsonb(v_role));
    claims := jsonb_set(
      claims, '{shop_id}',
      case when v_shop is null then 'null'::jsonb else to_jsonb(v_shop::text) end
    );
  end if;

  return jsonb_set(event, '{claims}', claims);
end;
$$;

-- Allow the auth server to execute the hook.
grant execute on function public.custom_access_token_hook to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook from authenticated, anon, public;

-- The hook reads profiles; let the auth admin role see it.
grant usage on schema public to supabase_auth_admin;
grant select on public.profiles to supabase_auth_admin;
