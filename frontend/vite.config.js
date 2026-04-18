import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Force IPv4 loopback so proxy matches uvicorn bind address on Windows.
      // Proxy /upload-timesheet and /health to the FastAPI backend
      '/upload-timesheet': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/submit-timesheet': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
