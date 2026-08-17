/**
 * Product marks for the detail panel.
 *
 * Hand-drawn simplified glyphs rather than fetched brand assets: the graph must
 * render offline and in CI, and a missing logo file in the middle of a client
 * demo is a worse outcome than a slightly simplified mark. Each is recognisable
 * at the size it is shown, and each sits next to the product name in text.
 *
 * Drop official SVGs into `public/logos/<key>.svg` and they will be preferred —
 * see `Logo` below.
 */

import { cn } from "@/lib/utils";

// Simplified glyphs in each product's own colour: enough to identify the
// technology, without redistributing anyone's trademarked artwork. Drawn
// rather than fetched so the page still renders with no network.
const MARKS: Record<string, { label: string; color: string; path?: string }> = {
  airtable: {
    label: "Airtable",
    color: "#fcb400",
    path: "M12 3 2.5 7.2 12 11.4l9.5-4.2L12 3ZM2.5 10.4v5.2L11 19.4v-5.2l-8.5-3.8Zm19 0L13 14.2v5.2l8.5-3.8v-5.2Z",
  },
  zapier: {
    label: "Zapier",
    color: "#ff4f00",
    path: "M12 2v6.6M12 15.4V22M2 12h6.6M15.4 12H22M5 5l4.7 4.7M14.3 14.3 19 19M19 5l-4.7 4.7M9.7 14.3 5 19",
  },
  claude: {
    label: "Claude Opus 5",
    color: "#d97757",
    path: "M12 3 6 21h3l1.3-4h3.4L15 21h3L12 3Zm-.9 11L12 10.6 12.9 14h-1.8Z",
  },
  gmail: {
    label: "Gmail",
    color: "#ea4335",
    path: "M3 6.5v11h4V11l5 3.6L17 11v6.5h4v-11L12 13 3 6.5Z",
  },
  fastapi: {
    label: "FastAPI",
    color: "#009688",
    path: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 4-5 7h3.2l-.8 5 5-7h-3.2l.8-5Z",
  },
  quickbooks: {
    label: "QuickBooks",
    color: "#2ca01c",
    path: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.2 5.2h2.4v9.6h-2.4V7.2Z",
  },
  // Deliberately grey. Joist is the one box in this diagram we do not
  // integrate with, and the mark should not imply otherwise.
  joist: { label: "Joist", color: "#8a8175" },
  nextjs: { label: "Next.js", color: "#111111" },
};

export function ProductMark({ logo, className }: { logo: string; className?: string }) {
  const mark = MARKS[logo];
  if (!mark) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border",
        "bg-surface px-2 py-0.5 text-xs font-medium text-secondary",
        className,
      )}
    >
      <span
        aria-hidden
        className="inline-block size-2 rounded-sm"
        style={{ backgroundColor: mark.color }}
      />
      {mark.label}
    </span>
  );
}

export function markColor(logo: string | undefined): string | null {
  return logo ? (MARKS[logo]?.color ?? null) : null;
}
