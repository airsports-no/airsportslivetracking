import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, type Locator } from "playwright";
import { STEP_LEAD_MS, STEP_PAUSE_AFTER_MS } from "../shared/edit";
import type { Timeline } from "../shared/timeline";
import { AUTH_FILE, RECORDINGS_DIR, SCRIPTS_DIR, settings, tutorialName } from "./config";
import { cleanUp } from "./cleanup";
import { showPdfInPage, zoomPdfInPage } from "./pdf-viewer";
import { differenceBeforeChapter, joinRecordings, keptRecording, type Earlier } from "./join";
import { narrate, writeTimingTemplate } from "./narrate";
import type { MapSteps, Tutorial, TutorialContext } from "./tutorial";

// npm run record -- <tutorial> [--headed] [--from "<chapter>"]
//
// Plays scripts/<tutorial>.ts in a browser and records what the screen shows (every change, as sharp JPEG frames from
// the browser itself), where each click and keystroke lands, and when each step, narration line and highlight happens.
// The narration is only marked: its voice is made afterwards (npm run narrate, which this runs at the end), and the
// video makes room for it. The video is made from this by `npm run render`, with the timing file's changes
// (scripts/<tutorial>.timing.ts, started here when there is none).
//
// --from "<chapter>" records only from that chapter on, and keeps the last recording up to it: the steps before it are
// played first exactly as when recording (the site reacts to their timing: a map pan done faster is a click), but what
// they show is not kept, to bring the site to where the chapter starts. After a recording that stopped half way, or to
// redo one part.

const TYPING_DELAY_MS = 55;
// Before each step the page is left still: first until it has stopped changing, then long enough for the video's
// camera to move to the next target (STEP_LEAD_MS), so nothing happens while the view moves. After each step the
// recording pauses (STEP_PAUSE_AFTER_MS). The cutting keeps both.
const STILL_MS = 300;
const STILL_MAX_WAIT_MS = 4000;
const DEVICE_SCALE_FACTOR = 2;

const fromIndex = process.argv.indexOf("--from");
const fromChapter = fromIndex > 0 ? process.argv[fromIndex + 1] : undefined;
const name = tutorialName(process.argv.slice(2).find((argument, index, all) => !argument.startsWith("--") && all[index - 1] !== "--from"));
if (!name || (fromIndex > 0 && !fromChapter)) {
  console.error('Usage: npm run record -- <tutorial name> [--headed] [--from "<chapter>"]');
  process.exit(1);
}
const headed = process.argv.includes("--headed");
const tutorial: Tutorial = (await import(pathToFileURL(path.join(SCRIPTS_DIR, `${name}.ts`)).href)).default;

const outputDir = path.join(RECORDINGS_DIR, name);
// --from: the last recording up to the chapter is kept (its frames after it go once the new part is there). Checked
// before cleaning up, so a mistyped chapter changes nothing.
let earlier: Earlier | null = null;
try {
  earlier = fromChapter ? keptRecording(outputDir, fromChapter) : null;
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}
if (!earlier) rmSync(outputDir, { recursive: true, force: true });

// What an earlier recording (or recording the clicks) created would otherwise be there twice
await cleanUp(tutorial.cleanUp);
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
// Before --from's chapter the steps are played as when recording, but nothing of them is kept
let keeping = !fromChapter;

// Clicks and keystrokes are seen from inside the page, so they are logged however they were made
await page.exposeBinding("__tutorialAction", (_source, action) => {
  if (startedAt) timeline.actions.push({ ...action, t: now() });
});
// Code passed to page.evaluate() is compiled by tsx, which wraps named inner functions in a __name() helper that does
// not exist in the page: without it they fail there (and a .catch() hides that)
await context.addInitScript("window.__name = window.__name || ((target) => target);");
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
  // Links and windows that would open a new tab (the live map) open in this one: the recording, and the script's page,
  // follow this tab only
  document.addEventListener("click", (event) => {
    const link = event.target && event.target.closest && event.target.closest("a[target]");
    if (link && link.target !== "_self") link.target = "_self";
  }, true);
  window.open = (url) => { if (url) window.location.assign(url); return window; };
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
// Steps that pick an element by its position among those that match (.nth(), .first(), .last()): another match
// before it, on a later day, changes which one is used
const BY_POSITION = /\.(nth\(\d+\)|first\(\)|last\(\))/;
const byPosition: string[] = [];
// The steps played before --from's chapter must be the kept recording's
const checkPlayedSteps = () => {
  const difference = earlier && differenceBeforeChapter(earlier, timeline.steps);
  if (difference) {
    throw new Error(
      `The steps before "${fromChapter}" are not those of the last recording (${difference}), so what is kept of it ` +
        "would not match: record the whole tutorial",
    );
  }
};
// The line of the tutorial script a step comes from, from where it was called (tsx maps it back to the script)
const SCRIPT_LINE = new RegExp(`scripts[\\\\/]${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\.ts:(\\d+):\\d+`);
const scriptLine = () => {
  const match = new Error().stack?.match(SCRIPT_LINE);
  return match ? Number(match[1]) : undefined;
};
// The time of the last chapter: no step after it is earlier (see chapter())
let chapterFloor = 0;
const recordStep = (label: string) => {
  const id = `${chapterName} #${++stepInChapter}`;
  if (startedAt) timeline.steps.push({ t: Math.max(now(), chapterFloor), id, label, line: scriptLine() });
  if (BY_POSITION.test(label) && !byPosition.includes(id)) {
    byPosition.push(id);
    console.warn(`  ${id} picks by position (${label.match(BY_POSITION)![0]}): a unique name or text is safer`);
  }
  return id;
};
const describe = (value: unknown) => (typeof value === "string" ? JSON.stringify(value) : JSON.stringify(value) ?? "");
const call = (name: string, args: unknown[]) => {
  const text = `${name}(${args.map(describe).join(", ")})`;
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
};

// An element out of view is scrolled to smoothly before the step, as a person scrolls to it: Playwright's own scrolling
// jumps there between two frames, so the video never shows the list moving. Centred in the list where it can be;
// nothing moves when it is in view already. Waits until the scrolling has stopped.
const scrollToSmoothly = async (locator: Locator) => {
  const handle = await locator.elementHandle({ timeout: 30000 }).catch(() => null);
  if (!handle) return;
  await handle
    .evaluate(
      (element) =>
        new Promise<void>((resolve) => {
          const rect = element.getBoundingClientRect();
          const inView = (box: { top: number; bottom: number; left: number; right: number }) =>
            rect.top >= box.top && rect.bottom <= box.bottom && rect.left >= box.left && rect.right <= box.right;
          let visible = inView({ top: 0, bottom: window.innerHeight, left: 0, right: window.innerWidth });
          for (let parent = element.parentElement; parent && visible; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            if (/(auto|scroll)/.test(style.overflowY + style.overflowX)) visible = inView(parent.getBoundingClientRect());
          }
          if (visible) return resolve();
          let last = Date.now();
          const onScroll = () => (last = Date.now());
          document.addEventListener("scroll", onScroll, true);
          element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
          const started = Date.now();
          const check = () => {
            if ((Date.now() - last > 200 && Date.now() - started > 300) || Date.now() - started > 3000) {
              document.removeEventListener("scroll", onScroll, true);
              resolve();
            } else setTimeout(check, 50);
          };
          check();
        }),
    )
    .catch(() => undefined);
  await handle.dispose();
};

// Steps made of other steps (fill() clicks, then types) settle once, before the first
let inStep = false;
const settled =
  <T extends unknown[], R>(action: (...args: T) => Promise<R>, name: (self: unknown) => string) =>
  async function (this: unknown, ...args: T): Promise<R> {
    if (inStep) return action.apply(this, args);
    inStep = true;
    try {
      // A locator's element: brought into view visibly first
      if (this && typeof (this as Locator).elementHandle === "function") await scrollToSmoothly(this as Locator);
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

// Dialogs (confirm, alert, "leave this page?") are accepted, as when the clicks were recorded, unless the script said
// nextDialog("dismiss") before the step
let nextDialogAnswer: "accept" | "dismiss" = "accept";
page.on("dialog", (dialog) => {
  const answer = nextDialogAnswer;
  nextDialogAnswer = "accept";
  console.log(`  dialog ${answer === "accept" ? "accepted" : "declined"}: ${dialog.message()}`);
  (answer === "accept" ? dialog.accept() : dialog.dismiss()).catch(() => undefined);
});

await page.goto(tutorial.startUrl ?? "/");
await page.waitForLoadState("networkidle").catch(() => undefined);

const cdp = await context.newCDPSession(page);
let frameCount = earlier?.lastFrameNumber ?? 0;
let previousFrame = "";
cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
  // Chrome repaints now and then without anything visible changing (an invisible blinking text cursor): only real
  // changes count, or the still stretches would not be cut
  if (data === previousFrame) return;
  previousFrame = data;
  lastFrameAt = Date.now();
  if (!startedAt) startedAt = Math.round((metadata.timestamp ?? Date.now() / 1000) * 1000);
  // Before --from's chapter: seen, so the page's stillness is known as when recording, but not kept
  if (!keeping) return;
  const file = `frames/${String(++frameCount).padStart(6, "0")}.jpg`;
  writeFileSync(path.join(outputDir, file), Buffer.from(data, "base64"));
  const t = metadata.timestamp ? Math.round(metadata.timestamp * 1000) - startedAt : now();
  timeline.frames.push({ t: Math.max(0, t), file: `recordings/${name}/${file}` });
});
const startRecording = async () => {
  await cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: 92,
    maxWidth: settings.viewport.width * DEVICE_SCALE_FACTOR,
    maxHeight: settings.viewport.height * DEVICE_SCALE_FACTOR,
  });
  while (!startedAt) await new Promise((resolve) => setTimeout(resolve, 20));
};
await startRecording();

// The route editor's map (window.__routeEditorMap, set by its useMapInit): where its top left corner is on the page
const NO_MAP = "The route editor's map is not on this page (window.__routeEditorMap)";
// A map step may come right after the step that opens the route editor: wait for its map
const waitForMap = () =>
  page
    .waitForFunction(() => Boolean((window as unknown as { __routeEditorMap?: unknown }).__routeEditorMap), null, {
      timeout: 15000,
    })
    .catch(() => undefined);
// Until the map has stopped moving (a wheel zoom's animation, the glide after a pan): a map position becomes a point on
// the screen only then, or a click lands where the map was a moment ago. Still: the same centre and zoom for 200 ms.
const waitForStillMap = () =>
  page
    .evaluate(
      () =>
        new Promise<void>((resolve) => {
          const map = (window as any).__routeEditorMap;
          if (!map) return resolve();
          const deadline = Date.now() + 4000;
          let last = "";
          let stillSince = Date.now();
          const check = () => {
            const center = map.getCenter();
            const now = `${center.lat.toFixed(8)},${center.lng.toFixed(8)},${map.getZoom()}`;
            if (now !== last) {
              last = now;
              stillSince = Date.now();
            }
            if (Date.now() - stillSince >= 200 || Date.now() > deadline) resolve();
            else setTimeout(check, 40);
          };
          check();
        }),
    )
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

// A drag recorded with where it started on the map (the recorder writes { at: [lat, lng], zoom }): it starts there
// however the map lies now, and its moves are scaled to the zoom, so dragging a point drags that point. Without one,
// the drag is played at the recorded positions in the map.
const anchoredPath = async (path: [number, number, number][], anchor?: { at: [number, number]; zoom: number }) => {
  if (!anchor) return path;
  const now = await page.evaluate(([lat, lng]) => {
    const map = (window as any).__routeEditorMap;
    const point = map.latLngToContainerPoint([lat, lng]);
    return { x: point.x, y: point.y, zoom: map.getZoom() };
  }, anchor.at);
  const scale = 2 ** (now.zoom - anchor.zoom);
  const [startX, startY] = path[0];
  return path.map(([x, y, ms]): [number, number, number] => [
    Math.round(now.x + (x - startX) * scale),
    Math.round(now.y + (y - startY) * scale),
    ms,
  ]);
};

// The zoom of the map.view the script has right after a wheel step (more wheel steps and comments may come between):
// what the wheel came to, for scripts recorded before the recorder wrote it into the wheel step
const scriptSource = readFileSync(path.join(SCRIPTS_DIR, `${name}.ts`), "utf8").split(/\r?\n/);
const zoomOfNextView = (line: number | undefined) => {
  if (line === undefined) return undefined;
  for (let index = line; index < scriptSource.length; index++) {
    const text = scriptSource[index].trim();
    const view = text.match(/^await map\.view\(\s*[-\d.]+\s*,\s*[-\d.]+\s*,\s*([-\d.]+)\s*\)/);
    if (view) return Number(view[1]);
    if (text && !text.startsWith("//") && !text.startsWith("await map.wheel(")) return undefined;
  }
  return undefined;
};

const mapSteps: MapSteps = {
  async view(lat, lng, zoom) {
    recordStep(call("map.view", [lat, lng, zoom]));
    await waitForMap();
    await waitForStillMap();
    await page.evaluate(
      ([lat, lng, zoom, message, animate]) =>
        new Promise<void>((resolve, reject) => {
          const map = (window as any).__routeEditorMap;
          if (!map) return reject(new Error(message));
          const center = map.getCenter();
          if (Math.abs(center.lat - lat) < 1e-7 && Math.abs(center.lng - lng) < 1e-7 && Math.abs(map.getZoom() - zoom) < 1e-3) {
            return resolve();
          }
          map.once("moveend", () => resolve());
          map.setView([lat, lng], zoom, { animate });
          setTimeout(() => resolve(), 3000);
        }),
      [lat, lng, zoom, NO_MAP, true] as const,
    );
  },
  click: settled(async (lat: number, lng: number) => {
    await waitForMap();
    await waitForStillMap();
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
  drag: settled(async (path: [number, number, number][], anchor?: { at: [number, number]; zoom: number }) => {
    const corner = await mapCorner();
    await waitForStillMap();
    const points = await anchoredPath(path, anchor);
    const [[startX, startY], ...rest] = points;
    await mouse.move(corner.x + startX, corner.y + startY);
    await mouse.down();
    for (const [x, y, ms] of rest) {
      // Played at the recorded speed even when fast forwarding: on the route editor's map a pan done too fast is a
      // click, which adds a waypoint
      if (ms) await sleep(ms);
      await mouse.move(corner.x + x, corner.y + y);
    }
    await mouse.up();
  }, () => "map.drag"),
  wheel: settled(async (ticks: [number, number, number, number][], options?: { to?: number }) => {
    const corner = await mapCorner();
    await waitForStillMap();
    // Where it came to: written by the recorder, or (scripts recorded before that) the map.view right after it
    const to = options?.to ?? zoomOfNextView(scriptLine());
    if (to === undefined) {
      for (const [x, y, deltaY, ms] of ticks) {
        if (ms) await sleep(ms);
        await mouse.move(corner.x + x, corner.y + y);
        await mouse.wheel(0, deltaY);
      }
      return;
    }
    // Leaflet's zoom for a series of ticks depends on their timing to the millisecond (ticks during its zoom animation
    // count for nothing), so played ticks zoom further than the recorded ones did: a zoom to where they came to
    // instead, around where the mouse was, as a wheel zoom
    const [x, y] = ticks[ticks.length - 1];
    await mouse.move(corner.x + x, corner.y + y, { steps: 8 });
    // One level at a time, each once its map tiles have loaded: a jump of several levels shrinks the old tiles to a
    // corner and shows the empty background until the new ones are there
    await page.evaluate(
      ([x, y, to]) =>
        new Promise<void>((resolve) => {
          const map = (window as any).__routeEditorMap;
          const giveUp = setTimeout(() => resolve(), 10000);
          const loading = () => {
            let busy = false;
            map.eachLayer((layer: any) => {
              if (typeof layer.isLoading === "function" && layer.isLoading()) busy = true;
            });
            return busy;
          };
          const next = () => {
            const now = map.getZoom();
            if (Math.abs(to - now) < 1e-3) {
              clearTimeout(giveUp);
              return resolve();
            }
            const started = Date.now();
            const whenLoaded = () => {
              if (loading() && Date.now() - started < 1500) setTimeout(whenLoaded, 50);
              else setTimeout(next, 150);
            };
            map.once("zoomend", () => setTimeout(whenLoaded, 50));
            // Around the map position under the mouse: a plain [x, y] would be read as a latitude and longitude
            map.setZoomAround(map.containerPointToLatLng([x, y]), Math.abs(to - now) <= 1 ? to : now + Math.sign(to - now));
          };
          next();
        }),
      [x, y, to] as const,
    );
    await waitForStillMap();
  }, () => "map.wheel"),
};

let hiddenSince: number | null = null;
let pdfRegionCount = 0;

const waitForStillPage = async () => {
  const deadline = Date.now() + STILL_MAX_WAIT_MS;
  while (Date.now() - lastFrameAt < STILL_MS && Date.now() < deadline) await sleep(50);
};

const showPdfPages = (pdf: Buffer, width: number | "page", pages: number[] | undefined) => showPdfInPage(page, pdf, { width, pages });

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
    // Not while only playing the steps before --from's chapter: nothing of them is kept
    if (keeping) console.log(`  ${step} say: ${text}`);
  },
  async highlight(target, options = {}) {
    const locator = typeof target === "string" ? page.locator(target) : target;
    await scrollToSmoothly(locator);
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
  async chapter(title) {
    if (!keeping && title === fromChapter) {
      checkPlayedSteps();
      // What was played before is not kept: the recording starts here, at 0
      keeping = true;
      for (const list of [timeline.frames, timeline.actions, timeline.highlights, timeline.steps, timeline.says,
        timeline.camera, timeline.holds, timeline.chapters!, timeline.hidden!]) {
        list.length = 0;
      }
      hiddenSince = null;
      startedAt = Date.now();
      console.log(`  recording from "${title}"`);
    }
    // Strictly after the last step and never after the next one, even within one millisecond: --from (join.ts) keeps
    // the steps before the chapter's time, and a step at the very same time would be taken for the chapter's own
    chapterFloor = Math.max(now(), (timeline.steps.at(-1)?.t ?? -1) + 1);
    timeline.chapters!.push({ t: chapterFloor, title });
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
    // Until the recording has the drawn pages too: a line said right after would otherwise hold an empty frame
    await waitForStillPage();
  },
  async zoomPdf(number, band, options = {}) {
    recordStep(call("zoomPdf", [number, band]));
    await zoomPdfInPage(page, number, band, options.durationMs ?? 1800);
  },
  nextDialog(answer) {
    nextDialogAnswer = answer;
  },
  day(offset = 0) {
    const date = new Date(Date.now() + offset * 86400000);
    return date.toLocaleDateString("sv-SE");
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

console.log(`Recording ${name}: ${tutorial.title}${fromChapter ? `, from "${fromChapter}"` : ""}`);
if (fromChapter) console.log("  playing the steps before it as when recording, without keeping them");
let failure: unknown = null;
try {
  await holdStill(800);
  // Also as globals, so pasted steps work whether or not run() lists the names it uses
  Object.assign(globalThis, tutorialContext);
  await tutorial.run(tutorialContext);
  if (!keeping) throw new Error(`The script has no chapter("${fromChapter}") to record from`);
  await tutorialContext.endHidden();
  await holdStill(1200);
} catch (error) {
  failure = error;
  // The page as it is now: frames are not captured while fast forwarding, and the last one may be some time back
  await page.screenshot({ path: path.join(outputDir, "stopped.png") }).catch(() => undefined);
} finally {
  await cdp.send("Page.stopScreencast").catch(() => undefined);
  timeline.durationMs = startedAt ? now() : 0;
  // --from: after the kept recording up to the chapter (unless the recording never got there)
  const result = earlier && keeping ? joinRecordings(earlier, timeline) : earlier ? earlier.full : timeline;
  writeFileSync(path.join(outputDir, "timeline.json"), JSON.stringify(result, null, 1));
  Object.assign(timeline, result);
  await browser.close();
}
// Reported here, not left uncaught: the voice library's handler for uncaught errors prints its whole minified source
// in front of the message
if (failure) {
  console.error(`\nThe recording stopped: ${failure instanceof Error ? failure.stack : failure}`);
  console.error(`What was recorded until then is kept in public/recordings/${name}/, with its narration so far.`);
  // What the page showed when it stopped: usually says why (a dialog, a page that did not load, a moved button)
  console.error(`The page as it was when it stopped: public/recordings/${name}/stopped.png`);
  // The voice for what was recorded, so it can be watched in Studio
  await narrate(name).catch((error) => console.error(`No narration made: ${error instanceof Error ? error.message : error}`));
  process.exit(1);
}
if (byPosition.length > 0) {
  console.warn(
    `${byPosition.length} step(s) pick an element by position (${byPosition.join(", ")}): if they ever pick the wrong ` +
      "one, use a name or text only that element has",
  );
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
