"""Adapter X via VENDOR (shadow API) — jalur murah untuk X tanpa API resmi mahal.

X API resmi kini pay-per-use (~$0.005/post; lihat x_twitter.py) atau tier lama
$200-5000/bln. Vendor komunitas (mis. TwitterAPI.io) menjual tweet ~$0.15-0.40/1k,
menanggung scraping/ToS di sisi mereka; kita konsumsi JSON bersih.

Data dilabeli platform="x" (sama seperti adapter resmi), tapi registry key "x_vendor"
agar Source bisa memilih jalur ini. TIDAK memakai akun tumbal/rotasi IP kita sendiri —
vendor yang menanggung; kita hanya klien API berbayar.
"""

from workers.adapters.vendor_base import VendorAdapter


class XVendorAdapter(VendorAdapter):
    platform = "x"
    key = "x_vendor"
    rate_note = "Mengikuti kuota kontrak vendor."
    cost_note = "~$0.15-0.40 per 1.000 tweet (vendor komunitas), jauh di bawah API resmi X."
    legal_note = (
        "Vendor menanggung pengumpulan; pilih penyedia yang patuh GDPR/UU PDP dan hanya "
        "data publik. Kita tidak menjalankan akun tumbal / rotasi IP sendiri."
    )
