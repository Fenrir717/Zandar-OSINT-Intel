"""Kontrak adapter koleksi (PRD §5): setiap sumber adalah plugin dengan
antarmuka seragam, sehingga menambah platform tidak menyentuh pipeline hilir.

Setiap adapter mendeklarasikan METADATA AKSES (tier, kredensial, biaya, catatan
legal). Metadata ini dipakai tiga tempat:
  - UI Collections/Sources — menandai sumber yang butuh kunci atau berbiaya,
  - Graph A `select_sources` — planner tidak boleh memilih sumber yang tidak siap,
  - `estimate_cost` — sumber metered wajib masuk estimasi biaya sebelum approval.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# free   : API resmi/terbuka, tanpa biaya per-item
# metered: resmi tapi dibayar per pemakaian → wajib guard biaya
# vendor : tidak ada akses resmi; hanya lewat penyedia data pihak ketiga berkontrak
AccessTier = Literal["free", "metered", "vendor"]


@dataclass
class RawItem:
    """Satu item mentah dari sumber — disimpan utuh ke raw lake sebelum diproses."""

    platform: str
    external_id: str
    author: str  # identitas mentah — di-pseudonim-kan (HMAC) saat enrichment, bukan di sini
    content: str
    url: str | None = None
    published_at: datetime | None = None
    title: str | None = None
    raw: dict = field(default_factory=dict)  # payload asli utuh untuk raw lake


class AdapterNotConfigured(RuntimeError):
    """Adapter dipanggil tanpa kredensial/konfigurasi yang diwajibkan."""


class CostGuardRejected(RuntimeError):
    """Sumber metered dipanggil tanpa konfirmasi biaya eksplisit."""


class BaseAdapter(ABC):
    """Adapter bersifat sync (dijalankan worker Celery) dan wajib:
    - menghormati rate limit sumbernya sendiri,
    - tidak melempar untuk item individual yang rusak (lewati + lanjut),
    - mengembalikan external_id yang stabil (kunci idempotensi hilir).
    """

    platform: str  # label data (provenance) pada Comment.platform
    # key = kunci registry (metode koleksi). Default = platform. Berbeda saat satu
    # platform punya beberapa metode: mis. x (API resmi) vs x_vendor (shadow API) vs
    # nitter — semuanya menghasilkan data platform="x" tapi lewat jalur berbeda.
    key: str = ""
    tier: AccessTier = "free"
    requires_credentials: bool = False
    # Field config wajib ada isinya sebelum collect() boleh jalan
    required_config: tuple[str, ...] = ()
    rate_note: str = ""
    cost_note: str = ""
    legal_note: str = ""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @classmethod
    def registry_key(cls) -> str:
        return cls.key or cls.platform

    @classmethod
    def describe(cls) -> dict:
        """Metadata untuk UI, planner, dan estimasi biaya."""
        return {
            "key": cls.registry_key(),
            "platform": cls.platform,
            "tier": cls.tier,
            "requires_credentials": cls.requires_credentials,
            "required_config": list(cls.required_config),
            "rate_note": cls.rate_note,
            "cost_note": cls.cost_note,
            "legal_note": cls.legal_note,
        }

    def require_config(self, *keys: str) -> None:
        missing = [k for k in keys if not self.config.get(k)]
        if missing:
            raise AdapterNotConfigured(
                f"Adapter '{self.platform}' butuh konfigurasi: {', '.join(missing)}. "
                "Isi di Sources.config (admin) atau variabel env terkait."
            )

    @abstractmethod
    def collect(self, query: dict) -> Iterator[RawItem]:
        """Ambil item untuk `query` (bentuk query didefinisikan per adapter)."""
        raise NotImplementedError
