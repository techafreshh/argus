import type { ReactNode } from "react";
import {
	BellIcon,
	FileTextIcon,
	GaugeIcon,
	GlobeIcon,
	HistoryIcon,
	ListPlusIcon,
	ReceiptTextIcon,
	WebhookIcon,
	WrenchIcon,
} from "lucide-react";

export type SidebarNavItem = {
	title: string;
	path?: string;
	icon?: ReactNode;
	subItems?: SidebarNavItem[];
};

export type SidebarNavGroup = {
	label: string;
	items: SidebarNavItem[];
};

export const navGroups: SidebarNavGroup[] = [
	{
		label: "Watch",
		items: [
			{ title: "Globe", path: "/", icon: <GlobeIcon /> },
			{ title: "Watchlist", path: "/watchlist", icon: <ListPlusIcon /> },
			{ title: "Alerts", path: "/alerts", icon: <BellIcon /> },
		],
	},
	{
		label: "Intelligence",
		items: [
			{ title: "Reports", path: "/reports", icon: <FileTextIcon /> },
			{ title: "Analogs", path: "/analogs", icon: <HistoryIcon /> },
			{ title: "Receipts", path: "/receipts", icon: <ReceiptTextIcon /> },
			{ title: "Toolbox", path: "/toolbox", icon: <WrenchIcon /> },
		],
	},
	{
		label: "System",
		items: [
			{ title: "Channels", path: "/channels", icon: <WebhookIcon /> },
			{ title: "Spend & eval", path: "/spend-eval", icon: <GaugeIcon /> },
		],
	},
];

export const navLinks: SidebarNavItem[] = navGroups.flatMap((group) => group.items);

/** Call to action when a gated pipeline action 401s: GitHub sign-in and a
 * bounce back to the room. Renders even while auth is disabled — GitHub
 * answers 404 and the room keeps working, so the CTA is only exposed where
 * a 401 actually happened. */
export function GitHubSignInCta({ next = "/" }: { next?: string }) {
	return (
		<a
			className="btn btn--primary"
			data-testid="github-signin"
			href={`/api/auth/login?next=${encodeURIComponent(next)}`}
		>
			Sign in with GitHub
		</a>
	);
}
