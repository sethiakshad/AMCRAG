import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backendPort = process.env.VITE_BACKEND_PORT || '8000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            console.warn(`[vite proxy] Backend connection failed (port ${backendPort}): ${err.message}. Is the backend running?`);
            if (res && 'writeHead' in res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Backend server is not running. Please start the backend first.' }));
            }
          });
        },
      },
      '/static': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
})

