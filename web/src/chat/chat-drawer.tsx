import {
	createContext,
	lazy,
	Suspense,
	useContext,
	useMemo,
	useState,
	type ReactNode,
} from "react";
import { Drawer } from "@/components/motion/drawer";
import { Loader } from "@/components/motion/loader";
import { MessageCircleIcon, XIcon } from "lucide-react";

const ChatPanel = lazy(() => import("./ChatPanel"));

type ChatDrawerState = { openChat: (question?: string) => void };

const ChatDrawerContext = createContext<ChatDrawerState>({ openChat: () => {} });

export function useChatDrawer(): ChatDrawerState {
	return useContext(ChatDrawerContext);
}

/** Global "Ask the Earth" dock: the AG-UI conversation slides over any page.
 * A floating launcher sits bottom-right on every route; a `question` handed to
 * `openChat` (e.g. from the ⌘K palette) asks itself on arrival. */
export function ChatDrawerProvider({ children }: { children: ReactNode }) {
	const [open, setOpen] = useState(false);
	const [seed, setSeed] = useState<string | null>(null);
	const value = useMemo<ChatDrawerState>(
		() => ({
			openChat: (question?: string) => {
				setSeed(question ?? null);
				setOpen(true);
			},
		}),
		[],
	);

	return (
		<ChatDrawerContext.Provider value={value}>
			{children}
			{!open && (
				<button
					type="button"
					aria-label="open chat drawer"
					data-testid="chat-fab"
					className="chat-fab"
					onClick={() => setOpen(true)}
				>
					<MessageCircleIcon className="chat-fab-icon" aria-hidden="true" />
					<span className="chat-fab-label">Ask the Earth</span>
				</button>
			)}
			<Drawer
				open={open}
				onOpenChange={(next) => {
					setOpen(next);
					// The seed is a one-shot for this open; clearing it here keeps
					// the panel's identity stable while the seeded run streams.
					if (!next) setSeed(null);
				}}
				side="right"
				ariaLabel="Ask the Earth"
				className="w-full max-w-[85vw] gap-0 p-4 sm:w-[560px]"
			>
				<div className="flex shrink-0 items-start justify-between gap-3 pb-2">
					<div>
						<h2 className="font-semibold text-foreground">Ask the Earth</h2>
						<p className="text-muted-foreground text-sm">
							Plans, tool calls and receipts stream live over AG-UI.
						</p>
					</div>
					<button
						type="button"
						aria-label="Close"
						data-beui="drawer-close"
						className="rounded-lg p-1.5 text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
						onClick={() => setOpen(false)}
					>
						<XIcon className="size-5" aria-hidden="true" />
					</button>
				</div>
				<Suspense fallback={<Loader variant="dots" size={20} label="Loading chat" />}>
					<ChatPanel key={seed ?? "empty"} initialQuestion={seed} />
				</Suspense>
			</Drawer>
		</ChatDrawerContext.Provider>
	);
}
