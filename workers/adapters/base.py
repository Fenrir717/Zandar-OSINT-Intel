"""Kontrak adapter koleksi (PRD §5): setiap sumber adalah plugin dengan
antarmuka seragam, sehingga menambah platform tidak menyentuh pipeline hilir.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    """Satu item mentah dari sumber — disimpan utuh ke raw lake sebelum diproses."""

    platform: str
    external_id: str
    author: str  # identitas mentah — di-pseudonim-kan (HMAC) saat enrichment, bukan di sini
    content: str
    url: str | None = None
    published_at: datetime | None = None
    raw: dict = field(default_factory=dict)  # payload asli utuh untuk raw lake


class BaseAdapter(ABC):
    """Adapter bersifat sync (dijalankan worker Celery) dan wajib:
    - menghormati rate limit sumbernya sendiri,
    - tidak melempar untuk item individual yang rusak (lewati + lanjut),
    - mengembalikan external_id yang stabil (kunci idempotensi hilir).
    """

    platform: str

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def collect(self, query: dict) -> Iterator[RawItem]:
        """Ambil item untuk `query` (bentuk query didefinisikan per adapter)."""
        raise NotImplementedError
