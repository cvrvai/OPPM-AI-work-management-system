# Gateway Service Feature Inventory

Last updated: 2026-04-20

## Scope

Gateway layer has two implementations that must remain aligned:

1. Python gateway (`services/gateway/`) for native development and health-aware routing
2. nginx gateway (`gateway/nginx.conf`) for containerized routing

## Current Routing Ownership

| Route pattern | Target service |
|---|---|
| `/api/v1/workspaces/{ws}/projects/{project_id}/ai/*` | Intelligence |
| `/api/v1/workspaces/{ws}/rag/*` | Intelligence |
| `/api/v1/workspaces/{ws}/ai/*` | Intelligence |
| `/internal/analyze-commits` | Intelligence |
| `/api/v1/workspaces/{ws}/mcp/*` | Automation |
| `/api/v1/workspaces/{ws}/github-accounts*` | Integrations |
| `/api/v1/workspaces/{ws}/commits*` | Integrations |
| `/api/v1/workspaces/{ws}/git/*` | Integrations |
| `/api/v1/git/webhook` | Integrations |
| `/api/*` (fallback) | Workspace |

## Service Flowchart

```mermaid
flowchart TD
    A[Incoming request] --> B[Gateway route matcher]
    B --> C{Path match}
    C -- AI patterns --> D[Forward to intelligence service]
    C -- Git patterns --> E[Forward to integrations service]
    C -- MCP patterns --> F[Forward to automation service]
    C -- /api fallback --> G[Forward to workspace service]
    C -- Health path --> H[Service health forwarding]

    D --> I[Upstream response passthrough]
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[Response to client]
```

## Runtime Responsibilities

- route matching and forwarding
- timeout policy by route class
- health-aware load balancing (Python gateway)
- response header forwarding (including multi-value headers)
- CORS handling for local development

## Dependencies

- Upstream service URLs from env settings
- Route-table parity between Python and nginx implementations

## Change Impact Checklist

- Any new service route family -> update **both** `services/gateway/main.py` and `gateway/nginx.conf`.
- Timeout policy changes -> update both gateways and note in architecture docs.
- Internal service-to-service paths (for example AI internal routes) -> verify gateway forwarding still supports expected deployment mode.

