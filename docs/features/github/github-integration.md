# Feature: GitHub Integration, Commits, And Commit Analysis

Last updated: 2026-05-01

## What It Does

- GitHub account registration
- Repo configuration per project
- Webhook ingestion
- Commit storage
- AI commit analysis
- Recent analysis feed and developer reports

## How It Works

1. `frontend/src/pages/Settings.tsx` manages GitHub accounts and repo configs.
2. `frontend/src/pages/Commits.tsx` loads commits and attached AI analysis.
3. GitHub sends push events to `POST /api/v1/git/webhook`.
4. The integrations service looks up an active repo config by `repository.full_name`.
5. It validates `X-Hub-Signature-256` using the stored webhook secret.
6. It stores commit events and triggers background AI analysis.
7. The intelligence service writes analysis results that are shown in the commits feed and dashboard.

## Frontend Files

- `frontend/src/pages/Settings.tsx`
- `frontend/src/pages/Commits.tsx`
- `frontend/src/pages/Dashboard.tsx`

## Backend Files

- `services/integrations/domains/github/router.py`
- `services/integrations/domains/github/service.py`
- `services/intelligence/domains/analysis/internal_router.py`
- `services/intelligence/domains/analysis/service.py`
- `shared/models/git.py`

## Primary Tables

- `github_accounts`
- `repo_configs`
- `commit_events`
- `commit_analyses`

## Update Notes

- Never expose `encrypted_token` or `webhook_secret` in responses.
- Webhook routing and HMAC verification must remain aligned across the integrations service and deployment gateway.
