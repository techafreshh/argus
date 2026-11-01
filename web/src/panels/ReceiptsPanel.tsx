import { useMemo, useState } from "react";
import { listReceipts, type Receipt } from "../api";

type SortKey = "tool" | "source" | "hash" | "tokens";

function sortKeyOf(r: Receipt, key: SortKey): string | number {
  if (key === "tool") return r.tool ?? "";
  if (key === "source") return r.source_url ?? "";
  if (key === "hash") return r.data_hash ?? "";
  const t = r.tokens ?? r.token_usage ?? 0;
  return typeof t === "number" ? t : Number(t) || 0;
}

/** Per-watch tool trail: sortable receipt table + activity stream. */
export default function ReceiptsPanel() {
  const [watchId, setWatchId] = useState("");
  const [entries, setEntries] = useState<Receipt[] | null>(null);
  const [note, setNote] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("tool");
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = async () => {
    setNote("");
    try {
      setEntries(await listReceipts(watchId.trim()));
    } catch (err) {
      setEntries(null);
      setNote(`Receipts unavailable — ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  };

  const sorted = useMemo(() => {
    if (!entries) return null;
    return [...entries].sort((a, b) => {
      const va = sortKeyOf(a, sortKey);
      const vb = sortKeyOf(b, sortKey);
      if (typeof va === "number" && typeof vb === "number") {
        return (va - vb) * sortDir;
      }
      return String(va).localeCompare(String(vb)) * sortDir;
    });
  }, [entries, sortKey, sortDir]);

  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === 1 ? " ↑" : " ↓") : "");

  return (
    <section aria-label="receipts">
      <h2>Receipts</h2>
      <div className="form-row">
        <label className="field" style={{ minWidth: 260 }}>
          <span className="field-label">Watch id</span>
          <input
            className="input"
            aria-label="receipts watch id"
            value={watchId}
            onChange={(e) => setWatchId(e.target.value)}
          />
        </label>
        <div className="field">
          <span className="field-label" aria-hidden="true">
            &nbsp;
          </span>
          <button type="button" className="btn btn--quiet" onClick={() => void load()}>
            Load receipts
          </button>
        </div>
      </div>
      {note && <p className="note note--error">{note}</p>}
      {entries !== null && entries.length === 0 && (
        <p className="note">No receipts yet — run a watch first</p>
      )}
      {sorted !== null && sorted.length > 0 && (
        <>
          <div className="table-scroll">
            <table aria-label="table" className="data-table">
              <thead>
                <tr>
                  <th>
                    <button type="button" onClick={() => toggleSort("tool")}>
                      Tool{arrow("tool")}
                    </button>
                  </th>
                  <th>
                    <button type="button" onClick={() => toggleSort("source")}>
                      Source{arrow("source")}
                    </button>
                  </th>
                  <th>Params</th>
                  <th>
                    <button type="button" onClick={() => toggleSort("hash")}>
                      Data hash{arrow("hash")}
                    </button>
                  </th>
                  <th className="num">
                    <button type="button" onClick={() => toggleSort("tokens")}>
                      Tokens{arrow("tokens")}
                    </button>
                  </th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.id} data-testid={`receipt-${r.id}`}>
                    <td>{r.tool}</td>
                    <td>
                      <a href={r.source_url} className="hash" style={{ maxWidth: 220 }} title={r.source_url}>
                        {r.source_url}
                      </a>
                    </td>
                    <td>
                      <span className="hash" style={{ maxWidth: 180 }} title={JSON.stringify(r.params)}>
                        {JSON.stringify(r.params)}
                      </span>
                    </td>
                    <td>
                      <span className="hash" title={r.data_hash}>
                        {r.data_hash}
                      </span>
                    </td>
                    <td className="num">{r.tokens ?? r.token_usage}</td>
                    <td>
                      <button
                        type="button"
                        aria-expanded={Boolean(expanded[r.id])}
                        onClick={() =>
                          setExpanded((prev) => ({ ...prev, [r.id]: !prev[r.id] }))
                        }
                      >
                        {expanded[r.id] ? "Hide" : "Show"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul aria-label="agent-activity" className="activity-list">
            {sorted.map((r) => (
              <li key={r.id} style={{ listStyle: "none" }}>
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((prev) => ({ ...prev, [r.id]: !prev[r.id] }))
                  }
                >
                  {r.tool} — {r.id}
                </button>
                {expanded[r.id] && (
                  <span data-testid="tool-result" className="receipt-line">
                    source <a href={r.source_url}>{r.source_url}</a> params{" "}
                    {JSON.stringify(r.params)} hash {r.data_hash} tokens{" "}
                    {r.tokens ?? r.token_usage}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
