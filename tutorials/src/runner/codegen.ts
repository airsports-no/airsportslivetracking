import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { AUTH_FILE, settings } from "./config";

// npm run codegen [-- <path on the site>]
//
// Opens the site in a browser, logged in, next to Playwright's recorder: click through the task and copy the code it
// writes into a tutorial script, between say() lines.

const startPath = process.argv[2] ?? "/";
const args = [
  "playwright",
  "codegen",
  "--target=javascript",
  `--viewport-size=${settings.viewport.width},${settings.viewport.height}`,
  ...(existsSync(AUTH_FILE) ? [`--load-storage=${AUTH_FILE}`] : []),
  new URL(startPath, settings.baseUrl).href,
];
spawnSync("npx", args, { stdio: "inherit" });
