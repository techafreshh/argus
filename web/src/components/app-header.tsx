"use client";

import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { AppBreadcrumbs } from "@/components/app-breadcrumbs";
import { CustomSidebarTrigger } from "@/components/custom-sidebar-trigger";
import { CommandPalette } from "@/palette/CommandPalette";
import { UtcClock } from "@/shell/utc-clock";
import { useChatDrawer } from "@/chat/chat-drawer";
import { Button } from "@/components/ui/button";
import { MessageSquareIcon } from "lucide-react";
import { navLinks } from "@/components/app-shared";

export function AppHeader({ pathname }: { pathname?: string }) {
	const { openChat } = useChatDrawer();
	const activeItem = navLinks.find((item) => item.path === pathname);
	return (
		<header
			className={cn(
				"mb-6 flex items-center justify-between gap-2 md:px-2"
			)}
		>
			<div className="flex items-center gap-3">
				<CustomSidebarTrigger />
				<Separator
					className="mr-2 h-4 data-[orientation=vertical]:self-center"
					orientation="vertical"
				/>
				<AppBreadcrumbs page={activeItem} />
			</div>
			<div className="flex items-center gap-2">
				<UtcClock />
				<Separator
					className="h-4 data-[orientation=vertical]:self-center"
					orientation="vertical"
				/>
				<CommandPalette />
				<Button
					aria-label="open chat"
					size="icon"
					variant="ghost"
					onClick={() => openChat()}
				>
					<MessageSquareIcon />
				</Button>
			</div>
		</header>
	);
}
