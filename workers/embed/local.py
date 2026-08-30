"""Embedder lokal — multilingual-e5-small (118M, ~470MB, ramah 4GB & CPU).

Jalur enrich untuk investigasi data_policy=local_only (embedding tak keluar infra).
Jauh lebih ringan dari BGE-M3 (568M) tapi tetap multilingual (termasuk Indonesia).
Impor torch/transformers LAZY (extra [ml]). Mean-pooling last_hidden_state.
"""

from workers.embed.base import Embedder

_DEFAULT_MODEL = "intfloat/multilingual-e5-small"


class LocalEmbedder(Embedder):
    def __init__(self) -> None:
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError('EMBED_PROVIDER=local butuh torch+transformers: pip install -e ".[ml]"') from exc

        from core.config import get_settings

        self._torch = torch
        model_id = get_settings().embed_model or _DEFAULT_MODEL
        self._dev = "cuda" if torch.cuda.is_available() else "cpu"
        # cache-first agar tak hang cek-update HF saat jaringan flaky
        for local_only in (True, False):
            try:
                self._tok = AutoTokenizer.from_pretrained(model_id, local_files_only=local_only)
                self._model = AutoModel.from_pretrained(model_id, local_files_only=local_only).to(self._dev)
                break
            except Exception:
                if not local_only:
                    raise
        self._model.eval()
        self.dim = self._model.config.hidden_size
        self.version = f"local:{model_id.split('/')[-1]}[{self._dev}]"

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        if not texts:
            return []
        torch = self._torch
        prefix = "query: " if kind == "query" else "passage: "  # e5 asimetris
        out: list[list[float]] = []
        for i in range(0, len(texts), 32):  # batch 32
            batch = [prefix + t for t in texts[i : i + 32]]
            enc = self._tok(batch, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self._dev)
            with torch.no_grad():
                hidden = self._model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)  # mean-pool
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)  # L2 (cosine-ready)
            out.extend(pooled.cpu().tolist())
        return out
