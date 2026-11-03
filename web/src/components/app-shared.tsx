import type { ReactNode } from "react";
import {
	BellIcon,
	FileTextIcon,
	GaugeIcon,
	GlobeIcon,
	HistoryIcon,
	ListPlusIcon,
	ReceiptTextIcon,
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
		items: [{ title: "Spend & eval", path: "/spend-eval", icon: <GaugeIcon /> }],
	},
];

export const navLinks: SidebarNavItem[] = navGroups.flatMap((group) => group.items);
