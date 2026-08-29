import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { Button } from "../components/ui";

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

  const label = { display: "block", fontSize: 11, textTransform: "uppercase" as const, letterSpacing: ".05em", color: "var(--muted)", fontWeight: 600, margin: "12px 0 5px" };
  const input = { width: "100%", padding: "9px 11px", border: "1px solid var(--line)", borderRadius: 6, fontSize: 14, background: "var(--surface)", color: "var(--ink)" };

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <form onSubmit={submit} style={{ width: 340, padding: 28, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, boxShadow: "var(--shadow)" }}>
        <h1 style={{ fontSize: 19, margin: "0 0 4px", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 30, height: 30, borderRadius: 6, background: "var(--accent-soft)", display: "grid", placeItems: "center" }}>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="var(--accent)" strokeWidth="1.8"><circle cx="10" cy="10" r="7" /><circle cx="10" cy="10" r="2.6" /></svg>
          </span>
          Zandar OSINT
        </h1>
        <p style={{ color: "var(--muted)", fontSize: 12, margin: "0 0 18px" }}>Enterprise Intelligence — masuk untuk melanjutkan</p>
        <label htmlFor="email" style={label}>Email</label>
        <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} style={input} autoComplete="username" />
        <label htmlFor="pw" style={label}>Password</label>
        <input id="pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={input} autoComplete="current-password" />
        <div style={{ marginTop: 18 }}><Button type="submit">{busy ? "Memproses…" : "Masuk"}</Button></div>
        <div role="alert" style={{ color: "var(--crit)", fontSize: 12, marginTop: 10, minHeight: 16 }}>{err}</div>
      </form>
    </div>
  );
}
