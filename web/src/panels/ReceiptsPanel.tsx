import { useState } from "react";
import { listReceipts, type Receipt } from "../api";

/** Per-watch tool trail: tool, source URL, params, 64-hex hash, plot, tokens. */
export default function ReceiptsPanel() {
  const [watchId, setWatchId] = useState("");
  const [entries, setEntries] = useState<Receipt[] | null>(null);
  const [note, setNote] = useState("");

  const load = async () => {
    setNote("loading…");
    try {
      setEntries(await listReceipts(watchId.trim()));
      setNote("");
    } catch (err) {
      setEntries(null);
      setNote(`receipts failed: ${String(err)}`);
    }
  };

  return (
    <section aria-label="receipts">
      <h2>Receipts</h2>
      <label>
        Watch id{" "}
        <input aria-label="receipts watch id" value={watchId} onChange={(e) => setWatchId(e.target.value)} />
      </label>{" "}
      <button type="button" onClick={() => void load()}>
        Load receipts
      </button>
      {note && <p>{note}</p>}
      {entries !== null && entries.length === 0 && <p>no receipts</p>}
      {entries !== null && entries.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Tool</th>
              <th>Source URL</th>
              <th>Params</th>
              <th>Data hash</th>
              <th>Plot</th>
              <th>Tokens</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((r) => (
              <tr key={r.id} data-testid={`receipt-${r.id}`}>
                <td>{r.tool}</td>
                <td>
                  <a href={r.source_url}>{r.source_url}</a>
                </td>
                <td>
                  <code>{JSON.stringify(r.params)}</code>
                </td>
                <td>
                  <code>{r.data_hash}</code>
                </td>
                <td>{(r as Receipt & { plot_path?: string }).plot_path ?? ""}</td>
                <td>{r.tokens ?? r.token_usage}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
