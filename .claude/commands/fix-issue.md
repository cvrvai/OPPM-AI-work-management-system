# Fix Issue Command

When fixing an issue, follow this workflow:

## 1. Reproduce
- Read the error message carefully
- Check backend logs for the request path, status code, and timing
- Check frontend console for network errors and React warnings
- Identify: is this a backend error, frontend error, or data issue?

## 2. Diagnose
- For 401: check if Authorization header is sent (`middleware.auth` debug logs)
- For 403: check workspace membership and role (`middleware.workspace`)
- For 404: check if the resource exists and is workspace-scoped correctly
- For CORS: check if `VITE_API_URL` is set (should NOT be set in dev — use Vite proxy)
- For React warnings: check JSX for whitespace text nodes, missing keys, etc.

## 3. Fix
- Make the minimal change needed
- Follow rules in `.claude/rules/`
- Test the fix locally before committing

## 4. Verify
- Run `cd frontend && npx tsc -b` for type errors
- Run `cd backend && python -c "from main import app"` for import errors
- Test the actual user flow in the browser

## 5. Document
- Update `docs/*.md` if the fix changes API behavior, architecture, or schema
- Update `.claude/rules/` if the fix reveals a new pattern to enforce
