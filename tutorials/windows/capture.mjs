// Records clicks for a tutorial script. Like Playwright's codegen (it uses the same locator generator), but clicks
// and drags on the map keep their exact position, which codegen does not record, and wheel zooming on the map is kept.
//
// Plain JavaScript that needs only the playwright package, so it runs on Windows: see codegen.ps1, which runs it.
//
//   node capture.mjs --output <file.js> --url <start url> [--auth <state.json>] [--viewport 1440,810]
//                    [--geolocation 60.8,11.1]
//
// Each recorded step is appended to the output file as it happens. Close the browser to finish: the login session is
// then saved to --auth.

import { appendFileSync, existsSync, writeFileSync } from "node:fs";

// window.playwright (the locator generator) is only there in this debug mode, which Playwright reads when it loads
process.env.PWDEBUG = "console";
const { chromium } = await import("playwright");

const option = (name, fallback) => {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
};

// The page side: turns what the user does into lines of Playwright code
const PAGE_SCRIPT = `(() => {
  const MAP = ".leaflet-container";
  const quote = (value) => JSON.stringify(String(value));
  const emit = (line) => window.__captureStep && window.__captureStep(line);
  const locatorOf = (element) => {
    try {
      return window.playwright.generateLocator(element, "javascript");
    } catch (error) {
      return "locator(" + quote(element.tagName.toLowerCase()) + ")";
    }
  };
  const mapOf = (element) => {
    if (!element.closest || element.closest(".leaflet-control")) return null;
    const map = element.closest(MAP);
    if (!map) return null;
    return map.closest("#map-container") || map;
  };
  const mapSelector = (map) => (map.id ? "#" + map.id : MAP);
  const round = (value) => Math.round(value);
  const isTextField = (element) =>
    (element instanceof HTMLInputElement &&
      ["text", "search", "email", "password", "url", "tel", "number", ""].includes(element.type)) ||
    element instanceof HTMLTextAreaElement;

  // Typing is written as one fill() when the field is left, but before whatever happens next
  let editing = null;
  const flushTyping = () => {
    if (editing && editing.element.value !== editing.value) {
      emit("await page." + locatorOf(editing.element) + ".fill(" + quote(editing.element.value) + ");");
      editing.value = editing.element.value;
    }
  };
  document.addEventListener("focusin", (event) => {
    flushTyping();
    editing = isTextField(event.target) ? { element: event.target, value: event.target.value } : null;
  }, true);

  let press = null;
  window.addEventListener("pointerdown", (event) => {
    flushTyping();
    press = { x: event.clientX, y: event.clientY, target: event.target, map: mapOf(event.target),
      locator: locatorOf(event.target) };
  }, true);
  window.addEventListener("pointerup", (event) => {
    if (!press) return;
    const { x, y, target, map, locator } = press;
    press = null;
    const moved = Math.hypot(event.clientX - x, event.clientY - y) > 6;
    if (moved) {
      // A drag (moving a waypoint, panning the map): replayed with the mouse, in page coordinates
      emit("await page.mouse.move(" + round(x) + ", " + round(y) + ");");
      emit("await page.mouse.down();");
      emit("await page.mouse.move(" + round(event.clientX) + ", " + round(event.clientY) + ", { steps: 20 });");
      emit("await page.mouse.up();");
    } else if (map) {
      const rect = map.getBoundingClientRect();
      emit("await page.locator(" + quote(mapSelector(map)) + ").click({ position: { x: " + round(x - rect.x) +
        ", y: " + round(y - rect.y) + " } });");
    } else if (!(target instanceof HTMLSelectElement) && !(target instanceof HTMLOptionElement)) {
      emit("await page." + locator + ".click();");
    }
  }, true);

  document.addEventListener("change", (event) => {
    const element = event.target;
    if (element instanceof HTMLSelectElement) {
      emit("await page." + locatorOf(element) + ".selectOption(" + quote(element.value) + ");");
    } else if (isTextField(element)) {
      flushTyping();
    }
  }, true);

  window.addEventListener("keydown", (event) => {
    if (["Enter", "Escape", "Tab"].includes(event.key)) {
      flushTyping();
      emit("await page.keyboard.press(" + quote(event.key) + ");");
    }
  }, true);

  // Zooming the map with the wheel changes where everything is: kept, summed per gesture
  let wheel = null;
  window.addEventListener("wheel", (event) => {
    if (!mapOf(event.target)) return;
    if (wheel) clearTimeout(wheel.timer);
    else wheel = { x: event.clientX, y: event.clientY, deltaY: 0 };
    wheel.deltaY += event.deltaY;
    wheel.timer = setTimeout(() => {
      emit("await page.mouse.move(" + round(wheel.x) + ", " + round(wheel.y) + ");");
      emit("await page.mouse.wheel(0, " + round(wheel.deltaY) + ");");
      emit("await page.waitForTimeout(600);");
      wheel = null;
    }, 400);
  }, { capture: true, passive: true });
})();`;

export async function startCapture({ output, url, auth, viewport = "1440,810", geolocation, onStep = () => {} }) {
  const [width, height] = viewport.split(",").map(Number);
  // Where the browser says it is (the route editor opens a new route's map there): must match TUTORIAL_GEOLOCATION
  const [latitude, longitude] = geolocation ? geolocation.split(",").map(Number) : [];
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width, height },
    storageState: auth && existsSync(auth) ? auth : undefined,
    ...(geolocation ? { geolocation: { latitude, longitude }, permissions: ["geolocation"] } : {}),
  });
  writeFileSync(
    output,
    `// Recorded ${new Date().toISOString()} from ${url}\n// Paste these lines into run() of the tutorial script.\n\n`,
  );
  const write = (line) => {
    appendFileSync(output, line + "\n");
    onStep(line);
  };
  await context.exposeBinding("__captureStep", (_source, line) => write(line));
  await context.addInitScript(PAGE_SCRIPT);
  const page = await context.newPage();
  // Playwright dismisses dialogs (confirm, alert) when nothing handles them, while recording and while replaying
  page.on("dialog", (dialog) => write(`// A dialog was dismissed: ${JSON.stringify(dialog.message())}`));
  await page.goto(url);
  return { browser, context, page };
}

if (process.argv[1] && process.argv[1].endsWith("capture.mjs")) {
  const output = option("output");
  const url = option("url");
  const auth = option("auth");
  if (!output || !url) {
    console.error("Usage: node capture.mjs --output <file.js> --url <start url> [--auth <state.json>] [--viewport w,h]");
    process.exit(1);
  }
  const { browser, context, page } = await startCapture({
    output,
    url,
    auth,
    viewport: option("viewport"),
    geolocation: option("geolocation"),
    onStep: (line) => console.log(line),
  });
  console.log("Recording. Close the browser window when you are done.");
  await page.waitForEvent("close", { timeout: 0 });
  if (auth) await context.storageState({ path: auth });
  await browser.close();
  console.log(`Recorded steps: ${output}`);
}
