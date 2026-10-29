/** Typed fetch client for the ARGUS REST spine (issues #6/#9/#10/#11). */

export interface BboxRegion {
  type: "bbox";
  coords: [number, number, number, number];
}

export interface WatchCreate {
  name: string;
  region: BboxRegion;
  question: string;
  cadence: string;
}

export interface Watch {
  id: string;
  name: string;
  region: unknown;
  question: string;
  template: string;
  cadence: string;
  status: string;
}

export interface AskPreview {
  ok?: boolean;
  template?: string | null;
  plan?: Record<string, unknown>;
  answer?: string;
  missing?: string[];
  adjacent?: string[];
  watch_id?: string;
  receipt_id?: string;
}

export interface AlertItem {
  id: string;
  watch_id: string;
  report_id: string | null;
  title: string;
  confidence: number;
  status: string;
  evidence: Record<string, unknown>;
  created_at: string;
  decided_at: string | null;
}

export interface Receipt {
  id: string;
  watch_id: string;
  tool: string;
  params: Record<string, unknown>;
  source_url: string;
  data_hash: string;
  token_usage: number;
  tokens: number;
  created_at: string;
}

async function asJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function checked<T>(res: Response): Promise<T> {
  const body = (await asJson(res)) as T;
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(body)}`);
  }
  return body;
}

export async function previewTemplate(
  question: string,
  region: Record<string, unknown>,
  cadence: string,
): Promise<AskPreview> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, region, cadence }),
  });
  return checked<AskPreview>(res);
}

export async function createWatch(payload: WatchCreate): Promise<Watch & { plan?: unknown; template?: string }> {
  const res = await fetch("/api/watches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return checked(res);
}

export async function listWatches(): Promise<Watch[]> {
  const res = await fetch("/api/watches");
  return checked<Watch[]>(res);
}

export async function listAlerts(): Promise<AlertItem[]> {
  const res = await fetch("/api/alerts");
  return checked<AlertItem[]>(res);
}

export async function approveAlert(id: string): Promise<{ ok: boolean; status: string }> {
  const res = await fetch(`/api/alerts/${id}/approve`, { method: "POST" });
  return checked(res);
}

export async function rejectAlert(id: string): Promise<{ ok: boolean; status: string }> {
  const res = await fetch(`/api/alerts/${id}/reject`, { method: "POST" });
  return checked(res);
}

export async function listReceipts(watchId: string): Promise<Receipt[]> {
  const res = await fetch(`/api/watches/${watchId}/receipts`);
  return checked<Receipt[]>(res);
}

/** Static in-bundle fixture: ENSO badge + sub-watcher chips (no live backend). */
export const ENSO_FIXTURE = {
  phase: "La Nina",
  index: -0.8,
  updated: "2024-01",
  source: "fixture",
} as const;

export const SUB_WATCHERS = [
  { id: "oisst", label: "OISST SST", detail: "daily anomaly" },
  { id: "chirps", label: "CHIRPS rain", detail: "dekadal" },
  { id: "firms", label: "FIRMS fires", detail: "near real-time" },
  { id: "s2", label: "Sentinel-2", detail: "optical tiles" },
] as const;
