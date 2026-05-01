# Feature: Dashboard And Notifications

Last updated: 2026-05-01

## What It Does

- Workspace dashboard stats
- Recent AI commit analysis on the dashboard
- User notifications in the header dropdown

## How It Works

1. `frontend/src/pages/Dashboard.tsx` loads workspace stats from `/dashboard/stats`.
2. The dashboard service aggregates projects, tasks, repos, commits, and recent analyses.
3. `frontend/src/components/layout/Header.tsx` loads `/v1/notifications` and `/v1/notifications/unread-count`.
4. Header actions mark individual notifications read, mark all read, or delete notifications.

## Frontend Files

- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/layout/Header.tsx`

## Backend Files

- `services/workspace/domains/dashboard/router.py`
- `services/workspace/domains/dashboard/service.py`
- `services/workspace/domains/notification/router.py`
- `services/workspace/domains/notification/service.py`
- `shared/models/notification.py`

## Primary Tables

- `notifications`
- `audit_log`
- plus projects, tasks, repo configs, commits, and analyses for dashboard aggregation

## Update Notes

- Notifications are user-scoped routes, not workspace-scoped routes.
