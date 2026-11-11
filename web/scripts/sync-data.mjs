// Copies benchmark results from the Python project into the web app.
//   ../results/summary.json     -> src/data/summary.json
//   ../results/examples/*.json  -> src/data/examples/
// Missing sources are skipped, so this is safe to run at any time.

import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const resultsDir = join(webRoot, "..", "results");
const dataDir = join(webRoot, "src", "data");

let copied = 0;

const summarySrc = join(resultsDir, "summary.json");
if (existsSync(summarySrc)) {
  mkdirSync(dataDir, { recursive: true });
  copyFileSync(summarySrc, join(dataDir, "summary.json"));
  console.log("copied summary.json");
  copied += 1;
} else {
  console.log(`skip: ${summarySrc} not found`);
}

const examplesSrc = join(resultsDir, "examples");
if (existsSync(examplesSrc)) {
  const examplesDst = join(dataDir, "examples");
  mkdirSync(examplesDst, { recursive: true });
  const files = readdirSync(examplesSrc).filter((f) => f.endsWith(".json"));
  for (const file of files) {
    copyFileSync(join(examplesSrc, file), join(examplesDst, file));
    copied += 1;
  }
  console.log(`copied ${files.length} example file(s)`);
  if (!files.includes("index.json")) {
    console.warn("warning: no index.json in ../results/examples - the example row may be stale");
  }
} else {
  console.log(`skip: ${examplesSrc} not found`);
}

console.log(`done: ${copied} file(s) copied`);
