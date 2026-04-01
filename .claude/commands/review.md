# Review Command

Code review checklist for the OPPM AI project.

## Security
- [ ] No hardcoded secrets or API keys
- [ ] All v1 routes require authentication
- [ ] Write operations check workspace role
- [ ] No raw SQL injection vectors (using Supabase client, not raw queries)
- [ ] GitHub webhook validates HMAC signature
- [ ] Sensitive fields not exposed in API responses

## Architecture
- [ ] Respects layer boundaries (Router → Service → Repository)
- [ ] No circular imports
- [ ] New tables have workspace_id and RLS policies
- [ ] Pydantic schemas validate all input

## Code Quality
- [ ] Type hints on all function signatures (backend)
- [ ] TypeScript types for all API responses (frontend)
- [ ] No `console.log` or `print()` statements
- [ ] Error cases handled, not silently swallowed
- [ ] No unused imports

## Documentation
- [ ] API changes reflected in `docs/API-REFERENCE.md`
- [ ] Schema changes reflected in `docs/ERD.md`
- [ ] Architecture changes reflected in `docs/ARCHITECTURE.md`
