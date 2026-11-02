"use client";

import { LogoIcon } from "@/components/logo";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { NavGroup } from "@/components/nav-group";
import { navGroups } from "@/components/app-shared";
import { StatusCard } from "@/shell/status-card";
import { Link } from "react-router-dom";

export function AppSidebar({ pathname }: { pathname?: string }) {
	return (
		<Sidebar collapsible="icon" variant="floating">
			<SidebarHeader className="h-14 justify-center">
				<SidebarMenuButton asChild tooltip="ARGUS control room">
					<Link to="/">
						<LogoIcon className="size-5" />
						<span className="font-mono tracking-[0.22em]">ARGUS</span>
					</Link>
				</SidebarMenuButton>
			</SidebarHeader>
			<SidebarContent>
				{navGroups.map((group, index) => (
					<NavGroup
						key={`sidebar-group-${index}`}
						{...group}
						pathname={pathname}
					/>
				))}
			</SidebarContent>
			<SidebarFooter>
				<StatusCard />
				<div className="mt-2 px-2 pb-1 font-mono text-[10px] text-muted-foreground group-data-[collapsible=icon]:hidden">
					v0.1.0 · MIT
				</div>
			</SidebarFooter>
		</Sidebar>
	);
}
