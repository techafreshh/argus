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

/** Per-watch tool trail: virtualized-feel sortable table + activity disclosure. */
export default function ReceiptsPanel() {
  const [watchId, setWatchId] = useState("");
  const [entries, setEntries] = useState<Receipt[] | null>(null);
  const [note, setNote] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("tool");
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

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

  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === 1 ? " ▲" : " ▼") : "");

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
      {sorted !== null && sorted.length > 0 && (
        <>
          <table aria-label="table" style={{ display: "block", maxHeight: 320, overflowY: "auto" }}>
            <thead style={{ position: "sticky", top: 0, background: "inherit" }}>
              <tr>
                <th>
                  <button type="button" onClick={() => toggleSort("tool")}>
                    Tool{arrow("tool")}
                  </button>
                </th>
                <th>
                  <button type="button" onClick={() => toggleSort("source")}>
                    Source URL{arrow("source")}
                  </button>
                </th>
                <th>Params</th>
                <th>
                  <button type="button" onClick={() => toggleSort("hash")}>
                    Data hash{arrow("hash")}
                  </button>
                </th>
                <th>Plot</th>
                <th>
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
          <ul aria-label="agent-activity">
            {sorted.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((prev) => ({ ...prev, [r.id]: !prev[r.id] }))
                  }
                >
                  {r.tool} — {r.id}
                </button>
                {expanded[r.id] && (
                  <span data-testid="tool-result">
                    source <a href={r.source_url}>{r.source_url}</a> params{" "}
                    <code>{JSON.stringify(r.params)}</code> hash{" "}
                    <code>{r.data_hash}</code> tokens {r.tokens ?? r.token_usage}
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
