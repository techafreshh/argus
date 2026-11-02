import type React from "react";

/** ARGUS mark: the watchman's aperture — a fixed eye inside an orbital sweep. */
export const LogoIcon = (props: React.ComponentProps<"svg">) => (
	<svg viewBox="0 0 24 24" fill="none" {...props}>
		<circle
			cx="12"
			cy="12"
			r="9.25"
			stroke="currentColor"
			strokeWidth="1.5"
		/>
		<circle cx="12" cy="12" r="3" fill="currentColor" />
		<path
			d="M12 2.75a9.25 9.25 0 0 1 9.25 9.25"
			stroke="currentColor"
			strokeWidth="2.75"
			strokeLinecap="round"
		/>
	</svg>
);
