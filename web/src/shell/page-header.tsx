import { TextReveal } from "@/components/motion/text-reveal";

/** Page title with a quiet word-by-word entrance. */
export function PageHeader({ title, blurb }: { title: string; blurb?: string }) {
	return (
		<div className="page-head mb-1">
			<TextReveal
				as="h1"
				text={title}
				className="font-heading text-lg font-medium tracking-tight"
			/>
			{blurb && <p className="text-sm text-muted-foreground">{blurb}</p>}
		</div>
	);
}
