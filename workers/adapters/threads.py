"""Adapter Threads (Meta) — komentar/replies publik by keyword, LOGGED-OUT (tanpa login).

Pukul GraphQL PUBLIK Threads sebagai tamu LOGGED-OUT (av=0, IsLoggedIn=False) — TANPA
akun/login. Dua tahap:
  1) Playwright POLOS (headless, TANPA stealth/undetected/proxy; navigator.webdriver
     TIDAK disembunyikan) untuk: (a) cari post by keyword, (b) tangkap token guest yang
     situs terbitkan sendiri (lsd/csrftoken/bloks).
  2) httpx POLOS POST ke /graphql/query (doc_id publik) → ambil replies tiap post.

BUKAN evasion: tanpa login, tanpa proxy/rotasi, tanpa spoof fingerprint. Meta tetap
bisa lihat ini otomatis; kalau 429/403 → berhenti SOPAN (fail-soft). Karena logged-out,
volume dibatasi Meta — untuk volume besar → vendor (Apify/Scrapfly).

Diadaptasi dari galihkjaya/threadscraper (MIT): pendekatan guest-GraphQL + token-capture.
Transport requests→httpx, ditambah pacing sopan kita (pacing.py), dibuat fail-soft &
config-driven. Butuh browser Playwright: pip install -e ".[social]" lalu
`python -m playwright install chromium`.

query = {
    "keywords": ["bank bca", "pinjol ilegal"],  # cari post by keyword (butuh Playwright)
    "post_codes": ["DYeZUeiElWy"],               # ATAU shortcode langsung (tetap butuh token)
    "max_posts": 50,                              # batas post per keyword
    "max_replies_per_post": 200,                  # batas replies per post
    "headless": true,                             # jalankan browser di balik layar (default true)
    # pacing sopan (reuse pacing.py):
    "delay_min": 2.0, "delay_max": 5.0, "batch_size": 0, "batch_rest_sec": 0,
    "user_agent": "...", "accept_language": "id-ID,...",  # UA jujur + bahasa (override default)
}
"""

import asyncio
import json
import random
import re
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import unquote_plus

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.pacing import PolitePacer, accept_language, user_agent

_ENDPOINT = "https://www.threads.com/graphql/query"
_MAX_POSTS_CAP = 300
_MAX_REPLIES_CAP = 1000
_MAX_KEYWORDS = 20
_MIN_TEXT = 5

# Envelope statis yang WAJIB agar endpoint publik logged-out menerima query (konstanta
# publik klien web Threads; UA/bahasa disuntik dinamis di _build_client). doc_id =
# persisted-query "BarcelonaPostPageDirectQuery" (replies sebuah post).
_BASE_HEADERS = {
    "accept": "*/*",
    "origin": "https://www.threads.com",
    "referer": "https://www.threads.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-asbd-id": "359341",
    "x-fb-friendly-name": "BarcelonaPostPageDirectQuery",
    "x-ig-app-id": "238260118697367",
    "x-logged-out-threads-migrated-request": "true",
    "x-root-field-name": "xdt_api__v1__text_feed__media_id__replies__connection",
}
_BASE_PAYLOAD = {
    "av": "0", "__user": "0", "__a": "1", "dpr": "1", "__ccg": "EXCELLENT",
    "__spin_b": "trunk", "hl": "en", "fb_api_caller_class": "RelayModern",
    "fb_api_req_friendly_name": "BarcelonaPostPageDirectQuery",
    "server_timestamps": "true", "doc_id": "26739870295663957",
}
_BASE_VARIABLES = {
    "sort_order": "TOP",
    "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": False,
    "__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider": True,
    "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider": False,
    "__relay_internal__pv__BarcelonaHasInlineReplyComposerrelayprovider": False,
    "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider": False,
}


# --------------------------------------------------------------------------- helpers

def _parse_cookie_header(cookie_str: str) -> dict:
    out: dict = {}
    for part in (cookie_str or "").split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _codes_from_json(body: str) -> list[str]:
    """Tarik shortcode post dari body JSON respons (cari field 'code')."""
    codes: list[str] = []
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return codes

    def walk(obj):
        if isinstance(obj, dict):
            code = obj.get("code")
            if isinstance(code, str) and len(code) > 5 and code not in codes:
                codes.append(code)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for it in obj:
                walk(it)

    walk(data)
    return codes


def _shortcode_to_id(shortcode: str) -> str:
    """Konversi shortcode Threads/Instagram → numeric media ID."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    n = 0
    try:
        for ch in shortcode:
            n = n * 64 + alphabet.index(ch)
    except ValueError:
        return ""
    return str(n)


def _ts(v):
    try:
        return datetime.fromtimestamp(int(v), UTC).replace(tzinfo=None) if v else None
    except (ValueError, OSError, TypeError):
        return None


# --------------------------------------------------------- Playwright (search + token)

async def _capture_once(page, context) -> dict:
    tokens: dict = {}
    captured = asyncio.Event()

    async def handle_request(request):
        if "/graphql/query" not in request.url or request.method.upper() != "POST" or captured.is_set():
            return
        headers = request.headers
        cookie_map = _parse_cookie_header(headers.get("cookie", ""))
        try:
            for c in await context.cookies("https://www.threads.com"):
                cookie_map.setdefault(c["name"], c["value"])
        except Exception:
            pass
        lsd_value = ""
        try:
            for part in (request.post_data or "").split("&"):
                if part.startswith("lsd="):
                    lsd_value = unquote_plus(part.split("=", 1)[1])
                    break
        except Exception:
            pass
        tokens.update({
            "lsd": lsd_value or cookie_map.get("lsd", ""),
            "csrftoken": cookie_map.get("csrftoken", ""),
            "x-csrftoken": headers.get("x-csrftoken", cookie_map.get("csrftoken", "")),
            "x-bloks-version-id": headers.get("x-bloks-version-id", ""),
            "mid": cookie_map.get("mid", ""),
        })
        captured.set()

    page.on("request", handle_request)
    await page.goto("https://www.threads.com", wait_until="networkidle", timeout=30_000)
    for selector in ("article", "[role='article']", "a[href*='/post/']"):
        try:
            el = page.locator(selector).first
            if await el.count() > 0:
                await el.click(timeout=5_000)
                break
        except Exception:
            pass
    try:
        await asyncio.wait_for(captured.wait(), timeout=8)
    except Exception:
        pass
    return tokens


async def _capture_tokens(page, context) -> dict:
    tokens: dict = {}
    for _ in range(3):
        got = await _capture_once(page, context)
        if got.get("lsd") and got.get("csrftoken"):
            return got
        tokens = got or tokens
        try:
            await page.keyboard.press("End")
            await asyncio.sleep(3)
        except Exception:
            pass
    return tokens


async def _search_codes(context, keyword: str, max_posts: int) -> list[str]:
    codes: list[str] = []
    api_codes: list[str] = []
    page = await context.new_page()

    async def handle_response(response):
        try:
            if "graphql" not in response.url or response.status != 200:
                return
            body = await response.text()
            if "thread_items" not in body and "edges" not in body:
                return
            for c in _codes_from_json(body):
                if c not in api_codes:
                    api_codes.append(c)
        except Exception:
            pass

    page.on("response", handle_response)
    url = f"https://www.threads.com/search?q={keyword.replace(' ', '+')}&serp_type=default"
    try:
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        prev, stall = 0, 0
        for _ in range(10):
            if len(codes) >= max_posts:
                break
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(1.5, 2.5))
            hrefs = await page.eval_on_selector_all("a[href*='/post/']", "els => els.map(e => e.href)")
            for href in hrefs:
                m = re.search(r"/post/([A-Za-z0-9_-]+)", href)
                if m and m.group(1) not in codes:
                    codes.append(m.group(1))
                if len(codes) >= max_posts:
                    break
            if len(codes) == prev:
                stall += 1
                if stall >= 3:
                    break
            else:
                stall = 0
            prev = len(codes)
    except Exception:
        pass
    finally:
        try:
            await page.close()
        except Exception:
            pass
    for c in api_codes:  # fallback: lengkapi dari sniff GraphQL bila href minim
        if len(codes) >= max_posts:
            break
        if c not in codes:
            codes.append(c)
    return codes[:max_posts]


async def _browser_collect(keywords: list[str], max_posts: int, headless: bool, ua: str):
    from playwright.async_api import async_playwright

    tokens: dict = {}
    codes: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(user_agent=ua, locale="id-ID")
            page = await context.new_page()
            try:
                tokens = await _capture_tokens(page, context)
            except Exception:
                tokens = {}
            for kw in keywords:
                try:
                    for c in await _search_codes(context, kw, max_posts):
                        if c not in codes:
                            codes.append(c)
                except Exception:
                    continue
        finally:
            await browser.close()
    return tokens, codes


def _browser_collect_sync(keywords: list[str], max_posts: int, headless: bool, ua: str):
    """Jalankan bagian async Playwright di thread terisolasi (hindari bentrok event-loop)."""
    box: dict = {}

    def run():
        try:
            box["res"] = asyncio.run(_browser_collect(keywords, max_posts, headless, ua))
        except Exception:
            box["res"] = ({}, [])

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join()
    return box.get("res", ({}, []))


# ------------------------------------------------------------------ httpx GraphQL

def _build_client(tokens: dict, ua: str, lang: str) -> httpx.Client:
    headers = {**_BASE_HEADERS, "user-agent": ua, "accept-language": lang}
    if tokens.get("x-csrftoken"):
        headers["x-csrftoken"] = tokens["x-csrftoken"]
    if tokens.get("x-bloks-version-id"):
        headers["x-bloks-version-id"] = tokens["x-bloks-version-id"]
    cookies = {}
    if tokens.get("csrftoken"):
        cookies["csrftoken"] = tokens["csrftoken"]
    if tokens.get("mid"):
        cookies["mid"] = tokens["mid"]
    return httpx.Client(headers=headers, cookies=cookies, timeout=15.0)


def _fetch_replies(client: httpx.Client, code: str, tokens: dict) -> dict | None:
    numeric = _shortcode_to_id(code)
    if not numeric:
        return None
    variables = {**_BASE_VARIABLES, "postID": numeric}
    payload = {**_BASE_PAYLOAD, "variables": json.dumps(variables, separators=(",", ":"))}
    if tokens.get("lsd"):
        payload["lsd"] = tokens["lsd"]
    try:
        resp = client.post(_ENDPOINT, data=payload)
    except Exception:
        return None
    if resp.status_code != 200:  # 429/403/dll → berhenti sopan (fail-soft)
        return None
    try:
        return resp.json()
    except (ValueError, TypeError):
        return None


def _parse_replies(raw: dict, post_code: str) -> list[dict]:
    if not isinstance(raw, dict) or "data" not in raw or "errors" in raw:
        return []
    rows: list[dict] = []
    try:
        inner = (raw.get("data") or {}).get("data") or {}
        for edge in (inner.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            for i, item in enumerate((edge.get("node") or {}).get("thread_items") or []):
                if not isinstance(item, dict):
                    continue
                post = item.get("post") or {}
                if not post:
                    continue
                caption = post.get("caption") or {}
                text = caption.get("text", "") if isinstance(caption, dict) else ""
                if not text:
                    tpa0 = post.get("text_post_app_info") or {}
                    frags = (tpa0.get("text_fragments") or {}).get("fragments") or []
                    text = " ".join(
                        f.get("plaintext", "") for f in frags
                        if isinstance(f, dict) and f.get("plaintext")
                    )
                user = post.get("user") or {}
                tpa = post.get("text_post_app_info") or {}
                rows.append({
                    "post_code": post_code,
                    "comment_id": post.get("pk", ""),
                    "comment_text": text,
                    "username": user.get("username") or "",
                    "like_count": post.get("like_count") or 0,
                    "reply_count": tpa.get("direct_reply_count") or 0,
                    "timestamp": post.get("taken_at") or "",
                    "type": "reply" if i > 0 else "comment",
                })
    except Exception:
        pass
    return rows


# ----------------------------------------------------------------------- adapter

class ThreadsAdapter(BaseAdapter):
    platform = "threads"
    key = "threads"
    tier = "free"
    requires_credentials = False
    rate_note = "GraphQL Threads logged-out + Playwright polos; tanpa login/proxy/stealth. Volume dibatasi Meta."
    legal_note = "Konten publik, tanpa akun/login. Fail-soft bila 429/403. Volume besar → vendor."

    def collect(self, query: dict) -> Iterator[RawItem]:
        try:
            import playwright  # noqa: F401 — lazy, cek ketersediaan
        except ImportError as exc:
            raise AdapterNotConfigured(
                'Playwright belum terpasang: pip install -e ".[social]" lalu python -m playwright install chromium'
            ) from exc

        keywords = [k for k in (query.get("keywords") or []) if k][:_MAX_KEYWORDS]
        post_codes = [c for c in (query.get("post_codes") or []) if c]
        if not keywords and not post_codes:
            raise AdapterNotConfigured("Threads butuh 'keywords' atau 'post_codes' pada query")

        max_posts = max(1, min(int(query.get("max_posts", 50)), _MAX_POSTS_CAP))
        max_replies = max(1, min(int(query.get("max_replies_per_post", 200)), _MAX_REPLIES_CAP))
        headless = bool(query.get("headless", True))
        ua, lang = user_agent(query), accept_language(query)
        pacer = PolitePacer.from_query(query, delay_min=2.0, delay_max=5.0)

        tokens, discovered = _browser_collect_sync(keywords, max_posts, headless, ua)
        codes = list(dict.fromkeys([*post_codes, *discovered]))[:_MAX_POSTS_CAP]
        if not tokens.get("lsd") or not codes:
            return  # token gagal ditangkap / tak ada post → berhenti sopan

        client = _build_client(tokens, ua, lang)
        try:
            for code in codes:
                pacer.wait()
                raw = _fetch_replies(client, code, tokens)
                if not raw:
                    continue
                n = 0
                for row in _parse_replies(raw, code):
                    if n >= max_replies:
                        break
                    text = (row.get("comment_text") or "").strip()
                    if len(text) < _MIN_TEXT:
                        continue
                    n += 1
                    uname = row.get("username") or ""
                    url = (f"https://www.threads.com/@{uname}/post/{code}" if uname
                           else f"https://www.threads.com/t/{code}")
                    yield RawItem(
                        platform=self.platform,
                        external_id=f"threads:{row.get('comment_id') or code}"[:255],
                        author=uname or "unknown",
                        content=text,
                        url=url,
                        published_at=_ts(row.get("timestamp")),
                        raw=row,
                    )
        finally:
            client.close()
