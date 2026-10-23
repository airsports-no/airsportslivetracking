import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, type Locator } from "playwright";
import { STEP_LEAD_MS, STEP_PAUSE_AFTER_MS } from "../shared/edit";
import type { Timeline } from "../shared/timeline";
import { AUTH_FILE, RECORDINGS_DIR, SCRIPTS_DIR, settings, tutorialName } from "./config";
import { cleanUp } from "./cleanup";
import { showPdfInPage } from "./pdf-viewer";
import { narrate, writeTimingTemplate } from "./narrate";
import type { MapSteps, Tutorial, TutorialContext } from "./tutorial";

// npm run record -- <tutorial> [--headed]
//
// Plays scripts/<tutorial>.ts in a browser and records what the screen shows (every change, as sharp JPEG frames from
// the browser itself), where each click and keystroke lands, and when each step, narration line and highlight happens.
// The narration is only marked: its voice is made afterwards (npm run narrate, which this runs at the end), and the
// video makes room for it. The video is made from this by `npm run render`, with the timing file's changes
// (scripts/<tutorial>.timing.ts, started here when there is none).

const TYPING_DELAY_MS = 55;
// Before each step the page is left still: first until it has stopped changing, then long enough for the video's
// camera to move to the next target (STEP_LEAD_MS), so nothing happens while the view moves. After each step the
// recording pauses (STEP_PAUSE_AFTER_MS). The cutting keeps both.
const STILL_MS = 300;
const STILL_MAX_WAIT_MS = 4000;
const DEVICE_SCALE_FACTOR = 2;

const name = tutorialName(process.argv.slice(2).find((argument) => !argument.startsWith("--")));
if (!name) {
  console.error("Usage: npm run record -- <tutorial name> [--headed]");
  process.exit(1);
}
const headed = process.argv.includes("--headed");
const tutorial: Tutorial = (await import(pathToFileURL(path.join(SCRIPTS_DIR, `${name}.ts`)).href)).default;

// What an earlier recording (or recording the clicks) created would otherwise be there twice
await cleanUp(tutorial.cleanUp);

const outputDir = path.join(RECORDINGS_DIR, name);
rmSync(outputDir, { recursive: true, force: true });
mkdirSync(path.join(outputDir, "frames"), { recursive: true });

const browser = await chromium.launch({ headless: !headed, slowMo: Number(process.env.TUTORIAL_SLOWMO || 0) });
const context = await browser.newContext({
  baseURL: settings.baseUrl,
  viewport: settings.viewport,
  deviceScaleFactor: DEVICE_SCALE_FACTOR,
  storageState: existsSync(AUTH_FILE) ? AUTH_FILE : undefined,
  ...(settings.geolocation
    ? {
        geolocation: {
          latitude: Number(settings.geolocation.split(",")[0]),
          longitude: Number(settings.geolocation.split(",")[1]),
        },
        permissions: ["geolocation"],
      }
    : {}),
});
const page = await context.newPage();

const timeline: Timeline = {
  name,
  title: tutorial.title,
  subtitle: tutorial.subtitle,
  series: tutorial.series,
  next: tutorial.next,
  music: tutorial.music,
  viewport: settings.viewport,
  durationMs: 0,
  frames: [],
  actions: [],
  highlights: [],
  steps: [],
  says: [],
  camera: [],
  holds: [],
  chapters: [],
  hidden: [],
  // Only the script's own settings: the defaults are applied when rendering, so changing them needs no new recording
  edit: { ...tutorial.edit },
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

let lastFrameAt = 0;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const settle = async () => {
  if (!startedAt) return;
  const deadline = Date.now() + STILL_MAX_WAIT_MS;
  while (Date.now() - lastFrameAt < STILL_MS && Date.now() < deadline) await sleep(50);
  await sleep(STEP_LEAD_MS);
};
// Each step of the script, named after the chapter it is in (see Step in timeline.ts)
let chapterName = "Start";
let stepInChapter = 0;
const usedChapterNames = new Set<string>();
const recordStep = (label: string) => {
  const id = `${chapterName} #${++stepInChapter}`;
  if (startedAt) timeline.steps.push({ t: now(), id, label });
  return id;
};
const describe = (value: unknown) => (typeof value === "string" ? JSON.stringify(value) : JSON.stringify(value) ?? "");
const call = (name: string, args: unknown[]) => {
  const text = `${name}(${args.map(describe).join(", ")})`;
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
};

// Steps made of other steps (fill() clicks, then types) settle once, before the first
let inStep = false;
const settled =
  <T extends unknown[], R>(action: (...args: T) => Promise<R>, name: (self: unknown) => string) =>
  async function (this: unknown, ...args: T): Promise<R> {
    if (inStep) return action.apply(this, args);
    inStep = true;
    try {
      await settle();
      recordStep(call(name(this), args));
      const result = await action.apply(this, args);
      await sleep(STEP_PAUSE_AFTER_MS);
      return result;
    } finally {
      inStep = false;
    }
  };

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
  }
  return originalSelectOption.apply(this, args);
};
for (const method of ["click", "dblclick", "fill", "selectOption", "check", "uncheck", "setChecked", "hover", "tap", "dragTo"]) {
  locatorPrototype[method] = settled(locatorPrototype[method], (locator) => `${locator}.${method}`);
}
// The map steps from the recorder: mouse.down starts a drag, wheel zooms the map
// The map steps replay their gestures with the plain mouse: the pause comes once, before the whole gesture
const mouse = {
  move: page.mouse.move.bind(page.mouse),
  down: page.mouse.down.bind(page.mouse),
  up: page.mouse.up.bind(page.mouse),
  click: page.mouse.click.bind(page.mouse),
  wheel: page.mouse.wheel.bind(page.mouse),
};
for (const method of ["click", "dblclick", "down", "wheel"] as const) {
  const original = page.mouse[method].bind(page.mouse) as (...args: unknown[]) => Promise<void>;
  (page.mouse as unknown as Record<string, unknown>)[method] = settled(original, () => `page.mouse.${method}`);
}

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
  lastFrameAt = Date.now();
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

// The route editor's map (window.__routeEditorMap, set by its useMapInit): where its top left corner is on the page
const NO_MAP = "The route editor's map is not on this page (window.__routeEditorMap)";
// A map step may come right after the step that opens the route editor: wait for its map
const waitForMap = () =>
  page
    .waitForFunction(() => Boolean((window as unknown as { __routeEditorMap?: unknown }).__routeEditorMap), null, {
      timeout: 15000,
    })
    .catch(() => undefined);
const mapCorner = async () => {
  await waitForMap();
  return page.evaluate((message) => {
    const map = (window as any).__routeEditorMap;
    if (!map) throw new Error(message);
    const rect = map.getContainer().getBoundingClientRect();
    return { x: rect.x, y: rect.y };
  }, NO_MAP);
};

const mapSteps: MapSteps = {
  async view(lat, lng, zoom) {
    recordStep(call("map.view", [lat, lng, zoom]));
    await waitForMap();
    await page.evaluate(
      ([lat, lng, zoom, message]) =>
        new Promise<void>((resolve, reject) => {
          const map = (window as any).__routeEditorMap;
          if (!map) return reject(new Error(message));
          const center = map.getCenter();
          if (Math.abs(center.lat - lat) < 1e-7 && Math.abs(center.lng - lng) < 1e-7 && Math.abs(map.getZoom() - zoom) < 1e-3) {
            return resolve();
          }
          map.once("moveend", () => resolve());
          map.setView([lat, lng], zoom, { animate: true });
          setTimeout(() => resolve(), 3000);
        }),
      [lat, lng, zoom, NO_MAP] as const,
    );
  },
  click: settled(async (lat: number, lng: number) => {
    await waitForMap();
    const point = await page.evaluate(
      ([lat, lng, message]) => {
        const map = (window as any).__routeEditorMap;
        if (!map) throw new Error(message);
        const rect = map.getContainer().getBoundingClientRect();
        const inMap = map.latLngToContainerPoint([lat, lng]);
        return { x: rect.x + inMap.x, y: rect.y + inMap.y };
      },
      [lat, lng, NO_MAP] as const,
    );
    await mouse.click(point.x, point.y);
  }, () => "map.click"),
  drag: settled(async (path: [number, number, number][]) => {
    const corner = await mapCorner();
    const [[startX, startY], ...rest] = path;
    await mouse.move(corner.x + startX, corner.y + startY);
    await mouse.down();
    for (const [x, y, ms] of rest) {
      if (ms) await sleep(ms);
      await mouse.move(corner.x + x, corner.y + y);
    }
    await mouse.up();
  }, () => "map.drag"),
  wheel: settled(async (ticks: [number, number, number, number][]) => {
    const corner = await mapCorner();
    for (const [x, y, deltaY, ms] of ticks) {
      if (ms) await sleep(ms);
      await mouse.move(corner.x + x, corner.y + y);
      await mouse.wheel(0, deltaY);
    }
  }, () => "map.wheel"),
};

let hiddenSince: number | null = null;
let pdfRegionCount = 0;

const waitForStillPage = async () => {
  const deadline = Date.now() + STILL_MAX_WAIT_MS;
  while (Date.now() - lastFrameAt < STILL_MS && Date.now() < deadline) await sleep(50);
};

const showPdfPages = (pdf: Buffer, width: number, pages: number[] | undefined) => showPdfInPage(page, pdf, { width, pages });

const holdStill = async (ms: number) => {
  timeline.holds.push({ t: now(), durationMs: ms });
  await page.waitForTimeout(ms);
};

const tutorialContext: TutorialContext = {
  page,
  async say(text, options = {}) {
    if (hiddenSince !== null) console.warn(`  say inside a hidden part, cut from the video with it: ${text}`);
    // Only marked: the video waits for the line when it is to be waited for, and keeps lines from overlapping
    const step = recordStep(`say(${JSON.stringify(text.length > 100 ? `${text.slice(0, 97)}...` : text)})`);
    timeline.says.push({ t: now(), step, text, spoken: options.spoken, wait: options.wait ?? true });
    console.log(`  ${step} say: ${text}`);
  },
  async highlight(target, options = {}) {
    const locator = typeof target === "string" ? page.locator(target) : target;
    await locator.scrollIntoViewIfNeeded();
    await settle();
    recordStep(`highlight(${typeof target === "string" ? JSON.stringify(target) : String(target)})`);
    const box = await locator.boundingBox();
    if (!box) throw new Error(`Nothing to highlight: ${target}`);
    const durationMs = options.durationMs ?? 2500;
    timeline.highlights.push({ t: now(), durationMs, box, label: options.label });
    if (options.wait ?? true) await page.waitForTimeout(durationMs);
  },
  async pause(ms) {
    recordStep(`pause(${ms})`);
    await holdStill(ms);
  },
  camera(mode) {
    timeline.camera.push({ t: now(), mode });
  },
  chapter(title) {
    timeline.chapters!.push({ t: now(), title });
    // The same title twice: the steps of the second are named "<title> (2) #<n>"
    let count = 1;
    while (usedChapterNames.has(count === 1 ? title : `${title} (${count})`)) count++;
    chapterName = count === 1 ? title : `${title} (${count})`;
    usedChapterNames.add(chapterName);
    stepInChapter = 0;
    console.log(`  chapter: ${title}`);
  },
  async startHidden() {
    if (hiddenSince !== null) return;
    hiddenSince = now();
    console.log("  hidden part starts");
  },
  async endHidden() {
    if (hiddenSince === null) return;
    // The video comes back on the page once it has finished changing (loading, drawing the map)
    await waitForStillPage();
    timeline.hidden!.push({ start: hiddenSince, end: now() });
    hiddenSince = null;
    console.log("  hidden part ends");
  },
  async showPdf(source, options = {}) {
    recordStep(call("showPdf", [source, ...(Object.keys(options).length ? [options] : [])]));
    const bytes = /^(https?:)?\//.test(source)
      ? await (async () => {
          const response = await context.request.get(source);
          if (!response.ok()) throw new Error(`Could not fetch the PDF ${source}: ${response.status()}`);
          return response.body();
        })()
      : readFileSync(source);
    await showPdfPages(bytes, options.width ?? 0.7, options.pages);
  },
  pdfPage(number) {
    return page.locator(`[data-pdf-page="${number}"]`);
  },
  async pdfRegion(number, region) {
    const id = `pdf-region-${++pdfRegionCount}`;
    await page.evaluate(
      ([id, number, region]) => {
        const pageBox = document.querySelector(`[data-pdf-page="${number}"]`);
        if (!pageBox) throw new Error(`Page ${number} of the PDF is not shown`);
        const marker = document.createElement("div");
        marker.id = id;
        marker.className = "pdf-region";
        marker.style.left = `${region.x * 100}%`;
        marker.style.top = `${region.y * 100}%`;
        marker.style.width = `${region.width * 100}%`;
        marker.style.height = `${region.height * 100}%`;
        pageBox.append(marker);
      },
      [id, number, region] as const,
    );
    return page.locator(`#${id}`);
  },
  map: mapSteps,
};

console.log(`Recording ${name}: ${tutorial.title}`);
let failure: unknown = null;
try {
  await holdStill(800);
  // Also as globals, so pasted steps work whether or not run() lists the names it uses
  Object.assign(globalThis, tutorialContext);
  await tutorial.run(tutorialContext);
  await tutorialContext.endHidden();
  await holdStill(1200);
} catch (error) {
  failure = error;
} finally {
  await cdp.send("Page.stopScreencast").catch(() => undefined);
  timeline.durationMs = now();
  writeFileSync(path.join(outputDir, "timeline.json"), JSON.stringify(timeline, null, 1));
  await browser.close();
}
// Reported here, not left uncaught: the voice library's handler for uncaught errors prints its whole minified source
// in front of the message
if (failure) {
  console.error(`\nThe recording stopped: ${failure instanceof Error ? failure.stack : failure}`);
  console.error(`What was recorded until then is kept in public/recordings/${name}/.`);
  process.exit(1);
}
console.log(
  `Recorded ${(timeline.durationMs / 1000).toFixed(1)} s: ${timeline.frames.length} frames, ` +
    `${timeline.actions.length} actions, ${timeline.steps.length} steps, ${timeline.says.length} narration lines.`,
);
// The voice now, so Studio has it straight away (only new or changed lines take time)
await narrate(name);
const template = writeTimingTemplate(name);
console.log(
  `${template ? `Started the timing file ${template}. ` : ""}Preview with npm run studio, list the steps with ` +
    `npm run steps -- ${name}, render with npm run render -- ${name}`,
);
