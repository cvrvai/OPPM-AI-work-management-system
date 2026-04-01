# Error Handling Rules

## Backend
- Use `HTTPException` for all error responses — never return error dicts manually
- Standard status codes: 400 (validation), 401 (not authed), 403 (not authorized), 404 (not found), 429 (rate limit)
- Always log exceptions before re-raising: `logger.warning("context: %s", error)`
- Service-layer validation raises `HTTPException`; repositories never raise HTTP errors
- Rate limiter returns 429 with `Retry-After` header

## Frontend
- API errors throw `Error(detail)` from `api.ts` — catch in mutations' `onError`
- Use `react-query` retry (1 retry by default) for transient failures
- Show toast/notification on mutation errors, not alerts
- Never silently swallow errors — at minimum log them

## Auth Errors
- 401 from backend → frontend should redirect to login or refresh token
- Token refresh is handled by Supabase JS client automatically via `onAuthStateChange`
- Backend validates via `supabase.auth.get_user(token)` — returns 401 for expired/invalid tokens
