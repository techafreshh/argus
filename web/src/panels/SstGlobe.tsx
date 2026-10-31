import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { AnimatedBadge } from "../beui";
import { getSstManifest, type SstFrame } from "../api";

/** Nino3.4 overlay corners: [[-170,5],[-120,5],[-120,-5],[-170,-5]]. */
const SST_COORDS: [[number, number], [number, number], [number, number], [number, number]] = [
  [-170, 5],
  [-120, 5],
  [-120, -5],
  [-170, -5],
];

const FRAME_MS = 125;

function sstBadgeStatus(phase: string): "info" | "success" | "warning" | "neutral" {
  if (phase === "El Nino") return "warning";
  if (phase === "La Nina") return "info";
  if (phase === "Neutral") return "success";
  return "neutral";
}

function frameUrl(month: string): string {
  return `/sst/frame-${month}.png`;
}

/** Monthly SST-anomaly globe: pre-rendered frames over the Nino3.4 band. */
export default function SstGlobe() {
  const divRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [frames, setFrames] = useState<SstFrame[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [mapFailed, setMapFailed] = useState(false);
  const [note, setNote] = useState("");

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

  useEffect(() => {
    if (!frames || frames.length === 0) return;
    const el = divRef.current;
    if (!el) return;
    let map: maplibregl.Map | null = null;
    try {
      map = new maplibregl.Map({
        container: el,
        style: {
          version: 8,
          sources: {
            basemap: {
              type: "raster",
              tiles: [
                "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
              ],
              tileSize: 256,
              maxzoom: 16,
              attribution: "Esri, HERE, Garmin, FAO, NOAA, USGS",
            },
          },
          layers: [{ id: "basemap", type: "raster", source: "basemap" }],
        },
        center: [-145, 0],
        zoom: 1.6,
      });
      const globe = { type: "globe" as const };
      try {
        (map as unknown as { setProjection(p: unknown): void }).setProjection(globe);
      } catch {
        /* older renderers ignore globe projection */
      }
      map.on("load", () => {
        try {
          map?.addSource("sst", {
            type: "image",
            url: frameUrl(frames[frames.length - 1].month),
            coordinates: SST_COORDS,
          });
          map?.addLayer({
            id: "sst-layer",
            type: "raster",
            source: "sst",
            paint: { "raster-opacity": 0.85 },
          });
        } catch {
          /* overlay is decorative; the basemap still paints */
        }
      });
      mapRef.current = map;
    } catch {
      /* WebGL unavailable in headless probes: still-image fallback below */
      setMapFailed(true);
    }
    return () => {
      try {
        map?.remove();
      } catch {
        /* noop */
      }
      if (mapRef.current === map) mapRef.current = null;
    };
  }, [frames]);

  useEffect(() => {
    if (!frames || frames.length === 0 || !playing) return;
    const timer = setInterval(() => {
      setIdx((prev) => (prev + 1) % frames.length);
    }, FRAME_MS);
    return () => clearInterval(timer);
  }, [frames, playing]);

  useEffect(() => {
    const map = mapRef.current;
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
  }, [frames, idx]);

  const current = frames?.[idx] ?? null;

  return (
    <div className="sst-wrap">
      <div ref={divRef} data-testid="globe-map" style={{ height: 260 }}>
        {mapFailed && current && (
          <img
            src={frameUrl(current.month)}
            alt={`SST anomaly ${current.month}`}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
      </div>
      {current && (
        <div className="sst-controls">
          <button
            type="button"
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
          <span data-testid="sst-month" aria-label="SST month">
            {current.month}
          </span>
          <AnimatedBadge status={sstBadgeStatus(current.phase)} testId="sst-badge">
            ENSO {current.phase} · {current.month}
          </AnimatedBadge>
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
