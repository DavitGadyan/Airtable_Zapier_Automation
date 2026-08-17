"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchReviewQueue, resolveReview, type ReviewItem } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

/**
 * The human-review queue.
 *
 * Everything the system declined to do on its own. This screen is what makes
 * conservative confidence thresholds affordable: being unsure costs one click
 * here, rather than becoming a duplicate job somebody finds in three weeks.
 */

const SHOWN_FIELDS = [
  "Bid Name",
  "Lot / Unit",
  "Address",
  "City",
  "State",
  "Scope of Work",
  "Bid Due Date",
  "PO Number",
  "Approved Amount",
  "Deposit Amount",
  "Match Method",
  "Match Score",
  "Extraction Confidence",
] as const;

const MONEY_FIELDS = new Set<string>([
  "Approved Amount",
  "Deposit Amount",
]);

export default function ReviewPage() {
  const [items, setItems] = React.useState<ReviewItem[] | null>(null);
  const [offline, setOffline] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    const result = await fetchReviewQueue();
    if (result.ok) {
      setItems(result.data.items);
      setOffline(false);
    } else {
      setOffline(result.offline);
      setItems(null);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function decide(item: ReviewItem, approve: boolean) {
    setBusy(item.record_id);
    await resolveReview(item.record_id, approve);
    await load();
    setBusy(null);
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-primary">
            Review queue
          </h1>
          <p className="mt-1 text-sm text-tertiary">
            Anything the system wasn&apos;t confident enough to apply on its own.
          </p>
        </div>
        {items ? (
          <Badge variant={items.length ? "warning" : "success"}>
            {items.length} waiting
          </Badge>
        ) : null}
      </div>

      {offline ? (
        <p className="mt-6 rounded-lg border border-border bg-surface-raised p-5 text-sm text-secondary">
          The extraction service isn&apos;t running, so there is nothing to show
          here yet.
        </p>
      ) : items && items.length === 0 ? (
        <div className="mt-6 rounded-lg border border-border bg-surface-raised p-6 text-center">
          <p className="text-sm font-medium text-primary">Queue is empty.</p>
          <p className="mt-1 text-sm text-tertiary">
            A short queue is the honest signal that extraction is working.
          </p>
        </div>
      ) : null}

      <ul className="mt-6 space-y-4">
        {items?.map((item) => (
          <li
            key={item.record_id}
            className="rounded-lg border border-border bg-surface-raised p-4"
          >
            {/* Not flex-wrap: a long reason would otherwise push the table
                badge onto its own line, so cards with wordy reasons look
                different from cards with short ones. */}
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-primary">
                  {String(
                    item.fields["Bid Name"] ??
                      item.fields["PO Number"] ??
                      item.record_id,
                  )}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-secondary">
                  {item.reason ?? "Flagged for review."}
                </p>
              </div>
              <Badge variant="outline" className="shrink-0">
                {item.table}
              </Badge>
            </div>

            <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
              {SHOWN_FIELDS.filter(
                (name) =>
                  item.fields[name] !== undefined && item.fields[name] !== "",
              ).map((name) => (
                <div key={name} className="flex gap-2">
                  <dt className="shrink-0 text-tertiary">{name}</dt>
                  <dd className="min-w-0 truncate text-secondary">
                    {/* Money reads as money. A bare 8400 next to a reviewer
                        deciding whether to approve an invoice is needless
                        friction. */}
                    {MONEY_FIELDS.has(name)
                      ? formatCurrency(Number(item.fields[name]))
                      : String(item.fields[name])}
                  </dd>
                </div>
              ))}
            </dl>

            <div className="mt-4 flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                disabled={busy === item.record_id}
                onClick={() => void decide(item, true)}
              >
                Approve
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={busy === item.record_id}
                onClick={() => void decide(item, false)}
              >
                Reject
              </Button>
              {/* Worth stating on the screen itself: rejecting is not a
                  delete, so a mistake here is recoverable. */}
              <span className="text-xs text-tertiary">
                Rejecting marks the record Cancelled — it is never deleted.
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
