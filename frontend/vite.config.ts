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
      '^/api/v1/workspaces/[^/]+/commits':          { target: 'http://localhost:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/github-accounts':  { target: 'http://localhost:8002', changeOrigin: true },
      '^/api/v1/workspaces/[^/]+/git':              { target: 'http://localhost:8002', changeOrigin: true },
      '^/api/git':                                   { target: 'http://localhost:8002', changeOrigin: true },

      // Everything else goes to the core service (port 8000)
      '/api': { target: 'http://localhost:8000', changeOrigin: true },

      '/mcp': { target: 'http://localhost:8003', changeOrigin: true },
    },
  },
})
