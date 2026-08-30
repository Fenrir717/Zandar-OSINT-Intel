// Layout aplikasi: sidebar ikon + header lengket. Responsif (drawer < 900px), toggle tema.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Icon, type IconName } from "./icons";

const NAV: { section: string; items: { to: string; label: string; icon: IconName; phase?: string }[] }[] = [
  { section: "Overview", items: [
    { to: "/", label: "Dashboard", icon: "dashboard" },
    { to: "/projects", label: "Projects", icon: "projects" },
    { to: "/investigations", label: "Investigations", icon: "search" },
  ]},
  { section: "Intelligence", items: [
    { to: "/collections", label: "Collections", icon: "collections" },
    { to: "/explorer", label: "Comment Explorer", icon: "comment" },
    { to: "/analysis", label: "AI Analysis", icon: "analysis" },
    { to: "/graph", label: "Knowledge Graph", icon: "graph", phase: "F3" },
    { to: "/timeline", label: "Timeline", icon: "timeline" },
    { to: "/forensics", label: "Forensik Narasi", icon: "spark" },
    { to: "/veracity", label: "Verifikasi Klaim", icon: "audit", phase: "F5" },
    { to: "/reports", label: "Reports", icon: "reports", phase: "F4" },
  ]},
  { section: "System", items: [
    { to: "/agents", label: "Agent Monitor", icon: "agents" },
    { to: "/settings", label: "Settings", icon: "settings" },
  ]},
];

const SUBTITLE: Record<string, string> = {
  "/": "Ikhtisar investigasi aktif, pipeline koleksi, dan status analisis AI.",
  "/projects": "Kelola project investigasi dan tingkat klasifikasi.",
  "/investigations": "Buat & kelola investigasi OSINT dengan sumber & pipeline analisis.",
  "/collections": "Pantau job koleksi, status antrean, dan performa kolektor.",
  "/explorer": "Telusuri & analisis komentar publik lintas platform dengan tag sentimen.",
  "/analysis": "Distribusi sentimen, emosi, intent, topik — dari klasifikasi IndoBERT lokal.",
  "/graph": "Graf entitas, relasi, dan komunitas hasil investigasi.",
  "/timeline": "Urutan kronologis kejadian, publikasi, dan aktivitas agen.",
  "/reports": "Ringkasan intelijen ber-sitasi dari narasi & analisis.",
  "/agents": "Pemantauan run agen LangGraph secara real-time — node, token, biaya.",
};

export function Shell({ user, onLogout, right, title, children }: {
  user?: { name: string; role: string };
  onLogout: () => void; right?: ReactNode; title: string; children: ReactNode;
}) {
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("zandar_theme") || "light");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("zandar_theme", theme);
  }, [theme]);
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); searchRef.current?.focus(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const sub = SUBTITLE[loc.pathname];

  return (
    <div className="app-shell" style={{ display: "grid", gridTemplateColumns: "var(--sidebar-w) 1fr", minHeight: "100vh" }}>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "open" : ""}`} style={{ background: "var(--surface)", borderRight: "1px solid var(--line)", padding: "16px 12px", display: "flex", flexDirection: "column", gap: 2, overflowY: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "6px 8px 18px" }}>
          <span style={{ width: 36, height: 36, borderRadius: 10, background: "var(--accent-grad)", display: "grid", placeItems: "center", color: "#fff", boxShadow: "0 2px 8px var(--accent-ring)" }}>
            <Icon name="target" size={20} stroke={2} />
          </span>
          <div style={{ lineHeight: 1.2 }}>
            <b style={{ fontSize: 15, letterSpacing: "-.01em" }}>Zandar OSINT</b>
            <span style={{ fontSize: 10, color: "var(--muted)", display: "block", marginTop: 1 }}>Enterprise Intelligence</span>
          </div>
        </div>

        {NAV.map((grp) => (
          <div key={grp.section}>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: ".13em", color: "var(--faint)", fontWeight: 700, padding: "14px 12px 5px" }}>{grp.section}</div>
            {grp.items.map((it) => (
              <NavLink key={it.to} to={it.to} end={it.to === "/"} className="nav-item"
                style={({ isActive }) => navStyle(isActive)}>
                {({ isActive }) => (
                  <>
                    <Icon name={it.icon} size={17} style={{ opacity: isActive ? 1 : .8, flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>{it.label}</span>
                    {it.phase && <span style={{ fontSize: 9, color: isActive ? "var(--accent-ink)" : "var(--faint)", fontWeight: 600 }}>{it.phase}</span>}
                    {isActive && <span aria-hidden style={{ position: "absolute", left: 0, top: 8, bottom: 8, width: 3, borderRadius: 3, background: "var(--accent)" }} />}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ padding: "10px 10px 4px", fontSize: 10, color: "var(--faint)" }}>Fase 2 · v0.1</div>
      </aside>

      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header style={{ position: "sticky", top: 0, zIndex: 40, display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px 12px", padding: "11px 20px", borderBottom: "1px solid var(--line)", background: "color-mix(in srgb, var(--surface) 86%, transparent)", backdropFilter: "blur(8px)" }}>
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Menu"><Icon name="menu" size={18} /></button>
          <div style={{ minWidth: 0, flexShrink: 1 }}>
            <h1 style={{ fontSize: 17, margin: 0, lineHeight: 1.2 }}>{title}</h1>
            {sub && <div className="hide-sm" style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "44vw" }}>{sub}</div>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto", flexWrap: "wrap", justifyContent: "flex-end" }}>
            {right}
            <div className="hide-sm" style={{ position: "relative", width: 214 }}>
              <Icon name="search" size={15} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: "var(--faint)" }} />
              <input ref={searchRef} className="input" placeholder="Cari intelijen…" style={{ paddingLeft: 33, paddingRight: 42, height: 38 }} />
              <kbd style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", fontSize: 10, color: "var(--faint)", background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: 5, padding: "2px 5px", fontFamily: "var(--font-mono)" }}>⌘K</kbd>
            </div>
            <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Ganti tema" title="Ganti tema">
              <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
            </button>
            <button className="icon-btn" aria-label="Notifikasi" title="Notifikasi" style={{ position: "relative" }}>
              <Icon name="bell" size={17} />
              <span style={{ position: "absolute", top: 8, right: 9, width: 6, height: 6, borderRadius: "50%", background: "var(--crit)", boxShadow: "0 0 0 2px var(--surface)" }} />
            </button>
            {user && (
              <div className="hide-sm" style={{ display: "flex", alignItems: "center", gap: 9, paddingLeft: 6 }}>
                <span style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--accent-grad)", color: "#fff", display: "grid", placeItems: "center", fontWeight: 700, fontSize: 13 }}>
                  {(user.name || "?").slice(0, 1).toUpperCase()}
                </span>
                <div style={{ lineHeight: 1.2 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600 }}>{user.name}</div>
                  <div style={{ fontSize: 10.5, color: "var(--muted)", textTransform: "capitalize" }}>{user.role}</div>
                </div>
              </div>
            )}
            <button className="icon-btn" onClick={onLogout} aria-label="Keluar" title="Keluar"><Icon name="logout" size={16} /></button>
          </div>
        </header>

        <main className="content" style={{ padding: "22px 24px", minWidth: 0, flex: 1 }}>
          <div className="page" key={loc.pathname}>{children}</div>
        </main>
      </div>
    </div>
  );
}

function navStyle(_isActive: boolean): React.CSSProperties {
  // Warna/hover via kelas .nav-item / .nav-item.active di CSS (react-router menambah .active)
  return {
    position: "relative", display: "flex", alignItems: "center", gap: 10, fontSize: 13,
    padding: "9px 12px", borderRadius: 9, textDecoration: "none",
  };
}
