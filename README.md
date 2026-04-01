# OPPM AI Work Management System

AI-powered One Page Project Manager (OPPM) with GitHub integration and multi-model commit analysis.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + TypeScript + Tailwind CSS v4 |
| Backend | Python FastAPI |
| Database | Supabase (PostgreSQL) |
| AI | Multi-model: Ollama, Kimi K2.5, Claude, OpenAI |
| Auth | Supabase Auth |
| Deployment | Docker Compose |

## Quick Start

### 1. Database Setup
Run `supabase/schema.sql` in your Supabase SQL Editor.

### 2. Environment
```bash
cp .env.example .env
# Fill in your Supabase credentials and AI API keys
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 5. Docker (alternative)
```bash
docker compose up
```

## Architecture

```
GitHub Push → Webhook → FastAPI Backend → AI Analysis → Supabase DB → React Dashboard
```

**Pipeline:**
1. Developer pushes code to GitHub
2. GitHub fires webhook to FastAPI
3. HMAC signature validated
4. Commit diff + metadata extracted
5. AI model analyzes against OPPM tasks
6. Scores stored: alignment, quality, progress
7. OPPM dashboard auto-updates

## Project Structure

```
├── frontend/          React + Vite + TypeScript
│   └── src/
│       ├── pages/     Dashboard, Projects, OPPMView, Commits, Settings
│       ├── components/ Layout, OPPM grid, UI components
│       ├── lib/       Supabase client, API wrapper, utilities
│       ├── stores/    Zustand auth store
│       └── types/     TypeScript interfaces
├── backend/           Python FastAPI
│   ├── routers/       API endpoints (projects, tasks, git, ai, dashboard)
│   └── services/      AI analyzer (multi-model)
├── supabase/          Database schema
└── docker-compose.yml Service orchestration
```
