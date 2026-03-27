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
    port: 5173,
  },
});
