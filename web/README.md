# web/ — Frontend (React + Vite + TypeScript)

SPA untuk 11 halaman intelijen. Identitas petrol-teal (dari PRD/wireframe),
dark-mode-ready. Panduan desain di `design-system/zandar-osint/MASTER.md` (uipro).

## Struktur

```
src/
  main.tsx              # entry + BrowserRouter
  App.tsx               # auth gate + routing 11 halaman
  theme.css             # design tokens (light + dark)
  lib/
    api.ts              # klien API terpusat (JWT), tipe selaras Pydantic
    useInvestigations.tsx
  components/
    Shell.tsx           # sidebar + header (dipakai semua halaman)
    ui.tsx              # primitif: Tile, Pill, Button, Card, Empty
  pages/
    Login.tsx
    CommentExplorer.tsx # halaman nyata pertama (stats, cari, filter, runs)
    Placeholder.tsx     # stub 10 halaman lain (menandai fase)
```

## Dev

```bash
cd web && npm install
npm run dev        # Vite :5173, proxy /api → :8010
```

Backend harus jalan di :8010 (`uvicorn api.main:app --port 8010`).

## Produksi

```bash
npm run build      # → web/dist
```

FastAPI menyajikan `web/dist` di `/` dengan fallback client-side routing
(lihat `api/main.py`). `node_modules/` dan `dist/` di-gitignore.

## Menambah halaman

1. Buat komponen di `src/pages/`.
2. Daftarkan `<Route>` di `App.tsx` (ganti `<Placeholder>` terkait).
3. Judul header di map `TITLES`; nav sudah ada di `Shell.tsx`.
