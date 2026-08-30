import { useEffect, useMemo, useState } from "react";
import { api, ApiError, type Investigation } from "../lib/api";
import { Button, Card, Empty, Field, Modal, Pill, ProgressBar } from "../components/ui";
import { Icon } from "../components/icons";

type Tone = "accent" | "ok" | "warn" | "crit" | "muted" | "info" | "violet";

const STATUS_OPTIONS = ["planning", "collecting", "analyzing", "verifying", "done"] as const;
const STATUS_TONE: Record<string, Tone> = {
  planning: "muted", collecting: "info", analyzing: "warn", verifying: "violet", done: "ok",
};
const STATUS_LABEL: Record<string, string> = {
  planning: "Perencanaan", collecting: "Mengumpulkan", analyzing: "Menganalisis", verifying: "Verifikasi", done: "Selesai",
};
const PRIORITY_TONE: Record<string, Tone> = {
  low: "muted", medium: "info", high: "warn", critical: "crit",
};
const PRIORITY_LABEL: Record<string, string> = {
  low: "Rendah", medium: "Sedang", high: "Tinggi", critical: "Kritis",
};

export function Investigations({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const [list, setList] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [showNew, setShowNew] = useState(false);

  useEffect(() => { headerSlot(null); }, []);

  useEffect(() => {
    let alive = true;
    api.investigations()
      .then((inv) => { if (alive) setList(inv); })
      .catch(() => { if (alive) setList([]); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return list.filter((inv) => {
      if (status && inv.status !== status) return false;
      if (!term) return true;
      return inv.title.toLowerCase().includes(term) || (inv.description || "").toLowerCase().includes(term);
    });
  }, [list, q, status]);

  return (
    <div>
      <div className="rise" style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari judul atau deskripsi…"
          className="input" style={{ flex: 1, minWidth: 220 }} />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="select" style={{ width: "auto" }}>
          <option value="">Semua status</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <Button icon="plus" onClick={() => setShowNew(true)}>Investigasi Baru</Button>
      </div>

      {showNew && (
        <NewInvestigationModal
          onClose={() => setShowNew(false)}
          onCreated={(inv) => { setList((prev) => [inv, ...prev]); setShowNew(false); }}
        />
      )}

      {loading ? (
        <Empty icon="search">Memuat investigasi…</Empty>
      ) : filtered.length === 0 ? (
        <Empty icon="search">
          {list.length === 0 ? "Belum ada investigasi." : "Tidak ada investigasi yang cocok dengan pencarian atau filter."}
        </Empty>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
          {filtered.map((inv, i) => <InvestigationCard key={inv.id} inv={inv} delay={(i % 4) + 1} />)}
        </div>
      )}
    </div>
  );
}

function NewInvestigationModal({ onClose, onCreated }: {
  onClose: () => void; onCreated: (inv: Investigation) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [dataPolicy, setDataPolicy] = useState("local_only");
  const [budget, setBudget] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const valid = title.trim().length >= 3;

  async function submit() {
    if (!valid || busy) return;
    setBusy(true); setErr("");
    try {
      const inv = await api.createInvestigation({
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        data_policy: dataPolicy,
        budget_cap_usd: budget.trim() ? Number(budget) : undefined,
      });
      onCreated(inv);
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 422 ? "Periksa isian (judul minimal 3 karakter)." : "Gagal membuat investigasi.");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Investigasi Baru"
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
      <Field label="Judul">
        <input className="input" value={title} autoFocus maxLength={255}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(); }}
          placeholder="mis. Narasi subsidi BBM 2026" />
      </Field>
      <Field label="Deskripsi" hint="Opsional — konteks singkat, target, atau hipotesis.">
        <textarea className="input" value={description} rows={3}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Ringkas fokus investigasi…" style={{ resize: "vertical" }} />
      </Field>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Field label="Prioritas">
          <select className="select" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {(["low", "medium", "high", "critical"] as const).map((p) => (
              <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
            ))}
          </select>
        </Field>
        <Field label="Kebijakan data">
          <select className="select" value={dataPolicy} onChange={(e) => setDataPolicy(e.target.value)}>
            <option value="local_only">Data lokal saja</option>
            <option value="api_ok">API diizinkan</option>
          </select>
        </Field>
      </div>
      <Field label="Batas anggaran (USD)" hint="Opsional — kosongkan bila tanpa batas.">
        <input className="input" value={budget} inputMode="decimal"
          onChange={(e) => setBudget(e.target.value.replace(/[^0-9.]/g, ""))}
          placeholder="mis. 5" />
      </Field>
      {err && <div style={{ fontSize: 12, color: "var(--crit)" }}>{err}</div>}
    </Modal>
  );
}

function InvestigationCard({ inv, delay }: { inv: Investigation; delay: number }) {
  const created = new Date(inv.created_at).toLocaleDateString("id", { day: "2-digit", month: "short", year: "numeric" });
  const progress = Math.max(0, Math.min(100, Math.round(inv.progress)));
  return (
    <Card hover className={`rise rise-${delay}`} style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <div style={{
          fontSize: 15, fontWeight: 700, lineHeight: 1.35,
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>{inv.title}</div>
        <div style={{
          fontSize: 12.5, color: "var(--muted)", marginTop: 4, lineHeight: 1.5,
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>{inv.description || "Tidak ada deskripsi."}</div>
      </div>

      <div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)", marginBottom: 5 }}>
          <span>Progres</span>
          <span className="tnum" style={{ fontWeight: 700, color: "var(--ink)" }}>{progress}%</span>
        </div>
        <ProgressBar value={progress} tone={STATUS_TONE[inv.status]} />
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Pill tone={STATUS_TONE[inv.status] ?? "muted"} dot>{STATUS_LABEL[inv.status] ?? inv.status}</Pill>
        <Pill tone={PRIORITY_TONE[inv.priority] ?? "muted"}>{PRIORITY_LABEL[inv.priority] ?? inv.priority}</Pill>
        <Pill tone={inv.data_policy === "local_only" ? "accent" : "info"}>
          {inv.data_policy === "local_only" ? "Data lokal saja" : "API diizinkan"}
        </Pill>
      </div>

      {inv.budget_cap_usd != null && (
        <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
          Batas anggaran{" "}
          <span className="tnum" style={{ color: "var(--ink)", fontWeight: 600 }}>${inv.budget_cap_usd.toLocaleString("id")}</span>
        </div>
      )}

      <div style={{
        display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--faint)",
        marginTop: "auto", paddingTop: 10, borderTop: "1px solid var(--line-2)",
      }}>
        <Icon name="timeline" size={12} />{created}
      </div>
    </Card>
  );
}
