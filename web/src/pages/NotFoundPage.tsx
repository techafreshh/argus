import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { PageHeader } from "../shell/page-header";

/** Unknown route — the room has seven doors and this is none of them. */
export default function NotFoundPage() {
	return (
		<div className="page flex flex-col items-start gap-3">
			<PageHeader title="404" blurb="No such room in the control room." />
			<Button asChild variant="outline" size="sm">
				<Link to="/">Back to the globe</Link>
			</Button>
		</div>
	);
}
