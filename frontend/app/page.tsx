"use client";

import * as React from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchPipeline, type PipelineStage } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * The pipeline board -- the "one easy-to-use dashboard" from the brief.
 *
 * The fourteen stages come from lib/architecture-data's sibling in the
 * backend (app/pipeline.py), which is the single source of truth shared by
 * the Airtable schema, the revision logic and this board.
 */

const STAGE_GROUPS: { title: string; stages: string[] }[] = [
  { title: "Bidding", stages: ["Bid Request", "Bid Assigned", "Bid Submitted"] },
  {
    title: "Won & funded",
    stages: ["PO Received", "Deposit Invoice Sent", "Deposit Paid"],
  },
  {
    title: "Delivery",
    stages: [
      "Crew Assigned",
      "Materials Ordered",
      "Scheduled",
      "In Progress",
      "Completed",
    ],
  },
  {
    title: "Closing",
    stages: ["Final Invoice Sent", "Final Payment Received", "Closed"],
  },
  { title: "Not proceeding", stages: ["Lost", "Cancelled"] },
];

// Stages where a job sitting still costs money: a PO with no deposit invoice,
// or completed work never invoiced. Surfacing these is most of the value of
// having a board at all.
const ATTENTION_STAGES = new Set(["PO Received", "Completed"]);

export default function PipelinePage() {
  const [stages, setStages] = React.useState<PipelineStage[] | null>(null);
  const [offline, setOffline] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    const result = await fetchPipeline();
    if (result.ok) {
      setStages(result.data.stages);
      setOffline(false);
      setError(null);
    } else {
      setOffline(result.offline);
      setError(result.error);
    }
    setLoading(false);
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const countFor = (name: string) =>
    stages?.find((s) => s.name === name)?.count ?? 0;
  const total = stages?.reduce((sum, s) => sum + s.count, 0) ?? 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-primary">
            Pipeline
          </h1>
          <p className="mt-1 text-sm text-tertiary">
            Every bid and job, in the fourteen stages from your process.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{total} live</Badge>
          <Button size="sm" onClick={() => void load()} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
      </div>

      {offline ? (
        <div className="mt-6 rounded-lg border border-border bg-surface-raised p-5">
          <p className="text-sm font-medium text-primary">
            The extraction service isn&apos;t running.
          </p>
          <p className="mt-1.5 text-sm text-secondary">
            Start it with{" "}
            <code className="rounded bg-surface-active px-1.5 py-0.5 font-mono text-xs">
              uvicorn app.main:app --reload
            </code>{" "}
            in <span className="font-mono text-xs">backend/</span>. The{" "}
            <Link
              href="/architecture"
              className="font-medium text-accent underline underline-offset-2"
            >
              Architecture
            </Link>{" "}
            tab works without it — it renders from static data on purpose.
          </p>
        </div>
      ) : error ? (
        <div className="mt-6 rounded-lg border border-danger bg-danger-subtle p-4 text-sm text-primary">
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STAGE_GROUPS.map((group) => (
          <section
            key={group.title}
            className="rounded-lg border border-border bg-surface-raised p-4"
          >
            <h2 className="text-[11px] font-medium uppercase tracking-wider text-tertiary">
              {group.title}
            </h2>
            <ul className="mt-3 space-y-1">
              {group.stages.map((stage) => {
                const count = countFor(stage);
                const attention = ATTENTION_STAGES.has(stage) && count > 0;
                return (
                  <li
                    key={stage}
                    className={cn(
                      "flex items-center justify-between rounded-md px-2 py-1.5 text-sm",
                      attention ? "bg-warning-subtle" : "",
                    )}
                  >
                    <span className="text-secondary">{stage}</span>
                    <span
                      className={cn(
                        "font-mono text-xs tabular-nums",
                        count > 0 ? "text-primary" : "text-tertiary",
                        attention ? "font-semibold text-warning" : "",
                      )}
                    >
                      {stages ? count : "—"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>

      <p className="mt-6 text-xs leading-relaxed text-tertiary">
        Highlighted stages are where a job sitting still costs money — a PO with
        no deposit invoice raised, or completed work never invoiced. Surfacing
        those is most of the point of having a board.
      </p>
    </div>
  );
}
