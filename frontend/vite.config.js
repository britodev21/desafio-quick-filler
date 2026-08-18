import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O backend roda em outra porta. Sem o proxy, o navegador trataria cada
// chamada como cross-origin e barraria por CORS; com ele, front e API saem
// da mesma origem e nada de CORS precisa existir no FastAPI.
const BACKEND = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/healthz': { target: BACKEND, changeOrigin: true },
    },
  },
})
