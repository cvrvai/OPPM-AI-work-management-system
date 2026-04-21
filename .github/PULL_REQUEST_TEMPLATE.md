## Summary

<!-- 1-3 bullet points describing what this PR changes and why -->

-
-

## Type

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor
- [ ] Documentation
- [ ] Infrastructure / DevOps

## Testing

- [ ] Backend tests pass: `cd apps/core && python -m pytest tests/ -v`
- [ ] Frontend type check passes: `cd frontend && npx tsc -b`
- [ ] Manually verified the affected flows

## Checklist

- [ ] Follows 4-layer architecture (Router → Service → Repository)
- [ ] New endpoints require `get_current_user` and workspace auth middleware
- [ ] All workspace-scoped data queries include `workspace_id`
- [ ] No `console.log` or `print()` in production code
- [ ] Frontend API calls go through `lib/api.ts`
- [ ] Relevant docs updated if behaviour changed
