import { useEffect, useState } from "react";
import { api, type Collection, type Run } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Card, Empty, IconButton, Pill, Tile } from "../components/ui";

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

  const latests = rows.map((r) => latestRun(r.runs));
  const running = latests.filter((r) => r && ["running", "queued"].includes(r.status)).length;
  const done = latests.filter((r) => r?.status === "done").length;
  const failed = latests.filter((r) => r?.status === "failed").length;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
        <IconButton icon="refresh" onClick={load} title="Segarkan" spinning={loading} />
      </div>

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
                <tr><th>Query</th><th>Jadwal</th><th>Status</th><th>Item</th><th>Error</th></tr>
              </thead>
              <tbody>
                {rows.map(({ col, runs }) => {
                  const lr = latestRun(runs);
                  const status = lr?.status;
                  const tone: Tone = status ? (STATUS_TONE[status] ?? "muted") : "muted";
                  return (
                    <tr key={col.id}>
                      <td style={{ fontWeight: 600, maxWidth: 320 }}>{JSON.stringify(col.query).slice(0, 60)}…</td>
                      <td style={{ fontFamily: "var(--font-mono)", color: "var(--muted)" }}>{col.schedule_cron || "manual"}</td>
                      <td><Pill tone={tone} dot>{status || "belum jalan"}</Pill></td>
                      <td className="tnum">{lr ? lr.items_collected : "–"}</td>
                      <td style={{ color: "var(--crit)" }}>{lr?.error || ""}</td>
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
