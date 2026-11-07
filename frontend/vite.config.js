import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In development the API runs on :8000; the dev server forwards /api calls to it.
    proxy: { "/api": "http://localhost:8000" },
  },
});
