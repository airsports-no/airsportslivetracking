// Records clicks for a tutorial script. Like Playwright's codegen (it uses the same locator generator), but the route
// editor's map is recorded so it replays exactly, which codegen cannot do: clicks as coordinates (map.click), panning,
// dragging and wheel zooming in full with their timing (map.drag, map.wheel), and the exact view the map comes to rest
// at after each move (map.view). Elsewhere a map without window.__routeEditorMap gets clicks by position.
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
  // The recorder's own phase box (F8) is not part of the tutorial
  const isOurs = (event) => Boolean(event.target && event.target.closest && event.target.closest("[data-capture-ui]"));

  document.addEventListener("focusin", (event) => {
    if (isOurs(event)) return;
    flushTyping();
    editing = isTextField(event.target) ? { element: event.target, value: event.target.value } : null;
  }, true);

  // The route editor's Leaflet map (window.__routeEditorMap): map clicks are written as coordinates and every map
  // movement ends with its exact view, so the replay lands on exactly the same points whatever the timing
  const leaflet = () => window.__routeEditorMap;
  const fixed = (value, digits) => Number(value.toFixed(digits));
  const relative = (map, event) => {
    const rect = map.getBoundingClientRect();
    return [round(event.clientX - rect.x), round(event.clientY - rect.y)];
  };

  let press = null;
  window.addEventListener("pointerdown", (event) => {
    if (isOurs(event)) return;
    flushTyping();
    const map = mapOf(event.target);
    press = { x: event.clientX, y: event.clientY, target: event.target, map, at: performance.now(),
      locator: locatorOf(event.target), path: map ? [[...relative(map, event), 0]] : [] };
  }, true);
  window.addEventListener("pointermove", (event) => {
    if (!press || !press.map) return;
    const now = performance.now();
    if (now - press.at < 16) return;
    press.path.push([...relative(press.map, event), round(now - press.at)]);
    press.at = now;
  }, true);
  window.addEventListener("pointerup", (event) => {
    if (isOurs(event)) return;
    if (!press) return;
    const { x, y, target, map, locator, path, at } = press;
    press = null;
    const moved = Math.hypot(event.clientX - x, event.clientY - y) > 6;
    if (map && moved) {
      // Panning, or dragging a point: the whole path with its timing, relative to the map
      path.push([...relative(map, event), round(performance.now() - at)]);
      emit("await map.drag(" + JSON.stringify(path) + ");");
      pendingView();
    } else if (moved) {
      emit("await page.mouse.move(" + round(x) + ", " + round(y) + ");");
      emit("await page.mouse.down();");
      emit("await page.mouse.move(" + round(event.clientX) + ", " + round(event.clientY) + ", { steps: 20 });");
      emit("await page.mouse.up();");
    } else if (map && leaflet()) {
      const point = leaflet().mouseEventToLatLng(event);
      emit("await map.click(" + fixed(point.lat, 7) + ", " + fixed(point.lng, 7) + ");");
    } else if (map) {
      const rect = map.getBoundingClientRect();
      emit("await page.locator(" + quote(mapSelector(map)) + ").click({ position: { x: " + round(x - rect.x) +
        ", y: " + round(y - rect.y) + " } });");
    } else if (!(target instanceof HTMLSelectElement) && !(target instanceof HTMLOptionElement)) {
      emit("await page." + locator + ".click();");
    }
  }, true);

  document.addEventListener("change", (event) => {
    if (isOurs(event)) return;
    const element = event.target;
    if (element instanceof HTMLSelectElement) {
      emit("await page." + locatorOf(element) + ".selectOption(" + quote(element.value) + ");");
    } else if (isTextField(element)) {
      flushTyping();
    }
  }, true);

  window.addEventListener("keydown", (event) => {
    if (isOurs(event)) return;
    if (event.key === "F8") {
      event.preventDefault();
      openPhaseBox();
      return;
    }
    if (["Enter", "Escape", "Tab"].includes(event.key)) {
      flushTyping();
      emit("await page.keyboard.press(" + quote(event.key) + ");");
    }
  }, true);

  // F8 marks the start of a new phase of the tutorial: a box asks for its name and, optionally, the narration to speak
  // while it happens. Written as a chapter() and a say() that does not wait, so the voice runs alongside the clicks.
  const openPhaseBox = () => {
    if (document.querySelector("[data-capture-ui]")) return;
    flushTyping();
    const host = document.createElement("div");
    host.setAttribute("data-capture-ui", "");
    host.style.cssText = "position:fixed;inset:0;z-index:2147483647;display:flex;align-items:flex-start;" +
      "justify-content:center;padding-top:80px;background:rgba(0,0,0,0.35)";
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = \`
      <style>
        form { width: 640px; background: #12161d; color: #f8fafc; border-radius: 14px; padding: 22px 24px;
          font: 15px system-ui, sans-serif; box-shadow: 0 20px 60px rgba(0,0,0,0.5); border-top: 4px solid #e11d24; }
        h2 { margin: 0 0 14px; font-size: 18px; }
        label { display: block; margin: 12px 0 6px; color: #94a3b8; }
        input, textarea { width: 100%; box-sizing: border-box; background: #0a0c10; color: #f8fafc;
          border: 1px solid #334155; border-radius: 8px; padding: 9px 11px; font: inherit; }
        textarea { height: 96px; resize: vertical; }
        p { margin: 12px 0 0; color: #94a3b8; font-size: 13px; }
      </style>
      <form>
        <h2>New phase</h2>
        <label for="title">Phase name (shown in the video and as a chapter)</label>
        <input id="title" autocomplete="off">
        <label for="narration">Narration, spoken while the phase happens (may be left empty)</label>
        <textarea id="narration"></textarea>
        <p>Enter (Ctrl+Enter in the narration) to add, Esc to cancel. Not part of the recording.</p>
      </form>\`;
    document.body.append(host);
    const form = root.querySelector("form");
    const title = root.getElementById("title");
    const narration = root.getElementById("narration");
    const close = () => host.remove();
    const submit = () => {
      const name = title.value.trim();
      const text = narration.value.trim().replace(/\\s+/g, " ");
      emit("");
      emit("// ── Phase" + (name ? ": " + name : "") + " ──");
      if (name) emit("await chapter(" + quote(name) + ");");
      emit(text ? "await say(" + quote(text) + ", { wait: false });" : "// await say(\\"\\", { wait: false });");
      close();
    };
    form.addEventListener("submit", (event) => { event.preventDefault(); submit(); });
    root.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") close();
      if (event.key === "Enter" && (event.target === title || event.ctrlKey)) { event.preventDefault(); submit(); }
    });
    title.focus();
  };

  // Wheel zooming: every tick with its timing, relative to the map
  let wheel = null;
  window.addEventListener("wheel", (event) => {
    if (isOurs(event)) return;
    const map = mapOf(event.target);
    if (!map) return;
    const now = performance.now();
    if (wheel) clearTimeout(wheel.timer);
    else wheel = { ticks: [], at: now };
    wheel.ticks.push([...relative(map, event), round(event.deltaY), round(now - wheel.at)]);
    wheel.at = now;
    wheel.timer = setTimeout(() => {
      emit("await map.wheel(" + JSON.stringify(wheel.ticks) + ");");
      wheel = null;
      pendingView();
    }, 400);
  }, { capture: true, passive: true });

  // After the map has come to rest (zoom animation, the glide after a pan, or a move the page made itself), its view,
  // unless a gesture is still being written or the view is unchanged
  let lastView = "";
  let viewTimer = null;
  const pendingView = () => {
    clearTimeout(viewTimer);
    viewTimer = setTimeout(() => {
      const map = leaflet();
      if (!map) return;
      if (wheel || (press && press.map)) return pendingView();
      const center = map.getCenter();
      const view = fixed(center.lat, 7) + ", " + fixed(center.lng, 7) + ", " + fixed(map.getZoom(), 3);
      if (view === lastView) return;
      lastView = view;
      emit("await map.view(" + view + ");");
    }, 450);
  };
  // A new route's map opens where the browser says it is (the route editor's locate()). Should it still be at the
  // editor's default view after a moment, the recorder moves it to the given location itself
  const DEFAULT_VIEW = [51.505, -0.09];
  let watched = null;
  setInterval(() => {
    const map = leaflet();
    if (map && map !== watched) {
      watched = map;
      lastView = "";
      setTimeout(() => {
        const start = window.__captureStart;
        const center = map.getCenter();
        if (start && Math.abs(center.lat - DEFAULT_VIEW[0]) < 1e-6 && Math.abs(center.lng - DEFAULT_VIEW[1]) < 1e-6) {
          map.setView([start.lat, start.lng], 11, { animate: false });
          window.__captureNote && window.__captureNote("The map did not move to the location: moved it there");
        }
        map.on("moveend", pendingView);
        pendingView();
      }, 1500);
    }
  }, 300);
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
    `// Recorded ${new Date().toISOString()} from ${url}\n// Paste these lines into run() of the tutorial script` +
      ` (which takes { page, say, highlight, camera, map }).\n\n`,
  );
  const write = (line) => {
    appendFileSync(output, line + "\n");
    onStep(line);
  };
  await context.exposeBinding("__captureStep", (_source, line) => write(line));
  await context.exposeBinding("__captureNote", (_source, note) => console.log(note));
  if (geolocation) {
    await context.addInitScript(`window.__captureStart = ${JSON.stringify({ lat: latitude, lng: longitude })};`);
  }
  await context.addInitScript(PAGE_SCRIPT);
  const page = await context.newPage();
  // Playwright dismisses dialogs (confirm, alert) when nothing handles them, while recording and while replaying
  page.on("dialog", (dialog) => write(`// A dialog was dismissed: ${JSON.stringify(dialog.message())}`));
  await page.goto(url);
  // Where a new route's map opens: say what the page sees, so a location that does not get through is noticed
  const seen = await page
    .evaluate(
      () =>
        new Promise((resolve) =>
          navigator.geolocation.getCurrentPosition(
            (position) => resolve(position.coords.latitude + ", " + position.coords.longitude),
            (error) => resolve("no location (" + error.message + ")"),
            { timeout: 5000 },
          ),
        ),
    )
    .catch((error) => "no location (" + error.message + ")");
  console.log(`Location given: ${geolocation || "none"}. The page sees: ${seen}`);
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
