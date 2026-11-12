"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  API_URL,
  ApiRequestError,
  MAX_QUESTION_CHARS,
  askStream,
  getLimits,
  getRun,
  type ClientErrorCode,
} from "../../lib/api";
import { ask } from "../../lib/content";
import { EXAMPLES, isExampleId, loadExampleRun } from "../../lib/examples";
import { fmtMs, fmtUsd } from "../../lib/format";
import type { Limits, Report, RunRecord, Step } from "../../lib/types";
import { Badge } from "../ui";
import { ReportView, evidenceDomId } from "./ReportView";
import { StepTrace } from "./StepTrace";

/** Delay between replayed steps of a stored example. */
const REPLAY_DELAY_MS = 350;

type LimitsState =
  | { kind: "disabled" }
  | { kind: "loading" }
  | { kind: "ok"; limits: Limits }
  | { kind: "unreachable" };

interface RunView {
  status: "idle" | "running" | "done" | "error";
  source: "example" | "live" | "stored" | null;
  question: string;
  system: string | null;
  runId: string | null;
  cached: boolean;
  steps: Step[];
  report: Report | null;
  error: string | null;
}

const IDLE: RunView = {
  status: "idle",
  source: null,
  question: "",
  system: null,
  runId: null,
  cached: false,
  steps: [],
  report: null,
  error: null,
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function errorText(code: ClientErrorCode, fallback: string): string {
  return ask.errors[code] ?? fallback;
}

function modeOf(state: LimitsState): { live: boolean; text: string; pending?: boolean } {
  switch (state.kind) {
    case "disabled":
      return { live: false, text: ask.mode.disabled };
    case "loading":
      return { live: false, text: ask.mode.loading, pending: true };
    case "unreachable":
      return { live: false, text: ask.mode.unreachable };
    case "ok": {
      const l = state.limits;
      if (l.cap_reached) return { live: false, text: ask.mode.capReached };
      if (!l.live_enabled) {
        return { live: false, text: l.reason ? `Cached mode - ${l.reason}` : ask.mode.liveOff };
      }
      if (l.remaining_today <= 0) return { live: false, text: ask.mode.noneLeft(l.daily_limit) };
      return { live: true, text: ask.mode.live(l.remaining_today, l.daily_limit) };
    }
  }
}

function setRunParam(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("run", id);
  else url.searchParams.delete("run");
  window.history.replaceState(null, "", url);
}

export function AskClient({ hideIntro = false }: { hideIntro?: boolean }) {
  const [limitsState, setLimitsState] = useState<LimitsState>(
    API_URL ? { kind: "loading" } : { kind: "disabled" },
  );
  const [question, setQuestion] = useState("");
  const [run, setRun] = useState<RunView>(IDLE);
  const [flash, setFlash] = useState<{ id: string; n: number } | null>(null);
  const [copied, setCopied] = useState(false);

  // Each new run bumps the token. Async work from older runs checks it and stops.
  const runToken = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const refreshLimits = useCallback(async () => {
    if (!API_URL) return;
    try {
      const limits = await getLimits();
      setLimitsState({ kind: "ok", limits });
    } catch {
      setLimitsState({ kind: "unreachable" });
    }
  }, []);

  const begin = useCallback((next: Partial<RunView>): number => {
    runToken.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setFlash(null);
    setCopied(false);
    setRun({ ...IDLE, status: "running", ...next });
    return runToken.current;
  }, []);

  /** Show a stored RunRecord. With animate, steps appear one by one. */
  const showRecord = useCallback(
    async (record: RunRecord, source: "example" | "stored", animate: boolean) => {
      const token = begin({
        source,
        question: record.question,
        system: record.system,
        runId: record.id,
        cached: true,
      });
      setQuestion(record.question.slice(0, MAX_QUESTION_CHARS));
      const steps = record.steps ?? [];
      if (animate) {
        for (const step of steps) {
          await sleep(REPLAY_DELAY_MS);
          if (runToken.current !== token) return;
          setRun((r) => ({ ...r, steps: [...r.steps, step] }));
        }
        await sleep(REPLAY_DELAY_MS);
        if (runToken.current !== token) return;
      }
      const failed = record.status === "error" || !record.report;
      setRun((r) => ({
        ...r,
        steps,
        report: record.report,
        status: failed ? "error" : "done",
        error: failed ? (record.error ?? "This run ended without a report.") : null,
      }));
    },
    [begin],
  );

  const playExample = useCallback(
    async (id: string) => {
      try {
        const record = await loadExampleRun(id);
        setRunParam(id);
        await showRecord(record, "example", true);
      } catch {
        begin({ status: "error", error: "This example could not be loaded." });
      }
    },
    [begin, showRecord],
  );

  const runLive = useCallback(
    async (q: string) => {
      const token = begin({ source: "live", question: q });
      setRunParam(null);
      const controller = new AbortController();
      abortRef.current = controller;
      const current = () => runToken.current === token;
      try {
        await askStream(
          q,
          (event) => {
            if (!current()) return;
            switch (event.type) {
              case "run":
                setRun((r) => ({ ...r, runId: event.data.run_id, cached: event.data.cached }));
                setRunParam(event.data.run_id);
                break;
              case "step":
                setRun((r) => ({ ...r, steps: [...r.steps, event.data] }));
                break;
              case "report":
                setRun((r) => ({ ...r, report: event.data }));
                break;
              case "error":
                setRun((r) => ({
                  ...r,
                  status: "error",
                  error: errorText(event.data.code, event.data.message),
                }));
                break;
              case "done":
                break;
            }
          },
          controller.signal,
        );
        if (!current()) return;
        setRun((r) => {
          if (r.status === "error") return r;
          if (r.report) return { ...r, status: "done" };
          return { ...r, status: "error", error: "The stream ended before a report arrived." };
        });
      } catch (err) {
        if (isAbort(err) || !current()) return;
        const code: ClientErrorCode = err instanceof ApiRequestError ? err.code : "internal";
        const message = err instanceof Error ? err.message : "Something went wrong.";
        setRun((r) => ({ ...r, status: "error", error: errorText(code, message) }));
      } finally {
        if (current()) abortRef.current = null;
        void refreshLimits();
      }
    },
    [begin, refreshLimits],
  );

  // On load: check limits, and open a shared run from /?run=<id>.
  useEffect(() => {
    let cancelled = false;
    async function init() {
      const limitsDone = refreshLimits();
      const id = new URLSearchParams(window.location.search).get("run");
      if (id) {
        if (isExampleId(id)) {
          await playExample(id);
        } else if (!API_URL) {
          begin({ status: "error", error: ask.errors.runNeedsApi });
        } else {
          const token = begin({ source: "stored", runId: id });
          try {
            const record = await getRun(id);
            if (!cancelled && runToken.current === token) {
              await showRecord(record, "stored", false);
            }
          } catch (err) {
            if (cancelled || runToken.current !== token) return;
            const code: ClientErrorCode = err instanceof ApiRequestError ? err.code : "internal";
            setRun((r) => ({
              ...r,
              status: "error",
              error: errorText(code, "This run could not be loaded."),
            }));
          }
        }
      }
      await limitsDone;
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [begin, playExample, refreshLimits, showRecord]);

  // Stop any in-flight work when the page unmounts.
  useEffect(() => {
    return () => {
      runToken.current += 1;
      abortRef.current?.abort();
    };
  }, []);

  const mode = modeOf(limitsState);
  const running = run.status === "running";
  const trimmed = question.trim();
  const canAsk = mode.live && !running && trimmed.length > 0;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (canAsk) void runLive(trimmed);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canAsk) void runLive(trimmed);
    }
  }

  function stop() {
    runToken.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setRun((r) => ({ ...r, status: "error", error: "Stopped." }));
  }

  function selectEvidence(id: string) {
    setFlash((f) => ({ id, n: (f?.n ?? 0) + 1 }));
    requestAnimationFrame(() => {
      document.getElementById(evidenceDomId(id))?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const stepLatency = run.steps.reduce((sum, s) => sum + (s.latency_ms ?? 0), 0);
  const stepCost = run.steps.reduce((sum, s) => sum + (s.cost_usd ?? 0), 0);

  return (
    <div>
      {hideIntro ? null : (
        <div className="max-w-3xl">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{ask.heading}</h1>
          <p className="mt-3 text-base leading-relaxed text-muted">{ask.intro}</p>
        </div>
      )}

      <p
        role="status"
        className={`tone ${mode.live ? "tone-ok" : mode.pending ? "" : "tone-warn"} mt-6 flex items-start gap-2 rounded-md px-3 py-2 text-sm`}
      >
        <span
          aria-hidden="true"
          className={`mt-1.5 h-2 w-2 shrink-0 rounded-full bg-current ${mode.pending ? "pulse-dot" : ""}`}
        />
        <span>{mode.text}</span>
      </p>

      <form onSubmit={onSubmit} className="mt-4">
        <label htmlFor="question" className="mb-1.5 block text-sm font-medium">
          {ask.inputLabel}
        </label>
        <div className="rounded-lg border border-line bg-surface focus-within:border-accent">
          <textarea
            id="question"
            name="question"
            rows={2}
            maxLength={MAX_QUESTION_CHARS}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={ask.placeholder}
            className="block w-full resize-none rounded-t-lg bg-transparent px-3.5 py-3 text-base outline-none placeholder:text-muted/70"
          />
          <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-2">
            <span className="font-mono text-xs text-muted">
              {question.length} / {MAX_QUESTION_CHARS}
            </span>
            <div className="flex items-center gap-2">
              {running ? (
                <button
                  type="button"
                  onClick={stop}
                  className="rounded-md border border-line px-3 py-1.5 text-sm font-medium hover:bg-sunken"
                >
                  {ask.stop}
                </button>
              ) : null}
              <button
                type="submit"
                disabled={!canAsk}
                title={mode.live ? undefined : "Live questions are off. Use a stored example."}
                className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-semibold text-bg hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {ask.submit}
              </button>
            </div>
          </div>
        </div>
      </form>

      <section aria-labelledby="examples-heading" className="mt-5">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <h2 id="examples-heading" className="text-sm font-medium">
            {ask.examplesHeading}
          </h2>
          <span className="text-xs text-muted">{ask.examplesNote}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.id}
              type="button"
              onClick={() => void playExample(ex.id)}
              aria-pressed={run.source === "example" && run.runId === ex.id}
              className={`flex max-w-full items-center gap-2 rounded-lg border bg-surface px-3 py-2 text-left text-sm hover:border-accent ${
                run.source === "example" && run.runId === ex.id ? "border-accent" : "border-line"
              }`}
            >
              <Badge tone="accent">{ex.tag}</Badge>
              <span className="min-w-0">{ex.question}</span>
            </button>
          ))}
        </div>
      </section>

      {run.status !== "idle" ? (
        <div className="mt-8 border-t border-line pt-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={run.source === "live" ? "ok" : "neutral"}>
              {run.source === "live"
                ? run.cached
                  ? "Live question - served from cache"
                  : "Live run"
                : run.source === "example"
                  ? "Stored example - replay"
                  : "Stored run"}
            </Badge>
            {run.runId ? <span className="font-mono text-xs text-muted">run {run.runId}</span> : null}
            {run.runId && run.status !== "running" ? (
              <button
                type="button"
                onClick={() => void copyShareLink()}
                className="text-xs text-accent underline underline-offset-2"
              >
                {copied ? ask.shareCopied : ask.shareLabel}
              </button>
            ) : null}
          </div>
          {run.question ? (
            <p className="mt-2 text-lg font-medium leading-snug">{run.question}</p>
          ) : null}
          {run.system === "fixture" ? (
            <p className="tone tone-warn mt-3 rounded-md px-3 py-2 text-sm">{ask.fixtureNote}</p>
          ) : null}
          {run.error ? (
            <p role="alert" className="tone tone-bad mt-3 rounded-md px-3 py-2 text-sm">
              {run.error}
            </p>
          ) : null}

          <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <section aria-labelledby="trace-heading">
              <div className="mb-3">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <h2 id="trace-heading" className="text-lg font-semibold tracking-tight">
                    {ask.traceHeading}
                  </h2>
                  {run.steps.length > 0 ? (
                    <span className="font-mono text-xs text-muted">
                      {run.steps.length} steps - {fmtMs(stepLatency)} - {fmtUsd(stepCost)}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm text-muted">{ask.traceNote}</p>
              </div>
              <StepTrace
                steps={run.steps}
                running={running}
                evidence={run.report?.evidence ?? null}
                onSelectEvidence={selectEvidence}
              />
            </section>

            <section aria-labelledby="report-heading">
              <h2 id="report-heading" className="mb-3 text-lg font-semibold tracking-tight">
                {ask.reportHeading}
              </h2>
              {run.report ? (
                <ReportView report={run.report} flash={flash} onSelectEvidence={selectEvidence} />
              ) : (
                <p className="rounded-lg border border-dashed border-line px-4 py-6 text-sm text-muted">
                  {running ? ask.reportPending : ask.reportEmpty}
                </p>
              )}
            </section>
          </div>
        </div>
      ) : (
        <p className="mt-8 rounded-lg border border-dashed border-line px-4 py-6 text-sm text-muted">
          {ask.traceEmpty}
        </p>
      )}
    </div>
  );
}
