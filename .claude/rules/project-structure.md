# Project Structure

## Repository Layout
```
├── .claude/                    # AI agent configuration
│   ├── rules/                  # Mandatory rules for all agents
│   └── commands/               # Reusable agent commands
├── services/                   # Python FastAPI microservices
│   ├── core/                   # Main service (auth, workspaces, projects, tasks)
│   │   ├── main.py             # App factory + middleware chain
│   │   ├── config.py           # Pydantic settings
│   │   ├── middleware/         # Auth, workspace, rate limit, logging
│   │   ├── repositories/       # Data access layer (SQLAlchemy async)
│   │   ├── services/           # Business logic layer
│   │   ├── schemas/            # Pydantic request/response models
│   │   └── routers/v1/         # API route handlers (workspace-scoped)
│   ├── ai/                     # AI / LLM service
│   ├── git/                    # GitHub integration service
│   ├── mcp/                    # MCP tool service
│   └── gateway/                # API gateway / load balancer
├── shared/                     # Shared Python package
│   ├── auth.py                 # JWT validation (python-jose HS256)
│   ├── database.py             # SQLAlchemy async engine
│   ├── models/                 # SQLAlchemy ORM models
│   └── schemas/                # Shared Pydantic schemas
├── frontend/                   # React + Vite frontend
│   └── src/
│       ├── components/         # Shared UI components
│       ├── hooks/              # Custom hooks
│       ├── lib/                # API client (api.ts), utils
│       ├── pages/              # Route-level page components
│       ├── stores/             # Zustand stores
│       └── types/              # TypeScript interfaces
├── docs/                       # Architecture documentation
└── docker-compose.yml
```

## Layer Dependencies (Backend)
```
Router → Service → Repository → SQLAlchemy async session
              ↘ Infrastructure (LLM adapters)
```
- Routers depend on Services and Schemas
- Services depend on Repositories
- Repositories depend on database.py
- Never import Router from Service, or Service from Repository
