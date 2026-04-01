# Project Structure

## Repository Layout
```
├── .claude/                    # AI agent configuration
│   ├── rules/                  # Mandatory rules for all agents
│   └── commands/               # Reusable agent commands
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # App factory + middleware chain
│   ├── config.py               # Pydantic settings
│   ├── database.py             # Supabase client singleton
│   ├── middleware/              # Auth, workspace, rate limit, logging
│   ├── repositories/           # Data access layer (BaseRepository)
│   ├── services/               # Business logic layer
│   ├── schemas/                # Pydantic request/response models
│   ├── routers/v1/             # API route handlers (workspace-scoped)
│   ├── routers/*.py            # Legacy route handlers
│   └── infrastructure/llm/    # AI model adapters
├── frontend/                   # React + Vite frontend
│   └── src/
│       ├── components/         # Shared UI components
│       ├── hooks/              # Custom hooks
│       ├── lib/                # API client, Supabase, utils
│       ├── pages/              # Route-level page components
│       ├── stores/             # Zustand stores
│       └── types/              # TypeScript interfaces
├── supabase/                   # Database schema
│   └── schema.sql              # Full DDL (reference, not auto-applied)
├── docs/                       # Architecture documentation
└── docker-compose.yml
```

## Layer Dependencies (Backend)
```
Router → Service → Repository → Supabase Client
              ↘ Infrastructure (LLM adapters)
```
- Routers depend on Services and Schemas
- Services depend on Repositories
- Repositories depend on database.py
- Never import Router from Service, or Service from Repository
