import type { ReactNode } from "react";

/** Local beUI-compatible surfaces: dependency-free React + index.css classes. */

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

type BadgeStatus = "info" | "success" | "warning" | "neutral" | "loading";

export function AnimatedBadge({
  status = "info",
  children,
  testId,
}: {
  status?: BadgeStatus;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <span className={`beui-badge beui-badge--${status}`} data-testid={testId}>
      {children}
    </span>
  );
}

export function DynamicIsland({ children }: { children: ReactNode }) {
  return (
    <div className="beui-island" aria-label="loop-status">
      <span className="dot" aria-hidden="true" />
      {children}
    </div>
  );
}

export function TextAnimation({ text }: { text: string }) {
  return <h1 className="beui-title">{text}</h1>;
}

const NAV_LINKS = [
  ["globe", "Globe"],
  ["watchlist", "Watchlist"],
  ["watches", "Watches"],
  ["alerts", "Alerts"],
  ["chat", "Chat"],
  ["receipts", "Receipts"],
  ["reports", "Reports"],
  ["spend-eval", "Spend + eval"],
  ["analog-timeline", "Analogs"],
] as const;

export function AnimatedSidebar() {
  return (
    <nav className="beui-sidebar" aria-label="control-room-nav">
      {NAV_LINKS.map(([target, label]) => (
        <a key={target} href={`#section-${target}`}>
          {label}
        </a>
      ))}
    </nav>
  );
}

export function ThemeToggle() {
  const toggle = () => {
    document.documentElement.classList.toggle("light");
  };
  return (
    <button type="button" className="beui-toggle" onClick={toggle} aria-label="theme-toggle">
      Toggle theme
    </button>
  );
}
