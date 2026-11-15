import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { '/api': loadEnv(mode, '.', 'SENTINEL_').SENTINEL_PROXY_TARGET || 'http://127.0.0.1:8000', '/healthz': loadEnv(mode, '.', 'SENTINEL_').SENTINEL_PROXY_TARGET || 'http://127.0.0.1:8000' },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
}))
