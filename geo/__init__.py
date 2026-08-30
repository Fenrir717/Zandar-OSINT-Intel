"""Pilar Riset Pasar Geospasial (general-purpose).

Agen geospasial: pilih KATEGORI bisnis + LOKASI → peta kompetitor, jarak
antar-kompetitor, densitas, radius aman (estimasi), dan ranking sub-zona
efektivitas lokasi — dari data OpenStreetMap (gratis, tanpa key).

Kategori tak di-hardcode: lihat geo.catalog. Laundry hanyalah instance pertama.
Sumber gratis punya batas cakupan (usaha informal sering tak terpetakan) — hasil
kompetitor adalah BATAS BAWAH, disampaikan eksplisit di output.
"""
