import { useState } from "react";
import { Scan as ScanIcon } from "lucide-react";
import GlobeMap, { type Bbox } from "./GlobeMap";

export type { Bbox };

export interface BboxPickerProps {
  value: Bbox | null;
  onChange: (bbox: Bbox) => void;
  onClear?: () => void;
  height?: number;
}

function fmt(n: number): string {
  return n.toFixed(4);
}

function readout(value: Bbox): string {
  return `${fmt(value[0])}, ${fmt(value[1])} → ${fmt(value[2])}, ${fmt(value[3])}`;
}

/** Region picker: drag a rectangle on the dark globe, or fine-tune via the
 * numeric inputs beside it. The outline stays on the map either way. */
export default function BboxPicker({
  value,
  onChange,
  onClear,
  height = 300,
}: BboxPickerProps) {
  const [drawing, setDrawing] = useState(false);

  return (
    <div className="flex flex-col gap-2">
      <GlobeMap
        testId="bbox-picker-map"
        style={{ height }}
        initialCenter={[12, 2]}
        initialZoom={2.2}
        drawBbox={drawing}
        aoi={value}
        onDrawComplete={(bbox) => {
          setDrawing(false);
          onChange(bbox);
        }}
        onDrawCancel={() => setDrawing(false)}
      />
      <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-xs">
        <button
          type="button"
          className={drawing ? "btn btn--primary" : "btn btn--quiet"}
          aria-label={drawing ? "finish drawing region" : "draw region on globe"}
          onClick={() => setDrawing((v) => !v)}
        >
          <ScanIcon className="size-3.5" aria-hidden="true" />
          {drawing ? "Drag a box on the globe…" : "Draw on globe"}
        </button>
        {value && onClear && (
          <button
            type="button"
            className="btn btn--quiet"
            aria-label="clear drawn region"
            onClick={() => {
              setDrawing(false);
              onClear();
            }}
          >
            Clear
          </button>
        )}
        <span
          className="font-mono"
          data-testid="bbox-readout"
          aria-label="region bounds"
        >
          {value ? readout(value) : "no region chosen yet"}
        </span>
      </div>
    </div>
  );
}
