import { useEffect, useRef, useState } from "react";
import {
  AgentActivity,
  type AgentActivityItem,
} from "@/components/agents/agent-activity";
import { ApprovalCard } from "@/components/agents/approval-card";
import { Citations } from "@/components/agents/citations";
import {
  Message,
  MessageAvatar,
  MessageContent,
  MessageFooter,
  MessageGroup,
  MessageHeader,
  MessageTyping,
} from "@/components/agents/message";
import { MessageBubble } from "@/components/agents/message-bubble";
import { MessageScroller } from "@/components/agents/message-scroller";
import { PromptInput } from "@/components/agents/prompt-input";
import { TodoList } from "@/components/agents/todo-list";
import { ToolResult } from "@/components/agents/tool-result";
import { ThinkingShimmer } from "@/components/agents/loading-states/thinking-shimmer";
import { approveAlert, listAlerts, rejectAlert } from "../api";
import { LogoIcon } from "../components/logo";
import { streamChat, type AguiEvent, type AguiMemory } from "./chatClient";

type PlanTodo = { label: string; detail: string; done: boolean };

type Citation = { receipt_id: string; data_hash: string; source_url: string };

type Receipt = { id: string; tool: string; hash: string };

type Decision = { state: "idle" | "submitting" | "approved" | "rejected"; note: string };

const stamp = () =>
  new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

type TranscriptRow =
  | { kind: "user"; content: string; ts: string }
  | {
      kind: "answer";
      content: string;
      template: string | null;
      recipeTitle: string | null;
      citations: Citation[];
      ts: string;
    }
  | { kind: "error"; text: string; ts: string };

function planTodos(plan: Record<string, unknown>): PlanTodo[] {
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

function receiptBody(tool: string, id: string, hash: string): string {
  return `tool      ${tool}\nreceipt   ${id}\ndata_hash ${hash}`;
}

function ChatInner({ initialQuestion }: { initialQuestion?: string | null }) {
  const [draft, setDraft] = useState("");
  const [todos, setTodos] = useState<PlanTodo[]>([]);
  const [activity, setActivity] = useState<AgentActivityItem[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [rows, setRows] = useState<TranscriptRow[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [lastWatch, setLastWatch] = useState("");
  const [decision, setDecision] = useState<Decision>({ state: "idle", note: "" });
  const [memories, setMemories] = useState<AguiMemory[]>([]);
  const [runCount, setRunCount] = useState(0);
  const threadRef = useRef(crypto.randomUUID());
  const activeStepRef = useRef<string | null>(null);
  const seededRef = useRef(false);

  // A question handed over from the ⌘K palette asks itself on first mount;
  // the drawer clears the seed on close, so the panel identity stays stable.
  useEffect(() => {
    if (!initialQuestion || seededRef.current) return;
    seededRef.current = true;
    ask(initialQuestion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ask = (text: string) => {
    const question = text.trim();
    if (busy || !question) return;
    setBusy(true);
    setDegraded(false);
    setDecision({ state: "idle", note: "" });
    setMemories([]);
    setStatus("Planning");
    setDraft("");
    setTodos([]);
    setReceipts([]);
    setActivity([]);
    setRunCount((n) => n + 1);
    setRows((prev) => [
      ...prev,
      { kind: "user", content: question, ts: stamp() },
    ]);
    let seq = 0;
    const onEvent = (event: AguiEvent) => {
      if (event.type === "tool_call") {
        const input = event.input ?? {};
        const plan = (input.plan ?? input) as Record<string, unknown>;
        if (plan && typeof plan === "object") setTodos(planTodos(plan));
        const stepId = `call-${runCount}-${seq++}`;
        activeStepRef.current = stepId;
        setActivity((prev) => [
          ...prev,
          { id: stepId, type: "step", label: event.tool, status: "active" },
        ]);
      } else if (event.type === "tool_result") {
        setTodos((prev) => prev.map((t) => ({ ...t, done: true })));
        setReceipts((prev) => [
          ...prev,
          {
            id: event.receipt.id,
            tool: event.tool,
            hash: event.receipt.data_hash,
          },
        ]);
        const stepId = activeStepRef.current;
        if (stepId) {
          activeStepRef.current = null;
          setActivity((prev) =>
            prev.map((item) =>
              item.type === "step" && item.id === stepId
                ? { ...item, status: "complete" }
                : item,
            ),
          );
        }
      } else if (event.type === "message") {
        if (event.plan && typeof event.plan === "object") {
          setTodos(planTodos(event.plan as Record<string, unknown>));
        }
        if (event.memories && event.memories.length > 0) {
          setMemories(event.memories);
        }
        setLastWatch(String(event.watch_id ?? ""));
        setRows((prev) => [
          ...prev,
          {
            kind: "answer",
            content: event.content,
            template: (event.template as string | null) ?? null,
            recipeTitle: (event.recipe_title as string | null) ?? null,
            citations: event.citations ?? [],
            ts: stamp(),
          },
        ]);
      } else if (event.type === "run_finished") {
        setBusy(false);
        if (!event.ok) {
          setDegraded(true);
          setStatus("");
          setRows((prev) => [
            ...prev,
            {
              kind: "error",
              text: String(event.error ?? "stream failed"),
              ts: stamp(),
            },
          ]);
        } else {
          setStatus("Run finished");
        }
      }
    };
    void streamChat(question, onEvent, { threadId: threadRef.current });
  };

  const decide = async (kind: "approve" | "reject") => {
    setDecision({ state: "submitting", note: "Deciding" });
    try {
      const alerts = await listAlerts();
      const target = alerts.find(
        (a) => a.watch_id === lastWatch && a.status === "queued",
      );
      if (!target) {
        setDecision({ state: "idle", note: "No queued alert for this run yet" });
        return;
      }
      if (kind === "approve") await approveAlert(target.id);
      else await rejectAlert(target.id);
      setDecision({
        state: kind === "approve" ? "approved" : "rejected",
        note: kind === "approve" ? "Approved" : "Rejected",
      });
    } catch (err) {
      setDecision({
        state: "idle",
        note: `Decision failed — ${err instanceof Error ? err.message : String(err)}`,
      });
    }
  };

  return (
    <section
      aria-label="chat"
      data-beui="chat-panel"
      className="flex min-h-0 min-w-0 flex-1 flex-col"
    >
      <MessageScroller
        className="min-h-0 min-w-0 flex-1 pb-3"
        viewportClassName="overflow-x-hidden"
        busy={busy}
      >
        <MessageGroup spacing="compact" className="min-w-0">
          {rows.map((row, i) => {
            if (row.kind === "user") {
              return (
                <Message key={i} from="user">
                  <MessageAvatar>O</MessageAvatar>
                  <MessageContent>
                    <MessageHeader>
                      You
                      <span aria-hidden="true">·</span>
                      <span className="tabular-nums">{row.ts}</span>
                    </MessageHeader>
                    <MessageBubble variant="tint">{row.content}</MessageBubble>
                  </MessageContent>
                </Message>
              );
            }
            if (row.kind === "error") {
              return (
                <Message key={i} from="assistant">
                  <MessageAvatar className="bg-destructive/15 text-destructive">
                    !
                  </MessageAvatar>
                  <MessageContent>
                    <MessageHeader>
                      ARGUS
                      <span aria-hidden="true">·</span>
                      <span className="tabular-nums">{row.ts}</span>
                    </MessageHeader>
                    <MessageBubble variant="danger">{row.text}</MessageBubble>
                  </MessageContent>
                </Message>
              );
            }
            return (
              <Message key={i} from="assistant">
                <MessageAvatar className="text-cool">
                  <LogoIcon className="size-4" />
                </MessageAvatar>
                <MessageContent>
                  <MessageHeader>
                    ARGUS
                    <span aria-hidden="true">·</span>
                    <span className="tabular-nums">{row.ts}</span>
                  </MessageHeader>
                  <MessageBubble
                    variant="soft"
                    data-beui="message-bubble"
                    className="max-w-full"
                  >
                    <p>{row.content}</p>
                    {row.template && (
                      <p className="mt-1 text-muted-foreground text-xs">
                        Followed recipe{" "}
                        <b className="text-foreground/90">
                          {row.recipeTitle ?? row.template}
                        </b>
                      </p>
                    )}
                    {row.citations.length > 0 && (
                      <div aria-label="citations" className="mt-2">
                        <Citations
                          title="Receipts"
                          citations={row.citations.map((c) => ({
                            id: c.receipt_id,
                            title: `receipt ${c.receipt_id}`,
                            domain: c.source_url
                              ? new URL(c.source_url, window.location.origin).host
                              : undefined,
                            url: c.source_url || undefined,
                            icon: <ReceiptGlyph />,
                          }))}
                        />
                      </div>
                    )}
                  </MessageBubble>
                  {row.template && (
                    <MessageFooter className="mt-1 w-full">
                      <div aria-label="approval-card" className="min-w-0 w-full">
                        <ApprovalCard
                          title="Deliver the queued alert?"
                          description={
                            lastWatch
                              ? `Watch ${lastWatch} — nothing publishes without your sign-off.`
                              : "Waiting for the watch id from this run."
                          }
                          approveLabel="Approve alert"
                          status={
                            decision.state === "idle" ? "pending" : decision.state
                          }
                          onApprove={() => void decide("approve")}
                          onReject={() => void decide("reject")}
                          result={
                            decision.note ? (
                              <span data-testid="chat-decision">{decision.note}</span>
                            ) : undefined
                          }
                        />
                        {decision.note && decision.state === "idle" && (
                          <span
                            data-testid="chat-decision"
                            className="mt-1 block text-muted-foreground text-xs"
                          >
                            {decision.note}
                          </span>
                        )}
                      </div>
                    </MessageFooter>
                  )}
                </MessageContent>
              </Message>
            );
          })}
          {busy && rows[rows.length - 1]?.kind === "user" && (
            <Message from="assistant">
              <MessageAvatar className="text-cool">
                <LogoIcon className="size-4" />
              </MessageAvatar>
              <MessageContent>
                <MessageTyping label="Measuring the Earth…" />
              </MessageContent>
            </Message>
          )}
        </MessageGroup>
      </MessageScroller>

      {status && (
        <div
          data-testid="chat-status"
          className="flex h-7 shrink-0 items-center text-muted-foreground text-sm"
        >
          {busy ? (
            <ThinkingShimmer>{status}</ThinkingShimmer>
          ) : (
            <span>{status}</span>
          )}
        </div>
      )}

      {memories.length > 0 && (
        <div
          aria-label="memory-chips"
          data-testid="memory-chips"
          className="memory-row shrink-0"
        >
          <span className="memory-label">Remembered</span>
          {memories.map((m) => (
            <span
              key={m.id || m.memory}
              data-testid="memory-chip"
              className="beui-chip memory-chip"
            >
              {m.memory}
            </span>
          ))}
        </div>
      )}

      {todos.length > 0 && (
        <TodoList
          title="Plan"
          items={todos.map((t) => ({
            id: t.label,
            title: t.label,
            detail: t.detail,
            status: t.done ? "completed" : "in-progress",
          }))}
          className="min-w-0 shrink-0"
          maxHeight={130}
        />
      )}

      {activity.length > 0 && (
        <div aria-label="agent-activity" className="min-w-0 shrink-0">
          <AgentActivity
            items={activity}
            status={busy ? "working" : "complete"}
            activeLabel={status || "Working…"}
            maxHeight={150}
          />
        </div>
      )}

      {receipts.length > 0 && (
        <div className="flex min-w-0 shrink-0 flex-col gap-1.5 pt-1">
          {receipts.map((r) => (
            <div key={`${r.id}-${r.tool}`} data-testid="tool-result" className="min-w-0">
              <ToolResult
                tool={r.tool}
                title="receipt"
                status="success"
                meta={`hash ${r.hash.slice(0, 16)}`}
                maxHeight={140}
                className="min-w-0 text-xs"
                copyText={receiptBody(r.tool, r.id, r.hash)}
              >
                <pre className="overflow-x-hidden font-mono text-[11px] leading-5 break-all whitespace-pre-wrap text-muted-foreground">
                  {receiptBody(r.tool, r.id, r.hash)}
                </pre>
              </ToolResult>
            </div>
          ))}
        </div>
      )}

      <div
        role="search"
        aria-label="chat-prompt"
        data-beui="prompt-input"
        className="mt-3 min-w-0 shrink-0 border-border/60 border-t pt-3"
      >
        <PromptInput
          value={draft}
          onValueChange={setDraft}
          onSubmit={ask}
          loading={busy}
          minRows={2}
          maxRows={5}
          placeholder="Ask the Earth anything — e.g. is the Niger delta flooding?"
          aria-label="chat question"
          data-beui="input"
          disabled={false}
        />
      </div>

      {degraded && (
        <p data-testid="chat-degraded" className="note note--warn mt-2 shrink-0">
          Chat is unavailable; the globe, watchlist, and alert panels keep working.
        </p>
      )}
    </section>
  );
}

function ReceiptGlyph() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
    >
      <path d="M4 1.5h8v13l-2-1.4-2 1.4-2-1.4-2 1.4v-13z" />
      <path d="M6 5.5h4M6 8h4M6 10.5h2" />
    </svg>
  );
}

export default function ChatPanel({
  initialQuestion,
}: {
  initialQuestion?: string | null;
} = {}) {
  // Build-time kill-switch: the panel mounts only when chat is enabled;
  // panels render regardless.
  if (import.meta.env.VITE_CHAT_ENABLED === "0") return null;
  return <ChatInner initialQuestion={initialQuestion} />;
}
