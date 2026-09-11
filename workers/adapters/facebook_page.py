"""Adapter Facebook Page (kartu bisnis publik) — httpx polos + UA jujur, fail-soft.

Ambil METADATA HALAMAN publik (BUKAN post/komentar — itu adapter `facebook`):
nama, kategori, alamat, telepon, email, website, jam buka, kisaran harga, rating,
likes/followers, page_id, status halaman bisnis. Berguna utk pilar riset-bisnis &
baseline reputasi (kartu nama publik sebuah brand/UMKM).

Metode: fetch https://www.facebook.com/<page> pakai httpx + SATU UA browser jujur
(pacing.py) + Accept-Language, lalu parse JSON Relay yang FB sematkan di
<script type="application/json"> untuk pengunjung anonim. TANPA login/cookie/token;
TANPA curl_cffi/TLS-spoof/stealth. Kalau FB menantang/blokir → BERHENTI SOPAN
(fail-soft), bukan lawan anti-bot. Yield VARIABEL: jalan saat FB sajikan halaman ke
klien polos, mandek saat ditantang. Untuk volume andal → vendor (Scrapfly/Apify).

PROBE LANGSUNG (12 Sep 2026, /bankbca): FB balas HTTP 400 ke klien httpx polos → 0
item. Jalur polos SERING diblok di domain utama FB (butuh fingerprint browser yg tak
kita palsukan). Maka nilai utama modul ini = LOGIKA PARSING yg reusable: transport
bisa diganti vendor (Scrapfly/Apify) yg menembus sah, HTML/JSON-nya lalu di-`_parse`.

Logika ekstraksi JSON diadaptasi dari SSujitX/facebook-page-scraper (MIT). Yang
DIGANTI: transport (asli curl_cffi impersonation → httpx polos) dan penanganan
error (asli sys.exit → fail-soft, lewati halaman yang gagal).

query = {
    "pages": ["bankbca", "https://www.facebook.com/BankBCA"],  # username / URL penuh
    "delay_min": 3.0, "delay_max": 8.0,   # pacing sopan antar-halaman (default aktif)
    "batch_size": 0, "batch_rest_sec": 0, # ambil N halaman lalu istirahat X dtk (0 = mati)
    "user_agent": "...", "accept_language": "id-ID,...",  # UA jujur + bahasa (override default)
}
"""

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.pacing import PolitePacer, accept_language, user_agent

_FB_BASE = "https://www.facebook.com/"
_MAX_PAGES_CAP = 100
_SCRIPT_RE = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL)
_META_DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"')

# Peta jenis "intro card" FB → field kartu bisnis (dari sumber MIT).
_INTRO_CARDS = {
    "INTRO_CARD_INFLUENCER_CATEGORY": "category",
    "INTRO_CARD_ADDRESS": "address",
    "INTRO_CARD_PROFILE_PHONE": "phone",
    "INTRO_CARD_PROFILE_EMAIL": "email",
    "INTRO_CARD_WEBSITE": "website",
    "INTRO_CARD_BUSINESS_HOURS": "business_hours",
    "INTRO_CARD_BUSINESS_PRICE": "business_price",
    "INTRO_CARD_RATING": "rating",
    "INTRO_CARD_BUSINESS_SERVICES": "services",
    "INTRO_CARD_OTHER_ACCOUNT": "social_accounts",
}


class FacebookPageAdapter(BaseAdapter):
    platform = "facebook_page"
    key = "facebook_page"
    tier = "free"
    requires_credentials = False
    rate_note = "httpx polos + 1 UA jujur ke halaman FB publik; tanpa curl_cffi/spoof. Yield variabel bila FB nantang."
    legal_note = "Hanya metadata halaman publik (kartu bisnis). Tanpa login/token. Fail-soft bila diblok."

    def collect(self, query: dict) -> Iterator[RawItem]:
        pages = [p for p in (query.get("pages") or []) if p]
        if not pages:
            raise AdapterNotConfigured("Facebook Page butuh 'pages' (username/URL halaman publik) pada query")

        headers = {
            "User-Agent": user_agent(query),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": accept_language(query),
            "Upgrade-Insecure-Requests": "1",
        }
        pacer = PolitePacer.from_query(query, delay_min=3.0, delay_max=8.0)

        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            for raw_page in pages[:_MAX_PAGES_CAP]:
                pacer.wait()  # jeda sopan antar-halaman
                url = self._normalize(raw_page)
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    html = resp.text
                except Exception:  # noqa: BLE001 — FB blokir/nantang/timeout → lewati sopan
                    continue
                item = self._parse(html, url)
                if item is not None:
                    yield item

    @staticmethod
    def _normalize(page: str) -> str:
        page = str(page).strip()
        if page.startswith(("http://", "https://")):
            return page
        return _FB_BASE + page.lstrip("/")

    def _parse(self, html: str, url: str) -> RawItem | None:
        card: dict = {}
        gen = self._extract(html, "username_for_profile", self._general)
        if gen:
            card.update(gen)
        prof = self._extract(html, "profile_tile_items", self._profile)
        if prof:
            card.update(prof)
        card.update(self._meta(html))

        name = card.get("page_name")
        content = self._summary(card)
        if not content:  # tak ada satupun field berguna → jangan yield item kosong
            return None
        page_id = card.get("page_id")
        ext = f"fbpage:{page_id}" if page_id else f"fbpage:{url.rstrip('/').rsplit('/', 1)[-1]}"
        card["captured_at"] = datetime.now(UTC).isoformat()
        card["source_url"] = url
        return RawItem(
            platform=self.platform,
            external_id=ext[:255],
            author=name or "unknown",
            content=content,
            url=card.get("page_url") or url,
            published_at=None,  # snapshot profil — bukan post bertanggal; captured_at ada di raw
            title=name,
            raw=card,
        )

    # --- ekstraksi JSON tersemat (adaptasi MIT, fail-soft) ---

    def _extract(self, html: str, key: str, fn) -> dict | None:
        """Cari <script application/json> yg memuat `key`, parse, jalankan `fn`. Fail-soft."""
        for block in _SCRIPT_RE.findall(html):
            if key not in block:
                continue
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            try:
                return fn(data)
            except (IndexError, KeyError, TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _requires(json_data: dict) -> list:
        requires = json_data.get("require", [])
        if not requires:
            return []
        return requires[0][3][0].get("__bbox", {}).get("require", [])

    def _general(self, json_data: dict) -> dict:
        info: dict = {}
        for require in self._requires(json_data):
            if "RelayPrefetchedStreamCache" not in require:
                continue
            result = require[3][1].get("__bbox", {}).get("result", {})
            user = (
                result.get("data", {}).get("user", {})
                .get("profile_header_renderer", {}).get("user", {})
            )
            if not user:
                continue
            info["page_name"] = user.get("name")
            info["page_url"] = user.get("url")
            delegate = user.get("delegate_page") or {}
            info["page_id"] = delegate.get("id")
            info["is_business_page"] = delegate.get("is_business_page_active")
            info["profile_pic"] = (
                user.get("profilePicLarge", {}).get("uri")
                or user.get("profilePicMedium", {}).get("uri")
                or user.get("profilePicSmall", {}).get("uri")
            )
            for content in (user.get("profile_social_context") or {}).get("content", []):
                uri = content.get("uri", "") or ""
                text = content.get("text", {}).get("text")
                if "friends_likes" in uri and not info.get("page_likes"):
                    info["page_likes"] = text
                elif "followers" in uri and not info.get("page_followers"):
                    info["page_followers"] = text
        return {k: v for k, v in info.items() if v is not None}

    def _profile(self, json_data: dict) -> dict:
        info: dict = {}
        for require in self._requires(json_data):
            if "RelayPrefetchedStreamCache" not in require:
                continue
            result = require[3][1].get("__bbox", {}).get("result", {})
            sections = result.get("data", {}).get("profile_tile_sections", {}).get("edges", [])
            for section in sections:
                nodes = section.get("node", {}).get("profile_tile_views", {}).get("nodes", [])
                for node in nodes:
                    vsr = node.get("view_style_renderer")
                    if not vsr:
                        continue
                    items = vsr.get("view", {}).get("profile_tile_items", {}).get("nodes", [])
                    for item in items:
                        tci = item.get("node", {}).get("timeline_context_item", {})
                        field = _INTRO_CARDS.get(tci.get("timeline_context_list_item_type"))
                        if not field:
                            continue
                        text = tci.get("renderer", {}).get("context_item", {}).get("title", {}).get("text")
                        if text:
                            info[field] = text
        return info

    @staticmethod
    def _meta(html: str) -> dict:
        m = _META_DESC_RE.search(html)
        if not m:
            return {}
        desc = m.group(1)
        out: dict = {}
        for field, pat in (
            ("likes_count", r"([\d,]+)\s+likes"),
            ("talking_count", r"([\d,]+)\s+talking about this"),
            ("were_here_count", r"([\d,]+)\s+were here"),
        ):
            found = re.search(pat, desc)
            if found:
                out[field] = found.group(1)
        return out

    @staticmethod
    def _summary(card: dict) -> str:
        labels = [
            ("page_name", None), ("category", "Kategori"), ("address", "Alamat"),
            ("phone", "Telp"), ("email", "Email"), ("website", "Web"),
            ("rating", "Rating"), ("business_hours", "Jam"), ("business_price", "Harga"),
            ("page_followers", "Pengikut"),
        ]
        parts = []
        for key, label in labels:
            val = card.get(key)
            if val:
                parts.append(str(val) if label is None else f"{label}: {val}")
        return " · ".join(parts)
