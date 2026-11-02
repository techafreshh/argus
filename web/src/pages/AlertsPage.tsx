import { useCallback, useEffect, useState } from "react";
import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import {
	approveAlert,
	listAlerts,
	listReceipts,
	rejectAlert,
	type AlertItem,
	type Receipt,
} from "../api";
import {
	AnimatedToastStack,
	useAnimatedToastStack,
} from "@/components/motion/animated-toast-stack";

function fmtConfidence(v: number): string {
	return `${Math.round(v <= 1 ? v * 100 : v)}%`;
}

function errText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}

function AlertFeed() {
	const [alerts, setAlerts] = useState<AlertItem[]>([]);
	const [evidence, setEvidence] = useState<Record<string, Receipt[]>>({});
	const [note, setNote] = useState("");
	const [failed, setFailed] = useState(false);
	const { toasts, showToast, dismissToast } = useAnimatedToastStack({ limit: 4 });

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
	}, [refresh]);

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
			showToast({
				title: `${kind === "approve" ? "Approved" : "Rejected"} ${a.id}`,
				status: kind === "approve" ? "success" : "info",
			});
			await refresh();
		} catch (err) {
			showToast({
				title: "Decision failed",
				description: errText(err),
				status: "error",
			});
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
			<AnimatedToastStack
				toasts={toasts}
				onDismiss={dismissToast}
				position="bottom-right"
				fixed
			/>
		</section>
	);
}

/** Nothing ships without a human: approve or reject with evidence in hand. */
export default function AlertsPage() {
	return (
		<div className="page">
			<PageHeader
				title="Alerts"
				blurb="Every outbound alert queues here for approval — ambiguity surfaces as ambiguity."
			/>
			<Card label="alerts">
				<AlertFeed />
			</Card>
		</div>
	);
}
