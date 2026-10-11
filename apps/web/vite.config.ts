import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], clearScreen: false, server: { port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8787' } }, envPrefix: ['VITE_', 'TAURI_ENV_'], build: { target: 'es2022' } });
