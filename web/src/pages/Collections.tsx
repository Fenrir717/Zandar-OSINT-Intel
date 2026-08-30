import { useEffect, useState } from "react";
import { api, ApiError, type AdapterInfo, type Collection, type Run } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Field, IconButton, Modal, Pill, Tile } from "../components/ui";

type Tone = "ok" | "crit" | "warn" | "muted";

const STATUS_TONE: Record<string, Tone> = { done: "ok", failed: "crit", running: "warn", queued: "warn" };

function latestRun(runs: Run[]): Run | null {
  if (runs.length === 0) return null;
  return runs.reduce((a, b) => {
    const ta = a.started_at ? new Date(a.started_at).getTime() : 0;
    const tb = b.started_at ? new Date(b.started_at).getTime() : 0;
    return tb > ta ? b : a;
  });
}

export function Collections({ headerSlot }: { headerSlot: (node: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [rows, setRows] = useState<{ col: Collection; runs: Run[] }[]>([]);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); else setRows([]); }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try {
      const cols = await api.collections(selected);
      const out = await Promise.all(cols.map(async (col) => ({ col, runs: await api.runs(col.id) })));
      setRows(out);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  async function runCol(id: string) {
    setRunningId(id);
    try {
      await api.runCollection(id);
      // Beri jeda agar worker sempat menandai run "running", lalu segarkan.
      setTimeout(() => { load().finally(() => setRunningId(null)); }, 900);
    } catch {
      setRunningId(null);
    }
  }

  const latests = rows.map((r) => latestRun(r.runs));
  const running = latests.filter((r) => r && ["running", "queued"].includes(r.status)).length;
  const done = latests.filter((r) => r?.status === "done").length;
  const failed = latests.filter((r) => r?.status === "failed").length;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14 }}>
        <Button icon="plus" onClick={() => setShowNew(true)} disabled={!selected}>Koleksi Baru</Button>
        <IconButton icon="refresh" onClick={load} title="Segarkan" spinning={loading} />
      </div>

      {showNew && selected && (
        <NewCollectionModal
          investigationId={selected}
          onClose={() => setShowNew(false)}
          onCreated={() => { setShowNew(false); load(); }}
        />
      )}

      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Total job" value={rows.length || "–"} icon="collections" /></div>
        <div className="rise rise-2"><Tile label="Berjalan" value={running} icon="spark" tone={running ? "warn" : undefined} /></div>
        <div className="rise rise-3"><Tile label="Selesai" value={done} icon="reports" /></div>
        <div className="rise rise-4"><Tile label="Gagal" value={failed} icon="audit" tone={failed ? "crit" : undefined} /></div>
      </div>

      {loading ? (
        <Empty icon="collections">Memuat koleksi…</Empty>
      ) : rows.length === 0 ? (
        <Empty icon="collections">Belum ada koleksi untuk investigasi ini.</Empty>
      ) : (
        <Card className="rise" style={{ padding: 0, overflow: "hidden" }}>
          <div className="scroll-x">
            <table className="tbl">
              <thead>
                <tr><th>Query</th><th>Jadwal</th><th>Status</th><th>Item</th><th>Error</th><th style={{ textAlign: "right" }}>Aksi</th></tr>
              </thead>
              <tbody>
                {rows.map(({ col, runs }) => {
                  const lr = latestRun(runs);
                  const status = lr?.status;
                  const tone: Tone = status ? (STATUS_TONE[status] ?? "muted") : "muted";
                  const busy = runningId === col.id || status === "running" || status === "queued";
                  return (
                    <tr key={col.id}>
                      <td style={{ fontWeight: 600, maxWidth: 320 }}>{JSON.stringify(col.query).slice(0, 60)}…</td>
                      <td style={{ fontFamily: "var(--font-mono)", color: "var(--muted)" }}>{col.schedule_cron || "manual"}</td>
                      <td><Pill tone={tone} dot>{status || "belum jalan"}</Pill></td>
                      <td className="tnum">{lr ? lr.items_collected : "–"}</td>
                      <td style={{ color: "var(--crit)" }}>{lr?.error || ""}</td>
                      <td style={{ textAlign: "right" }}>
                        <IconButton icon="refresh" onClick={() => runCol(col.id)}
                          title={busy ? "Sedang berjalan…" : "Jalankan sekarang"} spinning={busy} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function NewCollectionModal({ investigationId, onClose, onCreated }: {
  investigationId: string; onClose: () => void; onCreated: () => void;
}) {
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [platform, setPlatform] = useState("");
  const [keywords, setKeywords] = useState("");
  const [cron, setCron] = useState("");
  const [advanced, setAdvanced] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    api.adapters()
      .then((a) => { if (alive) { setAdapters(a); if (a.length && !platform) setPlatform(a[0].platform); } })
      .catch(() => { /* dropdown boleh manual */ });
    return () => { alive = false; };
  }, []);

  const kwList = keywords.split(",").map((k) => k.trim()).filter(Boolean);
  const valid = platform.trim().length > 0;

  async function submit() {
    if (!valid || busy) return;
    setBusy(true); setErr("");
    let query: Record<string, unknown> = kwList.length ? { keywords: kwList } : {};
    if (advanced.trim()) {
      try {
        const extra = JSON.parse(advanced);
        if (extra && typeof extra === "object" && !Array.isArray(extra)) query = { ...query, ...extra };
        else throw new Error("bukan objek");
      } catch {
        setErr("JSON lanjutan tidak valid — harus objek, mis. {\"sites\": [\"...\"]}.");
        setBusy(false);
        return;
      }
    }
    try {
      await api.createCollection({
        investigation_id: investigationId,
        platform: platform.trim(),
        query,
        schedule_cron: cron.trim() || undefined,
      });
      onCreated();
    } catch (e) {
      setErr(e instanceof ApiError ? `Gagal membuat koleksi (HTTP ${e.status}).` : "Gagal membuat koleksi.");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Koleksi Baru"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Batal</Button>
          <Button icon="plus" onClick={submit} disabled={!valid || busy}>
            {busy ? "Menyimpan…" : "Buat"}
          </Button>
        </>
      }
    >
      <Field label="Platform / sumber" hint="Sumber data untuk job pengumpulan ini.">
        {adapters.length ? (
          <select className="select" value={platform} onChange={(e) => setPlatform(e.target.value)}>
            {adapters.map((a) => (
              <option key={a.platform} value={a.platform}>
                {a.platform}{a.requires_credentials ? " — perlu kredensial" : ""}
              </option>
            ))}
          </select>
        ) : (
          <input className="input" value={platform} onChange={(e) => setPlatform(e.target.value)}
            placeholder="mis. rss, forum, github" />
        )}
      </Field>
      <Field label="Kata kunci" hint="Pisahkan dengan koma. Kosongkan untuk mengambil semua.">
        <input className="input" value={keywords} autoFocus
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="mis. subsidi, BBM, kenaikan" />
      </Field>
      <Field label="Jadwal (cron)" hint="Opsional. Kosong = manual saja.">
        <input className="input" value={cron} onChange={(e) => setCron(e.target.value)}
          placeholder="mis. 0 */6 * * *" style={{ fontFamily: "var(--font-mono)" }} />
      </Field>
      <Field label="Parameter lanjutan (JSON)" hint="Opsional — digabung ke query, mis. {&quot;sites&quot;: [&quot;https://…&quot;]}.">
        <textarea className="input" value={advanced} rows={2}
          onChange={(e) => setAdvanced(e.target.value)}
          placeholder='{"max_items": 100}' style={{ resize: "vertical", fontFamily: "var(--font-mono)", fontSize: 12 }} />
      </Field>
      {err && <div style={{ fontSize: 12, color: "var(--crit)" }}>{err}</div>}
    </Modal>
  );
}
