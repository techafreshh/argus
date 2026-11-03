import { Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "@/components/app-shell";
import { EnsoProvider } from "@/shell/enso-context";
import OnboardingWizard from "./onboarding/OnboardingWizard";
import GlobePage from "./pages/GlobePage";
import WatchlistPage from "./pages/WatchlistPage";
import AlertsPage from "./pages/AlertsPage";
import ReceiptsPage from "./pages/ReceiptsPage";
import ReportsPage from "./pages/ReportsPage";
import SpendEvalPage from "./pages/SpendEvalPage";
import AnalogsPage from "./pages/AnalogsPage";
import ToolboxPage from "./pages/ToolboxPage";
import NotFoundPage from "./pages/NotFoundPage";

/** The control room: one shell, one page per beat of the demo. */
export default function App() {
	const { pathname } = useLocation();
	return (
		<EnsoProvider>
			<AppShell pathname={pathname}>
				<Routes>
					<Route path="/" element={<GlobePage />} />
					<Route path="/watchlist" element={<WatchlistPage />} />
					<Route path="/alerts" element={<AlertsPage />} />
					<Route path="/receipts" element={<ReceiptsPage />} />
					<Route path="/reports" element={<ReportsPage />} />
					<Route path="/spend-eval" element={<SpendEvalPage />} />
					<Route path="/analogs" element={<AnalogsPage />} />
					<Route path="/toolbox" element={<ToolboxPage />} />
					<Route path="*" element={<NotFoundPage />} />
				</Routes>
			</AppShell>
			<OnboardingWizard />
		</EnsoProvider>
	);
}
