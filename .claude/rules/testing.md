# Testing Rules

## Backend Testing
- Test services with mocked repositories
- Test routers with `TestClient` and mocked dependencies
- Use `pytest` with `pytest-asyncio` for async tests
- Name test files: `test_{module}.py`
- Test both success and error paths (especially 401, 403, 404)

## Frontend Testing
- Use Vitest + React Testing Library
- Test components that contain business logic
- Mock API calls using MSW or direct mock
- Test workspace-scoped queries with and without workspace selected

## Manual Testing Checklist
- [ ] Create workspace → verify in Supabase
- [ ] Switch workspace → verify API calls include workspace_id
- [ ] Create project → verify workspace_id is set
- [ ] OPPM view → verify objectives, timeline, costs load
- [ ] GitHub webhook → verify commit analysis runs
- [ ] Notifications → verify unread count updates
