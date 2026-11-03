import { useEffect, useState } from "react";
import { authStatus, type AuthStatus } from "../api";
import { LogoIcon } from "@/components/logo";

export type AppGate = "pending" | "open" | "signin";

/**
 * App-load auth check: while the GitHub gate is armed and no session exists,
 * the dashboard never mounts — the visitor gets a full-screen ARGUS sign-in.
 * Local / keyless boots resolve to "open" and behave as before.
 */
export function useAppGate(): AppGate {
	const [gate, setGate] = useState<AppGate>("pending");

	useEffect(() => {
		let alive = true;
		authStatus()
			.then((status: AuthStatus) => {
				if (!alive) return;
				setGate(status.enabled && !status.user ? "signin" : "open");
			})
			.catch(() => {
				// The status route is open by design; if even it fails, stay out
				// of the room rather than flash a dashboard that 401s everywhere.
				if (alive) setGate("signin");
			});
		return () => {
			alive = false;
		};
	}, []);

	return gate;
}

export function GateSplash() {
	return (
		<div className="grid min-h-screen place-items-center bg-background">
			<span className="animate-pulse text-muted-foreground text-xs tracking-[0.3em]">
				ARGUS
			</span>
		</div>
	);
}

/** Pitch-black sign-in screen: the eye, the promise, one button. */
export function SignInScreen() {
	return (
		<div
			className="grid min-h-screen place-items-center bg-background"
			data-testid="signin-gate"
		>
			<div className="flex flex-col items-center gap-6 px-6 text-center">
				<div className="flex flex-col items-center gap-3">
					<LogoIcon className="size-20 text-cool" />
					<h1 className="font-semibold tracking-[0.35em] text-foreground text-xl">
						ARGUS
					</h1>
					<p className="max-w-sm text-balance text-muted-foreground text-sm">
						An autonomous analyst watching the planet from orbit — plan,
						acquire, analyze, verify, alert. With receipts.
					</p>
				</div>
				<a
					className="btn btn--primary"
					data-testid="github-signin"
					href="/api/auth/login?next=/"
				>
					Sign in with GitHub
				</a>
				<p className="text-muted-foreground text-xs">
					Pipeline runs need a sign-in. Nothing publishes without approval.
				</p>
			</div>
		</div>
	);
}
