import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import ReportsView from "../panels/ReportsView";

/** Graded reports: headline, numbers, confidence, before/after, sources. */
export default function ReportsPage() {
	return (
		<div className="page">
			<PageHeader
				title="Reports"
				blurb="Graded intelligence cards — hectares, counts, confidence, receipts."
			/>
			<Card label="reports">
				<ReportsView />
			</Card>
		</div>
	);
}
