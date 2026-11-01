import type { AskPreview } from "../api";

/** Honest missing-data card for out-of-catalog ask responses. */
export default function MissingDataCard({ preview }: { preview: AskPreview }) {
  const missing = Array.isArray(preview.missing) ? preview.missing : [];
  const adjacent = Array.isArray(preview.adjacent) ? preview.adjacent : [];
  return (
    <div
      className="missing-card"
      data-testid="missing-data-card"
      aria-label="missing-data-card"
      data-beui="card"
    >
      <p data-testid="missing-answer" className="missing-answer">
        {preview.answer ?? "No pipeline covers this."}
      </p>
      {missing.length > 0 && (
        <>
          <h4 className="missing-section">Missing</h4>
          <ul data-testid="missing-list" className="missing-list">
            {missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </>
      )}
      {adjacent.length > 0 && (
        <>
          <h4 className="missing-section">Adjacent pipelines</h4>
          <ul data-testid="adjacent-list" className="missing-list">
            {adjacent.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
