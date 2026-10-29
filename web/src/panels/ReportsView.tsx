import { useState } from "react";
import { getReport, type ReportCard } from "../api";

/** Graded report card: headline, hectares/counts, confidence, before/after, sources. */
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
        <article data-testid={`report-${card.id}`}>
          <h3>{card.headline}</h3>
          <p>
            {card.hectares} ha — counts {JSON.stringify(card.counts)} — confidence{" "}
            {Math.round(card.confidence * 100)}%
          </p>
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
          <ul>
            {card.sources.map((s) => (
              <li key={s}>
                <a href={s}>{s}</a>
              </li>
            ))}
          </ul>
        </article>
      )}
    </section>
  );
}
