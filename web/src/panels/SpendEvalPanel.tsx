import { useEffect, useRef, useState } from "react";
import { getEvalStatus, getSpend, type EvalStatus, type SpendLedger } from "../api";

/** One-shot count-up that ends on the exact target value. */
function CountUp({ value }: { value: number }) {
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
  const done = shown === value;
  return <span aria-label="number" data-testid="total-credits">{done ? value : shown}</span>;
}

/** Spend + eval: tabbed spend ledger and eval-gate probe status. */
export default function SpendEvalPanel() {
  const [spend, setSpend] = useState<SpendLedger | null>(null);
  const [evalStatus, setEvalStatus] = useState<EvalStatus | null>(null);
  const [note, setNote] = useState("");
  const [tab, setTab] = useState<"spend" | "eval">("spend");

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

  const probes = evalStatus?.probes;
  const familyCount = (v: unknown): number => (Array.isArray(v) ? v.length : 0);

  return (
    <section aria-label="spend-eval">
      <h2>Spend + eval</h2>
      {note && <p>{note}</p>}
      <div role="tablist" aria-label="tabs">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "spend"}
          onClick={() => setTab("spend")}
        >
          Spend
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "eval"}
          onClick={() => setTab("eval")}
        >
          Eval
        </button>
      </div>
      {tab === "spend" && (
        <div role="tabpanel">
          {spend ? (
            <>
              <p>
                total credits: <CountUp value={spend.total_credits} />
              </p>
              <table aria-label="table">
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
          ) : (
            !note && <p>loading spend…</p>
          )}
        </div>
      )}
      {tab === "eval" && (
        <div role="tabpanel">
          {evalStatus ? (
            <>
              <p data-testid="eval-precision">
                hits {evalStatus.hits} misses {evalStatus.misses} total {evalStatus.total}{" "}
                precision {evalStatus.precision} — probes {evalStatus.probes.status}
              </p>
              <ul>
                <li>
                  replay: {familyCount(probes?.replay)} — {probes?.status}
                </li>
                <li>
                  false_positive: {familyCount(probes?.false_positive)} — {probes?.status}
                </li>
                <li>
                  novel_question: {familyCount(probes?.novel_question)} — {probes?.status}
                </li>
              </ul>
            </>
          ) : (
            !note && <p>loading eval…</p>
          )}
        </div>
      )}
    </section>
  );
}
