import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard calls /api/... and Vite forwards it to FastAPI, so there is
// no CORS round-trip in development and no hostname baked into the build.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.BACKEND_PORT ?? '8000'}`,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
