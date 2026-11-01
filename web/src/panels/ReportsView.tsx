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

/** Graded report card: headline, count-up figures, citations, before/after imagery. */
export default function ReportsView() {
  const [reportId, setReportId] = useState("");
  const [card, setCard] = useState<ReportCard | null>(null);
  const [note, setNote] = useState("");

  const load = async () => {
    setNote("");
    try {
      setCard(await getReport(reportId.trim()));
    } catch (err) {
      setCard(null);
      setNote(`Report unavailable — ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const before = card ? card.before_url || card.before_path : "";
  const after = card ? card.after_url || card.after_path : "";
  const receipts = card?.receipts ?? [];

  return (
    <section aria-label="reports">
      <h2>Reports</h2>
      <div className="form-row">
        <label className="field" style={{ minWidth: 260 }}>
          <span className="field-label">Report id</span>
          <input
            className="input"
            aria-label="report id"
            value={reportId}
            onChange={(e) => setReportId(e.target.value)}
          />
        </label>
        <div className="field">
          <span className="field-label" aria-hidden="true">
            &nbsp;
          </span>
          <button type="button" className="btn btn--quiet" onClick={() => void load()}>
            Load report
          </button>
        </div>
      </div>
      {note && <p className="note note--error">{note}</p>}
      {card && (
        <article aria-label="card" data-testid={`report-${card.id}`}>
          <h3 style={{ fontSize: 16, fontWeight: 500 }}>{card.headline}</h3>
          <div className="stat-row">
            <div className="stat">
              <span className="stat-label">Area</span>
              <span className="stat-figure stat-figure--accent">
                <CountUp value={card.hectares} format={(v) => `${Math.round(v).toLocaleString("en-US")}`} />
              </span>
              <span className="stat-sub">hectares</span>
            </div>
            <div className="stat">
              <span className="stat-label">Confidence</span>
              <span className="stat-figure">
                <CountUp value={card.confidence * 100} format={(v) => `${Math.round(v)}%`} />
              </span>
              <span className="stat-sub">graded</span>
            </div>
            {Object.entries(card.counts).map(([k, v]) => (
              <div className="stat" key={k}>
                <span className="stat-label">{k}</span>
                <span className="stat-figure">{String(v)}</span>
                <span className="stat-sub">count</span>
              </div>
            ))}
          </div>
          <div aria-label="image-viewer" className="report-images">
            {before ? (
              <img src={before} alt="before" />
            ) : (
              <p className="report-image-slot">No before imagery</p>
            )}
            {after ? (
              <img src={after} alt="after" />
            ) : (
              <p className="report-image-slot">No after imagery</p>
            )}
          </div>
          <ul aria-label="citations" className="citations">
            {card.sources.map((s) => (
              <li key={s} className="receipt-line">
                <b>source</b> <a href={s}>{s}</a>
              </li>
            ))}
            {receipts.map((r) => (
              <li key={r.id} className="receipt-line">
                <b>receipt</b> <a href={`#receipt-${r.id}`}>{r.id}</a> hash {r.data_hash}
              </li>
            ))}
          </ul>
        </article>
      )}
    </section>
  );
}
