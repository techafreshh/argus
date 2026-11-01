import { useEffect, useState } from "react";
import { getEnsoStatus, type EnsoAnalog } from "../api";

/** Live analog timeline wired to GET /api/enso/status. */
export default function AnalogTimeline() {
  const [analogs, setAnalogs] = useState<EnsoAnalog[] | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const status = await getEnsoStatus();
        if (!alive) return;
        setAnalogs((status.analogs ?? []).slice(0, 3));
      } catch (err) {
        if (!alive) return;
        setNote(`Analog timeline unavailable — ${err instanceof Error ? err.message : String(err)}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const top = analogs?.[0];

  return (
    <section aria-label="analog-timeline">
      <h2>Analogs</h2>
      {note && <p className="note note--warn">{note}</p>}
      {analogs && analogs.length === 0 && <p className="note">No analogs yet</p>}
      {analogs && analogs.length > 0 && (
        <ol aria-label="timeline" className="analog-list">
          {analogs.map((a) => (
            <li
              key={a.month || String(a.year)}
              data-testid={`analog-${a.year || a.month}`}
              className={`analog-row${a === top ? " analog-row--top" : ""}`}
            >
              <span className="analog-month">{a.month}</span>
              <span className="analog-track" aria-hidden="true">
                <span
                  className="analog-bar"
                  style={{ width: `${Math.max(4, Math.round(a.similarity * 100))}%` }}
                />
              </span>
              <span className="analog-score" aria-label="number">
                {typeof a.similarity === "number" ? a.similarity.toFixed(4) : a.similarity}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
