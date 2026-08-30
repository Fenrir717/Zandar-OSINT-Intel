import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: Vite di :5174 (5173 sering dipakai pentest), proxy /api ke FastAPI (:8010).
// Build: output ke dist/, disajikan FastAPI di produksi.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",  // bind IPv4 eksplisit (hindari isu localhost/IPv6 di Windows)
    port: 5174,
    proxy: {
      "/api": { target: "http://127.0.0.1:8010", changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
