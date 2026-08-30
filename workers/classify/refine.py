"""Refinement sentimen: koreksi SARKASME/IRONI untuk item ber-confidence rendah.

Aditif: dijalankan SETELAH IndoBERT. Hanya item dengan confidence < ambang yang
dikirim ke LLM (hemat biaya) untuk dinilai ulang secara chain-of-thought —
sarkasme/ironi adalah kelemahan klasik model BERT. Teks ASLI (bukan pra-proses)
dipakai agar nuansa/emoji tetap terbaca.

Dinilai PER-ITEM (satu objek JSON per panggilan): model gratis kecil sering
mengabaikan instruksi "array", jadi satu-objek jauh lebih andal. Gagal LLM →
label asli dipertahankan.
"""

from workers.classify.base import Label

_THRESHOLD = 0.7   # confidence di bawah ini → dinilai ulang LLM
_MAX_REFINE = 80   # batas item per-run agar biaya terjaga

_SARCASM_SYSTEM = (
    "Anda pakar sentimen Bahasa Indonesia yang fokus pada SARKASME & IRONI "
    "(kelemahan model biasa). Nalar langkah-demi-langkah: apakah makna harfiah "
    "berbeda dari maksud sebenarnya (mis. pujian yang sebetulnya sindiran)? Lalu "
    "tentukan sentimen SEBENARNYA.\n"
    "Balas HANYA JSON: {\"sentiment\": \"pos|neg|neu\", \"is_sarcasm\": true|false, "
    "\"confidence\": 0.0-1.0}.\n"
    "Contoh: 'Mantap sekali layanannya, seminggu belum kelar juga' → "
    "{\"sentiment\":\"neg\",\"is_sarcasm\":true,\"confidence\":0.95}."
)

_BASE = {"pos": 0.7, "neg": -0.7, "neu": 0.0}


def refine_low_confidence(
    texts: list[str], labels: list[Label], threshold: float = _THRESHOLD
) -> list[Label]:
    """Nilai ulang item low-confidence via LLM (per-item); mutasikan & kembalikan `labels`."""
    idxs = [i for i, lab in enumerate(labels) if (lab.confidence or 0.0) < threshold][:_MAX_REFINE]
    if not idxs:
        return labels

    from graphs.llm import get_llm

    llm = get_llm()
    for gi in idxs:
        text = (texts[gi] or "").strip()[:400]
        if not text:
            continue
        try:
            r = llm.call_json("F", _SARCASM_SYSTEM, "Teks: " + text,
                              hint={"node": "sarcasm_refine"})
            d = r.data if isinstance(r.data, dict) else {}
        except Exception:  # noqa: BLE001 — LLM/parse gagal → biarkan label asli
            continue

        new_sent = str(d.get("sentiment", "")).lower().strip()
        if new_sent not in ("pos", "neg", "neu"):
            continue
        lab = labels[gi]
        changed = new_sent != lab.sentiment
        lab.sentiment = new_sent
        lab.is_sarcasm = bool(d.get("is_sarcasm", False))
        conf = d.get("confidence")
        lab.confidence = round(float(conf), 3) if isinstance(conf, (int, float)) else max(lab.confidence, 0.75)
        lab.sentiment_score = round(_BASE[new_sent] * lab.confidence, 3)
        if changed or lab.is_sarcasm:
            lab.model_version = (lab.model_version + "+refine")[:50]
    return labels
