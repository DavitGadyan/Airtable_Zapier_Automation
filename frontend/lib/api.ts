/**
 * Client for the FastAPI service.
 *
 * Every call returns a discriminated result rather than throwing. The
 * dashboard has to degrade to a readable "service not reachable" state instead
 * of a blank screen or an error overlay -- this app gets opened in front of
 * clients, and the Architecture tab in particular must render with the backend
 * stopped.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; offline: boolean };

export interface PipelineStage {
  name: string;
  count: number;
}

export interface PipelineResponse {
  stages: PipelineStage[];
  total: number;
}

export interface ReviewItem {
  table: string;
  record_id: string;
  created_time?: string;
  reason?: string;
  fields: Record<string, unknown>;
}

export interface ReviewQueueResponse {
  count: number;
  items: ReviewItem[];
}

async function get<T>(path: string): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) {
      return {
        ok: false,
        error: `${response.status} ${response.statusText}`,
        offline: false,
      };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    // A network-level failure is the expected case when the service is simply
    // not running, so it gets its own state rather than being reported as an
    // error the user could act on.
    return { ok: false, error: "Service not reachable", offline: true };
  }
}

export const fetchPipeline = () => get<PipelineResponse>("/pipeline");
export const fetchReviewQueue = () => get<ReviewQueueResponse>("/review-queue");

export async function resolveReview(
  recordId: string,
  approve: boolean,
  note?: string,
): Promise<ApiResult<unknown>> {
  try {
    const response = await fetch(`${API_BASE}/review/${recordId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve, note }),
    });
    if (!response.ok) {
      return {
        ok: false,
        error: `${response.status} ${response.statusText}`,
        offline: false,
      };
    }
    return { ok: true, data: await response.json() };
  } catch {
    return { ok: false, error: "Service not reachable", offline: true };
  }
}
