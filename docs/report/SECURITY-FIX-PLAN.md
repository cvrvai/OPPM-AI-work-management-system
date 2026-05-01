# Security Fix Plan: Remove X-Internal-API-Key from CORS

Last updated: 2026-05-01

## Issue

`X-Internal-API-Key` was added to CORS `allow_headers` in `services/gateway/main.py`. This violates the security rule:

> "NEVER expose `INTERNAL_API_KEY` or `JWT_SECRET_KEY` to the frontend"
> — `.claude/rules/security.md`

## Why This Is a Problem

1. **CORS allows browsers to send the header**: With `X-Internal-API-Key` in `allow_headers`, a malicious website can make cross-origin requests carrying this header.
2. **Internal endpoints become reachable**: If the internal API key is leaked (via frontend code, logs, or network inspection), attackers can call `/internal/analyze-commits` from a browser.
3. **Violates defense in depth**: Internal endpoints should be reachable only by backend services, not browsers.

## Current State

| Component | Detail |
|---|---|
| Internal endpoint | `POST /internal/analyze-commits` |
| Protection | `X-Internal-API-Key` header validation via `verify_internal_key` |
| Legitimate caller | `services/integrations/domains/github/service.py` (backend service) |
| Gateway route | Exists in both Python gateway and nginx.conf |
| CORS exposure | `X-Internal-API-Key` in `allow_headers` (NEW — needs removal) |

## How Internal Calls Actually Work

```
GitHub webhook → Integrations Service
    → DIRECT HTTP call to Intelligence Service (NOT through gateway)
    → POST {ai_service_url}/internal/analyze-commits
    → Header: X-Internal-API-Key: {settings.internal_api_key}
```

Backend services talk directly to each other. They do NOT enforce CORS. Removing `X-Internal-API-Key` from CORS `allow_headers` will NOT break internal service-to-service calls.

## Fix Required

### Immediate Fix
- [x] Remove `X-Internal-API-Key` from CORS `allow_headers` in `services/gateway/main.py`

### Verification
- [x] Confirm `services/integrations/domains/github/service.py` does NOT go through gateway for internal calls
- [x] Confirm internal endpoint still works via direct service-to-service call

### Documentation Update
- [x] Add comment in `services/gateway/main.py` explaining why internal headers are excluded from CORS
- [x] Update `.claude/rules/security.md` with explicit guidance on CORS and internal headers

## Additional Hardening (Future)

| Hardening | Effort | Impact |
|---|---|---|
| IP-restrict internal endpoints to Docker network / localhost | Low | High — prevents external access even with leaked key |
| Remove `/internal/*` from gateway public routes | Low | Medium — reduces attack surface |
| Add network-level segmentation (Docker internal network) | Medium | High — services can only talk within network |
| Rotate `INTERNAL_API_KEY` regularly | Low | Medium — limits window of exposure |

## Decision

**Remove `X-Internal-API-Key` from CORS immediately.** Internal endpoints are backend-only and should never be reachable from browsers.
