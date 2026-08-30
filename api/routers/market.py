"""Router Riset Pasar Geospasial (pilar general-purpose).

Membuka engine geo.* ke platform: pilih kategori + lokasi → peta kompetitor,
jarak antar-kompetitor, densitas, radius aman (estimasi), ranking sub-zona.
Sumber OpenStreetMap (gratis). Sinkron (Overpass ~30-90s) → dijalankan di thread
agar tak memblok event loop.
"""

import asyncio
import re

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from api.deps import CurrentUser

router = APIRouter(tags=["market"])


@router.get("/market/categories")
async def categories(user: CurrentUser) -> list[dict]:
    """Daftar kategori bisnis yang didukung (untuk dropdown UI)."""
    from geo.catalog import CATALOG

    return [{"key": c.key, "label": c.label, "note": c.note} for c in CATALOG.values()]


class MarketScanRequest(BaseModel):
    category: str
    location: str
    radius_m: int = 4000


@router.post("/market/scan")
async def market_scan(body: MarketScanRequest, user: CurrentUser) -> dict:
    """Jalankan riset pasar geospasial untuk kategori+lokasi. Kembalikan dict lengkap
    (kompetitor, spacing, demand, best_zones, caveats)."""
    from geo.market import run_market_research

    radius = max(500, min(8000, int(body.radius_m)))  # batasi agar query OSM wajar
    try:
        return await asyncio.to_thread(
            run_market_research, body.category, body.location, radius
        )
    except KeyError as exc:  # kategori tak dikenal
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except ValueError as exc:  # lokasi tak ditemukan
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except Exception as exc:  # Overpass/Nominatim gagal
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Sumber geospasial gagal: {exc}")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40] or "riset"


@router.post("/market/report")
async def market_report(body: dict, user: CurrentUser) -> dict:
    """Render hasil riset (dict dari /market/scan) → dokumen HTML laporan mandiri
    untuk diunduh. Tak memanggil ulang OSM — dipakai kembali dari hasil yang sudah ada."""
    from geo.report_html import build_report_document

    try:
        doc = build_report_document(body)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Hasil tak valid untuk laporan: {exc}")
    cat = (body.get("category") or {}).get("key", "riset")
    loc = (body.get("location") or {}).get("query", "")
    return {"filename": f"riset-pasar-{_slug(cat)}-{_slug(loc)}.html", "html": doc}


@router.post("/market/report.pdf")
async def market_report_pdf(body: dict, user: CurrentUser) -> Response:
    """Render hasil riset → PDF (Chromium headless server-side). Konsisten lintas
    browser, background tercetak, dan link tetap bisa diklik. Tak memanggil OSM ulang."""
    from geo.pdf import html_to_pdf
    from geo.report_html import build_report_document

    try:
        doc = build_report_document(body)
        pdf = await asyncio.to_thread(html_to_pdf, doc)
    except RuntimeError as exc:  # Chromium tak ada / gagal render
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Hasil tak valid untuk laporan: {exc}")
    cat = (body.get("category") or {}).get("key", "riset")
    loc = (body.get("location") or {}).get("query", "")
    fn = f"riset-pasar-{_slug(cat)}-{_slug(loc)}.pdf"
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )
