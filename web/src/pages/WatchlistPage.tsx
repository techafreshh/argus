import { useCallback, useEffect, useMemo, useState } from "react";
import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import BboxPicker, { type Bbox } from "../components/map/BboxPicker";
import { GitHubSignInCta } from "../components/app-shared";
import {
	createWatch,
	getPresets,
	listWatches,
	previewTemplate,
	type AskPreview,
	type Preset,
	type Watch,
} from "../api";

const BLANK = { minLon: "24", minLat: "-12.5", maxLon: "30", maxLat: "-8" };

function errText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}

/** One-click cookbook watches, shared with the onboarding wizard. */
export function PresetStrip({ onChanged }: { onChanged?: () => void }) {
	const [presets, setPresets] = useState<Preset[]>([]);
	const [starting, setStarting] = useState<string | null>(null);
	const [note, setNote] = useState("");
	const [failed, setFailed] = useState(false);

	useEffect(() => {
		let alive = true;
		getPresets()
			.then((rows) => {
				if (alive) setPresets(rows);
			})
			.catch(() => {
				/* the strip is additive; the manager below always works */
			});
		return () => {
			alive = false;
		};
	}, []);

	const start = async (preset: Preset) => {
		setStarting(preset.id);
		setFailed(false);
		setNote("");
		try {
			await createWatch({
				name: `${preset.title} · ${preset.region_label}`,
				region: { type: "bbox", coords: preset.bbox },
				question: preset.question || `Is ${preset.title.toLowerCase()} occurring?`,
				cadence: preset.cadence,
			});
			setNote(`Watch started — ${preset.title} over ${preset.region_label}.`);
			onChanged?.();
		} catch (err) {
			setFailed(true);
			setNote(`Could not start the watch — ${errText(err)}`);
		} finally {
			setStarting(null);
		}
	};

	if (presets.length === 0) return null;

	return (
		<section aria-label="preset-gallery" data-testid="preset-gallery" className="preset-section">
			<h2>Start from a cookbook preset</h2>
			<ul className="preset-grid">
				{presets.map((preset) => (
					<li key={preset.id} className="preset-card" data-testid={`preset-${preset.id}`}>
						<span className="preset-title">{preset.title}</span>
						<span className="preset-region">{preset.region_label}</span>
						<span className="preset-blurb">{preset.blurb}</span>
						<button
							type="button"
							className="btn btn--primary preset-start"
							disabled={starting !== null}
							onClick={() => void start(preset)}
						>
							{starting === preset.id ? "Starting…" : "Start watch"}
						</button>
					</li>
				))}
			</ul>
			{note && <p className={failed ? "note note--error" : "note"}>{note}</p>}
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

	const parsed = useMemo<Bbox | null>(() => {
		const nums = [bbox.minLon, bbox.minLat, bbox.maxLon, bbox.maxLat].map(Number);
		return nums.every((n) => Number.isFinite(n)) ? (nums as Bbox) : null;
	}, [bbox]);

	const setParsed = (next: Bbox) =>
		setBbox({
			minLon: String(next[0]),
			minLat: String(next[1]),
			maxLon: String(next[2]),
			maxLat: String(next[3]),
		});

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
				<div className="field span-2">
					<span className="field-label">Region</span>
					<BboxPicker
						value={parsed}
						onChange={setParsed}
						onClear={() => setBbox(BLANK)}
						height={240}
					/>
				</div>
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
			{failed && status.includes("Sign in with GitHub") && <GitHubSignInCta /> }
		</section>
	);
}

/** Onboarding: add a region + plain-English question, and see the standing watches. */
export default function WatchlistPage() {
	const [watches, setWatches] = useState<Watch[]>([]);

	const refresh = useCallback(async () => {
		try {
			setWatches(await listWatches());
		} catch {
			/* keep the room usable offline */
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	return (
		<div className="page">
			<PageHeader
				title="Watchlist"
				blurb="Add a region and a plain-English question — ARGUS schedules the rest."
			/>
			<PresetStrip onChanged={() => void refresh()} />
			<Card label="watchlist">
				<WatchlistManager onChanged={() => void refresh()} />
			</Card>
			<Card label="watches">
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
		</div>
	);
}
