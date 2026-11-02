import { Card } from "../beui";
import { PageHeader } from "../shell/page-header";
import ReceiptsPanel from "../panels/ReceiptsPanel";

/** Every tool call logs a receipt: source URL, params, data hash, tokens. */
export default function ReceiptsPage() {
	return (
		<div className="page">
			<PageHeader
				title="Receipts"
				blurb="Claims are audit trails — every tool call logs where its data came from."
			/>
			<Card label="receipts">
				<ReceiptsPanel />
			</Card>
		</div>
	);
}
