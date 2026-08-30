"""Prapemrosesan teks untuk klasifikasi (Tier 1 akurasi).

Aditif & konservatif: menormalkan sinyal INFORMAL khas medsos Indonesia sebelum
IndoBERT, tanpa merusak teks FORMAL (berita) — huruf besar/kecil dipertahankan,
hanya kata slang yang diganti ke baku, emoji jadi kata, dan perpanjangan huruf
(‘bagusss’) dirapikan. Teks asli TIDAK diubah (provenance) — ini hanya untuk
umpan ke model.
"""

import re

# Slang/singkatan Indonesia → baku. Fokus: negasi, intensitas, penghubung, dan
# kata beremosi (paling berpengaruh ke sentimen). Dicocokkan per-kata, case-insensitive.
SLANG: dict[str, str] = {
    "yg": "yang", "dgn": "dengan", "dg": "dengan", "utk": "untuk", "untk": "untuk",
    "tdk": "tidak", "gak": "tidak", "ga": "tidak", "ngga": "tidak", "nggak": "tidak",
    "gk": "tidak", "enggak": "tidak", "kagak": "tidak", "tak": "tidak", "gada": "tidak ada",
    "gpp": "tidak apa-apa", "gapapa": "tidak apa-apa", "gamau": "tidak mau",
    "gabisa": "tidak bisa", "gajelas": "tidak jelas", "gabakal": "tidak akan",
    "bgt": "sangat", "bngt": "sangat", "banget": "sangat", "banged": "sangat",
    "jg": "juga", "aja": "saja", "aj": "saja", "doang": "saja",
    "udah": "sudah", "udh": "sudah", "dah": "sudah", "sdh": "sudah", "blm": "belum",
    "belom": "belum", "bkn": "bukan", "krn": "karena", "karna": "karena", "krna": "karena",
    "klo": "kalau", "kalo": "kalau", "klu": "kalau", "gmn": "bagaimana", "gimana": "bagaimana",
    "knp": "kenapa", "sm": "sama", "dr": "dari", "dlm": "dalam",
    "org": "orang", "sy": "saya", "gw": "saya", "gue": "saya", "gua": "saya", "ane": "saya",
    "lu": "kamu", "lo": "kamu", "elu": "kamu", "kmu": "kamu", "loe": "kamu",
    "tp": "tetapi", "tpi": "tetapi", "tapi": "tetapi", "jd": "jadi", "jdi": "jadi",
    "bs": "bisa", "msh": "masih", "skrg": "sekarang", "skarang": "sekarang",
    "bener": "benar", "bnr": "benar", "emg": "memang", "emang": "memang",
    "cm": "hanya", "cuma": "hanya", "cuman": "hanya", "nih": "ini", "tuh": "itu",
    "dpt": "dapat", "hrs": "harus", "pdhl": "padahal", "thd": "terhadap",
    "kyk": "seperti", "kaya": "seperti", "kayak": "seperti", "spt": "seperti",
    "trs": "terus", "byk": "banyak", "dikit": "sedikit", "bbrp": "beberapa",
    "sgt": "sangat", "sngt": "sangat", "bwt": "buat", "pake": "pakai", "pk": "pakai",
    # kata beremosi / penilaian
    "mantul": "mantap", "mantab": "mantap", "kece": "keren", "gokil": "hebat",
    "kesel": "kesal", "sebel": "sebal", "capek": "lelah", "capai": "lelah",
    "males": "malas", "parah": "parah", "ribet": "rumit", "ampas": "buruk",
    "jelek": "buruk", "bagus": "bagus", "keren": "keren", "mahal": "mahal",
    "murah": "murah", "lemot": "lambat", "lelet": "lambat", "lola": "lambat",
    "anjir": "sialan", "anjay": "sialan", "anjg": "sialan", "bangsat": "bajingan",
    "php": "pemberi harapan palsu", "baper": "terbawa perasaan", "julid": "iri dengki",
    "gaje": "tidak jelas", "santuy": "santai", "woles": "santai", "mager": "malas",
}

# Emoji → kata sentimen Indonesia (agar tak hilang saat tokenisasi model).
EMOJI: dict[str, str] = {
    "😀": " senang ", "😃": " senang ", "😄": " senang ", "😁": " senang ",
    "😊": " senang ", "🙂": " senang ", "😉": " senang ", "😎": " keren ",
    "😂": " lucu ", "🤣": " lucu ", "😹": " lucu ",
    "❤️": " cinta ", "❤": " cinta ", "😍": " cinta ", "🥰": " cinta ", "😘": " cinta ", "💕": " cinta ",
    "👍": " bagus ", "👏": " bagus ", "🎉": " bagus ", "💯": " sempurna ", "🔥": " keren ", "⭐": " bagus ",
    "😭": " sedih ", "😢": " sedih ", "😞": " sedih ", "😔": " sedih ", "🥺": " sedih ", "😥": " sedih ",
    "😡": " marah ", "😠": " marah ", "🤬": " marah ", "💢": " marah ",
    "😱": " takut ", "😨": " takut ", "😰": " takut ", "😳": " malu ",
    "🤢": " jijik ", "🤮": " jijik ", "👎": " buruk ", "💔": " sedih ",
    "😐": " datar ", "😑": " datar ", "🤔": " bingung ", "😴": " bosan ", "🙏": " mohon ",
}

_WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
_ELONG_RE = re.compile(r"([A-Za-z])\1{2,}")   # 3+ huruf sama → 1 (‘bagusss’→‘bagus’)
_WS_RE = re.compile(r"\s+")


def _demojize(text: str) -> str:
    for emo, word in EMOJI.items():
        if emo in text:
            text = text.replace(emo, word)
    return text


def _deslang(text: str) -> str:
    def repl(m: re.Match) -> str:
        w = m.group(0)
        return SLANG.get(w.lower(), w)  # ganti hanya bila slang; case lain dipertahankan
    return _WORD_RE.sub(repl, text)


def preprocess_for_classify(text: str) -> str:
    """Normalkan teks informal untuk umpan model. Teks formal ~tak berubah."""
    if not text:
        return text
    text = _demojize(text)
    text = _ELONG_RE.sub(r"\1", text)
    text = _deslang(text)
    return _WS_RE.sub(" ", text).strip()
