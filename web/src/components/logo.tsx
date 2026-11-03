import type React from "react";

/** ARGUS mark: the watchman's eye over a wireframe globe on an orbital ring,
 * recreated from the brand lockup (eye almond crossing the sphere, iris with
 * a highlight, tilted orbit with satellites). currentColor throughout, so the
 * room's cyan tokens light it. */
export const LogoIcon = (props: React.ComponentProps<"svg">) => (
	<svg viewBox="0 0 24 24" fill="none" {...props}>
		{/* orbital ring + satellites */}
		<ellipse
			cx="12"
			cy="12"
			rx="11.2"
			ry="4.3"
			transform="rotate(-24 12 12)"
			stroke="currentColor"
			strokeWidth="1"
			opacity="0.5"
		/>
		<circle cx="20.1" cy="6.3" r="0.95" fill="currentColor" opacity="0.85" />
		<circle cx="3.9" cy="17.4" r="0.95" fill="currentColor" opacity="0.85" />
		{/* wireframe globe */}
		<circle cx="12" cy="12" r="7" stroke="currentColor" strokeWidth="1.25" opacity="0.75" />
		<ellipse cx="12" cy="12" rx="3" ry="7" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
		<path d="M5.2 12h13.6" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
		<path d="M6.5 8.5h11M6.5 15.5h11" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
		{/* the eye */}
		<path
			d="M2.8 12C5.8 8.1 18.2 8.1 21.2 12C18.2 15.9 5.8 15.9 2.8 12Z"
			stroke="currentColor"
			strokeWidth="1.5"
		/>
		<circle cx="12" cy="12" r="3.4" stroke="currentColor" strokeWidth="1.5" />
		<circle cx="12" cy="12" r="1.5" fill="currentColor" />
		<circle cx="13.3" cy="10.4" r="0.7" fill="currentColor" opacity="0.9" />
	</svg>
);
