"""Pipeline enrichment deterministik (PRD §6) — TANPA LLM.

normalisasi → deteksi bahasa → PII masking → pseudonimisasi author (UU PDP) → dedup hash.
Fase 2 mengganti langdetect → fastText lid.176 dan menambah near-duplicate via embedding.
"""

import hashlib
import hmac
import html
import re
import unicodedata

from langdetect import DetectorFactory, LangDetectException, detect

from core.config import get_settings

DetectorFactory.seed = 42  # langdetect deterministik antar-run

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+62|62|0)8\d{2}[\s.-]?\d{3,4}[\s.-]?\d{3,5}")
_NIK_RE = re.compile(r"\b\d{16}\b")  # NIK KTP — 16 digit


def normalize_text(text: str) -> str:
    """Buang markup, entity HTML, karakter kontrol; rapikan whitespace."""
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t ")
    return _WS_RE.sub(" ", text).strip()


def detect_language(text: str) -> str | None:
    if len(text) < 8:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def mask_pii(text: str) -> str:
    """Minimisasi data (PRD §12): email, nomor telepon, dan NIK tidak pernah disimpan."""
    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[telp]", text)
    return _NIK_RE.sub("[nik]", text)


def hash_author(platform: str, author_raw: str) -> str:
    """Pseudonim stabil per (platform, author) — HMAC agar tidak bisa di-reverse tanpa salt."""
    salt = get_settings().author_hash_salt.encode("utf-8")
    return hmac.new(salt, f"{platform}:{author_raw}".encode(), hashlib.sha256).hexdigest()


def dedup_hash(normalized_text: str) -> str:
    """Kunci dedup exact: teks ternormalisasi, huruf kecil, tanpa spasi ganda."""
    canonical = _WS_RE.sub(" ", normalized_text.lower()).strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enrich(platform: str, author_raw: str, content_raw: str) -> dict:
    """Jalankan seluruh tahap; kembalikan field siap simpan ke tabel comments."""
    normalized = normalize_text(content_raw)
    masked = mask_pii(normalized)
    return {
        "content": masked,
        "lang": detect_language(masked),
        "author_hash": hash_author(platform, author_raw),
        "dedup_hash": dedup_hash(masked),
    }
