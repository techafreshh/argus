import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import AnalogTimeline from "./panels/AnalogTimeline";
import SstGlobe from "./panels/SstGlobe";
import ReceiptsPanel from "./panels/ReceiptsPanel";
import ReportsView from "./panels/ReportsView";
import SpendEvalPanel from "./panels/SpendEvalPanel";
import CommandPalette from "./palette/CommandPalette";
import "./palette/palette.css";
import { Card, EnsoReadout, LoopIsland, Sidebar } from "./beui";
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

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function utcClock(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`;
}

function fmtConfidence(v: number): string {
  return `${Math.round(v <= 1 ? v * 100 : v)}%`;
}

function GlobeView() {
  return (
    <section aria-label="globe">
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
  const [failed, setFailed] = useState(false);
  const [heatUp, setHeatUp] = useState(false);

  const coords = () => [
    Number(bbox.minLon),
    Number(bbox.minLat),
    Number(bbox.maxLon),
    Number(bbox.maxLat),
  ];

  const doPreview = async () => {
    setStatus("Previewing");
    setFailed(false);
    try {
      const [a, b, c, d] = coords();
      const p = await previewTemplate(question, { type: "bbox", coords: [a, b, c, d] }, cadence);
      setPreview(p);
      setStatus("");
    } catch (err) {
      setStatus(`Preview failed — ${errText(err)}`);
      setFailed(true);
    }
  };

  const doCreate = async () => {
    setStatus("Creating");
    setFailed(false);
    try {
      const [a, b, c, d] = coords();
      await createWatch({
        name,
        region: { type: "bbox", coords: [a, b, c, d] },
        question,
        cadence,
      });
      setStatus("Watch created — first acquisition slot scheduled");
      onChanged();
    } catch (err) {
      setStatus(`Create failed — ${errText(err)}`);
      setFailed(true);
    }
  };

  return (
    <section aria-label="watchlist" data-beui="card">
      <h2>Watchlist manager</h2>
      <div className="form-grid">
        <label className="field span-2">
          <span className="field-label">Name</span>
          <input
            className="input"
            aria-label="watch name"
            data-beui="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="field span-2">
          <span className="field-label">Question</span>
          <input
            className="input"
            aria-label="watch question"
            data-beui="input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </label>
        {(
          [
            ["minLon", "Min lon"],
            ["minLat", "Min lat"],
            ["maxLon", "Max lon"],
            ["maxLat", "Max lat"],
          ] as const
        ).map(([key, label]) => (
          <label className="field" key={key}>
            <span className="field-label">{label}</span>
            <input
              className="input"
              aria-label={label}
              data-beui="input"
              value={bbox[key]}
              onChange={(e) => setBbox({ ...bbox, [key]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <div className="form-row">
        <label className="field">
          <span className="field-label">Cadence</span>
          <select
            className="input"
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
        <div className="field">
          <span className="field-label">Heat-up</span>
          <button
            type="button"
            role="switch"
            aria-checked={heatUp}
            aria-label="cadence heat-up"
            data-beui="switch"
            onClick={() => setHeatUp((v) => !v)}
          >
            {heatUp ? "On" : "Off"}
          </button>
        </div>
      </div>
      {heatUp && (
        <p className="note" data-testid="cadence-heatup">
          Heat-up re-prioritizes the schedule when a signal crosses threshold (demo
          surface — no scheduler change yet).
        </p>
      )}
      <p data-testid="template-preview-hint" className="note">
        {preview?.template
          ? `Routed to ${preview.template} · ${cadence} cadence`
          : `No template matched · ${cadence} cadence`}
      </p>
      <div className="form-row">
        <button type="button" className="btn btn--quiet" onClick={doPreview}>
          Preview template
        </button>
        <button type="button" className="btn btn--primary" onClick={doCreate}>
          Add watch
        </button>
      </div>
      {preview && (
        <pre className="dump" data-testid="template-preview">
          {JSON.stringify(preview, null, 2)}
        </pre>
      )}
      {status && (
        <p data-testid="watch-status" className={failed ? "note note--error" : "note"}>
          {status}
        </p>
      )}
    </section>
  );
}

function AlertFeed({ reloadKey }: { reloadKey: number }) {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [evidence, setEvidence] = useState<Record<string, Receipt[]>>({});
  const [note, setNote] = useState("");
  const [failed, setFailed] = useState(false);
  const [toasts, setToasts] = useState<string[]>([]);

  const refresh = useCallback(async () => {
    try {
      setAlerts(await listAlerts());
      setNote("");
      setFailed(false);
    } catch (err) {
      setNote(`Alerts unavailable — ${errText(err)}`);
      setFailed(true);
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
      setNote(`Evidence unavailable — ${errText(err)}`);
      setFailed(true);
    }
  };

  const decide = async (a: AlertItem, kind: "approve" | "reject") => {
    try {
      if (kind === "approve") await approveAlert(a.id);
      else await rejectAlert(a.id);
      setAlerts((prev) => prev.filter((x) => x.id !== a.id));
      setToasts((prev) => [...prev, `${kind === "approve" ? "Approved" : "Rejected"} ${a.id}`]);
      await refresh();
    } catch (err) {
      setNote(`Decision failed — ${errText(err)}`);
      setFailed(true);
    }
  };

  const queued = alerts.filter((a) => a.status === "queued");

  return (
    <section aria-label="alerts">
      <h2>Alert feed</h2>
      {note && (
        <p data-testid="alert-note" className={failed ? "note note--error" : "note"}>
          {note}
        </p>
      )}
      {queued.length === 0 && !note && <p className="note">No queued alerts</p>}
      <div data-beui="notification-stack" aria-label="queued-alerts">
        <ul className="activity-list" style={{ gap: 10 }}>
          {queued.map((a) => (
            <li
              key={a.id}
              data-testid={`alert-${a.id}`}
              data-beui="approval-card"
              aria-label="approval-card"
              className="alert-card"
              style={{ listStyle: "none" }}
            >
              <div className="alert-card-head">
                <span className="alert-card-title">{a.title}</span>
                <span className="alert-conf">{fmtConfidence(a.confidence)}</span>
              </div>
              <div className="alert-evidence">
                {Object.entries(a.evidence).length === 0 && (
                  <span className="alert-evidence-row">no evidence rows</span>
                )}
                {Object.entries(a.evidence).map(([k, v]) => (
                  <span key={k} className="alert-evidence-row">
                    <b>{k}</b> {typeof v === "string" ? v : JSON.stringify(v)}
                  </span>
                ))}
                {(evidence[a.id] ?? []).map((r) => (
                  <span key={r.id} className="alert-evidence-row">
                    <b>{r.tool}</b> {r.data_hash} tokens {r.tokens ?? r.token_usage}
                  </span>
                ))}
              </div>
              <div className="alert-actions">
                <button type="button" className="btn btn--primary" disabled={a.status !== "queued"} onClick={() => void decide(a, "approve")}>
                  Approve
                </button>
                <button type="button" className="btn btn--danger" disabled={a.status !== "queued"} onClick={() => void decide(a, "reject")}>
                  Reject
                </button>
                <button type="button" className="btn btn--quiet" onClick={() => void showEvidence(a)}>
                  Load evidence
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <div data-beui="animated-toast-stack" aria-label="toast-stack">
        {toasts.map((t) => (
          <div key={t} data-testid="decision-toast" className="toast">
            {t}
          </div>
        ))}
      </div>
    </section>
  );
}

const ChatPanel = lazy(() => import("./chat/ChatPanel"));

export default function App() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [enso, setEnso] = useState<EnsoStatus | null>(null);
  const [ensoNote, setEnsoNote] = useState("");
  const [lastTick, setLastTick] = useState("");
  const [clock, setClock] = useState(() => utcClock(new Date().toISOString()));

  useEffect(() => {
    const t = setInterval(() => setClock(utcClock(new Date().toISOString())), 1000);
    return () => clearInterval(t);
  }, []);

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
        setEnsoNote(`ENSO readout unavailable — ${errText(err)}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const subwatchers = enso?.subwatchers ?? [];

  return (
    <div className="beui-shell">
      <Sidebar />
      <main className="beui-main">
        <header className="beui-topbar">
          <h1 className="beui-title">Control room</h1>
          <CommandPalette />
          <span className="beui-clock">{clock}</span>
        </header>
        <div className="beui-strip">
          <LoopIsland count={watches.length} lastTick={utcClock(lastTick)} />
          <EnsoReadout enso={enso} />
        </div>
        {subwatchers.length > 0 && (
          <div aria-label="sub-watchers" className="beui-strip">
            {subwatchers.map((s) => (
              <span key={String(s.id)} className="beui-chip" data-testid={`chip-${String(s.id)}`}>
                {String(s.id)}
              </span>
            ))}
          </div>
        )}
        {ensoNote && <p className="note note--warn">{ensoNote}</p>}
        <Card label="globe" id="section-globe">
          <h2>Globe</h2>
          <GlobeView />
        </Card>
        <Card label="watchlist" id="section-watchlist">
          <WatchlistManager onChanged={() => void refresh()} />
        </Card>
        <Card label="watches" id="section-watches">
          <section aria-label="watches">
            <h2>Active watches ({watches.length})</h2>
            {watches.length === 0 && <p className="note">No watches yet — add one above</p>}
            <ul className="activity-list">
              {watches.map((w) => (
                <li key={w.id} className="receipt-line">
                  <b>{w.name}</b> {w.template} · {w.cadence}
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
