// Primitif UI. Semua via token tema + kelas .card/.btn/.badge (hover & motion di CSS).
import { useEffect } from "react";
import type { CSSProperties, ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon, type IconName } from "./icons";

type Tone = "accent" | "ok" | "warn" | "crit" | "muted" | "info" | "violet";

const toneVar: Record<Tone, { c: string; b: string; bg: string }> = {
  accent: { c: "var(--accent-ink)", b: "var(--accent)", bg: "var(--accent-soft)" },
  ok: { c: "var(--ok-ink)", b: "var(--ok)", bg: "var(--ok-soft)" },
  warn: { c: "var(--warn-ink)", b: "var(--warn)", bg: "var(--warn-soft)" },
  crit: { c: "var(--crit-ink)", b: "var(--crit)", bg: "var(--crit-soft)" },
  info: { c: "var(--info)", b: "var(--info)", bg: "var(--info-soft)" },
  violet: { c: "var(--violet)", b: "var(--violet)", bg: "var(--violet-soft)" },
  muted: { c: "var(--muted)", b: "var(--line)", bg: "var(--surface-2)" },
};

export function Pill({ children, tone = "muted", dot }: { children: ReactNode; tone?: Tone; dot?: boolean }) {
  const t = toneVar[tone];
  return (
    <span className="badge" style={{ color: t.c, borderColor: t.b, background: t.bg }}>
      {dot && <span className="dot" />} {children}
    </span>
  );
}

export function Button({ children, onClick, variant = "primary", type = "button", icon, disabled }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost";
  type?: "button" | "submit"; icon?: IconName; disabled?: boolean;
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`btn ${variant === "primary" ? "btn-primary" : "btn-ghost"}`}>
      {icon && <Icon name={icon} size={16} />} {children}
    </button>
  );
}

export function IconButton({ icon, onClick, title, spinning }: { icon: IconName; onClick?: () => void; title?: string; spinning?: boolean }) {
  return (
    <button className="icon-btn" onClick={onClick} title={title} aria-label={title}
      style={spinning ? { animation: "spin 1s linear infinite" } : undefined}>
      <Icon name={icon} size={17} />
    </button>
  );
}

export function Card({ children, style, hover, className }: { children: ReactNode; style?: CSSProperties; hover?: boolean; className?: string }) {
  return <div className={`card ${hover ? "card-hover" : ""} ${className || ""}`} style={style}>{children}</div>;
}

export function Tile({ label, value, tone, icon, delta, sub }: {
  label: string; value: ReactNode; tone?: "warn" | "crit"; icon?: IconName;
  delta?: { value: string; dir: "up" | "down" }; sub?: string;
}) {
  const color = tone === "crit" ? "var(--crit)" : tone === "warn" ? "var(--warn)" : "var(--ink)";
  return (
    <div className="card card-hover stat" style={{ padding: "15px 17px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".07em", color: "var(--muted)", fontWeight: 700 }}>{label}</div>
          <div className="tnum" style={{ fontSize: 27, fontWeight: 800, lineHeight: 1.15, marginTop: 6, color, letterSpacing: "-.02em" }}>{value}</div>
        </div>
        {icon && <span className="stat-ico" style={tone ? { background: tone === "crit" ? "var(--crit-soft)" : "var(--warn-soft)", color } : undefined}><Icon name={icon} size={19} /></span>}
      </div>
      {(delta || sub) && (
        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--muted)" }}>
          {delta && <span className={`delta ${delta.dir}`}><Icon name={delta.dir === "up" ? "trendUp" : "trendDown"} size={13} stroke={2.2} />{delta.value}</span>}
          {sub && <span>{sub}</span>}
        </div>
      )}
    </div>
  );
}

export function ProgressBar({ value, tone }: { value: number; tone?: Tone }) {
  const t = tone ? toneVar[tone].b : undefined;
  return (
    <div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: t ? t : undefined }} /></div>
  );
}

export function Empty({ children, icon }: { children: ReactNode; icon?: IconName }) {
  return (
    <div style={{ textAlign: "center", color: "var(--muted)", padding: "44px 24px", border: "1px dashed var(--line)", borderRadius: "var(--radius)", background: "var(--surface)" }}>
      {icon && <div style={{ display: "grid", placeItems: "center", marginBottom: 10, color: "var(--faint)" }}><Icon name={icon} size={26} /></div>}
      <div style={{ fontSize: 13 }}>{children}</div>
    </div>
  );
}

export function Skeleton({ h = 16, w = "100%", style }: { h?: number; w?: number | string; style?: CSSProperties }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} />;
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ animation: "spin .8s linear infinite" }} aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="var(--line)" strokeWidth="3" />
      <path d="M12 3a9 9 0 0 1 9 9" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// Banner JUJUR untuk halaman yang memakai data contoh / fitur fase berikutnya.
export function PreviewBanner({ phase, children }: { phase: string; children?: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: "var(--radius-sm)", background: "var(--warn-soft)", border: "1px solid var(--warn)", color: "var(--warn-ink)", fontSize: 12.5, marginBottom: 16 }}>
      <Icon name="spark" size={15} style={{ flexShrink: 0 }} />
      <span><b>Pratinjau {phase}</b>{children ? " — " : ""}{children}</span>
    </div>
  );
}

// Modal reusable — portal ke body (hindari containing-block dari .page yang ter-transform).
export function Modal({ title, onClose, children, footer, busy }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; busy?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, busy]);

  return createPortal(
    <div onClick={() => { if (!busy) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 200, display: "grid", placeItems: "center", padding: 20,
        background: "rgba(8,18,20,.52)", backdropFilter: "blur(3px)", animation: "fadeIn .16s ease",
      }}>
      <div onClick={(e) => e.stopPropagation()} className="card rise"
        style={{ width: 460, maxWidth: "100%", maxHeight: "88vh", overflowY: "auto", boxShadow: "var(--sh-lg)" }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
          padding: "14px 18px", borderBottom: "1px solid var(--line)", position: "sticky", top: 0,
          background: "var(--surface)", zIndex: 1,
        }}>
          <b style={{ fontSize: 15 }}>{title}</b>
          <button className="icon-btn" onClick={onClose} disabled={busy} aria-label="Tutup"><Icon name="x" size={16} /></button>
        </div>
        <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>{children}</div>
        {footer && (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, padding: "12px 18px", borderTop: "1px solid var(--line)" }}>
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

// Field — label + kontrol form, konsisten spacing.
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)" }}>{label}</span>
      {children}
      {hint && <span style={{ fontSize: 11, color: "var(--faint)" }}>{hint}</span>}
    </label>
  );
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
      <h3 style={{ margin: 0, fontSize: 15 }}>{children}</h3>
      {right}
    </div>
  );
}
