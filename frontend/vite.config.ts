import { defineConfig, loadEnv, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
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
    '/api': { target: proxyBase || 'http://127.0.0.1:80', changeOrigin: true, timeout: 300000, proxyTimeout: 300000 },
    '/v1': { target: proxyBase || 'http://127.0.0.1:80', changeOrigin: true },
    '/mcp': { target: proxyBase || 'http://127.0.0.1:80', changeOrigin: true },
  }

  const directProxy: ProxyMap = {
    // AI service routes (port 8001) — before generic /api rule
    '^/api/v1/workspaces/[^/]+/projects/[^/]+/ai': { target: 'http://127.0.0.1:8001', changeOrigin: true, timeout: 300000, proxyTimeout: 300000 },
    '^/api/v1/workspaces/[^/]+/ai':               { target: 'http://127.0.0.1:8001', changeOrigin: true, timeout: 300000, proxyTimeout: 300000 },
    '^/api/v1/workspaces/[^/]+/rag':              { target: 'http://127.0.0.1:8001', changeOrigin: true, timeout: 300000, proxyTimeout: 300000 },

    // MCP service routes (port 8001 — merged into intelligence)
    '^/api/v1/workspaces/[^/]+/mcp':              { target: 'http://127.0.0.1:8001', changeOrigin: true },
    '/mcp':                                         { target: 'http://127.0.0.1:8001', changeOrigin: true },

    // Everything else goes to the workspace service (port 8000) — includes GitHub, projects, tasks, OPPM
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    '/v1':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
  }

  const proxy: ProxyMap = proxyBase ? gatewayProxy : directProxy

  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'prompt',
        injectRegister: 'auto',
        workbox: {
          maximumFileSizeToCacheInBytes: 3 * 1024 * 1024, // 3 MB — OPPMView chunk is ~2.7 MB
          globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/.*\.(?:png|jpg|jpeg|svg|gif|woff2)$/,
              handler: 'CacheFirst',
              options: {
                cacheName: 'assets-cache',
                expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 },
              },
            },
            {
              urlPattern: /^\/api\/.*/,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-cache',
                expiration: { maxEntries: 200, maxAgeSeconds: 5 * 60 },
              },
            },
          ],
        },
        manifest: {
          name: 'FlowDesk Work Management',
          short_name: 'FlowDesk',
          description: 'AI-powered OPPM work management system',
          theme_color: '#f7f6f3',
          background_color: '#ffffff',
          display: 'standalone',
          icons: [
            { src: '/icon-192x192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icon-512x512.png', sizes: '512x512', type: 'image/png' },
          ],
        },
      }),
      {
        // Increase HTTP server socket timeout so long AI/LLM requests
        // (scaffold + LLM inference can take 60-180s) don't get killed
        // by the default Node.js ~30s socket timeout → 504 Gateway Timeout.
        name: 'server-timeout',
        configureServer(server) {
          server.httpServer?.setTimeout(300_000)
        },
      },
    ],
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
