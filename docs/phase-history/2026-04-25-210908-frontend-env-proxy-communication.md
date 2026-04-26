# Current Phase Tracker

## Task
Clarify Docker Compose Choice In Docker README

## Goal
Update the Docker documentation so developers can quickly choose the correct compose command for local development versus production-like container runs, and understand where the Google service-account file fits.

## Plan

### Phase 1: Verify Runtime Shape
- [x] Confirm which compose file is the base full-stack definition
- [x] Confirm what the dev override changes
- [x] Confirm the current Google service-account Docker mount path

### Phase 2: Documentation Update
- [x] Add a simple decision guide for which compose command to use
- [x] Clarify that `docker-compose.yml` is infrastructure only
- [x] Document the Google service-account file path and verification step

### Phase 3: Validation
- [x] Review the updated markdown for consistency with the compose files
- [x] Record any remaining ambiguity or drift

## Status
Complete

## Expected Files
- `docs/docker/README.md`
- `docs/PHASE-TRACKER.md`

## Verification
- Verified the README updates against `docker-compose.microservices.yml`, `docker-compose.dev.yml`, and `services/.env.example`.
- Confirmed the README now explains the base stack versus the dev overlay and documents the mounted Google service-account file path.

## Notes
- `docker-compose.microservices.yml` is the base full-stack app stack.
- `docker-compose.dev.yml` is an overlay for hot reload, source mounts, and direct host ports.
- `docker-compose.yml` is infrastructure only and does not start the full app by itself.
- The Google service-account mount is defined in the base microservices stack, so it applies in both normal and dev-overlay runs.