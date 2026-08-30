"""Katalog kategori bisnis → selector OSM (kompetitor + pendorong permintaan).

GENERAL: tambah kategori baru = tambah entri di sini, engine tak berubah. Tiap
selector berformat "key=value" (dicocokkan persis ke tag OSM). Pendorong
permintaan diberi bobot relatif (proksi kekuatan tarik pelanggan untuk kategori itu).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Category:
    key: str
    label: str
    competitor: list[str]                     # selector OSM kompetitor
    demand: list[tuple[str, float, str]] = field(default_factory=list)  # (selector, bobot, label)
    note: str = ""


# Pendorong permintaan yang sering dipakai lintas kategori (bisa dirujuk ulang)
_EDU = [("amenity=university", 5.0, "kampus"), ("amenity=college", 4.0, "kampus")]
_RESID = [("building=apartments", 4.0, "apartemen"), ("building=dormitory", 5.0, "asrama/kos")]
_OFFICE = [("office=government", 3.0, "kantor"), ("building=office", 3.0, "kantor")]
_TRANSIT = [("public_transport=station", 2.5, "transit"), ("railway=station", 3.0, "stasiun")]

CATALOG: dict[str, Category] = {
    "laundry": Category(
        "laundry", "Laundry / cuci-setrika",
        competitor=["shop=laundry", "shop=dry_cleaning"],
        # Pendorong laundry = mahasiswa/kos & hunian padat. Sekolah SENGAJA tak dipakai
        # (anak sekolah bukan pelanggan laundry) agar ranking sub-zona tak bias.
        demand=_EDU + _RESID,
        note="Permintaan laundry didominasi mahasiswa/kos & hunian padat (bukan sekolah).",
    ),
    "cafe": Category(
        "cafe", "Kafe / coffee shop",
        competitor=["amenity=cafe", "shop=coffee"],
        demand=_EDU + _OFFICE + [("amenity=coworking_space", 3.0, "coworking")],
        note="Permintaan kafe ~ kantor, kampus, keramaian komersial.",
    ),
    "resto": Category(
        "resto", "Rumah makan / warung",
        competitor=["amenity=restaurant", "amenity=fast_food"],
        demand=_EDU + _OFFICE + _RESID,
    ),
    "minimarket": Category(
        "minimarket", "Minimarket / toko kelontong",
        competitor=["shop=convenience", "shop=supermarket"],
        demand=_RESID + [("amenity=school", 1.5, "sekolah")] + _EDU,
    ),
    "apotek": Category(
        "apotek", "Apotek",
        competitor=["amenity=pharmacy"],
        demand=[("amenity=clinic", 4.0, "klinik"), ("amenity=hospital", 5.0, "RS"),
                ("amenity=doctors", 3.0, "dokter")] + _RESID,
    ),
    "salon": Category(
        "salon", "Salon / barbershop",
        competitor=["shop=hairdresser", "shop=beauty"],
        demand=_EDU + _RESID,
    ),
    "bengkel": Category(
        "bengkel", "Bengkel kendaraan",
        competitor=["shop=car_repair", "shop=motorcycle_repair"],
        demand=[("amenity=fuel", 3.0, "SPBU")] + _RESID,
    ),
    "gym": Category(
        "gym", "Gym / fitness",
        competitor=["leisure=fitness_centre", "leisure=sports_centre"],
        demand=_OFFICE + _RESID + _EDU,
    ),
}


def get_category(key: str) -> Category:
    c = CATALOG.get(key)
    if c is None:
        raise KeyError(f"Kategori tak dikenal: {key!r}. Tersedia: {', '.join(CATALOG)}")
    return c
