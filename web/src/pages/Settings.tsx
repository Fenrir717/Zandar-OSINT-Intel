import { useEffect, useState } from "react";
import { api, type SystemService, type SystemUser } from "../lib/api";
import { Button, Card, Empty, Pill, Spinner, Tile } from "../components/ui";
import { Icon, type IconName } from "../components/icons";

type Tone = "accent" | "ok" | "warn" | "crit" | "muted" | "info" | "violet";

const ROLES: { key: string; label: string; desc: string; tone: Tone }[] = [
  { key: "admin", label: "Administrator", desc: "Akses penuh sistem, pengguna, & pengaturan", tone: "accent" },
  { key: "lead", label: "Lead Analis", desc: "Kelola investigasi & tim, setujui rencana agen", tone: "info" },
  { key: "analyst", label: "Analis", desc: "Jalankan koleksi, analisis, & lihat laporan", tone: "muted" },
];
const ROLE_TONE: Record<string, Tone> = { admin: "accent", lead: "info", analyst: "muted" };

const STATUS_MAP: Record<string, { tone: Tone; label: string }> = {
  connected: { tone: "ok", label: "Tersambung" },
  configured: { tone: "info", label: "Terkonfigurasi" },
  not_configured: { tone: "warn", label: "Belum diatur" },
  down: { tone: "crit", label: "Terputus" },
};
const KIND_ICON: Record<string, IconName> = {
  Database: "collections", "Queue / Cache": "refresh", "Vector DB": "collections",
  "Graph DB": "graph", "Object Store": "collections", "AI Model": "analysis",
};

export function Settings({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const [services, setServices] = useState<SystemService[]>([]);
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [adapters, setAdapters] = useState(0);
  const [loading, setLoading] = useState(true);
  const [usersDenied, setUsersDenied] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("zandar_theme") || "light");

  useEffect(() => { headerSlot(null); }, []);
  useEffect(() => { load(); }, []);
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("zandar_theme", theme);
  }, [theme]);

  async function load() {
    setLoading(true);
    const [st, us, ad] = await Promise.allSettled([api.systemStatus(), api.systemUsers(), api.adapters()]);
    if (st.status === "fulfilled") setServices(st.value);
    if (us.status === "fulfilled") setUsers(us.value); else setUsersDenied(true);
    if (ad.status === "fulfilled") setAdapters(ad.value.length);
    setLoading(false);
  }

  const connected = services.filter((s) => s.status === "connected").length;
  const roleCount = (r: string) => users.filter((u) => u.role === r).length;

  if (loading) return <div style={{ display: "grid", placeItems: "center", padding: "80px 0" }}><Spinner size={28} /></div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="grid-stats">
        <div className="rise rise-1"><Tile label="Pengguna" value={users.length || (usersDenied ? "—" : 0)} icon="agents" /></div>
        <div className="rise rise-2"><Tile label="Peran (RBAC)" value={ROLES.length} icon="audit" /></div>
        <div className="rise rise-3"><Tile label="Sumber data" value={adapters || "—"} icon="collections" /></div>
        <div className="rise rise-4"><Tile label="Layanan aktif" value={`${connected}/${services.length}`} icon="spark" tone={connected < services.length ? "warn" : undefined} /></div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }} className="grid-2">
        {/* Users */}
        <Card className="rise" style={{ padding: 16 }}>
          <Head icon="agents" title="Pengguna Terdaftar" />
          {usersDenied ? <Empty icon="audit">Butuh peran admin/lead untuk melihat daftar pengguna.</Empty>
            : users.length === 0 ? <Empty icon="agents">Belum ada pengguna.</Empty>
            : <div style={{ display: "flex", flexDirection: "column" }}>
                {users.map((u, i) => (
                  <div key={u.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 0", borderBottom: i < users.length - 1 ? "1px solid var(--line-2)" : "none" }}>
                    <span style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--accent-soft)", color: "var(--accent-ink)", display: "grid", placeItems: "center", fontWeight: 700, fontSize: 13, flexShrink: 0 }}>
                      {(u.name || "?").slice(0, 1).toUpperCase()}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.name}</div>
                      <div style={{ fontSize: 11.5, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.email}</div>
                    </div>
                    <Pill tone={ROLE_TONE[u.role] ?? "muted"}>{u.role}</Pill>
                  </div>
                ))}
              </div>}
        </Card>

        {/* Roles */}
        <Card className="rise" style={{ padding: 16 }}>
          <Head icon="audit" title="Peran & Izin" />
          <div style={{ display: "flex", flexDirection: "column" }}>
            {ROLES.map((r, i) => (
              <div key={r.key} style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 0", borderBottom: i < ROLES.length - 1 ? "1px solid var(--line-2)" : "none" }}>
                <span style={{ color: `var(--${r.tone === "muted" ? "muted" : r.tone === "info" ? "info" : "accent"})` }}><Icon name="audit" size={17} /></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{r.label} <span style={{ fontSize: 11, color: "var(--faint)", fontFamily: "var(--font-mono)" }}>{r.key}</span></div>
                  <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{r.desc}</div>
                </div>
                <span className="tnum" title="jumlah pengguna" style={{ fontSize: 15, fontWeight: 800, color: "var(--ink)" }}>{roleCount(r.key)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* System configuration */}
      <Card className="rise" style={{ padding: 16 }}>
        <Head icon="settings" title="Konfigurasi Sistem" right={<span style={{ fontSize: 11, color: "var(--muted)" }}>{connected}/{services.length} tersambung</span>} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }} className="grid-2">
          {services.map((s) => {
            const m = STATUS_MAP[s.status] ?? STATUS_MAP.down;
            return (
              <div key={s.name} className="card" style={{ padding: "12px 14px", display: "flex", alignItems: "center", gap: 12, boxShadow: "none", background: "var(--surface-2)" }}>
                <span style={{ color: "var(--muted)" }}><Icon name={KIND_ICON[s.kind] ?? "collections"} size={18} /></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--faint)", fontWeight: 700 }}>{s.kind}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>{s.detail}</div>
                </div>
                <Pill tone={m.tone} dot>{m.label}</Pill>
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }} className="grid-2">
        {/* Appearance */}
        <Card className="rise" style={{ padding: 16 }}>
          <Head icon="sun" title="Tampilan" />
          <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 12 }}>Tema antarmuka (tersimpan di perangkat ini).</div>
          <div style={{ display: "flex", gap: 8 }}>
            {(["light", "dark"] as const).map((t) => (
              <button key={t} onClick={() => setTheme(t)} className="btn" style={{
                flex: 1, borderColor: theme === t ? "var(--accent)" : "var(--line)",
                background: theme === t ? "var(--accent-soft)" : "var(--surface)",
                color: theme === t ? "var(--accent-ink)" : "var(--ink)",
              }}>
                <Icon name={t === "light" ? "sun" : "moon"} size={16} /> {t === "light" ? "Terang" : "Gelap"}
              </button>
            ))}
          </div>
        </Card>

        {/* BYOK */}
        <ByokCard />
      </div>
    </div>
  );
}

function ByokCard() {
  const [provider, setProvider] = useState("openrouter");
  const [key, setKey] = useState("");
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <Head icon="analysis" title="Kunci LLM Sendiri (BYOK)" />
      <div style={{ display: "flex", alignItems: "flex-start", gap: 9, padding: "9px 12px", borderRadius: "var(--radius-sm)", background: "var(--warn-soft)", border: "1px solid var(--warn)", color: "var(--warn-ink)", fontSize: 11.5, marginBottom: 12, lineHeight: 1.5 }}>
        <Icon name="spark" size={14} style={{ flexShrink: 0, marginTop: 1 }} />
        <span><b>Pratinjau desain.</b> Default tetap memakai <code style={{ fontFamily: "var(--font-mono)" }}>.env</code> server. Penyimpanan terenkripsi (server-side, write-only) & pemakaian per-user = Fase berikutnya. Jangan masukkan kunci produksi di sini.</span>
      </div>
      <label style={label}>Provider</label>
      <select className="select" value={provider} onChange={(e) => setProvider(e.target.value)} style={{ marginBottom: 10 }}>
        {["openrouter", "groq", "gemini", "cerebras", "openai"].map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <label style={label}>API Key</label>
      <input className="input" type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-…" autoComplete="off" style={{ marginBottom: 12 }} />
      <Button variant="ghost" disabled icon="audit">Simpan aman — Fase berikutnya</Button>
    </Card>
  );
}

const label: React.CSSProperties = { display: "block", fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700, margin: "0 0 6px" };

function Head({ icon, title, right }: { icon: IconName; title: string; right?: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, fontWeight: 600 }}>
      <span style={{ color: "var(--accent)" }}><Icon name={icon} size={16} /></span>{title}
      {right && <span style={{ marginLeft: "auto" }}>{right}</span>}
    </div>
  );
}
