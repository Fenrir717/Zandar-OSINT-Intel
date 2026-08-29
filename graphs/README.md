# graphs/ — Orkestrasi LangGraph (Fase 2+)

Empat graph sesuai PRD §7 & §10.4. Dependensi `langgraph` sengaja belum
ditambahkan di Fase 0 — masuk bersama implementasi Graph A.

| Graph | Nama      | Fase | Isi |
|-------|-----------|------|-----|
| A     | Planner   | 2    | parse_intent → expand_keywords → select_sources → estimate_cost → `interrupt()` human_approval → dispatch |
| C     | Analysis  | 2    | cluster (HDBSCAN, kode) → label_narrative (map, Tier F) → cross_reference → risk_scoring (Tier R) → write_back |
| D     | Report    | 4    | outline → write_section (map, RAG) → verify_citations → assemble |
| E     | Veracity  | 5    | detect_checkworthy → normalize_claim → retrieve_evidence → score_sources → verdict |

Aturan untuk setiap node ber-LLM (PRD §9.2): structured output tervalidasi,
temperature 0, golden test berbasis fixture, trace Langfuse, cek budget
(`agent_runs.cost_usd` vs `investigations.budget_cap_usd`) sebelum memanggil model.
Checkpointer: `PostgresSaver`. Model dipanggil via tier abstrak (R/F/L, PRD §7.4),
dan `data_policy=local_only` memaksa Tier L.
