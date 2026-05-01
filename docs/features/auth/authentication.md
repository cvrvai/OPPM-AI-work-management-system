# Feature: Authentication And Session Bootstrap

Last updated: 2026-05-01

## What It Does

- Email/password signup and login
- Access-token bootstrap on app load
- Refresh-token retry on `401`
- Signout and profile update

## How It Works

1. `frontend/src/App.tsx` calls `authStore.initialize()`.
2. `frontend/src/stores/authStore.ts` reads `access_token` from local storage.
3. If the access token works, `GET /api/auth/me` returns the current user.
4. If the token is expired, `POST /api/auth/refresh` exchanges the refresh token for a new token pair.
5. `frontend/src/lib/api.ts` adds the bearer token to application requests and retries once on `401`.
6. `shared/auth.py` validates JWTs locally with `python-jose` and resolves the authenticated user.

## Frontend Files

- `frontend/src/App.tsx`
- `frontend/src/stores/authStore.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/Login.tsx`

## Backend Files

- `services/workspace/domains/auth/router.py`
- `services/workspace/domains/auth/service.py`
- `shared/auth.py`
- `shared/models/user.py`

## Primary Tables

- `users`
- `refresh_tokens`

## Update Notes

- Keep JWT validation local unless you intentionally redesign auth across backend and frontend.
- `refresh_tokens` persists token hashes, not raw tokens.
