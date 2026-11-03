import { useCallback, useEffect, useState } from "react";
import { TestTube2Icon, Trash2Icon, WebhookIcon } from "lucide-react";
import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import {
	createChannel,
	deleteChannel,
	listChannels,
	testChannel,
	type Channel,
} from "../api";

function errText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}

function createdLabel(iso: string): string {
	try {
		return new Date(iso).toLocaleString();
	} catch {
		return iso;
	}
}

/** Webhook notification channels: approved alerts push a signed envelope to
 * every registered target. Global channels receive all alerts; a channel
 * scoped to a watch receives only that watch's alerts. */
export default function ChannelsPage() {
	const [channels, setChannels] = useState<Channel[]>([]);
	const [target, setTarget] = useState("");
	const [note, setNote] = useState("");
	const [failed, setFailed] = useState(false);
	const [busyId, setBusyId] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		try {
			setChannels(await listChannels());
		} catch (err) {
			setFailed(true);
			setNote(`Could not load channels — ${errText(err)}`);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const add = async () => {
		const url = target.trim();
		if (!url) return;
		setFailed(false);
		setNote("Saving");
		try {
			await createChannel({ target: url });
			setTarget("");
			setNote("Channel saved — approved alerts will land there.");
			await refresh();
		} catch (err) {
			setFailed(true);
			setNote(`Save failed — ${errText(err)}`);
		}
	};

	const test = async (channel: Channel) => {
		setBusyId(channel.id);
		setFailed(false);
		setNote("Sending signed test event");
		try {
			const result = await testChannel(channel.id);
			setNote(
				result.ok
					? `Test delivered to ${channel.target} — check the receiver.`
					: `Test failed — ${result.error || `HTTP ${result.http_status ?? "?"}`}`,
			);
			setFailed(!result.ok);
		} catch (err) {
			setFailed(true);
			setNote(`Test failed — ${errText(err)}`);
		} finally {
			setBusyId(null);
		}
	};

	const remove = async (channel: Channel) => {
		setBusyId(channel.id);
		setFailed(false);
		try {
			await deleteChannel(channel.id);
			setNote(`Channel removed — ${channel.target}`);
			await refresh();
		} catch (err) {
			setFailed(true);
			setNote(`Delete failed — ${errText(err)}`);
		} finally {
			setBusyId(null);
		}
	};

	return (
		<div className="page">
			<PageHeader
				title="Channels"
				blurb="Approved alerts are pushed as HMAC-signed envelopes to every registered webhook — Slack, Discord, Telegram, n8n or your own endpoint. Nothing sends without your approval."
			/>
			<Card label="channels">
				<section aria-label="notification channels" data-testid="channels-page">
					<h2>Registered channels ({channels.length})</h2>
					{channels.length === 0 && (
						<p className="note">No channels yet — add a webhook URL below.</p>
					)}
					<ul className="activity-list">
						{channels.map((channel) => (
							<li
								key={channel.id}
								className="receipt-line"
								data-testid="channel-row"
							>
								<span aria-hidden="true">
									<WebhookIcon className="mr-1 inline size-3.5 align-[-2px]" />
								</span>
								<span className="font-mono">{channel.target}</span>
								<span className="beui-chip" data-testid="channel-status">
									{channel.status}
								</span>
								<span className="note">
									{channel.watch_id ? `scope ${channel.watch_id.slice(0, 8)}` : "all alerts"}
									{" · "}added {createdLabel(channel.created_at)}
								</span>
								<span className="alert-actions">
									<button
										type="button"
										className="btn btn--quiet"
										aria-label={`test webhook channel ${channel.target}`}
										disabled={busyId === channel.id}
										onClick={() => void test(channel)}
									>
										<TestTube2Icon className="mr-1 inline size-3.5" aria-hidden="true" />
										{busyId === channel.id ? "Testing…" : "Send test"}
									</button>
									<button
										type="button"
										className="btn btn--danger"
										aria-label={`remove webhook channel ${channel.target}`}
										disabled={busyId === channel.id}
										onClick={() => void remove(channel)}
									>
										<Trash2Icon className="mr-1 inline size-3.5" aria-hidden="true" />
										Remove
									</button>
								</span>
							</li>
						))}
					</ul>
					<div className="composer">
						<input
							className="input composer-input"
							aria-label="webhook channel target"
							data-beui="input"
							placeholder="https://hooks.example.com/argus"
							value={target}
							onChange={(e) => setTarget(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") void add();
							}}
						/>
						<button
							type="button"
							className="btn btn--primary composer-send"
							disabled={!target.trim()}
							onClick={() => void add()}
						>
							Add channel
						</button>
					</div>
					{note && (
						<p data-testid="channels-status" className={failed ? "note note--error" : "note"}>
							{note}
						</p>
					)}
				</section>
			</Card>
		</div>
	);
}
