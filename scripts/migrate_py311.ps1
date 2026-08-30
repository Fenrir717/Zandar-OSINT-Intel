# ============================================================================
# migrate_py311.ps1 - Migrasi OPSIONAL & NON-DESTRUKTIF ke Python 3.11 + torch CUDA
#
# Untuk memanfaatkan GPU (RTX 3050, 4GB VRAM) pada jalur ML (IndoBertClassifier /
# LocalEmbedder). `.venv` yang sudah ada (Python 3.14, CPU-only) TIDAK PERNAH
# disentuh, diubah, atau dihapus oleh skrip ini - worker/beat/uvicorn yang sedang
# jalan dari `.venv` tetap aman. Skrip ini hanya membuat `.venv311` BARU di
# sebelahnya. Rollback = cukup hapus `.venv311` (lihat docs/gpu-migration.md bagian Rollback).
#
# Idempoten: aman dijalankan berkali-kali (langkah yang sudah selesai dilewati).
#
# Pakai:
#   powershell -File scripts\migrate_py311.ps1
#
# Baca dulu: docs\gpu-migration.md
# ============================================================================

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Write-Step($msg) { Write-Host "`n$msg" -ForegroundColor Yellow }
function Write-Ok($msg) { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "  ! $msg" -ForegroundColor DarkYellow }

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Zandar OSINT - migrasi ke .venv311 (Python 3.11 + torch CUDA)" -ForegroundColor Cyan
Write-Host " NON-DESTRUKTIF: .venv yang ada TIDAK disentuh maupun dihapus." -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------- [1/6] cek py -3.11
Write-Step "[1/6] Mengecek Python 3.11 lewat 'py' launcher..."

# Catatan: sengaja TIDAK memakai `2>&1` pada perintah native di sini -- di
# PowerShell 5.1 itu membungkus stderr jadi ErrorRecord dan bisa memicu $?=False
# palsu meski exit code sukses. `python --version` menulis ke stdout, jadi cukup
# tangkap stdout & cek $LASTEXITCODE langsung setelah pemanggilan.
$py311Version = $null
$py311Found = $false
try {
    $py311Output = & py -3.11 --version
    if ($LASTEXITCODE -eq 0) {
        $py311Version = ($py311Output | Out-String).Trim()
        $py311Found = $true
    }
} catch {
    $py311Found = $false
}

if (-not $py311Found) {
    Write-Host ""
    Write-Host "  Python 3.11 TIDAK ditemukan lewat 'py -3.11'." -ForegroundColor Red
    Write-Host "  Skrip ini SENGAJA TIDAK memasang Python secara otomatis." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Pasang salah satu, lalu jalankan ulang skrip ini:" -ForegroundColor White
    Write-Host "    winget install Python.Python.3.11" -ForegroundColor White
    Write-Host "    atau unduh manual: https://www.python.org/downloads/release/python-3119/" -ForegroundColor White
    Write-Host "    (centang 'Add python.exe to PATH' saat instalasi)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Verifikasi setelah pasang:  py -3.11 --version" -ForegroundColor White
    Write-Host ""
    Write-Host "  Catatan: belum menjalankan skrip ini tidak mengubah apa pun - " -ForegroundColor Gray
    Write-Host "  .venv (CPU) yang ada tetap jalan normal." -ForegroundColor Gray
    exit 1
}
Write-Ok "$py311Version ditemukan"

# ---------------------------------------------------------------- [2/6] cek .venv lama aman
Write-Step "[2/6] Memastikan .venv lama tidak akan disentuh..."
if (Test-Path ".venv") {
    Write-Ok ".venv (CPU, Python 3.14) terdeteksi dan akan DIBIARKAN APA ADANYA."
} else {
    Write-Warn2 ".venv tidak ditemukan di sini - tidak masalah, skrip ini tetap hanya membuat .venv311."
}

# ---------------------------------------------------------------- [3/6] buat .venv311
Write-Step "[3/6] Membuat .venv311..."
if (Test-Path ".venv311") {
    Write-Ok ".venv311 sudah ada - dilewati (idempoten). Lanjut ke instalasi paket."
} else {
    & py -3.11 -m venv .venv311
    if ($LASTEXITCODE -ne 0) { throw "Gagal membuat .venv311 (exit $LASTEXITCODE)." }
    Write-Ok ".venv311 dibuat."
}

$py311 = ".\.venv311\Scripts\python.exe"
if (-not (Test-Path $py311)) { throw "Tidak ditemukan $py311 - pembuatan venv sepertinya gagal." }

# ---------------------------------------------------------------- [4/6] install proyek + ml extra
Write-Step "[4/6] Memasang dependensi (pip, proyek + extra [ml])..."
Write-Host "  > $py311 -m pip install -U pip"
& $py311 -m pip install -U pip
if ($LASTEXITCODE -ne 0) { throw "Gagal upgrade pip (exit $LASTEXITCODE)." }

Write-Host "  > $py311 -m pip install -e `".[ml]`""
& $py311 -m pip install -e ".[ml]"
if ($LASTEXITCODE -ne 0) { throw "Gagal install proyek + extra [ml] (exit $LASTEXITCODE)." }
Write-Ok "Proyek + torch (CPU default) + transformers terpasang."

# ---------------------------------------------------------------- [5/6] ganti torch -> build CUDA cu121
Write-Step "[5/6] Mengganti torch dengan build CUDA (cu121, cocok RTX 3050/Ampere)..."
Write-Host "  Ini TIDAK memengaruhi torch di .venv lama (venv lain, paket terpisah)." -ForegroundColor Gray

Write-Host "  > $py311 -m pip uninstall -y torch"
& $py311 -m pip uninstall -y torch
if ($LASTEXITCODE -ne 0) { Write-Warn2 "uninstall torch exit $LASTEXITCODE (lanjut - mungkin belum terpasang)." }

Write-Host "  > $py311 -m pip install torch --index-url https://download.pytorch.org/whl/cu121"
& $py311 -m pip install torch --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -ne 0) { throw "Gagal memasang torch CUDA (exit $LASTEXITCODE). Cek koneksi/proxy lalu ulangi." }
Write-Ok "torch build CUDA (cu121) terpasang."

# ---------------------------------------------------------------- [6/6] verifikasi
Write-Step "[6/6] Verifikasi GPU..."
$verifyScript = @"
import torch
print('torch      :', torch.__version__)
print('CUDA avail :', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU        :', torch.cuda.get_device_name(0))
    props = torch.cuda.get_device_properties(0)
    print(f'VRAM       : {props.total_memory / (1024**3):.1f} GB')
else:
    print('GPU        : (tidak terdeteksi -- cek driver NVIDIA / nvidia-smi)')
"@
$verifyFile = Join-Path $env:TEMP "zandar_verify_cuda.py"
Set-Content -Path $verifyFile -Value $verifyScript -Encoding utf8

& $py311 $verifyFile
$verifyExit = $LASTEXITCODE
Remove-Item $verifyFile -ErrorAction SilentlyContinue

if ($verifyExit -ne 0) {
    Write-Warn2 "Skrip verifikasi gagal jalan (exit $verifyExit) - cek pesan error di atas."
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Selesai." -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  .venv (Python 3.14, CPU) TIDAK berubah - masih bisa dipakai kapan saja." -ForegroundColor White
Write-Host "  .venv311 (Python 3.11, GPU) siap dipakai secara PARALEL." -ForegroundColor White
Write-Host ""
Write-Host "  Langkah lanjut:" -ForegroundColor White
Write-Host "    1. Set di .env:  CLASSIFIER_PROVIDER=indobert  dan  EMBED_PROVIDER=local" -ForegroundColor White
Write-Host "       (default proyek 'lexicon'/'stub' tidak memuat torch sama sekali)" -ForegroundColor White
Write-Host "    2. Bandingkan kecepatan:" -ForegroundColor White
Write-Host "         .\.venv\Scripts\python.exe    scripts\bench_device.py   (baseline CPU)" -ForegroundColor White
Write-Host "         .\.venv311\Scripts\python.exe  scripts\bench_device.py   (GPU)" -ForegroundColor White
Write-Host "    3. Jalankan servis dari .venv311, mis.:" -ForegroundColor White
Write-Host "         .\.venv311\Scripts\python.exe -m uvicorn api.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "  Detail lengkap & cara mengarahkan worker/beat: docs\gpu-migration.md" -ForegroundColor White
Write-Host "  Rollback: cukup hapus .venv311 (JANGAN pernah hapus .venv)." -ForegroundColor White
Write-Host ""
