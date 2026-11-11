// Stored example runs. Static JSON, zero API calls.
// index.json is bundled with the page. Each run file is loaded on demand.

import indexJson from "../data/examples/index.json";
import type { ExampleIndexEntry, RunRecord } from "./types";

export const EXAMPLES: ExampleIndexEntry[] = indexJson as ExampleIndexEntry[];

export function isExampleId(id: string): boolean {
  return EXAMPLES.some((e) => e.id === id);
}

export async function loadExampleRun(id: string): Promise<RunRecord> {
  if (!isExampleId(id)) throw new Error(`Unknown example: ${id}`);
  const mod = (await import(`../data/examples/${id}.json`)) as { default: unknown };
  return mod.default as RunRecord;
}
