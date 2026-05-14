# Dual-Frontend Gateway Setup

This configuration enables the OPPM AI API Gateway to serve **both** frontends from a single entry point:

| Path | Frontend | Description |
|------|----------|-------------|
| `/` | OPPM AI | Main OPPM work management UI |
| `/one/` | One-utilities-PM | One utilities PM frontend |
| `/api/*` | Shared | Both frontends use the same API |

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │         Nginx Gateway (Port 80)              │
                    │                                              │
     User ────────► │  /one/*  ──► One-utilities-PM (static files)│
                    │  /       ──► OPPM frontend (dev server:5174)│
                    │  /api/*  ──► OPPM workspace service          │
                    └─────────────────────────────────────────────┘
```

## Quick Start

### 1. Build the One-utilities-PM frontend

```powershell
cd "C:\Users\cheon\work project\internal\One-utilities-PM\frontend"
npm run build
```

### 2. Start OPPM services

```powershell
cd "C:\Users\cheon\work project\internal\OPPM-AI-work-management-system"

# Start backend services
docker compose -f docker-compose.microservices.yml up -d postgres redis workspace intelligence gateway

# Copy the built One frontend into the gateway container
docker cp "..\One-utilities-PM\frontend\dist/." oppm-ai-work-management-system-gateway-1:/usr/share/nginx/html/one/
```

### 3. Start OPPM frontend dev server (in a separate terminal)

```powershell
cd "C:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend"
npm run dev
```

### 4. Access the frontends

- **OPPM AI**: http://localhost/
- **One-utilities-PM**: http://localhost/one/

## Configuration Details

### One-utilities-PM Frontend Changes

The One-utilities-PM frontend needs to know its base path is `/one/`:

1. **Update `vite.config.js`** to set `base: '/one/'`:
   ```js
   export default defineConfig({
     base: '/one/',
     // ... rest of config
   })
   ```

2. **Update API client** (`src/services/workManagement/client.js`):
   The client already supports OPPM platform mode. Ensure these env vars are set:
   ```
   VITE_PLATFORM_GATEWAY_URL=http://localhost:80
   VITE_PLATFORM_WORKSPACE_ID=<your-workspace-id>
   VITE_PLATFORM_AUTH_MODE=oppm-credentials
   VITE_PLATFORM_EMAIL=your-email
   VITE_PLATFORM_PASSWORD=your-password
   ```

### OPPM Frontend (No Changes Needed)

The OPPM frontend continues to work at `/` as before.

## Nginx Configuration

The `nginx-dual-frontend.conf` adds these key blocks:

```nginx
# Serve One-utilities-PM static build at /one/
location /one/ {
    alias /usr/share/nginx/html/one/;
    try_files $uri $uri/ /one/index.html;
}

# SPA asset folders
location /one/assets/ {
    alias /usr/share/nginx/html/one/assets/;
    expires 1y;
}
```

## Development Mode

For hot-reload development of the One-utilities-PM frontend:

1. Uncomment the `one-frontend-dev` service in `docker-compose.dual-frontend.yml`
2. Update the nginx config to proxy `/one/` to `http://one-frontend-dev:5173`
3. Run: `docker compose -f docker-compose.microservices.yml -f docker-compose.dual-frontend.yml up -d`

## Troubleshooting

### 502 Bad Gateway
- Ensure the `workspace` service is healthy: `docker ps`
- Check workspace logs: `docker logs oppm-ai-work-management-system-workspace-1`
- Verify postgres is on the same network: `docker network inspect oppm-network`

### One frontend shows blank page
- Check browser console for 404 errors on JS/CSS assets
- Ensure `base: '/one/'` is set in `vite.config.js`
- Verify the dist folder exists: `ls One-utilities-PM/frontend/dist`

### CORS errors
- The gateway already adds CORS headers for `localhost:*` origins
- If using a different origin, update the `map $http_origin` block in nginx.conf

## Files Added

| File | Purpose |
|------|---------|
| `gateway/nginx-dual-frontend.conf` | Nginx config serving both frontends |
| `gateway/Dockerfile.dual` | Optional Dockerfile for building gateway with both frontends |
| `docker-compose.dual-frontend.yml` | Compose override mounting One frontend dist |
| `docs/DUAL-FRONTEND-GATEWAY.md` | This documentation |
