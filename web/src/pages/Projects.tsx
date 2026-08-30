import { useEffect, useMemo, useState } from "react";
import { api, type Project } from "../lib/api";
import { Card, Empty, Pill } from "../components/ui";
import { Icon } from "../components/icons";

export function Projects({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const [list, setList] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  useEffect(() => { headerSlot(null); }, []);

  useEffect(() => {
    let alive = true;
    api.projects()
      .then((p) => { if (alive) setList(p); })
      .catch(() => { if (alive) setList([]); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return list;
    return list.filter((p) => p.name.toLowerCase().includes(term));
  }, [list, q]);

  return (
    <div>
      <div className="rise" style={{ marginBottom: 16 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nama proyek…"
          className="input" style={{ maxWidth: 320 }} />
      </div>

      {loading ? (
        <Empty icon="projects">Memuat proyek…</Empty>
      ) : filtered.length === 0 ? (
        <Empty icon="projects">
          {list.length === 0 ? "Belum ada proyek." : "Tidak ada proyek yang cocok dengan pencarian."}
        </Empty>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
          {filtered.map((p, i) => <ProjectCard key={p.id} p={p} delay={(i % 4) + 1} />)}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ p, delay }: { p: Project; delay: number }) {
  const created = p.created_at
    ? new Date(p.created_at).toLocaleDateString("id", { day: "2-digit", month: "short", year: "numeric" })
    : "Tanggal tidak diketahui";
  return (
    <Card hover className={`rise rise-${delay}`} style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{
          width: 42, height: 42, borderRadius: 12, background: "var(--accent-soft)", color: "var(--accent-ink)",
          display: "grid", placeItems: "center", flexShrink: 0,
        }}>
          <Icon name="projects" size={20} />
        </span>
        <div style={{
          minWidth: 0, fontSize: 15, fontWeight: 700, lineHeight: 1.35,
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{p.name}</div>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <Pill tone="accent">{p.investigation_count} investigasi</Pill>
        <span style={{ fontSize: 11, color: "var(--faint)", display: "flex", alignItems: "center", gap: 6 }}>
          <Icon name="timeline" size={12} />{created}
        </span>
      </div>
    </Card>
  );
}
