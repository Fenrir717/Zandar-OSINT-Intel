// Layout aplikasi: sidebar navigasi + header. Membungkus semua halaman.
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV: { section: string; items: { to: string; label: string; phase?: string }[] }[] = [
  { section: "Overview", items: [
    { to: "/", label: "Dashboard" },
    { to: "/investigations", label: "Investigations" },
  ]},
  { section: "Intelligence", items: [
    { to: "/collections", label: "Collections" },
    { to: "/explorer", label: "Comment Explorer" },
    { to: "/analysis", label: "AI Analysis", phase: "F2" },
    { to: "/graph", label: "Knowledge Graph", phase: "F3" },
    { to: "/forensics", label: "Forensik Narasi", phase: "F3" },
    { to: "/veracity", label: "Verifikasi Klaim", phase: "F5" },
    { to: "/reports", label: "Reports", phase: "F4" },
  ]},
  { section: "System", items: [
    { to: "/agents", label: "Agent Monitor", phase: "F2" },
  ]},
];

function Logo() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="var(--accent)" strokeWidth="1.8" aria-hidden="true">
      <circle cx="10" cy="10" r="7" /><circle cx="10" cy="10" r="2.6" />
      <line x1="10" y1="1.5" x2="10" y2="5" /><line x1="10" y1="15" x2="10" y2="18.5" />
    </svg>
  );
}

export function Shell({ user, onLogout, right, title, children }: {
  user?: { name: string; role: string };
  onLogout: () => void;
  right?: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "var(--sidebar-w) 1fr", minHeight: "100vh" }}>
      <aside style={{ background: "var(--surface)", borderRight: "1px solid var(--line)", padding: "16px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 8px 16px" }}>
          <span style={{ width: 32, height: 32, borderRadius: 6, background: "var(--accent-soft)", display: "grid", placeItems: "center" }}><Logo /></span>
          <div><b style={{ fontSize: 15 }}>Zandar OSINT</b><span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>Enterprise Intelligence</span></div>
        </div>
        {NAV.map((grp) => (
          <div key={grp.section}>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: ".12em", color: "var(--muted)", fontWeight: 700, padding: "12px 12px 4px" }}>{grp.section}</div>
            {grp.items.map((it) => (
              <NavLink key={it.to} to={it.to} end={it.to === "/"} style={({ isActive }) => ({
                display: "flex", alignItems: "center", gap: 8, fontSize: 13, padding: "8px 12px", borderRadius: 6,
                textDecoration: "none", color: isActive ? "var(--accent-ink)" : "var(--muted)",
                background: isActive ? "var(--accent-soft)" : "transparent", fontWeight: isActive ? 600 : 400,
              })}>
                {it.label}
                {it.phase && <span style={{ fontSize: 9, color: "var(--muted)", marginLeft: "auto" }}>{it.phase}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </aside>

      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header style={{ display: "flex", alignItems: "center", gap: 14, padding: "0 26px", height: 60, borderBottom: "1px solid var(--line)", background: "var(--surface)" }}>
          <h1 style={{ fontSize: 19, margin: 0, fontWeight: 700 }}>{title}</h1>
          {right}
          <div style={{ flex: 1 }} />
          {user && <span style={{ fontSize: 12, color: "var(--muted)" }}>{user.name} · {user.role}</span>}
          <button onClick={onLogout} style={{ background: "transparent", border: "1px solid var(--line)", borderRadius: 6, padding: "7px 13px", fontSize: 12, color: "var(--ink)" }}>Keluar</button>
        </header>
        <main style={{ padding: "20px 26px", minWidth: 0, flex: 1 }}>{children}</main>
      </div>
    </div>
  );
}
