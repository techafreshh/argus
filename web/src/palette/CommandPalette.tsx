import { useCallback, useEffect, useState } from "react";
import { previewTemplate, type AskPreview } from "../api";
import MissingDataCard from "./MissingDataCard";

const DEMO_REGION = { type: "bbox", coords: [24, -12.5, 30, -8] } as const;

/** ⌘K command palette routing typed questions through POST /api/ask. */
export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("Is vegetation declining?");
  const [result, setResult] = useState<AskPreview | null>(null);
  const [note, setNote] = useState("");

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
    setNote("loading…");
    try {
      const preview = await previewTemplate(
        question,
        { type: "bbox", coords: [...DEMO_REGION.coords] },
        "daily",
      );
      setResult(preview);
      setNote(preview.template ? `template: ${preview.template}` : "template: unrouted");
    } catch (err) {
      setNote(`ask failed: ${String(err)}`);
    }
  }, [question]);

  return (
    <>
      <button type="button" aria-label="open command palette" onClick={() => setOpen(true)}>
        ⌘K Ask…
      </button>
      {open && (
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
                placeholder="Ask anything…"
              />
              <button type="button" onClick={() => void ask()}>
                Ask
              </button>
              <button type="button" aria-label="close command palette" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
            {note && <p data-testid="palette-status">{note}</p>}
            {result && result.template && (
              <pre data-testid="palette-plan">{JSON.stringify(result, null, 2)}</pre>
            )}
            {result && !result.template && <MissingDataCard preview={result} />}
          </div>
        </div>
      )}
    </>
  );
}
