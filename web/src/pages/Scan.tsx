// Scan — "agent Commander" satu klik: ketik topik → Graph A pilih sumber lintas
// adapter → tinjau cepat → koleksi + autonomous loop (classify→embed→narasi→graph).
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api, streamAgentEvents,
  type AgentEvent, type PlanData, type PlanSource, type Project,
} from "../lib/api";
import { Button, Card, Empty, Field, Pill, SectionTitle, Spinner } from "../components/ui";
import { Icon, type IconName } from "../components/icons";

type Step = "setup" | "review" | "running";
type Tone = "accent" | "ok" | "warn" | "crit" | "muted" | "info" | "violet";

// Tahap autonomous loop (setelah koleksi) — dipetakan dari node event 'scan'.
const PIPE_ORDER = ["collect", "classify", "embed", "narratives", "graph"] as const;
const STAGE_META: { key: string; label: string; icon: IconName; hint: string }[] = [
  { key: "collect", label: "Koleksi data", icon: "collections", hint: "menarik dari sumber terpilih" },
  { key: "classify", label: "Klasifikasi", icon: "analysis", hint: "sentimen · emosi · sarkasme" },
  { key: "embed", label: "Embedding", icon: "spark", hint: "vektor untuk klasterisasi" },
  { key: "narratives", label: "Narasi (Graph C)", icon: "target", hint: "kelompokkan & labeli narasi" },
  { key: "graph", label: "Knowledge graph", icon: "graph", hint: "entitas + sentimen per-target" },
];

function fmtQuery(q: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(q || {})) {
    if (v == null || (Array.isArray(v) && v.length === 0)) continue;
    const val = Array.isArray(v) ? v.join(", ") : String(v);
    parts.push(`${k}: ${val.length > 48 ? val.slice(0, 48) + "…" : val}`);
  }
  return parts.join(" · ") || "(default)";
}

export function Scan({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const nav = useNavigate();
  const [step, setStep] = useState<Step>("setup");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // setup
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [newProject, setNewProject] = useState("");
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [autoPipeline, setAutoPipeline] = useState(true);

  // hasil plan
  const [invId, setInvId] = useState("");
  const [runId, setRunId] = useState("");
  const [plan, setPlan] = useState<PlanData | null>(null);
  const [pick, setPick] = useState<boolean[]>([]);

  useEffect(() => { headerSlot(null); }, []);
  useEffect(() => {
    api.projects().then((p) => {
      setProjects(p);
      setProjectId(p[0]?.id || "__new__");
    }).catch(() => setProjectId("__new__"));
  }, []);

  async function runCommander() {
    const t = topic.trim();
    if (!t) { setError("Isi topik / kata kunci yang ingin discan."); return; }
    setBusy(true); setError("");
    try {
      let pid = projectId;
      if (projectId === "__new__") {
        const name = newProject.trim() || `Scan — ${t.slice(0, 40)}`;
        pid = (await api.createProject(name)).id;
      }
      const inv = await api.createInvestigation({
        title: title.trim() || t.slice(0, 60), description: t, project_id: pid,
      });
      localStorage.setItem("zandar_inv", inv.id); // jadikan investigasi aktif lintas halaman
      const res = await api.plan(inv.id, t);
      setInvId(inv.id);
      setRunId(res.agent_run_id);
      setPlan(res.plan);
      setPick((res.plan?.sources || []).map(() => true));
      setStep("review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Commander gagal menyusun rencana.");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!plan) return;
    setBusy(true); setError("");
    try {
      const edited: PlanSource[] = plan.sources.filter((_, i) => pick[i]);
      if (edited.length === 0) { setError("Pilih minimal satu sumber."); setBusy(false); return; }
      await api.approvePlan(runId, { edited_sources: edited, auto_pipeline: autoPipeline });
      setStep("running");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menyetujui rencana.");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    setBusy(true);
    try { await api.rejectPlan(runId); } catch { /* abaikan */ }
    setBusy(false);
    setStep("setup"); setPlan(null); setRunId("");
  }

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <ScanHero step={step} />
      {error && (
        <div style={{ padding: "10px 14px", borderRadius: "var(--radius-sm)", background: "var(--crit-soft)", border: "1px solid var(--crit)", color: "var(--crit-ink)", fontSize: 12.5, marginBottom: 14 }}>
          {error}
        </div>
      )}

      {step === "setup" && (
        <Card style={{ padding: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
            <Field label="Topik / kata kunci" hint="Commander akan memperluas ini (sinonim, slang, hashtag) lalu memilih sumber koleksi lintas adapter.">
              <textarea className="input" value={topic} onChange={(e) => setTopic(e.target.value)}
                placeholder="mis. subsidi BBM 2026 dampak ke masyarakat"
                rows={2} style={{ resize: "vertical", minHeight: 58, paddingTop: 9 }} autoFocus />
            </Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }} className="grid-2">
              <Field label="Project">
                <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)} style={{ height: 40 }}>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  <option value="__new__">+ Project baru…</option>
                </select>
              </Field>
              {projectId === "__new__" ? (
                <Field label="Nama project baru" hint="Kosongkan → dinamai dari topik.">
                  <input className="input" value={newProject} onChange={(e) => setNewProject(e.target.value)}
                    placeholder="mis. Riset Kebijakan Energi" style={{ height: 40 }} />
                </Field>
              ) : (
                <Field label="Judul investigasi" hint="Kosongkan → dari topik.">
                  <input className="input" value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="mis. Sentimen Subsidi BBM" style={{ height: 40 }} />
                </Field>
              )}
            </div>
            {projectId === "__new__" && (
              <Field label="Judul investigasi" hint="Kosongkan → dari topik.">
                <input className="input" value={title} onChange={(e) => setTitle(e.target.value)}
                  placeholder="mis. Sentimen Subsidi BBM" style={{ height: 40 }} />
              </Field>
            )}
            <label style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "11px 13px", border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", background: "var(--surface-2)", cursor: "pointer" }}>
              <input type="checkbox" checked={autoPipeline} onChange={(e) => setAutoPipeline(e.target.checked)} style={{ marginTop: 2 }} />
              <span style={{ fontSize: 12.5, lineHeight: 1.45 }}>
                <b>Autonomous loop</b> — setelah koleksi selesai, otomatis jalankan analisis penuh
                (klasifikasi → embedding → narasi → knowledge graph + sentimen). Matikan bila ingin koleksi saja.
              </span>
            </label>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button icon="target" onClick={runCommander} disabled={busy}>
                {busy ? "Commander menyusun…" : "Jalankan Commander"}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {step === "review" && plan && (
        <ReviewPlan plan={plan} pick={pick} setPick={setPick} busy={busy}
          autoPipeline={autoPipeline} onApprove={approve} onReject={reject} />
      )}

      {step === "running" && (
        <RunningView invId={invId} autoPipeline={autoPipeline}
          sourceCount={plan?.sources.filter((_, i) => pick[i]).length || 0}
          onOpen={(path) => nav(path)} />
      )}
    </div>
  );
}

function ScanHero({ step }: { step: Step }) {
  const label = step === "setup" ? "Susun scan" : step === "review" ? "Tinjau rencana Commander" : "Autonomous loop berjalan";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
      <span style={{ width: 46, height: 46, borderRadius: 13, background: "var(--accent-grad)", display: "grid", placeItems: "center", color: "#fff", boxShadow: "0 3px 12px var(--accent-ring)", flexShrink: 0 }}>
        <Icon name="target" size={24} stroke={2} />
      </span>
      <div style={{ minWidth: 0 }}>
        <h2 style={{ margin: 0, fontSize: 19, letterSpacing: "-.02em" }}>Scan Commander</h2>
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 2 }}>
          Satu kata kunci → agen memilih sumber, mengumpulkan, dan menganalisis otomatis · <b style={{ color: "var(--accent-ink)" }}>{label}</b>
        </div>
      </div>
    </div>
  );
}

function ReviewPlan({ plan, pick, setPick, busy, autoPipeline, onApprove, onReject }: {
  plan: PlanData; pick: boolean[]; setPick: (p: boolean[]) => void; busy: boolean;
  autoPipeline: boolean; onApprove: () => void; onReject: () => void;
}) {
  const intent = plan.intent || {};
  const chosen = pick.filter(Boolean).length;
  const topic = (intent.topic as string) || "";
  const region = (intent.region as string) || "";
  const period = intent.period_days as number | undefined;
  const actors = (intent.actors as string[]) || [];

  if (plan.sources.length === 0) {
    return <Empty icon="target">Commander tidak menemukan sumber yang cocok. Coba topik yang lebih spesifik atau tambahkan konteks (aktor, wilayah, periode).</Empty>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card style={{ padding: 18 }}>
        <SectionTitle right={<Pill tone="accent">{plan.keywords.length} kata kunci</Pill>}>Sasaran investigasi</SectionTitle>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px", fontSize: 12.5, color: "var(--muted)", marginBottom: 10 }}>
          {topic && <span><b style={{ color: "var(--ink)" }}>Topik:</b> {topic}</span>}
          {region && <span><b style={{ color: "var(--ink)" }}>Wilayah:</b> {region}</span>}
          {period != null && <span><b style={{ color: "var(--ink)" }}>Periode:</b> {period} hari</span>}
          {actors.length > 0 && <span><b style={{ color: "var(--ink)" }}>Aktor:</b> {actors.slice(0, 4).join(", ")}</span>}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {plan.keywords.slice(0, 24).map((k, i) => (
            <span key={i} style={{ fontSize: 11.5, padding: "3px 9px", borderRadius: 999, background: "var(--surface-2)", border: "1px solid var(--line)", color: "var(--ink)" }}>{k}</span>
          ))}
        </div>
      </Card>

      <Card style={{ padding: 18 }}>
        <SectionTitle right={<Pill tone={chosen ? "ok" : "warn"}>{chosen}/{plan.sources.length} dipilih</Pill>}>
          Sumber koleksi
        </SectionTitle>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {plan.sources.map((s, i) => (
            <label key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", background: pick[i] ? "var(--surface)" : "var(--surface-2)", opacity: pick[i] ? 1 : 0.6, cursor: "pointer" }}>
              <input type="checkbox" checked={pick[i]} onChange={(e) => { const n = [...pick]; n[i] = e.target.checked; setPick(n); }} />
              <span style={{ minWidth: 82 }}><Pill tone="info">{s.platform}</Pill></span>
              <span style={{ flex: 1, minWidth: 0, fontSize: 11.5, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{fmtQuery(s.query)}</span>
              {s.est_items != null && <span className="tnum" style={{ fontSize: 11.5, color: "var(--faint)" }}>~{s.est_items}</span>}
            </label>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: "var(--muted)", display: "flex", gap: 14, flexWrap: "wrap" }}>
          <span>Est. item: <b className="tnum" style={{ color: "var(--ink)" }}>{plan.cost.est_items}</b></span>
          <span>Est. biaya: <b className="tnum" style={{ color: plan.cost.within_budget ? "var(--ok-ink)" : "var(--crit-ink)" }}>${plan.cost.est_cost_usd.toFixed(2)}</b></span>
          <span>Setelah koleksi: <b style={{ color: "var(--ink)" }}>{autoPipeline ? "analisis penuh otomatis" : "berhenti (koleksi saja)"}</b></span>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <Button variant="ghost" icon="x" onClick={onReject} disabled={busy}>Tolak</Button>
        <Button icon="target" onClick={onApprove} disabled={busy || chosen === 0}>
          {busy ? "Mendispatch…" : `Setujui & Scan (${chosen})`}
        </Button>
      </div>
    </div>
  );
}

interface Progress { done: number; total: number; items: number; }

function RunningView({ invId, autoPipeline, sourceCount, onOpen }: {
  invId: string; autoPipeline: boolean; sourceCount: number; onOpen: (path: string) => void;
}) {
  const [node, setNode] = useState<string>("collect"); // node scan terakhir
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const [done, setDone] = useState(false);
  const [prog, setProg] = useState<Progress>({ done: 0, total: sourceCount, items: 0 });
  const [detail, setDetail] = useState("mengantre koleksi…");
  const scanStarted = useRef(false);

  // SSE — progres tahap autonomous loop (event 'scan' dari worker).
  useEffect(() => {
    const ac = new AbortController();
    streamAgentEvents((e: AgentEvent) => {
      if (e.investigation_id !== invId || e.graph !== "scan") return;
      scanStarted.current = true;
      if (e.node) setNode(e.node);
      if (e.detail) setDetail(e.detail);
      if (e.status === "failed" && e.node) setFailed((f) => new Set(f).add(e.node!));
      if (e.node === "done" && e.status === "done") setDone(true);
    }, ac.signal).catch(() => { /* stream putus — polling tetap jalan */ });
    return () => ac.abort();
  }, [invId]);

  // Polling koleksi — progres fase koleksi (collect_source tak memancarkan event).
  useEffect(() => {
    if (done) return;
    let stop = false;
    async function poll() {
      try {
        const cols = await api.collections(invId);
        const runsArr = await Promise.all(cols.map((c) => api.runs(c.id).catch(() => [])));
        let d = 0, items = 0;
        for (const rs of runsArr) {
          const last = rs[0];
          if (last && (last.status === "done" || last.status === "failed")) d++;
          for (const r of rs) items += r.items_collected || 0;
        }
        if (!stop) setProg({ done: d, total: cols.length || sourceCount, items });
      } catch { /* abaikan */ }
    }
    poll();
    const t = setInterval(poll, 3000);
    return () => { stop = true; clearInterval(t); };
  }, [invId, done, sourceCount]);

  const stages = autoPipeline ? STAGE_META : STAGE_META.slice(0, 1);
  const curIdx = done ? stages.length : PIPE_ORDER.indexOf(node as typeof PIPE_ORDER[number]);
  // fase koleksi dianggap selesai begitu tahap analisis pertama mulai (scan hanya jalan usai koleksi)
  const collectDone = scanStarted.current || (prog.total > 0 && prog.done >= prog.total);

  function stageState(key: string): "done" | "active" | "wait" | "fail" {
    if (failed.has(key)) return "fail";
    if (key === "collect") return collectDone ? "done" : "active";
    const idx = PIPE_ORDER.indexOf(key as typeof PIPE_ORDER[number]);
    if (done) return "done";
    if (idx < curIdx) return "done";
    if (idx === curIdx && scanStarted.current) return "active";
    return "wait";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card style={{ padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          {done ? <Icon name="reports" size={18} style={{ color: "var(--ok)" }} />
            : <Spinner size={18} />}
          <b style={{ fontSize: 14 }}>{done ? "Scan selesai" : "Agen bekerja…"}</b>
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>{detail}</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {stages.map((st, i) => {
            const state = stageState(st.key);
            const isCollect = st.key === "collect";
            return (
              <div key={st.key} style={{ display: "flex", alignItems: "center", gap: 13, padding: "11px 4px", borderBottom: i < stages.length - 1 ? "1px solid var(--line)" : "none" }}>
                <StageDot state={state} icon={st.icon} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: state === "wait" ? "var(--muted)" : "var(--ink)" }}>{st.label}</div>
                  <div style={{ fontSize: 11, color: "var(--faint)" }}>
                    {isCollect
                      ? `${prog.done}/${prog.total || "?"} sumber · ${prog.items} item terkumpul`
                      : st.hint}
                  </div>
                </div>
                <StageBadge state={state} />
              </div>
            );
          })}
        </div>
      </Card>

      {done && (
        <Card style={{ padding: 18 }}>
          <SectionTitle>Buka hasil</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <Button variant="ghost" icon="spark" onClick={() => onOpen("/forensics")}>Forensik Narasi</Button>
            <Button variant="ghost" icon="analysis" onClick={() => onOpen("/analysis")}>AI Analysis</Button>
            <Button variant="ghost" icon="graph" onClick={() => onOpen("/graph")}>Knowledge Graph</Button>
            <Button variant="ghost" icon="comment" onClick={() => onOpen("/explorer")}>Komentar</Button>
            <Button variant="ghost" icon="reports" onClick={() => onOpen("/reports")}>Reports</Button>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 12 }}>
            Investigasi ini kini jadi konteks aktif di semua halaman. Untuk verifikasi klaim & laporan
            ber-sitasi, buka Verifikasi Klaim / Reports.
          </div>
        </Card>
      )}
    </div>
  );
}

function StageDot({ state, icon }: { state: string; icon: IconName }) {
  const map: Record<string, { bg: string; c: string }> = {
    done: { bg: "var(--ok-soft)", c: "var(--ok)" },
    active: { bg: "var(--accent-soft)", c: "var(--accent)" },
    fail: { bg: "var(--crit-soft)", c: "var(--crit)" },
    wait: { bg: "var(--surface-2)", c: "var(--faint)" },
  };
  const s = map[state] || map.wait;
  return (
    <span style={{ width: 34, height: 34, borderRadius: 10, background: s.bg, color: s.c, display: "grid", placeItems: "center", flexShrink: 0 }}>
      {state === "active" ? <Spinner size={16} /> : <Icon name={state === "done" ? "reports" : state === "fail" ? "x" : icon} size={16} />}
    </span>
  );
}

function StageBadge({ state }: { state: string }) {
  const map: Record<string, { t: Tone; l: string }> = {
    done: { t: "ok", l: "selesai" }, active: { t: "accent", l: "berjalan" },
    fail: { t: "crit", l: "gagal" }, wait: { t: "muted", l: "antre" },
  };
  const s = map[state] || map.wait;
  return <Pill tone={s.t}>{s.l}</Pill>;
}
