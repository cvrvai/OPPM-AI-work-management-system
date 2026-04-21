# Security Rules

## Authentication
- JWT is validated locally via `python-jose` (HS256) using `JWT_SECRET_KEY` from environment
- NEVER store raw API keys in code — use environment variables
- NEVER log full tokens — log only `token[:20]...token[-10:]` for debugging
- GitHub webhook validation: HMAC-SHA256 with `X-Hub-Signature-256` header

## Authorization
- All v1 routes MUST require authentication (`get_current_user` dependency)
- Write operations MUST check workspace role via `require_write` or `require_admin`
- Backend authorization is the primary gate; always verify workspace membership in service layer

## Data Access
- NEVER query data without workspace_id scoping (except user-scoped resources like notifications)
- NEVER expose `INTERNAL_API_KEY` or `JWT_SECRET_KEY` to the frontend
- NEVER return sensitive data (encrypted_token, webhook_secret, api_key) in API responses

## Frontend
- Tokens stored in Zustand + localStorage via `useAuthStore`; auto-refresh handled in `api.ts`
- Use Vite proxy in development — never make cross-origin API calls in dev
- CORS is configured for production origins only
