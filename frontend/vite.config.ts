import { defineConfig, loadEnv, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

type ProxyMap = Record<string, ProxyOptions>

export default defineConfig(({ mode }) => {
  const env = {
    ...loadEnv(mode, __dirname, ''),
    ...process.env,
  }

  // Prefer an env-defined gateway target so native frontend dev can point at
  // Docker on port 80 and the Dockerized frontend can keep using gateway:80.
  const proxyBase = env.API_PROXY_BASE || env.VITE_API_PROXY_BASE

  const gatewayProxy: ProxyMap = {
    '/api': { target: proxyBase || 'http://127.0.0.1:80', changeOrigin: true },
    '/mcp': { target: proxyBase || 'http://127.0.0.1:80', changeOrigin: true },
  }

  const directProxy: ProxyMap = {
    // Git service routes (port 8002) — must be listed BEFORE the generic /api rule
    '^/api/v1/git/webhook':                        { target: 'http://127.0.0.1:8002', changeOrigin: true },
    '^/api/v1/workspaces/[^/]+/commits':          { target: 'http://127.0.0.1:8002', changeOrigin: true },
    '^/api/v1/workspaces/[^/]+/github-accounts':  { target: 'http://127.0.0.1:8002', changeOrigin: true },
    '^/api/v1/workspaces/[^/]+/git':              { target: 'http://127.0.0.1:8002', changeOrigin: true },
    '^/api/git':                                  { target: 'http://127.0.0.1:8002', changeOrigin: true },

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

  const proxy: ProxyMap = proxyBase ? gatewayProxy : directProxy

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      allowedHosts: ['localhost', '127.0.0.1', '.localhost'],
      proxy,
    },
  }
})
