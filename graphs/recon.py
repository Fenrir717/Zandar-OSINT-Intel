"""Agen Recon — penemuan target otomatis untuk sumber berbasis-URL.

Topik/keyword → cari web (DuckDuckGo HTML, gratis tanpa key) + situs benih dari LLM
→ dedup/saring → daftar URL untuk adapter `website` (web_extract mengekstrak isinya
saat koleksi). Membuka wacana web umum tanpa analis mengetik URL.

Ini "agent intel": hanya MENEMUKAN target (cepat, tanpa fetch konten). Pengambilan
& ekstraksi teks terjadi di adapter website saat collect_source. Gabungan dua jalur:
LLM-suggested (cepat) + search-driven (segar) sesuai rekomendasi.
"""

from __future__ import annotations

import re
import urllib.parse

import httpx

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120 Safari/537.36"}
_DDG = "https://html.duckduckgo.com/html/"
_RESULT_HREF = re.compile(r'result__a[^>]+href="([^"]+)"')

# Platform sosial / non-artikel → butuh adapter sendiri atau bukan teks artikel; dilewati.
_SKIP_HOSTS = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
    "youtube.com", "youtu.be", "pinterest.", "linkedin.com", "t.me", "wa.me",
    "shopee.", "tokopedia.", "lazada.", "bukalapak.",
)


def ddg_search(query: str, max_results: int = 10) -> list[str]:
    """DuckDuckGo HTML → daftar URL hasil (decode redirect uddg). Best-effort."""
    try:
        r = httpx.post(_DDG, data={"q": query}, headers=_UA, timeout=25, follow_redirects=True)
        if r.status_code != 200:
            return []
    except httpx.HTTPError:
        return []
    out: list[str] = []
    for href in _RESULT_HREF.findall(r.text):
        m = re.search(r"uddg=([^&]+)", href)
        url = urllib.parse.unquote(m.group(1)) if m else (href if href.startswith("http") else "")
        if url:
            out.append(url)
        if len(out) >= max_results:
            break
    return out


def _skip(url: str) -> bool:
    u = url.lower()
    return (not u.startswith("http")) or any(h in u for h in _SKIP_HOSTS)


def _llm_seed_urls(topic: str, keywords: list[str]) -> list[str]:
    """LLM (Tier F) menyarankan situs/blog/forum Indonesia relevan → URL. Divalidasi
    kasar (buang non-http); URL halusinasi yang mati akan gagal saat web_extract."""
    try:
        from graphs.llm import get_llm

        r = get_llm().call_json(
            "F",
            "Sebutkan hingga 8 situs/blog/forum Indonesia yang KEMUNGKINAN membahas "
            "topik ini (berita, blog, forum diskusi, komunitas). Balas JSON "
            '{"sites":["https://domain-atau-url", ...]} — URL absolut, tanpa media sosial.',
            f"topik: {topic}; kata kunci: {', '.join(keywords[:8])}",
            hint={"node": "recon_seed", "topic": topic},
        )
        sites = r.data.get("sites", []) if isinstance(r.data, dict) else []
    except Exception:
        return []
    out = []
    for s in sites:
        s = str(s).strip()
        if s and not s.startswith("http"):
            s = "https://" + s
        if s and not _skip(s):
            out.append(s)
    return out


def discover_targets(keywords: list[str], topic: str = "", max_urls: int = 20) -> list[dict]:
    """Gabung DDG (beberapa query intent) + benih LLM → URL unik tersaring → satu
    source `website`. Kembalikan list spec sumber (kosong bila tak menemukan apa pun)."""
    kws = [k for k in keywords if k][:6]
    if not kws and not topic:
        return []
    base = kws[0] if kws else topic
    # Query intent: perkaya dengan kata pemicu wacana Indonesia.
    queries = [base, f"{base} pengalaman", f"{base} keluhan", f"{base} forum"]
    if len(kws) > 1:
        queries.append(f"{kws[0]} {kws[1]}")

    urls: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        key = u.split("#")[0].rstrip("/").lower()
        if key and key not in seen and not _skip(u):
            seen.add(key)
            urls.append(u)

    for q in queries:
        for u in ddg_search(q, max_results=8):
            add(u)
        if len(urls) >= max_urls:
            break
    for u in _llm_seed_urls(topic, kws):
        add(u)

    urls = urls[:max_urls]
    specs: list[dict] = []
    if urls:
        specs.append({
            "platform": "website",
            "query": {"urls": urls, "keywords": keywords, "max_pages": len(urls)},
            "est_items": len(urls),
        })
    # Tulang punggung deterministik: media besar Indonesia (umum+bisnis+investasi) via
    # sitemap bulk. Selalu ikut bila ada keyword — tak bergantung DDG/LLM menemukannya.
    if kws:
        from graphs.media_seeds import sitemap_sources

        specs.extend(sitemap_sources(keywords, limit=6))
    return specs
