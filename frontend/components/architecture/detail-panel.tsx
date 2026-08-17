"use client";

import { ProductMark } from "@/components/architecture/product-mark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TIER_BY_ID, type ArchNode } from "@/lib/architecture-data";
import { cn } from "@/lib/utils";

/**
 * The focused component's rationale.
 *
 * Rendered as ordinary HTML, deliberately. Prose drawn into the WebGL scene is
 * unreadable once a video is compressed, and cost figures are the thing a client
 * most needs to actually read. The 3D scene carries structure; this carries
 * meaning.
 */
export function DetailPanel({
  node,
  onClose,
  tourNote,
}: {
  node: ArchNode | null;
  onClose: () => void;
  tourNote?: string;
}) {
  if (!node) {
    return (
      <aside className="flex h-full flex-col justify-center rounded-lg border border-border bg-surface-raised p-6 text-center">
        <p className="text-sm font-medium text-primary">Select a component</p>
        <p className="mt-1.5 text-xs leading-relaxed text-secondary">
          Click any node to see what it does, why it is there, what it saves, and
          what the customer feels. Or start the guided tour.
        </p>
      </aside>
    );
  }

  const tier = TIER_BY_ID.get(node.tier);

  return (
    <aside
      className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-surface-raised"
      aria-live="polite"
    >
      <header className="shrink-0 border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold tracking-tight text-primary">
                {node.label}
              </h2>
              {node.logo ? <ProductMark logo={node.logo} /> : null}
            </div>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-tertiary">
              <span
                aria-hidden
                className="inline-block size-2 rounded-full"
                style={{ backgroundColor: tier?.color }}
              />
              {tier?.label}
              {node.sub ? <span> · {node.sub}</span> : null}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 shrink-0"
            onClick={onClose}
            aria-label="Close detail panel"
          >
            <svg
              viewBox="0 0 24 24"
              className="size-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              aria-hidden
            >
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </Button>
        </div>

        {node.metric ? (
          <div className="mt-3 rounded-md border border-border bg-surface px-3 py-2">
            <p className="font-mono text-lg font-semibold tabular-nums text-primary">
              {node.metric.value}
              {node.metric.estimated ? (
                <Badge variant="outline" className="ml-2 align-middle">
                  estimate
                </Badge>
              ) : null}
            </p>
            <p className="mt-0.5 text-xs text-secondary">{node.metric.caption}</p>
          </div>
        ) : null}
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {/*
          Optional: where a component can be *shown* rather than described — the
          product's own UI, a sample result — render a small worked example here
          for that node's id. Build it from the real components rather than
          embedding a screenshot: it must render with the backend off, it stays
          legible at any zoom, and it cannot drift out of date with the design
          system.

            {node.id === "app" ? <ProductPreview /> : null}
        */}

        <Section title="What it does" body={node.what} />
        <Section title="Why it is used" body={node.whyUsed} />
        <Section
          title="Client benefit — cost"
          body={node.clientBenefit}
          accent="cost"
        />
        <Section
          title="User benefit — quality"
          body={node.userBenefit}
          accent="quality"
        />
      </div>

      {/* The presenter's line. Visible on screen deliberately: it is a prompt for
          the person recording, and it reads as a summary to anyone watching. */}
      <footer className="shrink-0 border-t border-border bg-surface px-5 py-3">
        <p className="text-[10px] font-medium uppercase tracking-widest text-tertiary">
          {tourNote ? "Guided tour" : "Say this"}
        </p>
        <p className="mt-1 text-xs italic leading-relaxed text-secondary">
          “{tourNote ?? node.demoNote}”
        </p>
      </footer>
    </aside>
  );
}

function Section({
  title,
  body,
  accent,
}: {
  title: string;
  body: string;
  accent?: "cost" | "quality";
}) {
  return (
    <div
      className={cn(
        accent && "rounded-md border-l-2 pl-3",
        accent === "cost" && "border-warning bg-warning-subtle/30 py-2 pr-3",
        accent === "quality" && "border-success bg-success-subtle/30 py-2 pr-3",
      )}
    >
      <h3 className="text-[10px] font-semibold uppercase tracking-widest text-tertiary">
        {title}
      </h3>
      <p className="mt-1 text-[13px] leading-relaxed text-primary">
        {renderEmphasis(body)}
      </p>
    </div>
  );
}

/**
 * Render `**bold**` spans, and nothing else.
 *
 * Not a markdown parser and shouldn't become one. The rationale copy is prose,
 * with exactly one thing worth emphasising: the sentence in each node that
 * works against our own interest ("not enabled by default, and this is
 * deliberate"). Those are the most persuasive lines on the page and they need
 * to catch the eye. Everything else stays plain — and without this, the
 * asterisks rendered literally, which looks like a bug in the deck.
 */
function renderEmphasis(text: string): React.ReactNode {
  if (!text.includes("**")) return text;
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={index} className="font-semibold">
        {part.slice(2, -2)}
      </strong>
    ) : (
      part
    ),
  );
}
