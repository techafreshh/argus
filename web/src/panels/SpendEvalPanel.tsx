import { useEffect, useState } from "react";
import { getEvalStatus, getSpend, type EvalStatus, type SpendLedger } from "../api";
import { Loader } from "@/components/motion/loader";
import { Sparkline } from "@/components/charts/sparkline";
import { NumberTicker } from "@/components/motion/number-ticker";

function probeState(status: string | undefined): string {
	if (!status) return "";
	if (/pass|ok|green/i.test(status)) return "probe-dot--pass";
	if (/fail|red/i.test(status)) return "probe-dot--fail";
	return "probe-dot--pending";
}

/** Spend + eval: tabbed spend ledger and eval-gate probe status. */
export default function SpendEvalPanel() {
	const [spend, setSpend] = useState<SpendLedger | null>(null);
	const [evalStatus, setEvalStatus] = useState<EvalStatus | null>(null);
	const [note, setNote] = useState("");
	const [tab, setTab] = useState<"spend" | "eval">("spend");

	useEffect(() => {
		let alive = true;
		(async () => {
			try {
				const [s, e] = await Promise.all([getSpend(), getEvalStatus()]);
				if (!alive) return;
				setSpend(s);
				setEvalStatus(e);
			} catch (err) {
				if (!alive) return;
				setNote(`Spend and eval unavailable — ${err instanceof Error ? err.message : String(err)}`);
			}
		})();
		return () => {
			alive = false;
		};
	}, []);

	const probes = evalStatus?.probes;
	const familyCount = (v: unknown): number => (Array.isArray(v) ? v.length : 0);
	const precision = evalStatus
		? evalStatus.precision <= 1
			? `${Math.round(evalStatus.precision * 100)}%`
			: `${Math.round(evalStatus.precision)}%`
		: "—";

	return (
		<section aria-label="spend-eval">
			<h2>Spend + eval</h2>
			{note && <p className="note note--error">{note}</p>}
			<div role="tablist" aria-label="tabs" className="tabbar">
				<button
					type="button"
					role="tab"
					aria-selected={tab === "spend"}
					onClick={() => setTab("spend")}
				>
					Spend
				</button>
				<button
					type="button"
					role="tab"
					aria-selected={tab === "eval"}
					onClick={() => setTab("eval")}
				>
					Eval
				</button>
			</div>
			{tab === "spend" && (
				<div role="tabpanel" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
					{spend ? (
						<>
							<div className="stat-row">
								<div className="stat">
									<span className="stat-label">Total credits</span>
									<span className="stat-figure stat-figure--accent" data-testid="total-credits">
										<NumberTicker value={spend.total_credits} decimals={2} startOnView={false} />
									</span>
									<span className="stat-sub">Meta Model API</span>
								</div>
								<div className="stat">
									<span className="stat-label">Calls</span>
									<span className="stat-figure">{spend.calls.length}</span>
									<span className="stat-sub">logged</span>
								</div>
							</div>
							{spend.calls.length > 0 && (
								<div className="spend-spark">
									<Sparkline
										data={spend.calls.map((c) => c.cost_credits)}
										label="Meta credits per call"
										variant="area"
										color="var(--cool)"
										height={44}
										showDelta={false}
									/>
									<span className="stat-sub">credits per call, oldest → newest</span>
								</div>
							)}
							{spend.calls.length > 0 && (
								<div className="table-scroll" style={{ maxHeight: 260 }}>
									<table aria-label="table" className="data-table">
										<thead>
											<tr>
												<th>Operation</th>
												<th>Model</th>
												<th className="num">Tokens in</th>
												<th className="num">Tokens out</th>
												<th className="num">Credits</th>
											</tr>
										</thead>
										<tbody>
											{spend.calls.map((c) => (
												<tr key={c.id}>
													<td>{c.operation}</td>
													<td>{c.model}</td>
													<td className="num">{c.tokens_in}</td>
													<td className="num">{c.tokens_out}</td>
													<td className="num">{c.cost_credits}</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							)}
						</>
					) : (
						!note && <Loader variant="dots" size={20} label="Loading spend" />
					)}
				</div>
			)}
			{tab === "eval" && (
				<div role="tabpanel" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
					{evalStatus ? (
						<>
							<div className="stat-row">
								<div className="stat">
									<span className="stat-label">Precision</span>
									<span className="stat-figure stat-figure--accent" data-testid="eval-precision">
										{precision}
									</span>
									<span className="stat-sub">
										{evalStatus.hits} hits · {evalStatus.misses} misses of {evalStatus.total}
									</span>
								</div>
								<div className="stat">
									<span className="stat-label">Probes</span>
									<span className="stat-figure">{evalStatus.probes.status}</span>
									<span className="stat-sub">eval gate</span>
								</div>
							</div>
							<ul className="probe-list">
								<li>
									<span className={`probe-dot ${probeState(probes?.status)}`} aria-hidden="true" />
									replay · {familyCount(probes?.replay)} probes
								</li>
								<li>
									<span className={`probe-dot ${probeState(probes?.status)}`} aria-hidden="true" />
									false positive · {familyCount(probes?.false_positive)} probes
								</li>
								<li>
									<span className={`probe-dot ${probeState(probes?.status)}`} aria-hidden="true" />
									novel question · {familyCount(probes?.novel_question)} probes
								</li>
							</ul>
						</>
					) : (
						!note && <Loader variant="dots" size={20} label="Loading eval" />
					)}
				</div>
			)}
		</section>
	);
}
