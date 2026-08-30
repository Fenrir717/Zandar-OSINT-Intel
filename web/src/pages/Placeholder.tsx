import { Card } from "../components/ui";
import { Icon, type IconName } from "../components/icons";

// Halaman yang belum dibangun — menandai fase & isi rencananya (dari PRD).
const ICON: Record<string, IconName> = {
  Dashboard: "dashboard", Investigations: "search", Collections: "collections",
  "AI Analysis": "analysis", "Knowledge Graph": "graph", "Forensik Narasi": "spark",
  "Verifikasi Klaim": "audit", Reports: "reports", Settings: "settings",
};

export function Placeholder({ title, phase, desc }: { title: string; phase: string; desc: string }) {
  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "62vh" }}>
      <Card hover style={{ padding: "38px 34px", maxWidth: 560, textAlign: "center" }}>
        <div style={{ width: 62, height: 62, margin: "0 auto 18px", borderRadius: 16, background: "var(--accent-soft)", color: "var(--accent-ink)", display: "grid", placeItems: "center" }}>
          <Icon name={ICON[title] || "spark"} size={28} stroke={1.7} />
        </div>
        <div className="badge" style={{ color: "var(--accent-ink)", borderColor: "var(--accent)", background: "var(--accent-soft)", margin: "0 auto" }}>
          <span className="dot" /> {phase === "—" ? "Direncanakan" : phase}
        </div>
        <h2 style={{ fontSize: 22, margin: "12px 0 10px" }}>{title}</h2>
        <p style={{ color: "var(--muted)", lineHeight: 1.65, margin: 0, fontSize: 13.5 }}>{desc}</p>
      </Card>
    </div>
  );
}
