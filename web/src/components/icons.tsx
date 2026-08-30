// Ikon SVG (gaya Lucide, stroke currentColor). Ganti emoji per panduan uipro.
import type { CSSProperties } from "react";

const P: Record<string, string> = {
  dashboard: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  projects: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  collections: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  comment: "M4 5h16v11H9l-5 4z",
  analysis: "M12 3a4 4 0 0 0-4 4 4 4 0 0 0-2 7 3.5 3.5 0 0 0 3 5 3 3 0 0 0 6 0 3 3 0 0 0 6 0 3.5 3.5 0 0 0 3-5 4 4 0 0 0-2-7 4 4 0 0 0-4-4 3 3 0 0 0-6 0zM12 3v18",
  graph: "M6 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM7.5 6.5l3.2 8M16.5 6.5l-3.2 8",
  timeline: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  reports: "M6 2h8l4 4v16H6zM14 2v4h4M9 13h6M9 17h6M9 9h2",
  agents: "M9 3h6v3H9zM6 6h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zM9 12h.01M15 12h.01M9 16h6M2 11v3M22 11v3",
  audit: "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 13.5a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H2a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h.1A1.7 1.7 0 0 0 10 3.1V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  bell: "M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9zM13.7 21a2 2 0 0 1-3.4 0",
  plus: "M12 5v14M5 12h14",
  refresh: "M21 12a9 9 0 1 1-2.6-6.4M21 3v4h-4",
  download: "M12 3v12M8 11l4 4 4-4M4 21h16",
  trendUp: "M3 17l6-6 4 4 8-8M15 7h6v6",
  trendDown: "M3 7l6 6 4-4 8 8M15 17h6v-6",
  chevronR: "M9 6l6 6-6 6",
  chevronD: "M6 9l6 6 6-6",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v3M12 20v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M1 12h3M20 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  menu: "M4 6h16M4 12h16M4 18h16",
  x: "M6 6l12 12M18 6L6 18",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 12h.01",
  filter: "M3 5h18l-7 8v5l-4 2v-7z",
  spark: "M13 2L4 14h7l-1 8 9-12h-7z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
};

export type IconName = keyof typeof P;

export function Icon({ name, size = 18, stroke = 1.8, style, className }: {
  name: IconName; size?: number; stroke?: number; style?: CSSProperties; className?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      style={style} className={className}>
      <path d={P[name]} />
    </svg>
  );
}
