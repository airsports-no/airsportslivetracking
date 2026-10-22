import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, type Locator } from "playwright";
import { DEFAULT_EDIT, type Timeline } from "../shared/timeline";
import { AUTH_FILE, RECORDINGS_DIR, SCRIPTS_DIR, settings } from "./config";
import { synthesise } from "./narration";
import type { Tutorial, TutorialContext } from "./tutorial";

// npm run record -- <tutorial> [--headed]
//
// Plays scripts/<tutorial>.ts in a browser and records what the screen shows (every change, as sharp JPEG frames from
// the browser itself), where each click and keystroke lands, and when each narration line and highlight happens. The
// video is made from this by `npm run render`.

const NARRATION_GAP_MS = 300;
const TYPING_DELAY_MS = 55;
const DEVICE_SCALE_FACTOR = 2;

const name = process.argv[2];
if (!name) {
  console.error("Usage: npm run record -- <tutorial name> [--headed]");
  process.exit(1);
}
const headed = process.argv.includes("--headed");
const tutorial: Tutorial = (await import(pathToFileURL(path.join(SCRIPTS_DIR, `${name}.ts`)).href)).default;

const outputDir = path.join(RECORDINGS_DIR, name);
rmSync(outputDir, { recursive: true, force: true });
mkdirSync(path.join(outputDir, "frames"), { recursive: true });
mkdirSync(path.join(outputDir, "narration"), { recursive: true });

const browser = await chromium.launch({ headless: !headed, slowMo: Number(process.env.TUTORIAL_SLOWMO || 350) });
const context = await browser.newContext({
  baseURL: settings.baseUrl,
  viewport: settings.viewport,
  deviceScaleFactor: DEVICE_SCALE_FACTOR,
  storageState: existsSync(AUTH_FILE) ? AUTH_FILE : undefined,
});
const page = await context.newPage();

const timeline: Timeline = {
  name,
  title: tutorial.title,
  subtitle: tutorial.subtitle,
  viewport: settings.viewport,
  durationMs: 0,
  frames: [],
  actions: [],
  highlights: [],
  narration: [],
  camera: [],
  holds: [],
  edit: { ...DEFAULT_EDIT, ...tutorial.edit },
  captions: tutorial.captions ?? true,
};
let startedAt = 0;
const now = () => Date.now() - startedAt;

// Clicks and keystrokes are seen from inside the page, so they are logged however they were made
await page.exposeBinding("__tutorialAction", (_source, action) => {
  if (startedAt) timeline.actions.push({ ...action, t: now() });
});
// A string, not a function: tsx adds helpers to compiled functions that do not exist inside the page
await context.addInitScript(`(() => {
  const interactive =
    "button, a, input, select, textarea, label, summary, [role=button], [role=option], [role=menuitem], [role=tab], " +
    "[role=checkbox], [role=radio], [role=switch], [role=link], [role=combobox], .leaflet-container";
  const boxOf = (element) => {
    const target = (element && element.closest && element.closest(interactive)) || element;
    if (!target || !target.getBoundingClientRect) return undefined;
    const rect = target.getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  };
  const report = (action) => window.__tutorialAction && window.__tutorialAction(action);
  let lastTyped = { element: null, at: 0 };
  let lastScroll = 0;
  window.addEventListener("pointerdown", (event) =>
    report({ kind: "click", x: event.clientX, y: event.clientY, box: boxOf(event.target) }), true);
  window.addEventListener("keydown", (event) => {
    const element = event.target;
    // One action per field, not per key
    if (lastTyped.element === element && Date.now() - lastTyped.at < 2000) {
      lastTyped.at = Date.now();
      return;
    }
    lastTyped = { element, at: Date.now() };
    const box = boxOf(element);
    if (box) report({ kind: "type", x: box.x + box.width / 2, y: box.y + box.height / 2, box });
  }, true);
  window.addEventListener("wheel", (event) => {
    if (Date.now() - lastScroll < 1000) return;
    lastScroll = Date.now();
    report({ kind: "scroll", x: event.clientX, y: event.clientY });
  }, { capture: true, passive: true });
  // The blinking text cursor would count as constant screen changes
  document.addEventListener("DOMContentLoaded", () => {
    const style = document.createElement("style");
    style.textContent = "* { caret-color: transparent !important; }";
    document.head.append(style);
  });
})();`);

// Codegen records fill(), which sets a field instantly: type it visibly instead
const locatorPrototype = Object.getPrototypeOf(page.locator("body"));
const originalFill = locatorPrototype.fill;
locatorPrototype.fill = async function (this: Locator, value: string, options?: object) {
  const kind = await this.evaluate((element) =>
    element instanceof HTMLInputElement ? element.type : element.tagName.toLowerCase(),
  );
  if (!["text", "search", "email", "password", "url", "tel", "number", "textarea"].includes(kind) || !value) {
    return originalFill.call(this, value, options);
  }
  await this.click();
  await this.press("ControlOrMeta+a");
  await this.pressSequentially(value, { delay: TYPING_DELAY_MS });
};
// Choosing from a native dropdown involves no click the page can see: log it as one
const originalSelectOption = locatorPrototype.selectOption;
locatorPrototype.selectOption = async function (this: Locator, ...args: unknown[]) {
  const box = await this.boundingBox();
  if (box && startedAt) {
    timeline.actions.push({ t: now(), kind: "click", x: box.x + box.width / 2, y: box.y + box.height / 2, box });
    await page.waitForTimeout(400);
  }
  return originalSelectOption.apply(this, args);
};

await page.goto(tutorial.startUrl ?? "/");
await page.waitForLoadState("networkidle").catch(() => undefined);

const cdp = await context.newCDPSession(page);
let frameCount = 0;
let previousFrame = "";
cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
  // Chrome repaints now and then without anything visible changing (an invisible blinking text cursor): only real
  // changes count, or the still stretches would not be cut
  if (data === previousFrame) return;
  previousFrame = data;
  if (!startedAt) startedAt = Math.round((metadata.timestamp ?? Date.now() / 1000) * 1000);
  const file = `frames/${String(++frameCount).padStart(6, "0")}.jpg`;
  writeFileSync(path.join(outputDir, file), Buffer.from(data, "base64"));
  const t = metadata.timestamp ? Math.round(metadata.timestamp * 1000) - startedAt : now();
  timeline.frames.push({ t: Math.max(0, t), file: `recordings/${name}/${file}` });
});
await cdp.send("Page.startScreencast", {
  format: "jpeg",
  quality: 92,
  maxWidth: settings.viewport.width * DEVICE_SCALE_FACTOR,
  maxHeight: settings.viewport.height * DEVICE_SCALE_FACTOR,
});
while (!startedAt) await new Promise((resolve) => setTimeout(resolve, 20));

let narrationEndsAt = 0;
const waitUntil = async (t: number) => {
  const remaining = t - now();
  if (remaining > 0) await page.waitForTimeout(remaining);
};

const tutorialContext: TutorialContext = {
  page,
  async say(text, options = {}) {
    // Lines never overlap
    await waitUntil(narrationEndsAt);
    // Generating the voice may take a moment: that still stretch is cut from the video
    const speech = await synthesise(text, options.spoken);
    const file = `narration/${String(timeline.narration.length + 1).padStart(3, "0")}.wav`;
    writeFileSync(path.join(outputDir, file), speech.wav);
    const t = now();
    timeline.narration.push({ t, durationMs: speech.durationMs, file: `recordings/${name}/${file}`, text });
    narrationEndsAt = t + speech.durationMs + NARRATION_GAP_MS;
    console.log(`  say: ${text}`);
    if (options.wait ?? true) await waitUntil(narrationEndsAt);
  },
  async highlight(target, options = {}) {
    const locator = typeof target === "string" ? page.locator(target) : target;
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.boundingBox();
    if (!box) throw new Error(`Nothing to highlight: ${target}`);
    const durationMs = options.durationMs ?? 2500;
    timeline.highlights.push({ t: now(), durationMs, box, label: options.label });
    if (options.wait ?? true) await page.waitForTimeout(durationMs);
  },
  async pause(ms) {
    timeline.holds.push({ t: now(), durationMs: ms });
    await page.waitForTimeout(ms);
  },
  camera(mode) {
    timeline.camera.push({ t: now(), mode });
  },
};

console.log(`Recording ${name}: ${tutorial.title}`);
try {
  await tutorialContext.pause(800);
  await tutorial.run(tutorialContext);
  await waitUntil(narrationEndsAt);
  await tutorialContext.pause(1200);
} finally {
  await cdp.send("Page.stopScreencast").catch(() => undefined);
  timeline.durationMs = now();
  writeFileSync(path.join(outputDir, "timeline.json"), JSON.stringify(timeline, null, 1));
  await browser.close();
}
console.log(
  `Recorded ${(timeline.durationMs / 1000).toFixed(1)} s: ${timeline.frames.length} frames, ` +
    `${timeline.actions.length} actions, ${timeline.narration.length} narration lines. ` +
    `Preview with npm run studio, render with npm run render -- ${name}`,
);
