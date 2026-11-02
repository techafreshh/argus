import { useEnso } from "@/shell/enso-context";
import { useChatDrawer } from "@/chat/chat-drawer";
import { AnimatedBadge } from "@/components/motion/animated-badge";
import { Button } from "@/components/ui/button";
import { MessageSquareIcon } from "lucide-react";

const PHASE_STATUS = {
	"El Nino": "warning",
	"La Nina": "info",
	Neutral: "neutral",
} as const;

const PHASE_NAMES: Record<string, string> = {
	"La Nina": "La Niña",
	"El Nino": "El Niño",
	Neutral: "Neutral",
};

/** Sidebar footer card: the hero eye's live phase + the ask-the-Earth handoff. */
export function StatusCard() {
	const { enso } = useEnso();
	const { openChat } = useChatDrawer();
	const phase = enso?.phase;
	const status = phase ? PHASE_STATUS[phase as keyof typeof PHASE_STATUS] ?? "neutral" : "loading";

	return (
		<div className="group/status-card relative flex min-h-24 w-full flex-col gap-1 overflow-hidden rounded-lg border bg-background px-3 pt-2.5 pb-2 *:text-nowrap transition-opacity group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:opacity-0">
			<span className="font-mono text-[10px] tracking-[0.14em] text-muted-foreground">
				EL VIGÍA · LIVE
			</span>
			<AnimatedBadge
				status={status}
				size="sm"
				pulse={status !== "neutral"}
				className="w-max self-start"
				data-testid="status-card-phase"
			>
				{enso ? PHASE_NAMES[enso.phase] ?? enso.phase : "reading"}
			</AnimatedBadge>
			<span className="text-[10px] text-muted-foreground">
				{enso ? `ONI ${typeof enso.oni === "number" ? enso.oni.toFixed(2) : "—"}°C · ${enso.month}` : "measuring the ocean"}
			</span>
			<Button
				variant="link"
				size="sm"
				className="w-max px-0 text-xs"
				onClick={openChat}
			>
				<MessageSquareIcon data-icon />
				Ask the Earth
			</Button>
		</div>
	);
}
