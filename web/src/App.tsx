import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, auth, type User } from "./lib/api";
import { Shell } from "./components/Shell";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { CommentExplorer } from "./pages/CommentExplorer";
import { AgentMonitor } from "./pages/AgentMonitor";
import { AIAnalysis } from "./pages/AIAnalysis";
import { Investigations } from "./pages/Investigations";
import { Projects } from "./pages/Projects";
import { Collections } from "./pages/Collections";
import { Timeline } from "./pages/Timeline";
import { KnowledgeGraph } from "./pages/KnowledgeGraph";
import { Reports } from "./pages/Reports";
import { ForensikNarasi } from "./pages/ForensikNarasi";
import { VerifikasiKlaim } from "./pages/VerifikasiKlaim";
import { Settings } from "./pages/Settings";

const TITLES: Record<string, string> = {
  "/": "Dashboard", "/projects": "Projects", "/investigations": "Investigations",
  "/collections": "Collections", "/explorer": "Comment Explorer", "/analysis": "AI Analysis",
  "/graph": "Knowledge Graph", "/timeline": "Timeline", "/forensics": "Forensik Narasi",
  "/veracity": "Verifikasi Klaim", "/reports": "Reports", "/agents": "Agent Monitor",
  "/settings": "Settings",
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
          <Route path="/" element={<Dashboard headerSlot={setHeaderRight} />} />
          <Route path="/projects" element={<Projects headerSlot={setHeaderRight} />} />
          <Route path="/investigations" element={<Investigations headerSlot={setHeaderRight} />} />
          <Route path="/collections" element={<Collections headerSlot={setHeaderRight} />} />
          <Route path="/explorer" element={<CommentExplorer headerSlot={setHeaderRight} />} />
          <Route path="/analysis" element={<AIAnalysis headerSlot={setHeaderRight} />} />
          <Route path="/graph" element={<KnowledgeGraph headerSlot={setHeaderRight} />} />
          <Route path="/timeline" element={<Timeline headerSlot={setHeaderRight} />} />
          <Route path="/reports" element={<Reports headerSlot={setHeaderRight} />} />
          <Route path="/agents" element={<AgentMonitor headerSlot={setHeaderRight} />} />
          <Route path="/forensics" element={<ForensikNarasi headerSlot={setHeaderRight} />} />
          <Route path="/veracity" element={<VerifikasiKlaim headerSlot={setHeaderRight} />} />
          <Route path="/settings" element={<Settings headerSlot={setHeaderRight} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    </Shell>
  );
}
