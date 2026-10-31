import { useEffect, useRef, useState } from "react";
import { getReport, type ReportCard } from "../api";

/** One-shot count-up that ends on the exact target value. */
function CountUp({ value, format }: { value: number; format?: (v: number) => string }) {
  const [shown, setShown] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    const start = performance.now();
    const dur = 600;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      setShown(value * t);
      if (t < 1) {
        raf.current = requestAnimationFrame(tick);
      } else {
        setShown(value);
      }
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value]);
  const done = Math.abs(shown - value) < 1e-9 || shown === value;
  const current = done ? value : shown;
  return <span aria-label="number">{format ? format(current) : String(current)}</span>;
}

/** Graded report card: headline, count-up numbers, citations, before/after viewer. */
export default function ReportsView() {
  const [reportId, setReportId] = useState("");
  const [card, setCard] = useState<ReportCard | null>(null);
  const [note, setNote] = useState("");

  const load = async () => {
    setNote("loading…");
    try {
      setCard(await getReport(reportId.trim()));
      setNote("");
    } catch (err) {
      setCard(null);
      setNote(`report failed: ${String(err)}`);
    }
  };

  const before = card ? card.before_url || card.before_path : "";
  const after = card ? card.after_url || card.after_path : "";
  const receipts = card?.receipts ?? [];

  return (
    <section aria-label="reports">
      <h2>Reports</h2>
      <label>
        Report id{" "}
        <input aria-label="report id" value={reportId} onChange={(e) => setReportId(e.target.value)} />
      </label>{" "}
      <button type="button" onClick={() => void load()}>
        Load report
      </button>
      {note && <p>{note}</p>}
      {card && (
        <article aria-label="card" data-testid={`report-${card.id}`}>
          <h3>{card.headline}</h3>
          <p>
            <CountUp value={card.hectares} format={(v) => `${v} ha`} /> — counts{" "}
            <code>{JSON.stringify(card.counts)}</code> — confidence{" "}
            <CountUp value={card.confidence * 100} format={(v) => `${Math.round(v)}%`} />
          </p>
          <div aria-label="image-viewer">
            {before ? (
              <img src={before} alt="before" />
            ) : (
              <p>no before imagery available</p>
            )}
            {after ? (
              <img src={after} alt="after" />
            ) : (
              <p>no after imagery available</p>
            )}
          </div>
          <ul aria-label="citations">
            {card.sources.map((s) => (
              <li key={s}>
                <a href={s}>{s}</a>
              </li>
            ))}
            {receipts.map((r) => (
              <li key={r.id}>
                <a href={`#receipt-${r.id}`}>receipt {r.id}</a>
              </li>
            ))}
          </ul>
        </article>
      )}
    </section>
  );
}
