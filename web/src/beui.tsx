import type { ReactNode } from "react";
import { AnimatedBadge } from "@/components/motion/animated-badge";

/** ARGUS chart-room surfaces: shared readouts used across pages. */

export function Card({
	children,
	label,
	id,
}: {
	children: ReactNode;
	label?: string;
	id?: string;
}) {
	return (
		<div
			className="beui-card"
			id={id}
			data-testid={label ? `card-${label}` : undefined}
		>
			{children}
		</div>
	);
}

/** Live loop readout: watches on the books + last scheduler tick (UTC). */
export function LoopIsland({ count, lastTick }: { count: number; lastTick: string }) {
	return (
		<div className="beui-island" aria-label="loop-status">
			<span className="dot" aria-hidden="true" />
			<span>
				{count} {count === 1 ? "watch" : "watches"} · last tick {lastTick || "—"}
			</span>
		</div>
	);
}

const PHASE_IDS: Record<string, string> = {
	"La Nina": "la_nina",
	"El Nino": "el_nino",
	Neutral: "neutral",
};

const PHASE_NAMES: Record<string, string> = {
	"La Nina": "La Niña",
	"El Nino": "El Niño",
	Neutral: "Neutral",
};

const PHASE_STATUS = {
	"La Nina": "info",
	"El Nino": "warning",
	Neutral: "neutral",
} as const;

function fmt(value: unknown, digits = 2, suffix = ""): string {
	if (typeof value !== "number" || !Number.isFinite(value)) return "—";
	return `${value.toFixed(digits)}${suffix}`;
}

/** ENSO instrument readout: own ONI against the NOAA official rail. */
export function EnsoReadout({
	enso,
}: {
	enso: {
		phase: string;
		intensity: string;
		trajectory: string;
		month: string;
		[key: string]: unknown;
	} | null;
}) {
	const phaseId = enso ? (enso.phase_id as string | undefined) ?? PHASE_IDS[enso.phase] ?? "neutral" : "";
	const phaseStatus = enso
		? PHASE_STATUS[enso.phase as keyof typeof PHASE_STATUS] ?? "neutral"
		: "loading";
	return (
		<div className="enso-readout" data-testid="enso-badge">
			<div className="enso-cell">
				<span className="enso-label">Phase</span>
				<AnimatedBadge
					status={phaseStatus}
					size="sm"
					pulse={Boolean(enso) && phaseStatus !== "neutral"}
					className="enso-value--phase"
					data-phase={phaseId || undefined}
					contentKey={`${enso?.phase ?? "reading"}-${enso?.month ?? ""}`}
				>
					{enso ? PHASE_NAMES[enso.phase] ?? enso.phase : "reading"}
				</AnimatedBadge>
			</div>
			<div className="enso-cell">
				<span className="enso-label">Niño3.4 ONI</span>
				<span className="enso-value">{fmt(enso?.oni)} °C</span>
				<span className="enso-label">own computation</span>
			</div>
			<div className="enso-cell">
				<span className="enso-label">NOAA ONI</span>
				<span className="enso-value">{fmt(enso?.noaa_oni)} °C</span>
				<span className="enso-label">official</span>
			</div>
			<div className="enso-cell enso-cell--agree">
				<span className="enso-label">Agreement</span>
				<span className="enso-value">{enso?.phase_agreement_pct != null ? fmt(enso.phase_agreement_pct, 1, "%") : "—"}</span>
				<span className="enso-label">40-yr phase</span>
			</div>
			<div className="enso-cell">
				<span className="enso-label">State</span>
				<span className="enso-value">{enso ? `${enso.intensity} · ${enso.trajectory}` : "—"}</span>
				<span className="enso-label">{enso?.month || "—"}</span>
			</div>
		</div>
	);
}
