import { defineConfig } from 'vite';

export default defineConfig({
  resolve: {
    alias: {
      components: '/src/components',
      features: '/src/features',
    },
  },
  server: {
    port: 5173,
  },
});
