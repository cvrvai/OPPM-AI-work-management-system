import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// When running inside Docker, API_PROXY_BASE is set to http://gateway:80 so
// all API traffic is routed through the nginx gateway instead of per-service
// localhost addresses (which are unreachable inside the frontend container).
const dockerBase = process.env.API_PROXY_BASE

const proxy = dockerBase
  ? {
      '/api': { target: dockerBase, changeOrigin: true },
      '/mcp': { target: dockerBase, changeOrigin: true },
    }
  : {
      // Git service routes (port 8002) — must be listed BEFORE the generic /api rule
      '^/api/v1/git/webhook':                        { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/commits':          { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/github-accounts':  { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/git':              { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/git':                                   { target: 'http://127.0.0.1:8002', changeOrigin: true },

      // AI service routes (port 8001) — before generic /api rule
      '^/api/v1/workspaces/[^/]+/projects/[^/]+/ai': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/ai':               { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/rag':              { target: 'http://127.0.0.1:8001', changeOrigin: true },

      // MCP service routes (port 8003) — before generic /api rule
      '^/api/v1/workspaces/[^/]+/mcp':              { target: 'http://127.0.0.1:8003', changeOrigin: true },

      // Everything else goes to the core service (port 8000)
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },

      '/mcp': { target: 'http://127.0.0.1:8003', changeOrigin: true },
    }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy,
  },
})
