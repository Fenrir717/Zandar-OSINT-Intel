import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: Vite di :5173, proxy /api ke FastAPI (:8010) — hindari isu CORS.
// Build: output ke dist/, disajikan FastAPI di produksi.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8010", changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
