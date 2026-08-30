import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { Icon } from "../components/icons";

export function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("admin@zandar.local");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try { await api.login(email, password); onDone(); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Gagal terhubung ke API"); }
    finally { setBusy(false); }
  }

  const label: React.CSSProperties = { display: "block", fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700, margin: "14px 0 6px" };

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}>
      <form onSubmit={submit} className="card rise" style={{ width: 372, padding: "30px 30px 26px", boxShadow: "var(--sh-lg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <span style={{ width: 40, height: 40, borderRadius: 11, background: "var(--accent-grad)", display: "grid", placeItems: "center", color: "#fff", boxShadow: "0 3px 10px var(--accent-ring)" }}>
            <Icon name="target" size={22} stroke={2} />
          </span>
          <div style={{ lineHeight: 1.2 }}>
            <h1 style={{ fontSize: 19, margin: 0 }}>Zandar OSINT</h1>
            <span style={{ fontSize: 11, color: "var(--muted)" }}>Enterprise Intelligence</span>
          </div>
        </div>
        <p style={{ color: "var(--muted)", fontSize: 12.5, margin: "10px 0 6px" }}>Masuk untuk melanjutkan ke platform analisis.</p>

        <label htmlFor="email" style={label}>Email</label>
        <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" style={{ height: 40 }} />
        <label htmlFor="pw" style={label}>Password</label>
        <input id="pw" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" style={{ height: 40 }} />

        <div style={{ marginTop: 20 }}>
          <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: "100%", height: 42, fontSize: 14 }}>
            {busy ? "Memproses…" : "Masuk"}
          </button>
        </div>
        <div role="alert" style={{ color: "var(--crit)", fontSize: 12, marginTop: 12, minHeight: 16, textAlign: "center" }}>{err}</div>
      </form>
    </div>
  );
}
