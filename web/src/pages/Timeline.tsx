import { useEffect, useMemo, useState } from "react";
import { api, type AgentRun, type Investigation } from "../lib/api";
import { Card, Empty, Pill } from "../components/ui";

type Tone = "ok" | "crit" | "info" | "accent";
type EventType = "investigation" | "agent";

interface TLEvent {
  type: EventType;
  time: number;
  when: string;
  title: string;
  meta: string;
  tone: Tone;
}

const GRAPH_LABEL: Record<string, string> = { planner: "Graph A · Planner", analysis: "Graph C · Narasi" };
const TYPE_LABEL: Record<EventType, string> = { investigation: "Investigasi", agent: "Agent" };
const TONE_COLOR: Record<Tone, string> = { ok: "var(--ok)", crit: "var(--crit)", info: "var(--info)", accent: "var(--accent)" };

function toneFor(type: EventType, status: string): Tone {
  if (status === "failed" || status === "rejected") return "crit";
  if (status === "done") return "ok";
  return type === "investigation" ? "info" : "accent";
}

function buildEvents(investigations: Investigation[], runs: AgentRun[]): TLEvent[] {
  const invEvents: TLEvent[] = investigations
    .filter((inv) => !!inv.created_at)
    .map((inv) => ({
      type: "investigation",
      time: new Date(inv.created_at).getTime(),
      when: inv.created_at,
      title: inv.title,
      meta: inv.status,
      tone: toneFor("investigation", inv.status),
    }));

  const agentEvents: TLEvent[] = [];
  for (const r of runs) {
    const when = r.ended_at || r.started_at;
    if (!when) continue;
    const tokens = (r.tokens_in + r.tokens_out).toLocaleString("id");
    agentEvents.push({
      type: "agent",
      time: new Date(when).getTime(),
      when,
      title: GRAPH_LABEL[r.graph_name] ?? r.graph_name,
      meta: `${r.status} · ${tokens} token`,
      tone: toneFor("agent", r.status),
    });
  }

  return [...invEvents, ...agentEvents].sort((a, b) => b.time - a.time);
}

export function Timeline({ headerSlot }: { headerSlot: (node: React.ReactNode) => void }) {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | EventType>("all");

  useEffect(() => { headerSlot(null); }, []);
  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const [inv, ar] = await Promise.all([api.investigations(), api.agentRuns()]);
        if (alive) { setInvestigations(inv); setRuns(ar); }
      } catch {
        if (alive) { setInvestigations([]); setRuns([]); }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const events = useMemo(() => buildEvents(investigations, runs), [investigations, runs]);
  const filtered = filter === "all" ? events : events.filter((e) => e.type === filter);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        {(["all", "investigation", "agent"] as const).map((f) => (
          <button key={f} onClick={() => setFilter(f)} style={{
            fontSize: 13, padding: "7px 14px", borderRadius: 999, border: "1px solid",
            borderColor: filter === f ? "var(--accent)" : "var(--line)",
            background: filter === f ? "var(--accent-soft)" : "var(--surface)",
            color: filter === f ? "var(--accent-ink)" : "var(--muted)", fontWeight: filter === f ? 600 : 400,
          }}>{f === "all" ? "Semua" : TYPE_LABEL[f]}</button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>{loading ? "…" : `${filtered.length} kejadian`}</span>
      </div>

      {loading ? (
        <Empty icon="timeline">Memuat linimasa…</Empty>
      ) : filtered.length === 0 ? (
        <Empty icon="timeline">Belum ada kejadian untuk ditampilkan.</Empty>
      ) : (
        <div style={{ position: "relative" }}>
          <span aria-hidden style={{ position: "absolute", left: 5, top: 8, bottom: 8, width: 2, background: "var(--line)" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {filtered.map((e, i) => (
              <div key={i} className="rise" style={{ display: "flex", gap: 14, position: "relative" }}>
                <span style={{
                  width: 12, height: 12, borderRadius: "50%", marginTop: 5, flexShrink: 0, zIndex: 1,
                  border: "2px solid var(--surface)", background: TONE_COLOR[e.tone],
                }} />
                <Card hover style={{ flex: 1, padding: "12px 15px", minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <Pill tone={e.type === "investigation" ? "info" : "accent"}>{TYPE_LABEL[e.type]}</Pill>
                    <b style={{ fontSize: 13.5 }}>{e.title}</b>
                    <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--faint)", whiteSpace: "nowrap" }}>
                      {new Date(e.when).toLocaleString("id", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>{e.meta}</div>
                </Card>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
