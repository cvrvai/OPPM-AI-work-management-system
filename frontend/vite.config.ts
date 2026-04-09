import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Git service routes (port 8002) — must be listed BEFORE the generic /api rule
      // because Vite picks the first matching prefix.
      '^/api/v1/workspaces/[^/]+/commits':          { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/github-accounts':  { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/git':              { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '^/api/git':                                   { target: 'http://127.0.0.1:8002', changeOrigin: true },

      // AI service routes (port 8001) — before generic /api rule
      '^/api/v1/workspaces/[^/]+/projects/[^/]+/ai': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/ai':               { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/rag':              { target: 'http://127.0.0.1:8001', changeOrigin: true },

      // Everything else goes to the core service (port 8000)
      '/api': { target: 'http://127.0.0.1:8010', changeOrigin: true },

      '/mcp': { target: 'http://127.0.0.1:8003', changeOrigin: true },
    },
  },
})
