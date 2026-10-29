import { useEffect, useState } from "react";
import { getEvalStatus, getSpend, type EvalStatus, type SpendLedger } from "../api";

/** Spend + eval: total credits, per-call table, ledger precision, probe status. */
export default function SpendEvalPanel() {
  const [spend, setSpend] = useState<SpendLedger | null>(null);
  const [evalStatus, setEvalStatus] = useState<EvalStatus | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [s, e] = await Promise.all([getSpend(), getEvalStatus()]);
        if (!alive) return;
        setSpend(s);
        setEvalStatus(e);
      } catch (err) {
        if (!alive) return;
        setNote(`spend/eval failed: ${String(err)}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section aria-label="spend-eval">
      <h2>Spend + eval</h2>
      {note && <p>{note}</p>}
      {spend && (
        <>
          <p data-testid="total-credits">total credits: {spend.total_credits}</p>
          <table>
            <thead>
              <tr>
                <th>Operation</th>
                <th>Model</th>
                <th>Tokens in</th>
                <th>Tokens out</th>
                <th>Cost credits</th>
              </tr>
            </thead>
            <tbody>
              {spend.calls.map((c) => (
                <tr key={c.id}>
                  <td>{c.operation}</td>
                  <td>{c.model}</td>
                  <td>{c.tokens_in}</td>
                  <td>{c.tokens_out}</td>
                  <td>{c.cost_credits}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {evalStatus && (
        <p data-testid="eval-precision">
          hits {evalStatus.hits} misses {evalStatus.misses} total {evalStatus.total} precision{" "}
          {evalStatus.precision} — probes {evalStatus.probes.status}
        </p>
      )}
    </section>
  );
}
