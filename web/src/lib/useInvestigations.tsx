import { useEffect, useState } from "react";
import { api, type Investigation } from "./api";

// State investigasi + pilihan aktif, dibagi lintas halaman via localStorage.
const SELECTED_KEY = "zandar_inv";

export function useInvestigations() {
  const [list, setList] = useState<Investigation[]>([]);
  const [selected, setSelected] = useState<string>(localStorage.getItem(SELECTED_KEY) || "");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.investigations().then((inv) => {
      setList(inv);
      setSelected((cur) => {
        const valid = inv.some((i) => i.id === cur) ? cur : inv[0]?.id || "";
        if (valid) localStorage.setItem(SELECTED_KEY, valid);
        return valid;
      });
    }).finally(() => setLoading(false));
  }, []);

  function choose(id: string) {
    setSelected(id);
    localStorage.setItem(SELECTED_KEY, id);
  }

  return { list, selected, choose, loading };
}

export function InvestigationPicker({ list, selected, onChange }: {
  list: Investigation[]; selected: string; onChange: (id: string) => void;
}) {
  return (
    <select value={selected} onChange={(e) => onChange(e.target.value)} className="select"
      style={{ height: 38, minWidth: 150, maxWidth: "min(260px, 44vw)", width: "auto", flexShrink: 1 }}>
      {list.length === 0 && <option>(belum ada investigasi)</option>}
      {list.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
    </select>
  );
}
