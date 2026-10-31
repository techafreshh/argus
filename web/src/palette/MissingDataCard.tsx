import type { AskPreview } from "../api";

/** Honest missing-data card for out-of-catalog ask responses. */
export default function MissingDataCard({ preview }: { preview: AskPreview }) {
  const missing = Array.isArray(preview.missing) ? preview.missing : [];
  const adjacent = Array.isArray(preview.adjacent) ? preview.adjacent : [];
  return (
    <div data-testid="missing-data-card" aria-label="missing-data-card" data-beui="card">
      <p data-testid="missing-answer">{preview.answer ?? "No pipeline covers this."}</p>
      <h4>Missing</h4>
      <ul data-testid="missing-list">
        {missing.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ul>
      <h4>Adjacent pipelines</h4>
      <ul data-testid="adjacent-list">
        {adjacent.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </div>
  );
}
