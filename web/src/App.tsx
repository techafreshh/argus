import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import AnalogTimeline from "./panels/AnalogTimeline";
import SstGlobe from "./panels/SstGlobe";
import ReceiptsPanel from "./panels/ReceiptsPanel";
import ReportsView from "./panels/ReportsView";
import SpendEvalPanel from "./panels/SpendEvalPanel";
import CommandPalette from "./palette/CommandPalette";
import "./palette/palette.css";
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

function GlobeView() {
  return (
    <section aria-label="globe">
      <h2>Globe</h2>
      <SstGlobe />
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
  const [heatUp, setHeatUp] = useState(false);

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
    <section aria-label="watchlist" data-beui="card">
      <h2>Watchlist manager</h2>
      <label>
        Name{" "}
        <input
          aria-label="watch name"
          data-beui="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
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
              data-beui="input"
              value={bbox[key]}
              onChange={(e) => setBbox({ ...bbox, [key]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <label>
        Question{" "}
        <input
          aria-label="watch question"
          data-beui="input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
      </label>
      <label>
        Cadence{" "}
        <select
          aria-label="watch cadence"
          role="combobox"
          data-beui="combobox"
          value={cadence}
          onChange={(e) => setCadence(e.target.value)}
        >
          <option value="daily">daily</option>
          <option value="weekly">weekly</option>
        </select>
      </label>
      <p data-testid="template-preview-hint">
        Template preview: {preview?.template ?? "unrouted"} · {cadence} cadence
      </p>
      <div>
        <button
          type="button"
          role="switch"
          aria-checked={heatUp}
          aria-label="cadence heat-up"
          data-beui="switch"
          onClick={() => setHeatUp((v) => !v)}
        >
          Heat-up {heatUp ? "on" : "off"}
        </button>
        {heatUp && (
          <p data-testid="cadence-heatup">
            Heat-up: {cadence} cadence warms the scheduler window (display only).
          </p>
        )}
      </div>
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
  const [toasts, setToasts] = useState<string[]>([]);

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
    setNote("deciding…");
    try {
      if (kind === "approve") await approveAlert(a.id);
      else await rejectAlert(a.id);
      setAlerts((prev) => prev.filter((x) => x.id !== a.id));
      setToasts((prev) => [...prev, `${kind}d ${a.id}`]);
      setNote(`${kind}d ${a.id}`);
      await refresh();
    } catch (err) {
      setNote(`decision failed: ${String(err)}`);
    }
  };

  const queued = alerts.filter((a) => a.status === "queued");

  return (
    <section aria-label="alerts">
      <h2>Alert feed</h2>
      {note && <p data-testid="alert-note">{note}</p>}
      <div data-beui="notification-stack" aria-label="queued-alerts">
        <ul>
          {queued.map((a) => (
            <li
              key={a.id}
              data-testid={`alert-${a.id}`}
              data-beui="approval-card"
              aria-label="approval-card"
            >
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
      </div>
      <div data-beui="animated-toast-stack" aria-label="toast-stack">
        {toasts.map((t) => (
          <div key={t} data-testid="decision-toast">
            {t}
          </div>
        ))}
      </div>
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
        <CommandPalette />
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
