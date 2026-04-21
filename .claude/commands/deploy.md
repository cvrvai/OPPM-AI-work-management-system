# Deploy Command

Deploy the OPPM AI system. Run these steps in order:

## Pre-deploy Checks
1. Run `cd frontend && npm run build` — must complete with zero errors
2. Run `cd backend && python -c "from main import app; print('OK')"` — must import cleanly
3. Verify all environment variables are set in production `.env`

## Database
1. Check for pending SQL migrations in `docs/ERD.md` or migration files
2. Apply via `psql` or the MCP `execute_sql` tool
3. Verify indexes are in place for workspace_id foreign keys

## Backend
1. Build Docker images: `docker compose build`
2. Run: `docker compose up -d`

## Frontend
1. Build: `cd frontend && npm run build`
2. Serve `dist/` via nginx or CDN
3. Set `VITE_API_URL` to production backend URL

## Post-deploy
1. Test `/health` endpoint returns `{"status": "ok", "version": "2.0.0"}`
2. Test login flow
3. Test workspace creation
4. Test OPPM view loads
