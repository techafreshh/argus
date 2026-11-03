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

/** Raised when a gated pipeline action needs a GitHub sign-in. */
export class AuthError extends Error {
  constructor() {
    super("Sign in with GitHub to run pipeline actions.");
    this.name = "AuthError";
  }
}

export function isAuthError(err: unknown): boolean {
  return err instanceof Error && err.message.includes("Sign in with GitHub");
}

async function checked<T>(res: Response): Promise<T> {
  const body = (await asJson(res)) as T;
  if (!res.ok) {
    if (res.status === 401) throw new AuthError();
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(body)}`);
  }
  return body;
}

export interface SpendCall {
  id: string;
  operation: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_credits: number;
  created_at: string;
}

export interface SpendLedger {
  total_credits: number;
  calls: SpendCall[];
}

export interface ReportCard {
  id: string;
  watch_id: string;
  alert_id: string;
  headline: string;
  hectares: number;
  counts: Record<string, unknown>;
  confidence: number;
  before_url: string;
  after_url: string;
  before_path: string;
  after_path: string;
  sources: string[];
  receipts: Receipt[];
}

export interface EvalStatus {
  hits: number;
  misses: number;
  total: number;
  precision: number;
  total_credits: number;
  probes: {
    replay: unknown[];
    false_positive: unknown[];
    novel_question: unknown[];
    status: string;
  };
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

export async function getSpend(): Promise<SpendLedger> {
  const res = await fetch("/api/spend");
  return checked<SpendLedger>(res);
}

export async function getReport(id: string): Promise<ReportCard> {
  const res = await fetch(`/api/reports/${id}`);
  return checked<ReportCard>(res);
}

export async function getEvalStatus(): Promise<EvalStatus> {
  const res = await fetch("/api/eval/status");
  return checked<EvalStatus>(res);
}

export interface EnsoAnalog {
  month: string;
  year: number;
  similarity: number;
  distance?: number;
}

export interface SubWatcher {
  id: string;
  [key: string]: unknown;
}

export interface EnsoStatus {
  phase: string;
  intensity: string;
  trajectory: string;
  month: string;
  analogs: EnsoAnalog[];
  subwatchers: SubWatcher[];
  [key: string]: unknown;
}

export interface SstFrame {
  month: string;
  anomaly: number;
  phase: string;
}

export interface SstManifest {
  frames: SstFrame[];
}

export async function getSstManifest(): Promise<SstManifest> {
  const res = await fetch("/sst/manifest.json");
  const raw = await checked<Record<string, unknown>>(res);
  const frames = Array.isArray(raw["frames"])
    ? (raw["frames"] as SstFrame[])
    : [];
  return {
    frames: frames.map((f) => ({
      month: String(f.month ?? ""),
      anomaly: Number(f.anomaly ?? 0),
      phase: String(f.phase ?? ""),
    })),
  };
}

export async function getEnsoStatus(): Promise<EnsoStatus> {
  const res = await fetch("/api/enso/status");
  const raw = await checked<Record<string, unknown>>(res);
  const subs =
    (raw["subwatchers"] as SubWatcher[] | undefined) ??
    (raw["subWatchers"] as SubWatcher[] | undefined) ??
    (raw["sub_watchers"] as SubWatcher[] | undefined) ??
    [];
  const analogs = Array.isArray(raw["analogs"])
    ? (raw["analogs"] as EnsoAnalog[])
    : [];
  return {
    ...raw,
    phase: String(raw["phase"] ?? ""),
    intensity: String(raw["intensity"] ?? ""),
    trajectory: String(raw["trajectory"] ?? ""),
    month: String(raw["month"] ?? ""),
    analogs,
    subwatchers: Array.isArray(subs) ? subs : [],
  } as EnsoStatus;
}

/* --- Cookbook presets, notification channels, toolbox, decision log --- */

export interface Preset {
  id: string;
  title: string;
  blurb: string;
  sensor: string;
  question: string;
  cadence: string;
  region_label: string;
  bbox: [number, number, number, number];
}

export interface Channel {
  id: string;
  kind: string;
  target: string;
  watch_id: string | null;
  status: string;
  created_at: string;
}

export interface Delivery {
  id: string;
  alert_id: string | null;
  channel_id: string;
  status: string;
  http_status: number | null;
  error: string;
  attempts: number;
  created_at: string;
}

export interface TraceStep {
  id: string;
  tool: string;
  params: Record<string, unknown>;
  source_url: string;
  data_hash: string;
  created_at: string;
}

export interface ReportTrace {
  report_id: string;
  route: {
    template: string | null;
    recipe_id: string | null;
    recipe_title: string | null;
    recipe_blurb: string | null;
    question: string | null;
  };
  watch: {
    id: string;
    name: string;
    region: unknown;
    question: string;
    template: string;
    cadence: string;
    status: string;
  } | null;
  alert: {
    id: string;
    title: string;
    confidence: number;
    status: string;
    evidence: Record<string, unknown>;
    created_at: string;
    decided_at: string | null;
  };
  steps: TraceStep[];
  deliveries: Delivery[];
  predictions: Record<string, unknown>[];
}

export interface ToolboxSource {
  id: string;
  name: string;
  kind: string;
  url: string;
  coverage: string;
  cadence: string;
  auth: string;
  used_by: string[];
  status: string;
}

export async function getPresets(): Promise<Preset[]> {
  const res = await fetch("/api/presets");
  const body = await checked<{ presets: Preset[] }>(res);
  return body.presets;
}

export async function listChannels(): Promise<Channel[]> {
  const res = await fetch("/api/channels");
  return checked<Channel[]>(res);
}

export async function createChannel(input: {
  target: string;
  secret?: string;
  watch_id?: string;
}): Promise<Channel> {
  const res = await fetch("/api/channels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return checked<Channel>(res);
}

export async function deleteChannel(id: string): Promise<{ ok: boolean }> {
  const res = await fetch(`/api/channels/${id}`, { method: "DELETE" });
  return checked<{ ok: boolean }>(res);
}

export async function testChannel(
  id: string,
): Promise<{ ok: boolean; http_status: number | null; error: string }> {
  const res = await fetch(`/api/channels/${id}/test`, { method: "POST" });
  return checked(res);
}

export async function getReportTrace(reportId: string): Promise<ReportTrace> {
  const res = await fetch(`/api/reports/${reportId}/trace`);
  return checked<ReportTrace>(res);
}

export async function getToolbox(): Promise<ToolboxSource[]> {
  const res = await fetch("/api/toolbox");
  const body = await checked<{ sources: ToolboxSource[] }>(res);
  return body.sources;
}
