import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import maplibregl, {
  type GeoJSONSource,
  type LngLat,
  type Map as MlMap,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export type Bbox = [number, number, number, number];

export const ESRI_DARK_TILES =
  "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}";

/** Degrees per second of the demo-mode drift; a full lap takes ~2.4 min. */
const SPIN_DEG_PER_S = 2.5;
/** Quiet period after user interaction before the drift resumes. */
const SPIN_RESUME_MS = 5000;
/** Grace period before a wedged globe rebuilds itself flat. */
const GLOBE_GRACE_MS = 7000;

const EMPTY_COLLECTION = {
  type: "FeatureCollection" as const,
  features: [],
};

/**
 * Globe reprojection wedges permanently under software rasterizers
 * (SwiftShader/llvmpipe): tiles retry forever, the style never finishes
 * loading, and even `setProjection` is refused ("Style is not done
 * loading") — so the fallback has to happen at construction. Hardware
 * GL renders the globe fine and keeps the atmosphere.
 */
function detectSoftwareRenderer(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") ??
      (canvas.getContext("webgl") as WebGLRenderingContext | null);
    if (!gl) return false;
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = dbg
      ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL))
      : String(gl.getParameter(gl.RENDERER));
    return /swiftshader|llvmpipe|softpipe|software raster/i.test(renderer);
  } catch {
    return false;
  }
}

const SOFTWARE_GL = detectSoftwareRenderer();

function buildStyle(globe: boolean): StyleSpecification {
  const style: StyleSpecification = {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: [ESRI_DARK_TILES],
        tileSize: 256,
        maxzoom: 16,
        attribution: "Esri, HERE, Garmin, FAO, NOAA, USGS",
      },
      aoi: { type: "geojson", data: EMPTY_COLLECTION },
    },
    layers: [
      { id: "basemap", type: "raster", source: "basemap" },
      {
        id: "aoi-fill",
        type: "fill",
        source: "aoi",
        paint: { "fill-color": "#58c4e8", "fill-opacity": 0.08 },
      },
      {
        id: "aoi-line",
        type: "line",
        source: "aoi",
        paint: { "line-color": "#58c4e8", "line-width": 1.5 },
      },
    ],
  };
  if (globe) {
    style.projection = { type: "globe" };
    style.sky = {
      "sky-color": "#000004",
      "horizon-color": "#0b1826",
      "fog-color": "#04101c",
      "sky-horizon-blend": 0.6,
      "horizon-fog-blend": 0.4,
      "fog-ground-blend": 0.08,
      "atmosphere-blend": 0.8,
    };
  }
  return style;
}

function aoiPolygon(bbox: Bbox) {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  return {
    type: "FeatureCollection" as const,
    features: [
      {
        type: "Feature" as const,
        properties: {},
        geometry: {
          type: "Polygon" as const,
          coordinates: [
            [
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ],
          ],
        },
      },
    ],
  };
}

function bboxFrom(a: LngLat, b: LngLat): Bbox {
  return [
    Math.min(a.lng, b.lng),
    Math.min(a.lat, b.lat),
    Math.max(a.lng, b.lng),
    Math.max(a.lat, b.lat),
  ];
}

export interface GlobeMapProps {
  /** data-testid hook for the map container (e.g. "globe-map"). */
  testId?: string;
  style?: CSSProperties;
  className?: string;
  initialCenter?: [number, number];
  initialZoom?: number;
  /** Slow demo drift; pauses on interaction and while drawing. */
  autoRotate?: boolean;
  /** Drag-rectangle AOI picking. While active, panning is disabled. */
  drawBbox?: boolean;
  /** Bbox outline to render (from manual inputs or a completed draw). */
  aoi?: Bbox | null;
  onDrawComplete?: (bbox: Bbox) => void;
  onDrawCancel?: () => void;
  /** Called once the map exists and baseline layers are installed. */
  onReady?: (map: MlMap) => void;
  /** Rendered inside the map container when WebGL is unavailable. */
  fallback?: ReactNode;
}

/** Reusable pitch-black globe: MapLibre 5 globe projection (flat under
 * software renderers), dark atmosphere, Esri dark-gray raster tiles,
 * optional AOI draw mode and demo drift. */
export default function GlobeMap({
  testId,
  style,
  className,
  initialCenter,
  initialZoom,
  autoRotate = false,
  drawBbox = false,
  aoi = null,
  onDrawComplete,
  onDrawCancel,
  onReady,
  fallback,
}: GlobeMapProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);
  // Bumped once when a globe that never finishes loading rebuilds flat.
  const [forceFlat, setForceFlat] = useState(false);
  const drawCompleteRef = useRef(onDrawComplete);
  const drawCancelRef = useRef(onDrawCancel);
  const readyRef = useRef(onReady);
  const loadedRef = useRef(false);
  drawCompleteRef.current = onDrawComplete;
  drawCancelRef.current = onDrawCancel;
  readyRef.current = onReady;

  useEffect(() => {
    const el = divRef.current;
    if (!el) return;
    const globe = !SOFTWARE_GL && !forceFlat;
    // Defaults are applied inside: a `= [x, y]` destructuring default would
    // mint a new array each render and re-run this effect forever.
    const center = initialCenter ?? [-145, 0];
    const zoom = initialZoom ?? 1.6;
    let map: MlMap | null = null;
    try {
      map = new maplibregl.Map({
        container: el,
        style: buildStyle(globe),
        center,
        zoom,
      });
    } catch {
      // WebGL unavailable in headless probes: still-image fallback below.
      setMapFailed(true);
      return;
    }
    mapRef.current = map;
    loadedRef.current = false;
    // Dev/e2e handle registered at construction so probes reach pre-load maps.
    (window as unknown as { __argusMaps?: MlMap[] }).__argusMaps = [
      ...((window as unknown as { __argusMaps?: MlMap[] }).__argusMaps ?? []),
      map,
    ];
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "bottom-right",
    );
    let graceTimer = 0;
    if (globe) {
      try {
        map.setSky(buildStyle(globe).sky!);
      } catch {
        /* sky spec unsupported: flat basemap still paints */
      }
      // An unknown wedge (never `load`) gets one flat rebuild.
      graceTimer = window.setTimeout(() => {
        if (loadedRef.current) return;
        setForceFlat(true);
      }, GLOBE_GRACE_MS);
    }
    map.on("load", () => {
      loadedRef.current = true;
      setReady(true);
      readyRef.current?.(map as MlMap);
    });
    return () => {
      window.clearTimeout(graceTimer);
      try {
        map?.remove();
      } catch {
        /* noop */
      }
      if (mapRef.current === map) mapRef.current = null;
      setReady(false);
    };
    // Primitive deps: object/array props arrive as fresh literals per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCenter?.[0], initialCenter?.[1], initialZoom, forceFlat]);

  // Render the committed AOI outline (manual input or last draw).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const paint = () => {
      try {
        const src = map.getSource("aoi") as GeoJSONSource | undefined;
        src?.setData(aoi ? aoiPolygon(aoi) : EMPTY_COLLECTION);
      } catch {
        /* style not ready yet; rebuilt on the next aoi/ready change */
      }
    };
    if (map.isStyleLoaded()) paint();
    else map.once("load", paint);
    return () => {
      map.off("load", paint);
    };
  }, [aoi, ready, forceFlat]);

  // Drag-rectangle draw mode: crosshair cursor, drag-pan suspended, Escape cancels.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !drawBbox || !ready || mapFailed) return;
    const canvas = map.getCanvas();
    const previousCursor = canvas.style.cursor;
    canvas.style.cursor = "crosshair";
    map.dragPan.disable();
    let dragStart: LngLat | null = null;

    const onDown = (e: maplibregl.MapMouseEvent) => {
      if (e.originalEvent.button !== 0) return;
      dragStart = e.lngLat;
    };
    const onMove = (e: maplibregl.MapMouseEvent) => {
      if (!dragStart) return;
      try {
        const src = map.getSource("aoi") as GeoJSONSource | undefined;
        src?.setData(aoiPolygon(bboxFrom(dragStart, e.lngLat)));
      } catch {
        /* preview is decorative */
      }
    };
    const onUp = (e: maplibregl.MapMouseEvent) => {
      if (!dragStart) return;
      const bbox = bboxFrom(dragStart, e.lngLat);
      dragStart = null;
      drawCompleteRef.current?.(bbox);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") drawCancelRef.current?.();
    };

    map.on("mousedown", onDown);
    map.on("mousemove", onMove);
    map.on("mouseup", onUp);
    document.addEventListener("keydown", onKey);
    return () => {
      map.off("mousedown", onDown);
      map.off("mousemove", onMove);
      map.off("mouseup", onUp);
      document.removeEventListener("keydown", onKey);
      canvas.style.cursor = previousCursor;
      map.dragPan.enable();
    };
  }, [drawBbox, ready, mapFailed, forceFlat]);

  // Demo drift: pauses while the reader interacts or draws, resumes after a beat.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !autoRotate || drawBbox || !ready || mapFailed) return;
    let raf = 0;
    let last = performance.now();
    let lastInteract = -Infinity;

    const mark = () => {
      lastInteract = performance.now();
    };
    const canvasContainer = map.getCanvasContainer();
    canvasContainer.addEventListener("pointerdown", mark);
    canvasContainer.addEventListener("wheel", mark);
    map.on("dragstart", mark);
    map.on("zoomstart", mark);

    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      if (now - lastInteract > SPIN_RESUME_MS) {
        const c = map.getCenter();
        const wrapped = ((((c.lng + SPIN_DEG_PER_S * dt) % 360) + 540) % 360) - 180;
        map.setCenter([wrapped, c.lat]);
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      canvasContainer.removeEventListener("pointerdown", mark);
      canvasContainer.removeEventListener("wheel", mark);
      map.off("dragstart", mark);
      map.off("zoomstart", mark);
    };
  }, [autoRotate, drawBbox, ready, mapFailed, forceFlat]);

  return (
    <div ref={divRef} data-testid={testId} style={style} className={className}>
      {mapFailed && fallback}
    </div>
  );
}
