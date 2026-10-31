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
        setNote(`analog timeline unavailable: ${String(err)}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section aria-label="analog-timeline">
      <h2>Analog timeline</h2>
      {note && <p>{note}</p>}
      {analogs && (
        <ol aria-label="timeline">
          {analogs.map((a) => (
            <li key={a.month || String(a.year)} data-testid={`analog-${a.year || a.month}`}>
              <span aria-label="number">{a.month}</span> — similarity{" "}
              <span aria-label="number">{a.similarity}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
