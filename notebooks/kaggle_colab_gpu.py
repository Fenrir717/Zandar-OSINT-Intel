# %% [markdown]
# # Zandar OSINT — Klasifikasi & Embedding di GPU Cloud Gratis (Kaggle / Colab)
#
# Skrip **self-contained** (tak butuh repo proyek ini di-clone) untuk menjalankan
# klasifikasi (sentimen/emosi/toksisitas) + embedding lokal proyek Zandar OSINT di GPU
# gratis (biasanya **T4, 16GB VRAM** — jauh lebih lega dari RTX 3050 4GB lokal).
#
# Berguna untuk backfill/job berat sekali-jalan **tanpa** migrasi GPU lokal (lihat
# `docs/gpu-migration.md` §10). Format file ini adalah "percent format" (`# %%`) —
# bisa dibuka langsung sebagai notebook via `jupytext`, atau **disalin cell-per-cell**
# ke sel baru di Kaggle Notebook / Google Colab.
#
# **PENTING**: file ini memuat sintaks khusus Jupyter (`!pip install ...`). JANGAN
# dijalankan langsung dengan `python notebooks/kaggle_colab_gpu.py` — buka sebagai
# notebook (Kaggle/Colab/Jupyter) dulu.
#
# ## Langkah cepat
# 1. **Aktifkan GPU**:
#    - **Kaggle**: panel kanan notebook → *Settings* → *Accelerator* → pilih **GPU T4 x1**
#      (bukan x2, kuota lebih hemat). Di *Settings* → *Internet* → nyalakan **On**
#      (dibutuhkan untuk mengunduh model dari Hugging Face Hub).
#    - **Colab**: menu *Runtime* → *Change runtime type* → *Hardware accelerator* →
#      **T4 GPU** → *Save*.
# 2. **Upload CSV komentar** kamu — wajib punya kolom `content` (lihat §4 di bawah).
# 3. Jalankan sel-sel berurutan dari atas ke bawah.
# 4. **Unduh hasil** — instruksi otomatis muncul di sel terakhir tiap bagian.
#
# Catatan kuota: Kaggle GPU gratis ±30 jam/minggu, sesi maks ±9 jam. Colab gratis
# sesi ±12 jam, ketersediaan GPU tidak dijamin di jam sibuk. Kedua environment
# **ephemeral** — paket yang di-`pip install` hilang tiap sesi baru, jalankan ulang
# sel instalasi tiap kali buka notebook baru.

# %% [markdown]
# ## 1. Cek device & instal dependensi tambahan
#
# `torch` **sudah terpasang bawaan** di image GPU Kaggle/Colab dengan CUDA aktif —
# JANGAN `pip install torch` ulang di sini (berisiko menimpa build CUDA yang sudah
# cocok dengan driver mereka). Kita hanya perlu `transformers` + `sentencepiece`
# (tokenizer beberapa model butuh sentencepiece).

# %%
import torch

print("torch      :", torch.__version__)
print("CUDA avail :", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU        :", torch.cuda.get_device_name(0))
else:
    print("!! GPU TIDAK terdeteksi. Aktifkan dulu sesuai instruksi di §0 sebelum lanjut.")
    print("   (skrip tetap bisa jalan di CPU, tapi jauh lebih lambat — bukan tujuan notebook ini)")

# %%
!pip install -q transformers sentencepiece

# %% [markdown]
# ## 2. Nama model — HARDCODE (notebook ini terpisah dari repo, tidak bisa baca
# `core/config.py`). Nama berikut disalin persis dari default proyek Zandar OSINT
# (`core/config.py`: `indobert_sentiment_model`, `indobert_emotion_model`,
# `indobert_hatespeech_model`, `embed_model`).

# %%
MODEL_SENTIMENT = "w11wo/indonesian-roberta-base-sentiment-classifier"
MODEL_EMOTION = "StevenLimcorn/indonesian-roberta-base-emotion-classifier"
MODEL_TOXICITY = "Hate-speech-CNERG/dehatebert-mono-indonesian"
MODEL_EMBEDDING = "intfloat/multilingual-e5-small"

# %% [markdown]
# ## 3. Muat model di GPU (fp16, batched)
#
# Sama seperti `workers/classify/indobert.py` & `workers/embed/local.py` di proyek:
# fp16 di GPU (lebih hemat VRAM & lebih cepat), fp32 di CPU (fallback). Batch default
# di sini **64** (naik dari 32 yang dipakai lokal di RTX 3050 4GB) karena T4 16GB
# punya jauh lebih banyak VRAM longgar — boleh dinaikkan lagi kalau tidak OOM.

# %%
from transformers import AutoModel, AutoTokenizer, pipeline

DEVICE = 0 if torch.cuda.is_available() else -1  # convensi pipeline(): 0=GPU pertama, -1=CPU
DEVICE_STR = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32
BATCH_SIZE = 64


def make_pipeline(task: str, model_id: str, **kw):
    """Coba `dtype=` (nama kwarg baru di transformers), fallback `torch_dtype=`
    (nama lama) — versi transformers pre-installed di Kaggle/Colab berbeda-beda."""
    for kwarg_name in ("dtype", "torch_dtype", None):
        try:
            extra = {kwarg_name: DTYPE} if kwarg_name else {}
            return pipeline(task, model=model_id, device=DEVICE, truncation=True, **extra, **kw)
        except TypeError:
            continue
    raise RuntimeError(f"Gagal memuat pipeline untuk {model_id}")


print("Memuat model sentimen...")
clf_sentiment = make_pipeline("text-classification", MODEL_SENTIMENT)
print("Memuat model emosi...")
clf_emotion = make_pipeline("text-classification", MODEL_EMOTION)
print("Memuat model toksisitas...")
clf_toxicity = make_pipeline("text-classification", MODEL_TOXICITY, top_k=None)  # semua skor

print("Memuat model embedding...")
embed_tokenizer = AutoTokenizer.from_pretrained(MODEL_EMBEDDING)
embed_model = AutoModel.from_pretrained(MODEL_EMBEDDING).to(DEVICE_STR)
if torch.cuda.is_available():
    embed_model = embed_model.half()  # fp16 — .half() aman lintas versi transformers
embed_model.eval()
print("Semua model dimuat.")

# %% [markdown]
# ## 4. Upload data komentar
#
# CSV kamu **wajib** punya kolom `content` (teks komentar) — nama kolom lain bebas
# dan akan disalin apa adanya ke file hasil.
#
# - **Colab**: sel di bawah membuka dialog upload file langsung dari browser.
# - **Kaggle**: upload lewat panel kanan *"+ Add Data"* → *Upload* → pilih CSV kamu
#   → SEBELUM lanjut, ganti `INPUT_CSV` di bawah sesuai path yang muncul (biasanya
#   `/kaggle/input/<nama-dataset>/<nama-file>.csv`).

# %%
import sys

IN_COLAB = "google.colab" in sys.modules

if IN_COLAB:
    from google.colab import files

    print("Upload file CSV komentar kamu (wajib ada kolom 'content')...")
    uploaded = files.upload()
    INPUT_CSV = next(iter(uploaded.keys()))
else:
    # --- KAGGLE: GANTI path ini sesuai dataset yang kamu upload lewat "+ Add Data" ---
    INPUT_CSV = "/kaggle/input/NAMA-DATASET-KAMU/komentar.csv"  # <-- EDIT BARIS INI
    print(f"Kaggle terdeteksi. Pastikan path berikut sesuai dataset yang di-upload:\n  {INPUT_CSV}")

# %% [markdown]
# ## 5. Jalankan klasifikasi (batched, GPU)
#
# Mapping label & fungsi `hate_score` di bawah disalin persis dari
# `workers/classify/indobert.py` proyek Zandar OSINT, supaya output notebook ini
# **konsisten** dengan output classifier lokal (skala skor, nama label internal, dst).

# %%
import pandas as pd

df = pd.read_csv(INPUT_CSV)
assert "content" in df.columns, "CSV harus punya kolom 'content'"
texts = df["content"].astype(str).tolist()
print(f"{len(texts)} baris dimuat dari {INPUT_CSV}")

# label internal Zandar (lihat workers/classify/base.py: SENTIMENTS/EMOTIONS)
_SENT_MAP = {
    "positive": ("pos", 0.7), "negative": ("neg", -0.7), "neutral": ("neu", 0.0),
    "LABEL_0": ("neg", -0.7), "LABEL_1": ("neu", 0.0), "LABEL_2": ("pos", 0.7),
}
_EMO_MAP = {
    "anger": "anger", "fear": "fear", "happy": "joy", "love": "trust", "sadness": "sadness",
    "joy": "joy", "sad": "sadness", "trust": "trust", "surprise": "surprise", "disgust": "disgust",
}


def hate_score(scores) -> float:
    """dehatebert: cari probabilitas label 'hate' dari daftar skor top_k=None."""
    if isinstance(scores, dict):
        scores = [scores]
    for s in scores:
        lbl = str(s.get("label", "")).lower()
        if ("hate" in lbl and "non" not in lbl) or lbl in ("label_1", "abusive", "toxic"):
            return round(float(s.get("score", 0.0)), 3)
    return 0.0


import time

t0 = time.time()
print("Menjalankan klasifikasi sentimen...")
sent_out = clf_sentiment(texts, batch_size=BATCH_SIZE)
print("Menjalankan klasifikasi emosi...")
emo_out = clf_emotion(texts, batch_size=BATCH_SIZE)
print("Menjalankan klasifikasi toksisitas...")
tox_out = clf_toxicity(texts, batch_size=BATCH_SIZE)
dt = time.time() - t0

sentiments, sentiment_scores, emotions, toxicities = [], [], [], []
for i in range(len(texts)):
    s_lbl, s_score = _SENT_MAP.get(sent_out[i]["label"], ("neu", 0.0))
    sentiments.append(s_lbl)
    sentiment_scores.append(round(s_score * float(sent_out[i].get("score", 0.5)), 3))
    emotions.append(_EMO_MAP.get(emo_out[i]["label"].lower(), "neutral"))
    toxicities.append(hate_score(tox_out[i]))

df["sentiment"] = sentiments
df["sentiment_score"] = sentiment_scores
df["emotion"] = emotions
df["toxicity"] = toxicities

rate = len(texts) / dt if dt > 0 else 0.0
print(f"Klasifikasi selesai: {len(texts)} baris dalam {dt:.1f}s ({rate:.1f} dok/dtk)")

# %% [markdown]
# ## 6. Embedding (opsional — simpan vektor untuk Qdrant)
#
# Set `SAVE_VECTORS = False` kalau cuma butuh label klasifikasi (file hasil jauh lebih
# kecil tanpa kolom vektor 384-dim per baris).

# %%
import torch.nn.functional as F

SAVE_VECTORS = True


def embed_texts(texts: list[str], kind: str = "passage", batch_size: int = BATCH_SIZE) -> list[list[float]]:
    prefix = "query: " if kind == "query" else "passage: "  # e5 asimetris (sama seperti lokal)
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [prefix + t for t in texts[i : i + batch_size]]
        enc = embed_tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt").to(DEVICE_STR)
        with torch.no_grad():
            hidden = embed_model(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)  # mean-pool
        pooled = F.normalize(pooled, p=2, dim=1)  # L2 (cosine-ready) — sama seperti lokal
        out.extend(pooled.float().cpu().tolist())
    return out


t0 = time.time()
print("Menjalankan embedding...")
vectors = embed_texts(texts)
dt = time.time() - t0
rate = len(texts) / dt if dt > 0 else 0.0
print(f"Embedding selesai: dimensi={len(vectors[0])}, {dt:.1f}s ({rate:.1f} dok/dtk)")

if SAVE_VECTORS:
    df["embedding"] = [str(v) for v in vectors]  # disimpan sbg string repr list agar aman di CSV

# %% [markdown]
# ## 7. Simpan & unduh hasil

# %%
OUTPUT_CSV = "hasil_klasifikasi_embedding.csv"
df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
print(f"Tersimpan: {OUTPUT_CSV} ({len(df)} baris)")

if IN_COLAB:
    from google.colab import files

    files.download(OUTPUT_CSV)
else:
    print(f"Kaggle: file ada di /kaggle/working/{OUTPUT_CSV}")
    print("Unduh lewat panel 'Output' di sisi kanan notebook Kaggle (tombol unduh per-file).")

# %% [markdown]
# ---
# ## 8. BONUS (opsional, TERPISAH) — kerangka fine-tuning IndoBERT sentimen
#
# Contoh fine-tuning model sentimen di gold set **NusaX-Senti** (Bahasa Indonesia,
# sumber sama dengan `workers/classify/eval.py::load_nusax` di proyek — GitHub raw,
# tanpa perlu paket `datasets` HF Hub). **Bukan bagian wajib alur klasifikasi di
# atas** — jalankan sel ini hanya kalau kamu mau bereksperimen menyempurnakan model.
#
# Setelah selesai, unduh folder model hasil fine-tune (§9), lalu pakai lokal dengan
# mengubah `INDOBERT_SENTIMENT_MODEL` di `.env` proyek Zandar ke path lokal model itu
# (atau upload ke Hugging Face Hub sebagai repo privat lalu isi nama repo-nya).

# %%
!pip install -q accelerate datasets

# %%
import csv
import io

import requests
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

NUSAX_RAW = "https://raw.githubusercontent.com/IndoNLP/nusax/main/datasets/sentiment/indonesian"
_LABEL2ID = {"negative": 0, "neutral": 1, "positive": 2}
_ID2LABEL = {0: "neg", 1: "neu", 2: "pos"}


def load_nusax_split(split: str) -> Dataset:
    resp = requests.get(f"{NUSAX_RAW}/{split}.csv", timeout=60)
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    texts = [r["text"] for r in rows]
    labels = [_LABEL2ID[r["label"].strip().lower()] for r in rows]
    return Dataset.from_dict({"text": texts, "label": labels})


train_ds = load_nusax_split("train")
val_ds = load_nusax_split("valid")
print(f"NusaX-Senti ID: train={len(train_ds)} valid={len(val_ds)}")

base_model = MODEL_SENTIMENT  # lanjutkan fine-tune dari model yang sudah kita pakai produksi
ft_tokenizer = AutoTokenizer.from_pretrained(base_model)
ft_model = AutoModelForSequenceClassification.from_pretrained(
    base_model, num_labels=3, id2label=_ID2LABEL, label2id=_LABEL2ID, ignore_mismatched_sizes=True
)


def tokenize(batch):
    return ft_tokenizer(batch["text"], truncation=True, max_length=256)


train_ds = train_ds.map(tokenize, batched=True)
val_ds = val_ds.map(tokenize, batched=True)
collator = DataCollatorWithPadding(tokenizer=ft_tokenizer)

training_args = TrainingArguments(
    output_dir="./finetuned-sentiment",
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    num_train_epochs=3,
    learning_rate=2e-5,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    fp16=torch.cuda.is_available(),
    report_to=[],
)

trainer = Trainer(
    model=ft_model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    data_collator=collator,
    processing_class=ft_tokenizer,
)
trainer.train()

trainer.save_model("./finetuned-sentiment/final")
ft_tokenizer.save_pretrained("./finetuned-sentiment/final")
print("Model fine-tuned tersimpan di ./finetuned-sentiment/final")

# %% [markdown]
# ## 9. Unduh model hasil fine-tuning (hanya kalau §8 dijalankan)

# %%
import shutil

shutil.make_archive("finetuned-sentiment", "zip", "./finetuned-sentiment/final")

if IN_COLAB:
    from google.colab import files

    files.download("finetuned-sentiment.zip")
else:
    print("Kaggle: unduh finetuned-sentiment.zip lewat panel 'Output' di kanan notebook.")
