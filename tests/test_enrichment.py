from workers.enrichment import (
    dedup_hash,
    detect_language,
    enrich,
    hash_author,
    mask_pii,
    normalize_text,
)


def test_normalize_strips_html_and_whitespace() -> None:
    assert normalize_text("<p>Halo  <b>dunia</b></p>\n\n") == "Halo dunia"
    assert normalize_text("a&amp;b") == "a&b"


def test_mask_pii() -> None:
    masked = mask_pii("hubungi saya di budi@example.com atau 081234567890, NIK 3171234567890123")
    assert "budi@example.com" not in masked
    assert "081234567890" not in masked
    assert "3171234567890123" not in masked
    assert "[email]" in masked and "[telp]" in masked and "[nik]" in masked


def test_author_hash_stable_and_platform_scoped() -> None:
    a = hash_author("youtube", "user-1")
    assert a == hash_author("youtube", "user-1")  # stabil
    assert a != hash_author("reddit", "user-1")  # beda platform → beda pseudonim
    assert len(a) == 64 and "user-1" not in a


def test_dedup_hash_canonical() -> None:
    assert dedup_hash("Beras  MAHAL") == dedup_hash("beras mahal")
    assert dedup_hash("beras mahal") != dedup_hash("beras murah")


def test_detect_language_indonesian() -> None:
    lang = detect_language("Harga beras naik terus, pemerintah harus segera bertindak sekarang")
    assert lang == "id"


def test_enrich_bundle() -> None:
    out = enrich("rss", "Penulis", "<b>Halo</b> email saya x@y.co")
    assert set(out) == {"content", "lang", "author_hash", "dedup_hash"}
    assert "[email]" in out["content"]
