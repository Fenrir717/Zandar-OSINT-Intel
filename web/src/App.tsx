import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, auth, type User } from "./lib/api";
import { Shell } from "./components/Shell";
import { Login } from "./pages/Login";
import { CommentExplorer } from "./pages/CommentExplorer";
import { AgentMonitor } from "./pages/AgentMonitor";
import { Placeholder } from "./pages/Placeholder";

const TITLES: Record<string, string> = {
  "/": "Dashboard", "/investigations": "Investigations", "/collections": "Collections",
  "/explorer": "Comment Explorer", "/analysis": "AI Analysis", "/graph": "Knowledge Graph",
  "/forensics": "Forensik Narasi", "/veracity": "Verifikasi Klaim", "/reports": "Reports",
  "/agents": "Agent Monitor",
};

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [headerRight, setHeaderRight] = useState<ReactNode>(null);
  const loc = useLocation();

  useEffect(() => {
    if (!auth.token) { setReady(true); return; }
    api.me().then(setUser).catch(() => auth.clear()).finally(() => setReady(true));
  }, []);

  useEffect(() => { setHeaderRight(null); }, [loc.pathname]);

  function onLoggedIn() { api.me().then(setUser); }
  function logout() { auth.clear(); setUser(null); }

  if (!ready) return null;
  if (!user) return <Login onDone={onLoggedIn} />;

  const title = TITLES[loc.pathname] || "Zandar OSINT";

  return (
    <Shell user={user} onLogout={logout} title={title} right={headerRight}>
      <Routes>
        <Route path="/explorer" element={<CommentExplorer headerSlot={setHeaderRight} />} />
        <Route path="/" element={<Placeholder title="Dashboard" phase="Fase 2" desc="Ringkasan investigasi aktif, aktivitas koleksi, distribusi sentimen, budget LLM. Menyusul setelah pipeline analisis Fase 2." />} />
        <Route path="/investigations" element={<Placeholder title="Investigations" phase="Fase 1→2" desc="Daftar & pembuatan investigasi dengan tipe target dan data_policy. Backend sudah ada (CRUD + audit); UI menyusul." />} />
        <Route path="/collections" element={<Placeholder title="Collections" phase="Fase 1" desc="Kelola sumber & jadwal koleksi (11 adapter, cron). Backend + worker/beat sudah jalan; UI daftar menyusul. Sementara lihat Riwayat Koleksi di Comment Explorer." />} />
        <Route path="/analysis" element={<Placeholder title="AI Analysis" phase="Fase 2" desc="Distribusi sentimen/emosi/intent, tren temporal, top topik — dari klasifikasi IndoBERT lokal." />} />
        <Route path="/graph" element={<Placeholder title="Knowledge Graph" phase="Fase 3" desc="Graf entitas & relasi interaktif, highlight komunitas CIB (Neo4j GDS)." />} />
        <Route path="/forensics" element={<Placeholder title="Forensik Narasi" phase="Fase 3" desc="Matriks kuadran Otentisitas × Kebenaran, skor ABC+D, peta TTP DISARM." />} />
        <Route path="/veracity" element={<Placeholder title="Verifikasi Klaim" phase="Fase 5" desc="Verdict klaim (didukung/dibantah/tak cukup/bertentangan) ber-bukti & skor kredibilitas sumber." />} />
        <Route path="/reports" element={<Placeholder title="Reports" phase="Fase 4" desc="Laporan intelijen ber-sitasi (Graph D), ekspor PDF, label klasifikasi." />} />
        <Route path="/agents" element={<AgentMonitor headerSlot={setHeaderRight} />} />
        <Route path="*" element={<Navigate to="/explorer" replace />} />
      </Routes>
    </Shell>
  );
}
