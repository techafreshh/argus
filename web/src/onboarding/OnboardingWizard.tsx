import { useCallback, useEffect, useState } from "react";
import {
	createChannel,
	createWatch,
	getPresets,
	type Preset,
} from "../api";

const STORAGE_KEY = "argus.onboarded";

/** True once the first-run wizard has been finished or skipped. */
export function isOnboarded(): boolean {
	try {
		return localStorage.getItem(STORAGE_KEY) === "1";
	} catch {
		return true; // storage unavailable -> never nag
	}
}

type Step = 1 | 2 | 3;

function errText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}

/** 3-step first-run wizard: meet ARGUS -> start a preset watch -> get notified.
 * Skippable at every step; remembered in localStorage. */
export default function OnboardingWizard() {
	const [visible, setVisible] = useState(false);
	const [step, setStep] = useState<Step>(1);
	const [presets, setPresets] = useState<Preset[]>([]);
	const [starting, setStarting] = useState<string | null>(null);
	const [note, setNote] = useState("");
	const [failed, setFailed] = useState(false);
	const [webhookUrl, setWebhookUrl] = useState("");
	const [webhookNote, setWebhookNote] = useState("");
	const [webhookOk, setWebhookOk] = useState<boolean | null>(null);

	useEffect(() => {
		if (!isOnboarded()) setVisible(true);
	}, []);

	useEffect(() => {
		if (!visible || step !== 2 || presets.length > 0) return;
		let alive = true;
		getPresets()
			.then((rows) => {
				if (alive) setPresets(rows);
			})
			.catch(() => {
				if (alive) setNote("Preset catalog unavailable — you can add watches later.");
			});
		return () => {
			alive = false;
		};
	}, [visible, step, presets.length]);

	const finish = useCallback(() => {
		try {
			localStorage.setItem(STORAGE_KEY, "1");
		} catch {
			/* storage unavailable: wizard just re-shows next visit */
		}
		setVisible(false);
	}, []);

	const startPreset = async (preset: Preset) => {
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
			setStep(3);
		} catch (err) {
			setFailed(true);
			setNote(`Could not start the watch — ${errText(err)}`);
		} finally {
			setStarting(null);
		}
	};

	const saveWebhook = async () => {
		const target = webhookUrl.trim();
		if (!target) return;
		setWebhookNote("");
		try {
			await createChannel({ target });
			setWebhookOk(true);
			setWebhookNote("Channel saved — approved alerts will land there.");
		} catch (err) {
			setWebhookOk(false);
			setWebhookNote(`Save failed — ${errText(err)}`);
		}
	};

	if (!visible) return null;

	return (
		<div className="wizard-overlay" role="dialog" aria-modal="true" aria-label="onboarding">
			<div className="wizard-card" data-testid="onboarding-wizard">
				<ol className="wizard-steps" aria-label="wizard progress">
					{([1, 2, 3] as Step[]).map((n) => (
						<li
							key={n}
							className={`wizard-step${n === step ? " is-current" : ""}${n < step ? " is-done" : ""}`}
							aria-current={n === step ? "step" : undefined}
						>
							{n === 1 ? "Meet ARGUS" : n === 2 ? "Start a watch" : "Stay notified"}
						</li>
					))}
				</ol>

				{step === 1 && (
					<div className="wizard-body">
						<h2>An autonomous eye on the Earth</h2>
						<p className="wizard-lede">
							ARGUS turns plain questions into scheduled satellite analysis. Ask
							&ldquo;is the Niger delta flooding?&rdquo; and it routes the question
							through a cookbook recipe, acquires imagery, verifies against
							baselines, and queues an alert for your approval — with a receipt
							for every tool call.
						</p>
						<div className="wizard-actions">
							<button type="button" className="btn btn--primary" onClick={() => setStep(2)}>
								Start
							</button>
							<button type="button" className="btn btn--quiet" onClick={finish}>
								Skip
							</button>
						</div>
					</div>
				)}

				{step === 2 && (
					<div className="wizard-body">
						<h2>Pick a cookbook preset</h2>
						<p className="wizard-lede">
							Each preset is a full analysis recipe: region, sensor, cadence,
							verification and alert threshold. One click starts the watch.
						</p>
						{note && <p className={failed ? "note note--error" : "note"}>{note}</p>}
						<ul className="preset-grid" aria-label="preset-list" data-testid="preset-list">
							{presets.map((preset) => (
								<li key={preset.id} className="preset-card" data-testid={`preset-${preset.id}`}>
									<span className="preset-title">{preset.title}</span>
									<span className="preset-region">{preset.region_label}</span>
									<span className="preset-blurb">{preset.blurb}</span>
									<button
										type="button"
										className="btn btn--primary preset-start"
										disabled={starting !== null}
										onClick={() => void startPreset(preset)}
									>
										{starting === preset.id ? "Starting…" : "Start watch"}
									</button>
								</li>
							))}
							{presets.length === 0 && !note && (
								<li className="note">Loading cookbook presets…</li>
							)}
						</ul>
						<div className="wizard-actions">
							<button type="button" className="btn btn--quiet" onClick={finish}>
								Skip — I&rsquo;ll browse first
							</button>
						</div>
					</div>
				)}

				{step === 3 && (
					<div className="wizard-body">
						<h2>Where should alerts land?</h2>
						<p className="wizard-lede">
							Approvals can push a signed report envelope to any webhook — Slack,
							Discord, Telegram, n8n or your own endpoint. You can add channels
							any time; alerts always wait for your approval in-app.
						</p>
						<div className="composer">
							<input
								className="input composer-input"
								aria-label="webhook url"
								placeholder="https://hooks.example.com/argus"
								value={webhookUrl}
								onChange={(e) => setWebhookUrl(e.target.value)}
							/>
							<button
								type="button"
								className="btn btn--primary composer-send"
								disabled={!webhookUrl.trim()}
								onClick={() => void saveWebhook()}
							>
								Save
							</button>
						</div>
						{webhookNote && (
							<p className={webhookOk === false ? "note note--error" : "note"}>
								{webhookNote}
							</p>
						)}
						<div className="wizard-actions">
							<button type="button" className="btn btn--primary" onClick={finish}>
								Enter the control room
							</button>
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
