# Feature: Team, Invites, And Member Skills

Last updated: 2026-05-01

## What It Does

- Member listing and role updates
- Invite creation, preview, acceptance, resend, revoke, decline
- Workspace-specific display names
- Member skill matrix

## How It Works

1. `frontend/src/pages/Team.tsx` loads workspace members and skill lists.
2. `frontend/src/pages/Settings.tsx` includes workspace-member and invite-management panels.
3. `frontend/src/pages/AcceptInvite.tsx` uses the public preview route and then the authenticated accept route.
4. `frontend/src/pages/Invitations.tsx` loads pending invites for the current user and allows accept or decline.
5. Core workspace routes and services update member roles, invite state, and skills.

## Frontend Files

- `frontend/src/pages/Team.tsx`
- `frontend/src/pages/Settings.tsx`
- `frontend/src/pages/AcceptInvite.tsx`
- `frontend/src/pages/Invitations.tsx`
- `frontend/src/components/layout/Sidebar.tsx`

## Backend Files

- `services/workspace/domains/workspace/router.py`
- `services/workspace/domains/workspace/service.py`
- `shared/models/workspace.py`

## Primary Tables

- `workspace_members`
- `workspace_invites`
- `member_skills`

## Update Notes

- Workspace display names are stored per membership, not on the user record.
- Invites are authenticated on accept, but preview is public by token.
