// Primitif UI kecil dipakai lintas halaman. Semua via token tema.
import type { CSSProperties, ReactNode } from "react";

export function Tile({ label, value, tone }: { label: string; value: ReactNode; tone?: "warn" | "crit" }) {
  const color = tone === "crit" ? "var(--crit)" : tone === "warn" ? "var(--warn)" : "var(--ink)";
  const border = tone === "crit" ? "var(--crit)" : tone === "warn" ? "var(--warn)" : "var(--line)";
  return (
    <div style={{ background: "var(--surface)", border: `1px solid ${border}`, borderRadius: "var(--radius)", padding: "12px 16px", boxShadow: "var(--shadow)" }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, fontVariantNumeric: "tabular-nums", color }}>{value}</div>
    </div>
  );
}

const pillTone: Record<string, CSSProperties> = {
  accent: { background: "var(--accent-soft)", color: "var(--accent-ink)", borderColor: "var(--accent)" },
  ok: { background: "var(--ok-soft)", color: "var(--ok)", borderColor: "var(--ok)" },
  warn: { background: "var(--warn-soft)", color: "var(--warn)", borderColor: "var(--warn)" },
  crit: { background: "var(--crit-soft)", color: "var(--crit)", borderColor: "var(--crit)" },
  muted: { background: "var(--surface)", color: "var(--muted)", borderColor: "var(--line)" },
};

export function Pill({ children, tone = "muted" }: { children: ReactNode; tone?: keyof typeof pillTone }) {
  return (
    <span style={{ fontSize: 11, padding: "2px 9px", border: "1px solid", borderRadius: 999, whiteSpace: "nowrap", ...pillTone[tone] }}>
      {children}
    </span>
  );
}

export function Button({ children, onClick, variant = "primary", type = "button" }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost"; type?: "button" | "submit";
}) {
  const s: CSSProperties = variant === "primary"
    ? { background: "var(--accent)", color: "#fff", borderColor: "var(--accent-ink)" }
    : { background: "var(--surface)", color: "var(--ink)", borderColor: "var(--line)" };
  return (
    <button type={type} onClick={onClick} style={{ border: "1px solid", borderRadius: 6, padding: "9px 16px", fontWeight: 600, fontSize: 13, transition: "background .15s, border-color .15s", ...s }}>
      {children}
    </button>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--radius)", boxShadow: "var(--shadow)", ...style }}>{children}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div style={{ textAlign: "center", color: "var(--muted)", padding: 40, border: "1px dashed var(--line)", borderRadius: "var(--radius)", background: "var(--surface)" }}>{children}</div>;
}
