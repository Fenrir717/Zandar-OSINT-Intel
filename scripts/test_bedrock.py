"""Uji koneksi Amazon Bedrock (Converse API + bearer token).

Isi di .env:  AWS_BEARER_TOKEN_BEDROCK, AWS_REGION, BEDROCK_MODEL_R, BEDROCK_MODEL_F
Lalu jalankan:
    .venv/Scripts/python.exe scripts/test_bedrock.py

Uji ini TIDAK butuh LLM_PROVIDER=bedrock — ia memanggil BedrockProvider langsung.
"""

from core.config import get_settings
from graphs.llm import BedrockProvider

_SYS = 'Anda asisten uji. Balas HANYA JSON {"ok": true, "pesan": "<jawaban singkat>"}.'
_USER = "Apa ibukota Indonesia? Jawab di field pesan."


def main() -> None:
    s = get_settings()
    tok = s.aws_bearer_token_bedrock
    print("== Konfigurasi Bedrock ==")
    print("  AWS_REGION       :", s.aws_region or "(kosong)")
    print("  token terisi     :", bool(tok), f"(panjang {len(tok)})" if tok else "")
    print("  BEDROCK_MODEL_R  :", s.bedrock_model_r or "(kosong)")
    print("  BEDROCK_MODEL_F  :", s.bedrock_model_f or "(kosong)")

    if not tok or not (s.bedrock_model_r and s.bedrock_model_f):
        print("\n>> Lengkapi AWS_BEARER_TOKEN_BEDROCK + BEDROCK_MODEL_R/F di .env dulu, "
              "lalu jalankan lagi.")
        return

    p = BedrockProvider()
    print("\n== Panggilan uji per tier ==")
    for tier in ("F", "R"):
        try:
            r = p.call_json(tier, _SYS, _USER, hint={"node": "test"})
            print(f"  [{tier}] OK  tokens in={r.tokens_in} out={r.tokens_out}  data={r.data}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{tier}] GAGAL: {e}")
    print("\nBila kedua tier OK: ubah LLM_PROVIDER=bedrock di .env, lalu restart API + worker.")


if __name__ == "__main__":
    main()
