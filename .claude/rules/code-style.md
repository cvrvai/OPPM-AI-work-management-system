# Code Style Rules

## Backend (Python)
- Use type hints for all function signatures
- Use `logging.getLogger(__name__)` — never `print()`
- Services are plain functions, not classes
- Repositories are classes inheriting `BaseRepository`
- Use `session.execute(select(...).limit(1))` and `.scalar_one_or_none()` for single-row queries
- Pydantic models: use `model_config` to suppress protected namespace warnings for `model_*` fields

## Frontend (TypeScript / React)
- Functional components only
- Use `@tanstack/react-query` for server state, Zustand for client state
- API calls go through `lib/api.ts` — never call `fetch` directly from components
- Use `useWorkspaceStore` for workspace context, `useAuthStore` for auth
- Path alias: `@/` maps to `src/`
- No whitespace text nodes inside `<colgroup>`, `<thead>`, `<tbody>`, `<tr>` — use `{/* comment */}` without extra spaces

## General
- No `console.log` in production code (use `logger` on backend)
- Prefer early returns over nested conditionals
- Keep components under 300 lines; extract large sub-sections to separate components
