import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the API runs on :8000 (make run); in production Caddy serves both.
// changeOrigin stays false so the API sees the browser's Host, which its CSRF Origin
// check compares against (Caddy and Cloudflare Tunnel preserve Host the same way).
const api = { target: 'http://127.0.0.1:8000', changeOrigin: false }

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/app/api': api,
      '/v1': api,
    },
  },
})
