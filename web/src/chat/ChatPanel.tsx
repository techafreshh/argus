import { useRef, useState } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { approveAlert, listAlerts, rejectAlert } from "../api";
import { streamChat, type AguiEvent } from "./chatClient";

type TodoItem = { label: string; detail: string; done: boolean };

type TranscriptRow =
  | { kind: "activity"; text: string }
  | { kind: "tool"; tool: string; receiptId: string; hash: string }
  | {
      kind: "answer";
      content: string;
      template: string | null;
      watchId: string;
      receiptId: string;
      citations: { receipt_id: string; data_hash: string; source_url: string }[];
    }
  | { kind: "error"; text: string };

function planTodos(plan: Record<string, unknown>): TodoItem[] {
  const steps: Array<[string, unknown]> = [
    ["sensor", plan.sensor],
    ["aoi", plan.aoi],
    ["window", plan.window],
    ["comparison", plan.comparison],
    ["cadence", plan.cadence],
  ];
  return steps.map(([label, value]) => ({
    label,
    detail: typeof value === "string" ? value : JSON.stringify(value ?? null),
    done: value !== undefined && value !== null && value !== "",
  }));
}

function ChatInner() {
  const [question, setQuestion] = useState("Is flooding worsening here?");
  const [bboxText, setBboxText] = useState("3,6,4,7");
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [rows, setRows] = useState<TranscriptRow[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [lastWatch, setLastWatch] = useState("");
  const [decision, setDecision] = useState("");
  const threadRef = useRef(crypto.randomUUID());

  const parseBbox = (): [number, number, number, number] | undefined => {
    const parts = bboxText
      .split(",")
      .map((p) => Number(p.trim()))
      .filter((n) => Number.isFinite(n));
    if (parts.length !== 4) return undefined;
    return [parts[0], parts[1], parts[2], parts[3]];
  };

  const ask = async () => {
    if (busy) return;
    setBusy(true);
    setDegraded(false);
    setDecision("");
    setStatus("streaming plan…");
    setRows((prev) => [...prev, { kind: "activity", text: `asking: ${question}` }]);
    const onEvent = (event: AguiEvent) => {
      if (event.type === "tool_call") {
        const input = event.input ?? {};
        const plan = (input.plan ?? input) as Record<string, unknown>;
        if (plan && typeof plan === "object") setTodos(planTodos(plan));
        setRows((prev) => [
          ...prev,
          { kind: "activity", text: `agent activity: tool_call ${event.tool}` },
        ]);
      } else if (event.type === "tool_result") {
        setTodos((prev) => prev.map((t) => ({ ...t, done: true })));
        setRows((prev) => [
          ...prev,
          {
            kind: "tool",
            tool: event.tool,
            receiptId: event.receipt.id,
            hash: event.receipt.data_hash,
          },
        ]);
      } else if (event.type === "message") {
        if (event.plan && typeof event.plan === "object") {
          setTodos(planTodos(event.plan as Record<string, unknown>));
        }
        setLastWatch(String(event.watch_id ?? ""));
        setRows((prev) => [
          ...prev,
          {
            kind: "answer",
            content: event.content,
            template: (event.template as string | null) ?? null,
            watchId: String(event.watch_id ?? ""),
            receiptId: String(event.receipt_id ?? ""),
            citations: event.citations ?? [],
          },
        ]);
      } else if (event.type === "run_finished") {
        setBusy(false);
        if (!event.ok) {
          setDegraded(true);
          setStatus(`chat unavailable — panels still work below`);
          setRows((prev) => [
            ...prev,
            { kind: "error", text: String(event.error ?? "stream failed") },
          ]);
        } else {
          setStatus("run finished");
        }
      }
    };
    const bbox = parseBbox();
    await streamChat(question, onEvent, {
      bbox,
      threadId: threadRef.current,
    });
  };

  const decide = async (kind: "approve" | "reject") => {
    setDecision("deciding…");
    try {
      const alerts = await listAlerts();
      const target = alerts.find(
        (a) => a.watch_id === lastWatch && a.status === "queued",
      );
      if (!target) {
        setDecision("no queued alert for this run yet");
        return;
      }
      if (kind === "approve") await approveAlert(target.id);
      else await rejectAlert(target.id);
      setDecision(`${kind}d ${target.id}`);
    } catch (err) {
      setDecision(`decision failed: ${String(err)}`);
    }
  };

  return (
    <section aria-label="chat">
      <h2>Ask the Earth</h2>
      <div role="search" aria-label="command-palette">
        <label>
          Question{" "}
          <input
            aria-label="chat question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </label>{" "}
        <label>
          BBox{" "}
          <input
            aria-label="chat bbox"
            value={bboxText}
            onChange={(e) => setBboxText(e.target.value)}
          />
        </label>{" "}
        <button type="button" onClick={() => void ask()} disabled={busy}>
          {busy ? "Streaming…" : "Ask"}
        </button>
      </div>
      {status && <p data-testid="chat-status">{status}</p>}
      {todos.length > 0 && (
        <ol aria-label="todo-list">
          {todos.map((t) => (
            <li key={t.label}>
              [{t.done ? "x" : " "}] {t.label}: {t.detail}
            </li>
          ))}
        </ol>
      )}
      <ul aria-label="agent-activity">
        {rows.map((row, i) => (
          <li key={i}>
            {row.kind === "activity" && <span>{row.text}</span>}
            {row.kind === "tool" && (
              <span data-testid="tool-result">
                tool-result {row.tool} receipt {row.receiptId} hash {row.hash}
              </span>
            )}
            {row.kind === "answer" && (
              <div>
                <p>{row.content}</p>
                {row.template && <p>template: {row.template}</p>}
                {row.citations.length > 0 && (
                  <ul aria-label="citations">
                    {row.citations.map((c) => (
                      <li key={c.receipt_id}>
                        citation receipt {c.receipt_id} hash {c.data_hash}
                        {c.source_url ? ` source ${c.source_url}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
                {row.template && (
                  <div aria-label="approval-card">
                    <button
                      type="button"
                      disabled={!lastWatch}
                      onClick={() => void decide("approve")}
                    >
                      Approve alert
                    </button>{" "}
                    <button
                      type="button"
                      disabled={!lastWatch}
                      onClick={() => void decide("reject")}
                    >
                      Reject alert
                    </button>
                    {decision && <span data-testid="chat-decision"> {decision}</span>}
                  </div>
                )}
              </div>
            )}
            {row.kind === "error" && <span>{row.text}</span>}
          </li>
        ))}
      </ul>
      {degraded && (
        <p data-testid="chat-degraded">
          Chat is unavailable; the globe, watchlist, and alert panels below keep
          working.
        </p>
      )}
    </section>
  );
}

export default function ChatPanel() {
  // Build-time kill-switch: the panel (and its CopilotKit context) mounts
  // only when chat is enabled; panels render regardless.
  if (import.meta.env.VITE_CHAT_ENABLED === "0") return null;
  try {
    return (
      <CopilotKit runtimeUrl="/api/copilot" agent="argus">
        <ChatInner />
      </CopilotKit>
    );
  } catch {
    // A CopilotKit context failure must never blank the panels.
    return <ChatInner />;
  }
}
