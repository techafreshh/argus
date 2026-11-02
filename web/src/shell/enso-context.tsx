import {
	createContext,
	useContext,
	useEffect,
	useState,
	type ReactNode,
} from "react";
import { getEnsoStatus, type EnsoStatus } from "../api";

type EnsoState = { enso: EnsoStatus | null; note: string };

const EnsoContext = createContext<EnsoState>({ enso: null, note: "" });

/** Fetches the ENSO readout once for the whole room (sidebar card + globe). */
export function EnsoProvider({ children }: { children: ReactNode }) {
	const [state, setState] = useState<EnsoState>({ enso: null, note: "" });

	useEffect(() => {
		let alive = true;
		(async () => {
			try {
				const status = await getEnsoStatus();
				if (!alive) return;
				setState({ enso: status, note: "" });
			} catch (err) {
				if (!alive) return;
				setState({
					enso: null,
					note: `ENSO readout unavailable — ${err instanceof Error ? err.message : String(err)}`,
				});
			}
		})();
		return () => {
			alive = false;
		};
	}, []);

	return <EnsoContext.Provider value={state}>{children}</EnsoContext.Provider>;
}

export function useEnso(): EnsoState {
	return useContext(EnsoContext);
}
