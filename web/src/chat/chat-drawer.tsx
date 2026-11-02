import {
	createContext,
	lazy,
	Suspense,
	useContext,
	useMemo,
	useState,
	type ReactNode,
} from "react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Loader } from "@/components/motion/loader";

const ChatPanel = lazy(() => import("./ChatPanel"));

type ChatDrawerState = { openChat: () => void };

const ChatDrawerContext = createContext<ChatDrawerState>({ openChat: () => {} });

export function useChatDrawer(): ChatDrawerState {
	return useContext(ChatDrawerContext);
}

/** Global "Ask the Earth" dock: the AG-UI conversation slides over any page. */
export function ChatDrawerProvider({ children }: { children: ReactNode }) {
	const [open, setOpen] = useState(false);
	const value = useMemo<ChatDrawerState>(() => ({ openChat: () => setOpen(true) }), []);

	return (
		<ChatDrawerContext.Provider value={value}>
			{children}
			<Sheet open={open} onOpenChange={setOpen}>
				<SheetContent
					side="right"
					className="flex w-full flex-col gap-0 overflow-y-auto p-4 sm:max-w-[520px]"
				>
					<SheetHeader className="pb-2">
						<SheetTitle>Ask the Earth</SheetTitle>
						<SheetDescription>
							Plans, tool calls and receipts stream live over AG-UI.
						</SheetDescription>
					</SheetHeader>
					<Suspense fallback={<Loader variant="dots" size={20} label="Loading chat" />}>
						<ChatPanel />
					</Suspense>
				</SheetContent>
			</Sheet>
		</ChatDrawerContext.Provider>
	);
}
