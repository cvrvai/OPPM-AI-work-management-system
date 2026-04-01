# Deploy Command

Deploy the OPPM AI system. Run these steps in order:

## Pre-deploy Checks
1. Run `cd frontend && npm run build` — must complete with zero errors
2. Run `cd backend && python -c "from main import app; print('OK')"` — must import cleanly
3. Verify all environment variables are set in production `.env`

## Database
1. Check for pending migrations in `supabase/schema.sql`
2. Apply via Supabase Dashboard or MCP `apply_migration`
3. Verify RLS policies are active on all tables

## Backend
1. Build Docker image: `docker build -t oppm-backend ./backend`
2. Run: `docker run -p 8000:8000 --env-file ./backend/.env oppm-backend`

## Frontend
1. Build: `cd frontend && npm run build`
2. Serve `dist/` via nginx or CDN
3. Set `VITE_API_URL` to production backend URL
4. Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`

## Post-deploy
1. Test `/health` endpoint returns `{"status": "ok", "version": "2.0.0"}`
2. Test login flow
3. Test workspace creation
4. Test OPPM view loads
