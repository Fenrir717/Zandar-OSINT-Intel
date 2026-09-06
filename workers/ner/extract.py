"""Ekstraksi entitas (NER) lokal — Person / Organization / Location (Fase 3).

Model transformers Indonesia, impor LAZY (extra [ml]), cache-first (agar tak hang
cek jaringan). Entitas jadi node knowledge graph; ko-okurensi antar-entitas dalam
satu komentar jadi relasi. Berjalan di CPU (GPU otomatis bila CUDA tersedia).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# label model (skema Wikiann/CoNLL) -> taksonomi internal graph
_TYPE_MAP = {
    "PER": "person", "PERSON": "person", "B-PER": "person", "I-PER": "person",
    "ORG": "organization", "B-ORG": "organization", "I-ORG": "organization",
    "LOC": "location", "GPE": "location", "B-LOC": "location", "I-LOC": "location",
}
_MIN_SCORE = 0.75
_MAX_CHARS = 512

# Kata percakapan/sapaan/singkatan yang sering salah diekstrak NER sebagai "entitas"
# (riset: ~22% entitas junk — "kak kalo", "hallo min", "bang kal", "gk", "tf").
_JUNK_WORDS = frozenset({
    "kak", "min", "bang", "bg", "gan", "sis", "sy", "gua", "gue", "aku", "kamu",
    "halo", "hallo", "kalo", "kalau", "gk", "ga", "gak", "tf", "yg", "dm", "pm",
    "kah", "sih", "dong", "deh", "tolong", "mohon", "maaf", "silahkan", "silakan",
    "permisi", "hai", "selamat", "pak", "bu", "mbak", "mas", "om", "tante", "kal",
})


def _is_junk(name: str) -> bool:
    """True bila nama entitas = fragmen percakapan/singkatan, bukan entitas nyata."""
    n = name.lower().strip()
    if len(n.replace(" ", "")) <= 2:            # singkatan pendek: gk, tf, bg
        return True
    toks = n.split()
    if toks and all(t in _JUNK_WORDS for t in toks):   # semua token = filler
        return True
    if len(toks) <= 2 and any(t in _JUNK_WORDS for t in toks):  # frasa pendek ber-filler
        return True
    return False


@dataclass
class Entity:
    text: str
    type: str  # person | organization | location
    score: float


def normalize(name: str) -> str:
    """Normalisasi nama entitas untuk dedup (lower, rapikan spasi, buang '##')."""
    return re.sub(r"\s+", " ", name.replace("##", "").strip()).lower()


class NerExtractor:
    def __init__(self) -> None:
        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError('NER butuh torch+transformers: pip install -e ".[ml]"') from exc

        from core.config import get_settings

        model_id = get_settings().ner_model
        dev = 0 if torch.cuda.is_available() else -1
        tok = mdl = None
        for local_only in (True, False):  # cache-first, lalu online
            try:
                tok = AutoTokenizer.from_pretrained(model_id, local_files_only=local_only)
                mdl = AutoModelForTokenClassification.from_pretrained(model_id, local_files_only=local_only)
                break
            except Exception:
                if not local_only:
                    raise
        self._pipe = pipeline(
            "ner", model=mdl, tokenizer=tok, aggregation_strategy="simple", device=dev,
        )
        self.version = f"ner:{model_id.split('/')[-1]}[{'cuda' if dev == 0 else 'cpu'}]"

    def extract(self, texts: list[str]) -> list[list[Entity]]:
        """Kembalikan daftar entitas per teks (sudah dedup dalam-komentar)."""
        if not texts:
            return []
        clipped = [t[:_MAX_CHARS] for t in texts]
        results = self._pipe(clipped, batch_size=16)
        if isinstance(results, dict):  # transformers kadang balas dict utk input tunggal
            results = [results]
        out: list[list[Entity]] = []
        for res in results:
            seen: dict[str, Entity] = {}
            for e in res or []:
                typ = _TYPE_MAP.get(str(e.get("entity_group", "")).upper())
                name = (e.get("word") or "").replace("##", "").strip()
                score = float(e.get("score", 0.0))
                if not typ or len(name) < 2 or score < _MIN_SCORE or _is_junk(name):
                    continue
                key = f"{typ}:{normalize(name)}"
                if key not in seen or score > seen[key].score:
                    seen[key] = Entity(text=name, type=typ, score=round(score, 3))
            out.append(list(seen.values()))
        return out
