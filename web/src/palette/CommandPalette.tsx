import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
	BellIcon,
	FileTextIcon,
	GaugeIcon,
	GlobeIcon,
	HistoryIcon,
	ListPlusIcon,
	MessageCircleIcon,
	OrbitIcon,
	ReceiptTextIcon,
	WebhookIcon,
	WrenchIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import {
	CommandPalette as BeUICommandPalette,
	type CommandItem,
} from "@/components/motion/command-palette";
import { useChatDrawer } from "@/chat/chat-drawer";

/** Rooms and surfaces the palette can jump to. */
const PLACES: Array<{ label: string; path: string; icon: CommandItem["icon"] }> = [
	{ label: "Globe — live SST watch", path: "/", icon: GlobeIcon },
	{ label: "Watchlist — add a watch", path: "/watchlist", icon: ListPlusIcon },
	{ label: "Alerts — approval queue", path: "/alerts", icon: BellIcon },
	{ label: "Reports — graded intelligence", path: "/reports", icon: FileTextIcon },
	{ label: "Analogs — closest years", path: "/analogs", icon: HistoryIcon },
	{ label: "Receipts — every tool call", path: "/receipts", icon: ReceiptTextIcon },
	{ label: "Toolbox — source registry", path: "/toolbox", icon: WrenchIcon },
	{ label: "Channels — webhook delivery", path: "/channels", icon: WebhookIcon },
	{ label: "Spend & eval — budget, probes", path: "/spend-eval", icon: GaugeIcon },
];

/** Catalog-backed examples: every one routes to a real pipeline. */
const EXAMPLES = [
	"Is flooding worsening here?",
	"Any active fire anomalies this week?",
	"Is a drought developing here?",
] as const;

/** ⌘K: jump anywhere, or ask ARGUS a question (streams into the chat dock).
 * Fuzzy filter, grouped results, keyboard cursor — beUI command palette. */
export function CommandPalette() {
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");
	const navigate = useNavigate();
	const { openChat } = useChatDrawer();

	const question = query.trim();
	const items: CommandItem[] = [
		...(question
			? [
					{
						id: "ask-argus",
						label: `Ask ARGUS — “${question}”`,
						group: "Ask the Earth",
						keywords: ["question", "ask", "chat", "pipeline"],
						icon: OrbitIcon,
						hint: "Enter",
						onSelect: () => openChat(question),
					},
				]
			: []),
		{
			id: "open-chat",
			label: "Open the chat dock",
			group: "Ask the Earth",
			keywords: ["chat", "conversation", "ag-ui"],
			icon: MessageCircleIcon,
			onSelect: () => openChat(),
		},
		...EXAMPLES.map((example, i) => ({
			id: `example-${i}`,
			label: example,
			group: "Try one",
			keywords: ["example", "recipe"],
			icon: OrbitIcon,
			onSelect: () => openChat(example),
		})),
		...PLACES.map((place) => ({
			id: `go-${place.path}`,
			label: place.label,
			group: "Go to",
			keywords: ["navigate", "page", "room"],
			icon: place.icon,
			onSelect: () => navigate(place.path),
		})),
	];

	return (
		<>
			<Button
				type="button"
				variant="outline"
				size="sm"
				className="gap-2 text-muted-foreground"
				aria-label="open command palette"
				data-beui="command-palette"
				onClick={() => setOpen(true)}
			>
				Ask the Earth
				<KbdGroup>
					<Kbd>⌘</Kbd>
					<Kbd>K</Kbd>
				</KbdGroup>
			</Button>
			<BeUICommandPalette
				open={open}
				onOpenChange={setOpen}
				onQueryChange={setQuery}
				items={items}
				placeholder="Ask the Earth anything, or jump anywhere…"
				emptyMessage="Type a question and press Enter to ask ARGUS."
			/>
		</>
	);
}
