import { defineConfig } from 'vite';

export default defineConfig({
  resolve: {
    alias: {
      components: '/src/components',
      features: '/src/features',
      shared: '/src/shared',
    },
  },
  server: {
    host: process.env.ORDER_SYSTEM_DEV_HOST ?? '127.0.0.1',
    port: 5173,
    strictPort: true,
    headers: { 'Cache-Control': 'no-store' },
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
});
