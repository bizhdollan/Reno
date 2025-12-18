import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true, // Listen on all addresses
    allowedHosts: [
      'cisted-repletely-isabela.ngrok-free.dev',
      '.ngrok-free.dev', // Allow all ngrok-free.dev subdomains
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})