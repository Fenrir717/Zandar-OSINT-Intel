import { Card } from "../components/ui";

// Halaman yang belum dibangun — menandai fase & isi rencananya (dari PRD).
export function Placeholder({ title, phase, desc }: { title: string; phase: string; desc: string }) {
  return (
    <Card style={{ padding: "40px 32px", maxWidth: 640 }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--accent-ink)", fontWeight: 600, letterSpacing: ".08em" }}>{phase}</div>
      <h2 style={{ fontSize: 22, margin: "6px 0 10px" }}>{title}</h2>
      <p style={{ color: "var(--muted)", lineHeight: 1.6, margin: 0 }}>{desc}</p>
    </Card>
  );
}
