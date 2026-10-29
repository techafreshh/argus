/** SSE client for the additive AG-UI bridge (POST /api/ag-ui).
 *
 * Reads `data: {json}` frames into a typed event union. Any transport
 * failure surfaces as a terminal `run_finished` error event so the panel
 * can degrade to a panels-only notice instead of hanging.
 */

export type AguiToolReceipt = {
  id: string;
  tool: string;
  params: Record<string, unknown>;
  source_url: string;
  data_hash: string;
  tokens: number;
};

export type AguiCitation = {
  receipt_id: string;
  data_hash: string;
  source_url: string;
};

export type AguiEvent =
  | { type: "run_started"; threadId: string; question: string; agent: string }
  | { type: "tool_call"; tool: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool: string; receipt: AguiToolReceipt }
  | {
      type: "message";
      role: string;
      content: string;
      template?: string | null;
      plan?: Record<string, unknown>;
      watch_id?: string;
      receipt_id?: string;
      citations?: AguiCitation[];
    }
  | { type: "run_finished"; ok: boolean; error?: string; [key: string]: unknown };

export interface ChatRunOptions {
  bbox?: [number, number, number, number];
  region?: Record<string, unknown>;
  cadence?: string;
  threadId?: string;
  signal?: AbortSignal;
}

function errorFinish(message: string): AguiEvent {
  return { type: "run_finished", ok: false, error: message };
}

export async function streamChat(
  question: string,
  onEvent: (event: AguiEvent) => void,
  options: ChatRunOptions = {},
): Promise<void> {
  const body: Record<string, unknown> = { question };
  if (options.region) body.region = options.region;
  if (options.bbox) body.bbox = options.bbox;
  if (options.cadence) body.cadence = options.cadence;
  if (options.threadId) body.threadId = options.threadId;
  let res: Response;
  try {
    res = await fetch("/api/ag-ui", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: options.signal,
    });
  } catch (err) {
    onEvent(errorFinish(`chat transport failed: ${String(err)}`));
    return;
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (!res.ok || !contentType.includes("text/event-stream")) {
    // Disabled flag or handshake JSON: degrade without breaking panels.
    try {
      const payload = (await res.json()) as { disabled?: boolean };
      if (payload && payload.disabled) {
        onEvent(errorFinish("chat disabled on server (panels-only mode)"));
        return;
      }
    } catch {
      /* fall through to generic error */
    }
    onEvent(errorFinish(`chat unavailable: HTTP ${res.status}`));
    return;
  }
  if (!res.body) {
    onEvent(errorFinish("chat stream has no body"));
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (chunk: string) => {
    buffer += chunk;
    let idx = buffer.indexOf("\n\n");
    while (idx >= 0) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of frame.split("\n")) {
        const text = line.trim();
        if (!text.startsWith("data:")) continue;
        const payload = text.slice("data:".length).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload) as AguiEvent);
        } catch {
          /* ignore malformed frames; the terminal frame still lands */
        }
      }
      idx = buffer.indexOf("\n\n");
    }
  };
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      dispatch(decoder.decode(value, { stream: true }));
    }
    dispatch(decoder.decode());
    if (buffer.trim()) {
      try {
        onEvent(JSON.parse(buffer.trim()) as AguiEvent);
      } catch {
        /* trailing bytes without a frame boundary */
      }
    }
  } catch (err) {
    onEvent(errorFinish(`chat stream failed: ${String(err)}`));
  }
}
