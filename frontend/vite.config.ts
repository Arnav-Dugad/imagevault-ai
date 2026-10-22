import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run build` writes the website into the Python app, which serves it.
// `npm run dev` serves it with live reload and forwards /api to the Python server on port 8000.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../app/static", emptyOutDir: true },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
