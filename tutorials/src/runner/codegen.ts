import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { AUTH_FILE, RECORDINGS_DIR, ROOT, SCRIPTS_DIR, settings } from "./config";
import { narrate, writeTimingTemplate } from "./narrate";

// npm run codegen -- <name> [startPath] [--chapter <title>] [--paused] [--live]
// npm run live -- <name> [startPath] [--paused]
//
// Opens the site in a browser, logged in, and records what you do with capture.mjs (including F7 overlay cards,
// F8 chapters + voice, F9 hidden setup, F10 pause, and route-editor map recording). If scripts/<name>.ts does not
// exist yet, it is created automatically when you close the browser.
//
// With --live (or `npm run live -- <name>`), high-DPI video frames and public/recordings/<name>/timeline.json are
// captured in the same single pass while you click—ideal for slow downloads or one-off tasks that should not be run twice.

const rest: string[] = [];
let chapter: string | undefined;
let paused = false;
let live = false;
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === "--chapter" && process.argv[i + 1]) {
    chapter = process.argv[++i];
  } else if (process.argv[i] === "--paused") {
    paused = true;
  } else if (process.argv[i] === "--live") {
    live = true;
  } else {
    rest.push(process.argv[i]);
  }
}

const firstArg = rest[0] ?? "recording";
const isPathFirst = firstArg.startsWith("/") || firstArg.startsWith("http");
const name = isPathFirst ? "recording" : firstArg.replace(/\.ts$/, "");
const startPath = isPathFirst ? firstArg : (rest[1] ?? "/");

const recordedDir = path.join(ROOT, "recorded");
mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
mkdirSync(recordedDir, { recursive: true });

const output = path.join(recordedDir, chapter ? `${name}.chapter.js` : `${name}.js`);
const script = path.join(SCRIPTS_DIR, `${name}.ts`);
if (chapter && !existsSync(script)) {
  console.error(`No tutorial script ${script} to re-record a chapter of`);
  process.exit(1);
}

const liveDir = live ? path.join(RECORDINGS_DIR, name) : undefined;
const captureMjs = path.join(ROOT, "windows", "capture.mjs");
const args = [
  captureMjs,
  "--output",
  output,
  "--url",
  new URL(startPath, settings.baseUrl).href,
  "--auth",
  AUTH_FILE,
  "--viewport",
  `${settings.viewport.width},${settings.viewport.height}`,
  "--script",
  script,
  ...(settings.geolocation ? ["--geolocation", settings.geolocation] : []),
  ...(chapter ? ["--chapter", chapter] : []),
  ...(paused ? ["--paused"] : []),
  ...(liveDir ? ["--live", liveDir] : []),
];

const result = spawnSync("node", args, { stdio: "inherit" });
if (result.status === 0 && liveDir && existsSync(path.join(liveDir, "timeline.json"))) {
  await narrate(name);
  const template = writeTimingTemplate(name);
  if (template) console.log(`Created timing file: ${template}`);
}
process.exit(result.status ?? 0);
