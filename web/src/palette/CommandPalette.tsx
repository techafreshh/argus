import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { useChatDrawer } from "@/chat/chat-drawer";
import { previewTemplate, type AskPreview } from "../api";
import MissingDataCard from "./MissingDataCard";

const DEMO_REGION = { type: "bbox", coords: [24, -12.5, 30, -8] } as const;

/** Catalog-backed examples: every one routes to a real pipeline. */
const EXAMPLES = [
	"Is flooding worsening here?",
	"Any active fire anomalies this week?",
	"Is a drought developing here?",
] as const;

const PLACES = [
	{ label: "Globe", path: "/" },
	{ label: "Watchlist", path: "/watchlist" },
	{ label: "Alerts", path: "/alerts" },
	{ label: "Reports", path: "/reports" },
	{ label: "Analogs", path: "/analogs" },
	{ label: "Receipts", path: "/receipts" },
	{ label: "Spend & eval", path: "/spend-eval" },
] as const;

/** ⌘K command palette: navigate the room, or route a typed question through POST /api/ask. */
export function CommandPalette() {
	const [open, setOpen] = useState(false);
	const [question, setQuestion] = useState("Is vegetation declining?");
	const [result, setResult] = useState<AskPreview | null>(null);
	const [note, setNote] = useState("");
	const [failed, setFailed] = useState(false);
	const navigate = useNavigate();
	const { openChat } = useChatDrawer();

	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			const mod = e.metaKey || e.ctrlKey;
			if (mod && (e.key === "k" || e.key === "K")) {
				e.preventDefault();
				setOpen((v) => !v);
			} else if (e.key === "Escape") {
				setOpen(false);
			}
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);

	const ask = useCallback(async () => {
		setFailed(false);
		try {
			const preview = await previewTemplate(
				question,
				{ type: "bbox", coords: [...DEMO_REGION.coords] },
				"daily",
			);
			setResult(preview);
			setNote("");
		} catch (err) {
			setNote(`Ask failed — ${err instanceof Error ? err.message : String(err)}`);
			setFailed(true);
		}
	}, [question]);

	const go = (path: string) => {
		setOpen(false);
		navigate(path);
	};

	return (
		<>
			<Button
				type="button"
				variant="outline"
				size="sm"
				className="gap-2 text-muted-foreground"
				aria-label="open command palette"
				onClick={() => setOpen(true)}
			>
				Ask the Earth
				<KbdGroup>
					<Kbd>⌘</Kbd>
					<Kbd>K</Kbd>
				</KbdGroup>
			</Button>
			{open &&
				// Portal: the overlay must escape the animated main column, or the
				// entrance transform traps the fixed positioning inside the topbar.
				createPortal(
					<div data-beui="command-palette" role="dialog" aria-label="command palette">
						<div className="palette-dialog">
							<div data-beui="morphing-search">
								<input
									aria-label="ask anything"
									autoFocus
									value={question}
									onChange={(e) => setQuestion(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") void ask();
									}}
									placeholder="Ask the Earth"
								/>
								<span className="kbd" aria-hidden="true">
									Enter
								</span>
								<button type="button" className="btn btn--primary" onClick={() => void ask()}>
									Ask
								</button>
								<button
									type="button"
									className="btn btn--quiet"
									aria-label="close command palette"
									onClick={() => setOpen(false)}
								>
									Close
								</button>
							</div>
							<div className="palette-examples">
								<span className="palette-examples-label">Go to</span>
								{PLACES.map((p) => (
									<button
										key={p.path}
										type="button"
										className="tag"
										onClick={() => go(p.path)}
									>
										{p.label}
									</button>
								))}
								<button type="button" className="tag" onClick={() => { setOpen(false); openChat(); }}>
									Open chat
								</button>
							</div>
							{!result && (
								<div className="palette-examples">
									<span className="palette-examples-label">Try</span>
									{EXAMPLES.map((q) => (
										<button key={q} type="button" className="tag" onClick={() => setQuestion(q)}>
											{q}
										</button>
									))}
								</div>
							)}
							{note && (
								<p data-testid="palette-status" className={failed ? "note note--error" : "note"}>
									{note}
								</p>
							)}
							{result && result.template && (
								<pre className="dump" data-testid="palette-plan">
									{JSON.stringify(result, null, 2)}
								</pre>
							)}
							{result && !result.template && <MissingDataCard preview={result} />}
						</div>
					</div>,
					document.body,
				)}
		</>
	);
}
