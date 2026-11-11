// Browser client for the WhyBot FastAPI backend.
// The base URL is public (NEXT_PUBLIC_API_URL). No keys ever reach the browser.

import { readSse } from "./sse";
import type { ApiErrorCode, Limits, Report, RunEvent, RunRecord, Step } from "./types";

export const API_URL: string | null =
  (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "") || null;

export const MAX_QUESTION_CHARS = 400;

export type ClientErrorCode = ApiErrorCode | "unreachable" | "not_found" | "disabled";

export class ApiRequestError extends Error {
  code: ClientErrorCode;
  constructor(code: ClientErrorCode, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
  }
}

const KNOWN_CODES: readonly string[] = [
  "rate_limited",
  "spend_cap",
  "no_llm",
  "bad_request",
  "timeout",
  "internal",
];

function codeForStatus(status: number): ClientErrorCode {
  if (status === 429) return "rate_limited";
  if (status === 404) return "not_found";
  if (status === 400 || status === 422) return "bad_request";
  if (status === 503) return "no_llm";
  if (status === 504) return "timeout";
  return "internal";
}

/** Turn a non-200 response into an ApiRequestError. Body is `{detail: {code, message}}` or `{detail: string}`. */
async function errorFromResponse(res: Response): Promise<ApiRequestError> {
  let code = codeForStatus(res.status);
  let message = `Request failed with status ${res.status}.`;
  try {
    const body: unknown = await res.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      const d = detail as { code?: unknown; message?: unknown };
      if (typeof d.code === "string" && KNOWN_CODES.includes(d.code)) {
        code = d.code as ApiErrorCode;
      }
      if (typeof d.message === "string") message = d.message;
    }
  } catch {
    // Not JSON. Keep the default message.
  }
  return new ApiRequestError(code, message);
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  if (!API_URL) {
    throw new ApiRequestError("disabled", "The live API is not configured.");
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiRequestError("unreachable", "The live API could not be reached.");
  }
  if (!res.ok) throw await errorFromResponse(res);
  return res;
}

export async function getLimits(signal?: AbortSignal): Promise<Limits> {
  const res = await request("/limits", { signal, headers: { Accept: "application/json" } });
  return (await res.json()) as Limits;
}

export async function getRun(id: string, signal?: AbortSignal): Promise<RunRecord> {
  const res = await request(`/runs/${encodeURIComponent(id)}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  return (await res.json()) as RunRecord;
}

export type AskEvent =
  | { type: "run"; data: RunEvent }
  | { type: "step"; data: Step }
  | { type: "report"; data: Report }
  | { type: "error"; data: { code: ClientErrorCode; message: string } }
  | { type: "done" };

/**
 * POST /ask and stream the agent's events.
 * Resolves when the stream ends. Throws ApiRequestError for non-200 or network failure.
 */
export async function askStream(
  question: string,
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await request("/ask", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ question }),
  });
  if (!res.body) {
    throw new ApiRequestError("internal", "The API returned an empty stream.");
  }
  try {
    await readSse(res.body, (frame) => {
      let data: unknown;
      try {
        data = JSON.parse(frame.data);
      } catch {
        return; // Skip a malformed frame instead of killing the run.
      }
      switch (frame.event) {
        case "run":
          onEvent({ type: "run", data: data as RunEvent });
          break;
        case "step":
          onEvent({ type: "step", data: data as Step });
          break;
        case "report":
          onEvent({ type: "report", data: data as Report });
          break;
        case "error": {
          const d = (data ?? {}) as { code?: unknown; message?: unknown };
          onEvent({
            type: "error",
            data: {
              code:
                typeof d.code === "string" && KNOWN_CODES.includes(d.code)
                  ? (d.code as ApiErrorCode)
                  : "internal",
              message: typeof d.message === "string" ? d.message : "The agent failed.",
            },
          });
          break;
        }
        case "done":
          onEvent({ type: "done" });
          break;
      }
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    if (err instanceof ApiRequestError) throw err;
    throw new ApiRequestError("unreachable", "The connection to the live API was lost.");
  }
}
