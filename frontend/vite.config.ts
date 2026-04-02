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
      // AI service (port 8001) — most specific first
      '^/api/v1/workspaces/[^/]+/projects/[^/]+/ai/': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '^/api/v1/workspaces/[^/]+/rag/': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '^/api/v1/workspaces/[^/]+/ai/': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      // MCP service (port 8003)
      '^/api/v1/workspaces/[^/]+/mcp/': {
        target: 'http://localhost:8003',
        changeOrigin: true,
      },
      // Git service (port 8002)
      '^/api/v1/workspaces/[^/]+/github-accounts': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '^/api/v1/workspaces/[^/]+/commits': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '^/api/v1/workspaces/[^/]+/git/': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '^/api/v1/git/webhook': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      // All other API routes → core service (port 8000)
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
