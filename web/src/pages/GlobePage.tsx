import { useCallback, useEffect, useState } from "react";
import { Card, EnsoReadout, LoopIsland } from "../beui";
import SstGlobe from "../panels/SstGlobe";
import { PageHeader } from "../shell/page-header";
import { useEnso } from "../shell/enso-context";
import { listWatches, type Watch } from "../api";

function utcClock(iso: string): string {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	const p = (n: number) => String(n).padStart(2, "0");
	return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`;
}

/** Home: the planet, the loop status, and the hero eye's live readout. */
export default function GlobePage() {
	const { enso, note } = useEnso();
	const [watches, setWatches] = useState<Watch[]>([]);
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
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const subwatchers = enso?.subwatchers ?? [];

	return (
		<div className="page">
			<PageHeader
				title="Globe"
				blurb="Sea-surface temperature anomalies 1982 → now, measured over the Niño3.4 band."
			/>
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
			{note && <p className="note note--warn">{note}</p>}
			<Card label="globe">
				<section aria-label="globe">
					<SstGlobe />
				</section>
			</Card>
		</div>
	);
}
