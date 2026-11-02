import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import AnalogTimeline from "../panels/AnalogTimeline";

/** The analog engine: today's ocean state against the closest historical years. */
export default function AnalogsPage() {
	return (
		<div className="page">
			<PageHeader
				title="Analogs"
				blurb="Closest historical years to today's ocean state — and what happened next."
			/>
			<Card label="analog-timeline">
				<AnalogTimeline />
			</Card>
		</div>
	);
}
