import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import AnalogTimeline from "./panels/AnalogTimeline";
import ReceiptsPanel from "./panels/ReceiptsPanel";
import ReportsView from "./panels/ReportsView";
import SpendEvalPanel from "./panels/SpendEvalPanel";
import {
  AnimatedBadge,
  AnimatedSidebar,
  Card,
  DynamicIsland,
  TextAnimation,
  ThemeToggle,
} from "./beui";
import {
  approveAlert,
  createWatch,
  getEnsoStatus,
  listAlerts,
  listReceipts,
  listWatches,
  previewTemplate,
  rejectAlert,
  type AlertItem,
  type AskPreview,
  type EnsoStatus,
  type Receipt,
  type Watch,
} from "./api";

const BLANK = { minLon: "24", minLat: "-12.5", maxLon: "30", maxLat: "-8" };

function SstCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let frame = 0;
    let alive = true;
    const W = (canvas.width = 480);
    const H = (canvas.height = 220);
    const draw = () => {
      if (!alive) return;
      frame += 1;
      const img = ctx.createImageData(W, H);
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          const i = (y * W + x) * 4;
          const wave =
            Math.sin((x / W) * Math.PI * 4 + frame / 12) *
            Math.cos((y / H) * Math.PI * 3 + frame / 20);
          const v = Math.max(0, Math.min(1, 0.5 + wave * 0.35 + (y / H - 0.5) * 0.4));
          img.data[i] = Math.round(40 + v * 200);
          img.data[i + 1] = Math.round(90 + v * 90);
          img.data[i + 2] = Math.round(200 - v * 130);
          img.data[i + 3] = 255;
        }
      }
      ctx.putImageData(img, 0, 0);
      requestAnimationFrame(draw);
    };
    draw();
    return () => {
      alive = false;
    };
  }, []);
  return <canvas ref={ref} aria-label="SST animation" style={{ width: "100%", display: "block" }} />;
}

function GlobeView() {
  const divRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = divRef.current;
    if (!el) return;
    let map: maplibregl.Map | null = null;
    try {
      // maplibre-gl v5 globe projection; empty style keeps the room offline-safe.
      map = new maplibregl.Map({
        container: el,
        style: { version: 8, sources: {}, layers: [] },
        center: [20, 0],
        zoom: 1.2,
      });
      const globe = { type: "globe" as const };
      try {
        (map as unknown as { setProjection(p: unknown): void }).setProjection(globe);
      } catch {
        /* older renderers ignore globe projection */
      }
    } catch {
      /* WebGL unavailable in headless probes: canvas fallback below still shows */
    }
    return () => {
      try {
        map?.remove();
      } catch {
        /* noop */
      }
    };
  }, []);
  return (
    <section aria-label="globe">
      <h2>Globe</h2>
      <div ref={divRef} data-testid="globe-map" style={{ height: 260 }} />
      <SstCanvas />
    </section>
  );
}

function WatchlistManager({ onChanged }: { onChanged: () => void }) {
  const [name, setName] = useState("Gulf of Guinea watch");
  const [bbox, setBbox] = useState(BLANK);
  const [question, setQuestion] = useState("Is vegetation declining?");
  const [cadence, setCadence] = useState("daily");
  const [preview, setPreview] = useState<AskPreview | null>(null);
  const [status, setStatus] = useState("");

  const coords = () => [
    Number(bbox.minLon),
    Number(bbox.minLat),
    Number(bbox.maxLon),
    Number(bbox.maxLat),
  ];

  const doPreview = async () => {
    setStatus("previewing…");
    try {
      const [a, b, c, d] = coords();
      const p = await previewTemplate(question, { type: "bbox", coords: [a, b, c, d] }, cadence);
      setPreview(p);
      setStatus(p.template ? `template: ${p.template}` : "template: unrouted");
    } catch (err) {
      setStatus(`preview failed: ${String(err)}`);
    }
  };

  const doCreate = async () => {
    setStatus("creating…");
    try {
      const [a, b, c, d] = coords();
      await createWatch({
        name,
        region: { type: "bbox", coords: [a, b, c, d] },
        question,
        cadence,
      });
      setStatus("watch created (201)");
      onChanged();
    } catch (err) {
      setStatus(`create failed: ${String(err)}`);
    }
  };

  return (
    <section aria-label="watchlist">
      <h2>Watchlist manager</h2>
      <label>
        Name <input aria-label="watch name" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <div>
        {(
          [
            ["minLon", "Min lon"],
            ["minLat", "Min lat"],
            ["maxLon", "Max lon"],
            ["maxLat", "Max lat"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} style={{ marginRight: 8 }}>
            {label}{" "}
            <input
              aria-label={label}
              value={bbox[key]}
              onChange={(e) => setBbox({ ...bbox, [key]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <label>
        Question{" "}
        <input aria-label="watch question" value={question} onChange={(e) => setQuestion(e.target.value)} />
      </label>
      <label>
        Cadence{" "}
        <select aria-label="watch cadence" value={cadence} onChange={(e) => setCadence(e.target.value)}>
          <option value="daily">daily</option>
          <option value="weekly">weekly</option>
        </select>
      </label>
      <div>
        <button type="button" onClick={doPreview}>
          Preview template
        </button>{" "}
        <button type="button" onClick={doCreate}>
          Add watch
        </button>
      </div>
      {preview && (
        <pre data-testid="template-preview">{JSON.stringify(preview, null, 2)}</pre>
      )}
      {status && <p data-testid="watch-status">{status}</p>}
    </section>
  );
}

function AlertFeed({ reloadKey }: { reloadKey: number }) {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [evidence, setEvidence] = useState<Record<string, Receipt[]>>({});
  const [note, setNote] = useState("");

  const refresh = useCallback(async () => {
    try {
      setAlerts(await listAlerts());
    } catch (err) {
      setNote(`alerts failed: ${String(err)}`);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, reloadKey]);

  const showEvidence = async (a: AlertItem) => {
    try {
      const receipts = await listReceipts(a.watch_id);
      setEvidence((prev) => ({ ...prev, [a.id]: receipts }));
    } catch (err) {
      setNote(`evidence failed: ${String(err)}`);
    }
  };

  const decide = async (a: AlertItem, kind: "approve" | "reject") => {
    try {
      if (kind === "approve") await approveAlert(a.id);
      else await rejectAlert(a.id);
      await refresh();
    } catch (err) {
      setNote(`decision failed: ${String(err)}`);
    }
  };

  return (
    <section aria-label="alerts">
      <h2>Alert feed</h2>
      {note && <p>{note}</p>}
      <ul>
        {alerts.map((a) => (
          <li key={a.id} data-testid={`alert-${a.id}`}>
            <strong>{a.title}</strong> — confidence {a.confidence} — status {a.status}
            <details>
              <summary>Evidence</summary>
              <pre>{JSON.stringify(a.evidence, null, 2)}</pre>
              {(evidence[a.id] ?? []).map((r) => (
                <p key={r.id}>
                  receipt {r.tool} {r.data_hash} tokens={r.tokens ?? r.token_usage}
                </p>
              ))}
              <button type="button" onClick={() => void showEvidence(a)}>
                Load evidence
              </button>
            </details>
            <button
              type="button"
              disabled={a.status !== "queued"}
              onClick={() => void decide(a, "approve")}
            >
              Approve
            </button>{" "}
            <button type="button" disabled={a.status !== "queued"} onClick={() => void decide(a, "reject")}>
              Reject
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

const ChatPanel = lazy(() => import("./chat/ChatPanel"));

function badgeStatus(phase: string): "info" | "success" | "warning" | "neutral" {
  if (phase === "El Nino") return "warning";
  if (phase === "La Nina") return "info";
  if (phase === "Neutral") return "success";
  return "neutral";
}

export default function App() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [enso, setEnso] = useState<EnsoStatus | null>(null);
  const [ensoNote, setEnsoNote] = useState("");
  const [lastTick, setLastTick] = useState("");

  const refresh = useCallback(async () => {
    try {
      const list = await listWatches();
      setWatches(list);
      const stamps = list
        .map((w) => (w as unknown as { updated_at?: unknown }).updated_at)
        .filter((v): v is string => typeof v === "string" && v.length > 0)
        .sort();
      setLastTick(stamps.length > 0 ? stamps[stamps.length - 1] : new Date().toISOString());
    } catch {
      /* room stays usable offline */
      setLastTick((prev) => prev || new Date().toISOString());
    }
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const status = await getEnsoStatus();
        if (!alive) return;
        setEnso(status);
      } catch (err) {
        if (!alive) return;
        setEnsoNote(`enso failed: ${String(err)}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const subwatchers = enso?.subwatchers ?? [];

  return (
    <div className="beui-shell">
      <AnimatedSidebar />
      <main className="beui-main">
        <TextAnimation text="ARGUS Control Room" />
        <div>
          <ThemeToggle />
        </div>
        <DynamicIsland>
          <span>
            watches {watches.length} · last tick {lastTick || "—"}
          </span>
        </DynamicIsland>
        {enso ? (
          <AnimatedBadge status={badgeStatus(enso.phase)} testId="enso-badge">
            ENSO {enso.phase} · {enso.intensity} · {enso.trajectory} · {enso.month}
          </AnimatedBadge>
        ) : (
          <AnimatedBadge status="loading" testId="enso-badge">
            ENSO loading…
          </AnimatedBadge>
        )}
        {ensoNote && <p>{ensoNote}</p>}
        <div aria-label="sub-watchers">
          {subwatchers.map((s) => (
            <span key={String(s.id)} className="beui-chip" data-testid={`chip-${String(s.id)}`}>
              {String(s.id)}
            </span>
          ))}
        </div>
        <Card label="globe" id="section-globe">
          <div className="beui-globe-wrap">
            <GlobeView />
          </div>
        </Card>
        <Card label="watchlist" id="section-watchlist">
          <WatchlistManager onChanged={() => void refresh()} />
        </Card>
        <Card label="watches" id="section-watches">
          <section aria-label="watches">
            <h2>Watches ({watches.length})</h2>
            <ul>
              {watches.map((w) => (
                <li key={w.id}>
                  {w.name} — {w.template} — {w.cadence}
                </li>
              ))}
            </ul>
          </section>
        </Card>
        <Card label="alerts" id="section-alerts">
          <AlertFeed reloadKey={reloadKey} />
        </Card>
        <Card label="chat" id="section-chat">
          <Suspense fallback={null}>
            <ChatPanel />
          </Suspense>
        </Card>
        <Card label="receipts" id="section-receipts">
          <ReceiptsPanel />
        </Card>
        <Card label="reports" id="section-reports">
          <ReportsView />
        </Card>
        <Card label="spend-eval" id="section-spend-eval">
          <SpendEvalPanel />
        </Card>
        <Card label="analog-timeline" id="section-analog-timeline">
          <AnalogTimeline />
        </Card>
      </main>
    </div>
  );
}
