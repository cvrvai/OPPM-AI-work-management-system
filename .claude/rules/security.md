# Security Rules

## Authentication
- NEVER decode JWT locally — always validate via `supabase.auth.get_user(token)`
- NEVER store raw API keys in code — use environment variables
- NEVER log full tokens — log only `token[:20]...token[-10:]` for debugging
- GitHub webhook validation: HMAC-SHA256 with `X-Hub-Signature-256` header

## Authorization
- All v1 routes MUST require authentication (`get_current_user` dependency)
- Write operations MUST check workspace role via `require_write` or `require_admin`
- RLS is defense-in-depth — backend authorization is the primary gate
- Service role key bypasses RLS; always verify workspace membership in service layer

## Data Access
- NEVER query data without workspace_id scoping (except user-scoped resources like notifications)
- NEVER expose service_role_key to the frontend
- NEVER return sensitive data (encrypted_token, webhook_secret, api_key) in API responses

## Frontend
- Store tokens in Supabase JS client (localStorage with auto-refresh)
- Use Vite proxy in development — never make cross-origin API calls in dev
- CORS is configured for production origins only
