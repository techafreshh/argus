/** Fixture-driven analog timeline (client-side until an analog endpoint lands). */

const EVENTS = [
  { year: 1982, label: "Baseline dry-season composite", kind: "baseline" },
  { year: 1997, label: "Strong El Nino anomaly", kind: "analog" },
  { year: 2010, label: "La Nina greening pulse", kind: "analog" },
  { year: 2016, label: "Record warm-year browning", kind: "analog" },
  { year: 2024, label: "Current state", kind: "now" },
] as const;

const TOP_ANALOGS = [
  { year: 2016, similarity: 0.91 },
  { year: 1997, similarity: 0.84 },
  { year: 2010, similarity: 0.72 },
] as const;

export default function AnalogTimeline() {
  return (
    <section aria-label="analog-timeline">
      <h2>Analog timeline (fixture)</h2>
      <ol>
        {EVENTS.map((e) => (
          <li key={e.year} data-testid={`analog-${e.year}`}>
            {e.year} — {e.label}
          </li>
        ))}
      </ol>
      <h3>Top 3 analogs</h3>
      <ul>
        {TOP_ANALOGS.map((a) => (
          <li key={a.year}>
            {a.year} — similarity {a.similarity}
          </li>
        ))}
      </ul>
    </section>
  );
}
