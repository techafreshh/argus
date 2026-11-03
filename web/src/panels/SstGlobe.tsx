import { useCallback, useEffect, useState } from "react";
import type { Map as MlMap } from "maplibre-gl";
import GlobeMap from "../components/map/GlobeMap";
import { getSstManifest, type SstFrame } from "../api";

/** Nino3.4 overlay corners: [[-170,5],[-120,5],[-120,-5],[-170,-5]]. */
const SST_COORDS: [[number, number], [number, number], [number, number], [number, number]] = [
  [-170, 5],
  [-120, 5],
  [-120, -5],
  [-170, -5],
];

const FRAME_MS = 125;

/** Phase color follows the room rule: cool cyan = La Nina, warm amber = El Nino. */
function phaseColor(phase: string): string {
  if (phase === "El Nino") return "var(--warm)";
  if (phase === "La Nina") return "var(--cool)";
  return "var(--foreground)";
}

function frameUrl(month: string): string {
  return `/sst/frame-${month}.png`;
}

/** Monthly SST-anomaly globe: pre-rendered frames over the Nino3.4 band. */
export default function SstGlobe() {
  const [map, setMap] = useState<MlMap | null>(null);
  const [frames, setFrames] = useState<SstFrame[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [note, setNote] = useState("");

  const onReady = useCallback((m: MlMap) => setMap(m), []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const manifest = await getSstManifest();
        if (!alive) return;
        if (manifest.frames.length === 0) {
          setNote("SST frames unavailable");
          return;
        }
        setFrames(manifest.frames);
        setIdx(manifest.frames.length - 1);
      } catch (err) {
        if (!alive) return;
        setNote(`SST frames unavailable: ${String(err)}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Install the frame overlay once both the map and the manifest exist.
  useEffect(() => {
    const last = frames?.[frames.length - 1];
    if (!map || !last) return;
    try {
      if (!map.getSource("sst")) {
        map.addSource("sst", {
          type: "image",
          url: frameUrl(last.month),
          coordinates: SST_COORDS,
        });
        map.addLayer({
          id: "sst-layer",
          type: "raster",
          source: "sst",
          paint: { "raster-opacity": 0.85 },
        });
      }
    } catch {
      /* overlay is decorative; the basemap still paints */
    }
  }, [map, frames]);

  useEffect(() => {
    if (!frames || frames.length === 0 || !playing) return;
    const timer = setInterval(() => {
      setIdx((prev) => (prev + 1) % frames.length);
    }, FRAME_MS);
    return () => clearInterval(timer);
  }, [frames, playing]);

  useEffect(() => {
    const frame = frames?.[idx];
    if (!map || !frame) return;
    try {
      const src = map.getSource("sst") as unknown as
        | { updateImage(opts: { url: string }): void }
        | undefined;
      src?.updateImage({ url: frameUrl(frame.month) });
    } catch {
      /* source not ready yet; the next tick retries */
    }
  }, [map, frames, idx]);

  const current = frames?.[idx] ?? null;

  return (
    <div className="sst-wrap">
      <GlobeMap
        testId="globe-map"
        // Fill the space below the room's readout strip instead of a fixed
        // cramped 260px window; clamped so it never collapses on short views.
        style={{ height: "clamp(460px, calc(100vh - 330px), 860px)" }}
        autoRotate
        onReady={onReady}
        fallback={
          current && (
            <img
              src={frameUrl(current.month)}
              alt={`SST anomaly ${current.month}`}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          )
        }
      />
      {current && (
        <div className="sst-controls">
          <button
            type="button"
            className="btn btn--quiet"
            data-testid="sst-play"
            aria-label={playing ? "pause SST animation" : "play SST animation"}
            onClick={() => setPlaying((v) => !v)}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <input
            type="range"
            data-testid="sst-scrubber"
            aria-label="SST month scrubber"
            min={0}
            max={frames!.length - 1}
            value={idx}
            onChange={(e) => setIdx(Number(e.target.value))}
          />
          <span className="sst-month" data-testid="sst-month" aria-label="SST month">
            {current.month}
          </span>
          <span className="sst-month" style={{ color: phaseColor(current.phase) }} data-testid="sst-badge">
            {current.phase}
          </span>
        </div>
      )}
      {current && (
        <div className="sst-legend" aria-label="SST anomaly legend">
          <span className="sst-legend-cool">La Nina · cool</span>
          <span className="sst-legend-bar" aria-hidden="true" />
          <span className="sst-legend-warm">warm · El Nino</span>
        </div>
      )}
      {note && <p>{note}</p>}
    </div>
  );
}
