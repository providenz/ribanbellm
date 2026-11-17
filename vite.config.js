import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    // Django backend (cd backend && uv run python manage.py runserver)
    proxy: { '/api': process.env.API_URL || 'http://localhost:8000' },
  },
});
