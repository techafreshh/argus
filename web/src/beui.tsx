import { useEffect, useState, type ReactNode } from "react";
import {
  Bell,
  FileText,
  Gauge,
  Globe,
  History,
  ListPlus,
  MessageSquare,
  Radar,
  ReceiptText,
} from "lucide-react";

/** ARGUS chart-room surfaces: dependency-free React + index.css classes. */

export function Card({
  children,
  label,
  id,
}: {
  children: ReactNode;
  label?: string;
  id?: string;
}) {
  return (
    <div
      className="beui-card"
      id={id}
      data-testid={label ? `card-${label}` : undefined}
    >
      {children}
    </div>
  );
}

/** Live loop readout: watches on the books + last scheduler tick (UTC). */
export function LoopIsland({ count, lastTick }: { count: number; lastTick: string }) {
  return (
    <div className="beui-island" aria-label="loop-status">
      <span className="dot" aria-hidden="true" />
      <span>
        {count} {count === 1 ? "watch" : "watches"} · last tick {lastTick || "—"}
      </span>
    </div>
  );
}

const PHASE_IDS: Record<string, string> = {
  "La Nina": "la_nina",
  "El Nino": "el_nino",
  Neutral: "neutral",
};

const PHASE_NAMES: Record<string, string> = {
  "La Nina": "La Niña",
  "El Nino": "El Niño",
  Neutral: "Neutral",
};

function fmt(value: unknown, digits = 2, suffix = ""): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

/** ENSO instrument readout: own ONI against the NOAA official rail. */
export function EnsoReadout({
  enso,
}: {
  enso: {
    phase: string;
    intensity: string;
    trajectory: string;
    month: string;
    [key: string]: unknown;
  } | null;
}) {
  const phaseId = enso ? (enso.phase_id as string | undefined) ?? PHASE_IDS[enso.phase] ?? "neutral" : "";
  const phaseName = enso ? PHASE_NAMES[enso.phase] ?? enso.phase : "—";
  return (
    <div className="enso-readout" data-testid="enso-badge">
      <div className="enso-cell">
        <span className="enso-label">Phase</span>
        <span className="enso-value enso-value--phase" data-phase={phaseId || undefined}>
          {phaseName}
        </span>
      </div>
      <div className="enso-cell">
        <span className="enso-label">Niño3.4 ONI</span>
        <span className="enso-value">{fmt(enso?.oni)} °C</span>
        <span className="enso-label">own computation</span>
      </div>
      <div className="enso-cell">
        <span className="enso-label">NOAA ONI</span>
        <span className="enso-value">{fmt(enso?.noaa_oni)} °C</span>
        <span className="enso-label">official</span>
      </div>
      <div className="enso-cell enso-cell--agree">
        <span className="enso-label">Agreement</span>
        <span className="enso-value">{enso?.phase_agreement_pct != null ? fmt(enso.phase_agreement_pct, 1, "%") : "—"}</span>
        <span className="enso-label">40-yr phase</span>
      </div>
      <div className="enso-cell">
        <span className="enso-label">State</span>
        <span className="enso-value">{enso ? `${enso.intensity} · ${enso.trajectory}` : "—"}</span>
        <span className="enso-label">{enso?.month || "—"}</span>
      </div>
    </div>
  );
}

const NAV_LINKS = [
  ["globe", "Globe", Globe],
  ["watchlist", "Watchlist", ListPlus],
  ["watches", "Watches", Radar],
  ["alerts", "Alerts", Bell],
  ["chat", "Chat", MessageSquare],
  ["receipts", "Receipts", ReceiptText],
  ["reports", "Reports", FileText],
  ["spend-eval", "Spend + eval", Gauge],
  ["analog-timeline", "Analogs", History],
] as const;

const SECTION_IDS = NAV_LINKS.map(([target]) => target);

function useActiveSection(): string {
  const [active, setActive] = useState<string>(SECTION_IDS[0] ?? "");
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActive(entry.target.id.replace("section-", ""));
          }
        }
      },
      { rootMargin: "-15% 0px -70% 0px" },
    );
    for (const id of SECTION_IDS) {
      const el = document.getElementById(`section-${id}`);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);
  return active;
}

export function Sidebar() {
  const active = useActiveSection();
  return (
    <nav className="beui-sidebar" aria-label="control-room-nav">
      <div className="beui-brand">
        <span className="beui-brand-mark" aria-hidden="true" />
        <span className="beui-brand-name">ARGUS</span>
      </div>
      <div className="beui-nav">
        {NAV_LINKS.map(([target, label, Icon]) => (
          <a
            key={target}
            href={`#section-${target}`}
            className={active === target ? "is-active" : undefined}
          >
            <Icon aria-hidden="true" />
            {label}
          </a>
        ))}
      </div>
      <div className="beui-sidebar-footer">v0.1.0 · MIT</div>
    </nav>
  );
}
