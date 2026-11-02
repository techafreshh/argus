import { useEffect, useState } from "react";

function utcClock(iso: string): string {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	const p = (n: number) => String(n).padStart(2, "0");
	return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`;
}

/** Live UTC clock for the header — the room runs on UTC, always. */
export function UtcClock() {
	const [now, setNow] = useState(() => utcClock(new Date().toISOString()));
	useEffect(() => {
		const t = setInterval(() => setNow(utcClock(new Date().toISOString())), 1000);
		return () => clearInterval(t);
	}, []);
	return (
		<span
			aria-label="utc-clock"
			className="hidden font-mono text-xs text-muted-foreground sm:inline"
		>
			{now} UTC
		</span>
	);
}
