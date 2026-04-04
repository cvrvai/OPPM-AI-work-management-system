# Software Requirements Specification

Last updated: 2026-04-04

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification defines the product scope, major functional requirements, interfaces, and non-functional requirements for the OPPM AI Work Management System.

It is written against the current product and codebase direction.

### 1.2 Product Summary

OPPM AI Work Management System is a multi-tenant, workspace-scoped project management platform built around the One Page Project Manager method.

The system combines:

- workspace and role-based collaboration
- project and task tracking
- OPPM objectives, timeline, and cost views
- AI-assisted planning and summaries
- GitHub commit analysis
- MCP tools for AI integrations

### 1.3 Intended Audience

This document is for:

- engineers implementing new features
- technical leads reviewing scope and constraints
- QA and product reviewers validating behavior
- future maintainers who need a stable product-level reference

## 2. Product Scope

The system shall provide a workspace-based environment where authenticated users can:

- create and join workspaces
- manage project portfolios inside a workspace
- define OPPM objectives, timeline entries, and costs
- create and complete tasks aligned to project objectives
- collaborate through roles, member skills, and notifications
- connect GitHub repositories and analyze commits against project work
- configure AI models and use AI chat, summaries, and retrieval
- expose structured MCP tools for model-based workflows

## 3. User Classes And Roles

### 3.1 Global User

A global user is an authenticated account in the system.

Global users can:

- sign up
- log in
- refresh their session
- update their profile
- join multiple workspaces

### 3.2 Workspace Roles

Workspace roles are scoped per workspace.

Supported roles:

- `owner`
- `admin`
- `member`
- `viewer`

Role expectations:

- `owner` and `admin` can manage workspace settings, members, and admin flows
- `member` can perform normal write actions on projects and tasks
- `viewer` can read but not write workspace data

## 4. System Context

### 4.1 Frontend Context

The system shall provide a web frontend for:

- login and invite acceptance
- dashboard
- projects
- project detail and task views
- OPPM view
- team view
- commits view
- settings and admin flows

### 4.2 Backend Context

The backend shall expose HTTP APIs through a gateway and split responsibilities across services:

- core service
- AI service
- Git service
- MCP service

### 4.3 External Systems

The platform may integrate with:

- GitHub webhooks and repository APIs
- LLM providers such as Ollama, OpenAI, Anthropic, Kimi, or custom endpoints
- email delivery for invites
- Redis for rate limiting and caching support

## 5. Functional Requirements

### 5.1 Authentication And Identity

- `FR-AUTH-1` The system shall allow a user to register with email and password.
- `FR-AUTH-2` The system shall allow a user to log in with email and password.
- `FR-AUTH-3` The system shall issue access and refresh tokens on successful authentication.
- `FR-AUTH-4` The system shall allow refresh-token exchange for new session tokens.
- `FR-AUTH-5` The system shall allow the current user to retrieve their own identity.
- `FR-AUTH-6` The system shall allow the current user to update profile fields supported by the backend.
- `FR-AUTH-7` The system shall allow the current user to sign out.

### 5.2 Workspace Management

- `FR-WS-1` The system shall allow an authenticated user to create a workspace.
- `FR-WS-2` The system shall allow a user to list only workspaces they belong to.
- `FR-WS-3` The system shall enforce workspace membership before exposing workspace-scoped data.
- `FR-WS-4` The system shall allow authorized admins to update workspace metadata.
- `FR-WS-5` The system shall allow authorized admins to delete a workspace.
- `FR-WS-6` The system shall allow users to switch active workspace in the frontend.

### 5.3 Membership, Roles, And Invites

- `FR-MEM-1` The system shall allow admins to list workspace members.
- `FR-MEM-2` The system shall allow admins to change member roles.
- `FR-MEM-3` The system shall allow admins to remove members.
- `FR-MEM-4` The system shall allow a member to update their workspace display name.
- `FR-MEM-5` The system shall allow admins to invite a user by email.
- `FR-MEM-6` The system shall support public preview of invite metadata before acceptance.
- `FR-MEM-7` The system shall allow an authenticated user to accept a valid invite.
- `FR-MEM-8` The system shall allow admins to resend or revoke pending invites.
- `FR-MEM-9` The system shall allow members to manage skill tags on their own workspace membership.
- `FR-MEM-10` The system shall allow admins to manage member skills for any workspace member.

### 5.4 Projects

- `FR-PROJ-1` The system shall allow write-enabled users to create projects within a workspace.
- `FR-PROJ-2` The system shall store project metadata including code, objective summary, schedule, budget, planning hours, priority, status, and lead.
- `FR-PROJ-3` The system shall allow users to list and retrieve projects within their workspace.
- `FR-PROJ-4` The system shall allow write-enabled users to update projects.
- `FR-PROJ-5` The system shall allow write-enabled users to delete projects.
- `FR-PROJ-6` The system shall support project membership assignment with project-level roles.

### 5.5 Tasks And Execution

- `FR-TASK-1` The system shall allow write-enabled users to create tasks under a project.
- `FR-TASK-2` The system shall allow users to list and retrieve tasks filtered by workspace and optionally by project.
- `FR-TASK-3` The system shall allow write-enabled users to update task title, description, status, priority, progress, dates, objective link, and assignee.
- `FR-TASK-4` The system shall allow write-enabled users to delete tasks.
- `FR-TASK-5` The system shall support task daily reports with report date, hours, description, and approval state.
- `FR-TASK-6` The system shall allow write-enabled users to approve or reject task reports.

### 5.6 OPPM Planning

- `FR-OPPM-1` The system shall allow users to view project objectives.
- `FR-OPPM-2` The system shall allow write-enabled users to create, update, and delete objectives.
- `FR-OPPM-3` The system shall allow users to view project timeline entries.
- `FR-OPPM-4` The system shall allow write-enabled users to create or update timeline entries keyed by week.
- `FR-OPPM-5` The system shall allow users to view project cost rows.
- `FR-OPPM-6` The system shall allow write-enabled users to create, update, and delete cost rows.

### 5.7 Dashboard And Notifications

- `FR-DASH-1` The system shall provide workspace-level dashboard summary metrics.
- `FR-NOTIF-1` The system shall provide user-scoped notifications.
- `FR-NOTIF-2` The system shall allow users to list notifications and unread counts.
- `FR-NOTIF-3` The system shall allow users to mark notifications read individually or in bulk.
- `FR-NOTIF-4` The system shall allow users to delete notifications.

### 5.8 AI Features

- `FR-AI-1` The system shall allow workspace admins to configure AI models per workspace.
- `FR-AI-2` The system shall allow workspace members to use workspace-level AI chat.
- `FR-AI-3` The system shall allow write-enabled users to use project-level AI chat.
- `FR-AI-4` The system shall allow write-enabled users to request an AI-generated project plan.
- `FR-AI-5` The system shall allow write-enabled users to commit an accepted AI-generated plan into project data.
- `FR-AI-6` The system shall allow users to request project weekly summaries.
- `FR-AI-7` The system shall allow admins to reindex workspace content for retrieval.
- `FR-AI-8` The system shall provide a workspace-scoped RAG query endpoint returning context and sources.

### 5.9 GitHub Integration

- `FR-GIT-1` The system shall allow admins to register GitHub accounts per workspace.
- `FR-GIT-2` The system shall allow write-enabled users to configure repositories against projects.
- `FR-GIT-3` The system shall accept GitHub push webhooks for configured repositories.
- `FR-GIT-4` The system shall validate webhook signatures before processing.
- `FR-GIT-5` The system shall store commit events for accepted push payloads.
- `FR-GIT-6` The system shall trigger AI-based commit analysis after commit storage.
- `FR-GIT-7` The system shall expose commit history, developer reports, and recent analyses.

### 5.10 MCP Tools

- `FR-MCP-1` The system shall list MCP tools available to the current workspace.
- `FR-MCP-2` The system shall execute MCP tool calls scoped to the current workspace.

## 6. External Interface Requirements

### 6.1 User Interface

The UI shall provide:

- authenticated and public route separation
- workspace selector
- project and task views
- OPPM planning views
- settings pages for members, GitHub, and AI model configuration
- chat entry and panel for AI conversations

### 6.2 API Interface

The system shall expose HTTP JSON APIs under `/api`.

Public route group examples:

- `/api/auth/*`
- `/api/v1/workspaces/*`
- `/api/v1/git/webhook`

Detailed route definitions are documented in [API-REFERENCE.md](API-REFERENCE.md).

### 6.3 GitHub Interface

The system shall accept GitHub webhook requests signed with `X-Hub-Signature-256`.

### 6.4 AI Provider Interface

The system shall support configured LLM providers through provider-specific or custom endpoints.

## 7. Data Requirements

- `DR-1` The system shall store users, workspaces, memberships, invites, and member skills.
- `DR-2` The system shall store projects, project members, tasks, task reports, OPPM objectives, timeline entries, and cost rows.
- `DR-3` The system shall store GitHub accounts, repo configs, commit events, and commit analyses.
- `DR-4` The system shall store AI model configurations and document embeddings.
- `DR-5` The system shall store notifications and audit log records.
- `DR-6` The system shall use workspace membership as the main relational anchor for role-sensitive collaboration features.

## 8. Security Requirements

- `SEC-1` The system shall require authentication for protected endpoints.
- `SEC-2` The system shall validate workspace membership before serving workspace-scoped resources.
- `SEC-3` The system shall restrict admin-only operations to `owner` and `admin` roles.
- `SEC-4` The system shall protect internal service routes with a dedicated internal API key.
- `SEC-5` The system shall validate GitHub webhooks with HMAC SHA-256 signatures.
- `SEC-6` The system shall avoid returning sensitive secrets such as encrypted GitHub tokens or webhook secrets in public API responses.
- `SEC-7` The system shall store refresh tokens in revocable persisted form.

## 9. Non-Functional Requirements

### 9.1 Performance

- `NFR-PERF-1` The system should return standard CRUD responses within normal interactive web latency under typical load.
- `NFR-PERF-2` The gateway should route requests to the owning service with minimal additional overhead.
- `NFR-PERF-3` Long-running AI and analysis flows should be isolated from the core CRUD path where possible.

### 9.2 Reliability

- `NFR-REL-1` The system should expose health endpoints for each backend service.
- `NFR-REL-2` Webhook ingestion should acknowledge valid requests quickly and continue heavy work asynchronously.
- `NFR-REL-3` The frontend should retry access-token refresh automatically on authorization expiry.

### 9.3 Maintainability

- `NFR-MAINT-1` The system should preserve the service ownership boundaries documented in the architecture and reference docs.
- `NFR-MAINT-2` Shared database models should remain centralized in the shared package.
- `NFR-MAINT-3` New API contracts should be reflected in the API, ERD, and testing documentation.

### 9.4 Security And Privacy

- `NFR-SEC-1` Sensitive credentials shall not be exposed to the frontend.
- `NFR-SEC-2` Token logging shall remain redacted.
- `NFR-SEC-3` Workspace isolation shall be enforced consistently across routes and services.

## 10. Constraints And Assumptions

- the product is workspace-scoped and multi-tenant
- frontend traffic is expected to go through the gateway rather than directly to backend services
- the backend services share one PostgreSQL database through the shared ORM package
- Redis is a support dependency, not the primary database
- AI capability quality depends on configured model availability
- GitHub commit analysis depends on repo configuration and valid webhook setup

## 11. Out Of Scope For This Revision

The following are not formalized as requirements in this SRS revision:

- native mobile applications
- offline-first synchronization
- enterprise SSO or SCIM provisioning
- billing workflows beyond workspace plan fields
- advanced portfolio forecasting beyond the current OPPM and AI summary surface

## 12. Supporting Documents

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [API-REFERENCE.md](API-REFERENCE.md)
- [ERD.md](ERD.md)
- [FLOWCHARTS.md](FLOWCHARTS.md)
- [FRONTEND-REFERENCE.md](FRONTEND-REFERENCE.md)
- [MICROSERVICES-REFERENCE.md](MICROSERVICES-REFERENCE.md)
- [MICROSERVICES-REVIEW.md](MICROSERVICES-REVIEW.md)
- [PHASE-TRACKER.md](PHASE-TRACKER.md)
- [TESTING-GUIDE.md](TESTING-GUIDE.md)
