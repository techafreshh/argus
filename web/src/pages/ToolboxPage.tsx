import { useEffect, useState } from "react";
import { getToolbox, type ToolboxSource } from "../api";
import { PageHeader } from "../shell/page-header";

function errText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}

function statusClass(status: string): string {
	if (status === "live") return "toolkit-dot toolkit-dot--live";
	if (status === "offline") return "toolkit-dot toolkit-dot--offline";
	return "toolkit-dot toolkit-dot--stale";
}

function SourceRow({ source }: { source: ToolboxSource }) {
	return (
		<li className="toolkit-row" data-testid={`source-${source.id}`}>
			<span className={statusClass(source.status)} aria-label={`source status ${source.status}`} />
			<div className="toolkit-main">
				<span className="toolkit-name">
					<a href={source.url} target="_blank" rel="noreferrer">
						{source.name}
					</a>
				</span>
				<span className="toolkit-coverage">{source.coverage}</span>
			</div>
			<span className="beui-chip">{source.cadence}</span>
			{source.used_by.filter((t) => t !== "__freeform__").length > 0 && (
				<span className="toolkit-usedby">
					{source.used_by.map((t) => (
						<span key={t} className="beui-chip chip-recipe">
							{t}
						</span>
					))}
				</span>
			)}
			{source.used_by.includes("__freeform__") && (
				<span className="beui-chip chip-recipe">freeform geocoding</span>
			)}
		</li>
	);
}

/** The toolbox: the curated public-data registry ARGUS can reach right now. */
export default function ToolboxPage() {
	const [sources, setSources] = useState<ToolboxSource[] | null>(null);
	const [note, setNote] = useState("");

	useEffect(() => {
		let alive = true;
		getToolbox()
			.then((rows) => {
				if (alive) setSources(rows);
			})
			.catch((err) => {
				if (alive) setNote(`Toolbox unavailable — ${errText(err)}`);
			});
		return () => {
			alive = false;
		};
	}, []);

	const live = sources?.filter((s) => s.status === "live").length ?? 0;

	return (
		<div className="page">
			<PageHeader
				title="Toolbox"
				blurb="The curated public-data registry behind the cookbook — probed live, receipts for every use."
			/>
			{note && <p className="note note--error">{note}</p>}
			{sources && (
				<p className="note" data-testid="toolbox-summary">
					{live} of {sources.length} sources reachable {sources.length ? "" : ""}
				</p>
			)}
			<ul className="toolkit-list" aria-label="toolbox-sources">
				{sources?.map((source) => <SourceRow key={source.id} source={source} />)}
				{sources === null && !note && <li className="note">Probing sources…</li>}
			</ul>
		</div>
	);
}
