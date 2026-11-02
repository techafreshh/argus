import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import SpendEvalPanel from "../panels/SpendEvalPanel";

/** Judge-facing efficiency: Meta credits consumed + eval-gate probe status. */
export default function SpendEvalPage() {
	return (
		<div className="page">
			<PageHeader
				title="Spend & eval"
				blurb="What the demo consumes, and whether the honesty gates hold."
			/>
			<Card label="spend-eval">
				<SpendEvalPanel />
			</Card>
		</div>
	);
}
