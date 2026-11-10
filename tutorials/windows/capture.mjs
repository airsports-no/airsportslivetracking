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

import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

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
  // always: written while recording is paused (F10) too, as a phase marked then (F8) starts what comes after it
  const emit = (line, always = false) => window.__captureStep && window.__captureStep(line, always);
  // A locator that picks by position (a CSS path with nth-child, .nth(), .first()) depends on the order of what is on
  // the page: one more route in a list, and it picks another. Such a button or link is written instead by a text only
  // its surroundings have: "the Create task button in the card with Task 2.A5 Unknown legs".
  const POSITIONAL = /nth-child|nth-of-type|\\.nth\\(|\\.first\\(\\)|\\.last\\(\\)/;
  const squash = (text) => (text || "").trim().replace(/\\s+/g, " ");
  const nameOf = (element) => squash(element.getAttribute("aria-label") || element.innerText || element.value);
  const xpathString = (text) => (text.includes('"') ? "'" + text + "'" : '"' + text + '"');
  const byItsSurroundings = (element) => {
    const target = element.closest("button, a, [role=button], [role=link]");
    if (!target) return null;
    const role = target.tagName === "A" || target.getAttribute("role") === "link" ? "link" : "button";
    const name = nameOf(target);
    if (!name || name.length > 60 || (name.includes('"') && name.includes("'"))) return null;
    const kind = role === "link" ? "a, [role=link]" : "button, [role=button]";
    const sameIn = (root) => [...root.querySelectorAll(kind)].filter((item) => nameOf(item) === name).length;
    // Texts to name the surroundings by: headings (a card's title) first, then other texts with words in them (not
    // "22.82 NM", which changes with the route)
    const texts = (root) => {
      const headings = [...root.querySelectorAll("h1, h2, h3, h4, h5, h6, [role=heading]")];
      const leaves = [...root.querySelectorAll("*")].filter((item) => item.children.length === 0);
      return [...headings, ...leaves]
        .filter((item) => !item.closest(kind))
        .map((item) => squash(item.textContent))
        .filter((text) => text.length >= 3 && text.length <= 80 && /[A-Za-zÆØÅæøå]{3}/.test(text));
    };
    const onPage = texts(document.body);
    for (let box = target.parentElement, depth = 0; box && depth < 12; box = box.parentElement, depth++) {
      const same = sameIn(box);
      if (same > 1) break;
      if (same !== 1) continue;
      const text = texts(box).find((candidate) => onPage.filter((other) => other === candidate).length === 1);
      if (!text) continue;
      const self = role === "link" ? "self::a or @role='link'" : "self::button or @role='button'";
      const ancestor = "xpath=ancestor::*[.//*[" + self + "][normalize-space(.)=" + xpathString(name) + " or @aria-label=" +
        xpathString(name) + "]][1]";
      return "getByText(" + quote(text) + ", { exact: true }).locator(" + quote(ancestor) + ").getByRole(" + quote(role) +
        ", { name: " + quote(name) + ", exact: true })";
    }
    return null;
  };
  const locatorOf = (element) => {
    let generated;
    try {
      generated = window.playwright.generateLocator(element, "javascript");
    } catch (error) {
      return "locator(" + quote(element.tagName.toLowerCase()) + ")";
    }
    return POSITIONAL.test(generated) ? byItsSurroundings(element) || generated : generated;
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
    // Where on the map a drag starts, and the zoom: the replay starts it there however the map lies
    const anchor = map && leaflet()
      ? { at: [fixed(leaflet().mouseEventToLatLng(event).lat, 7), fixed(leaflet().mouseEventToLatLng(event).lng, 7)],
          zoom: leaflet().getZoom() }
      : null;
    press = { x: event.clientX, y: event.clientY, target: event.target, map, anchor, at: performance.now(),
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
    const { x, y, target, map, anchor, locator, path, at } = press;
    press = null;
    const moved = Math.hypot(event.clientX - x, event.clientY - y) > 6;
    if (map && moved) {
      // Panning, or dragging a point: the whole path with its timing, relative to the map
      path.push([...relative(map, event), round(performance.now() - at)]);
      emit("await map.drag(" + JSON.stringify(path) + (anchor ? ", " + JSON.stringify(anchor) : "") + ");");
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
    } else if (element instanceof HTMLInputElement && ["date", "datetime-local"].includes(element.type) && element.value) {
      // Chosen in the browser's own picker, which the clicks do not show. The date is written as so many days from the
      // day it is recorded (day(0) is that day): the replay uses the day it runs, so it is never in the past
      const [date, time] = element.value.split("T");
      const midnight = (value) => new Date(value + "T00:00").getTime();
      const recordedOn = new Date();
      const pad = (number) => String(number).padStart(2, "0");
      const today = recordedOn.getFullYear() + "-" + pad(recordedOn.getMonth() + 1) + "-" + pad(recordedOn.getDate());
      const offset = Math.round((midnight(date) - midnight(today)) / 86400000);
      const value = time ? "\`" + "$" + "{day(" + offset + ")}T" + time + "\`" : "day(" + offset + ")";
      emit("await page." + locatorOf(element) + ".fill(" + value + ");");
    } else if (element instanceof HTMLInputElement && ["time", "month", "week", "color", "range"].includes(element.type)) {
      // Chosen in the browser's own picker, which the clicks do not show: the value it ended with
      emit("await page." + locatorOf(element) + ".fill(" + quote(element.value) + ");");
    } else if (isTextField(element)) {
      flushTyping();
    }
  }, true);

  window.addEventListener("keydown", (event) => {
    if (isOurs(event)) return;
    const isCtrlShift = event.ctrlKey && event.shiftKey && !event.altKey && !event.metaKey;
    const isPlain = !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey;
    if ((isCtrlShift && (event.code === "F7" || event.code === "Digit7")) || (isPlain && event.code === "F7")) {
      event.preventDefault();
      event.stopPropagation();
      openOverlayBox();
      return;
    }
    if ((isCtrlShift && (event.code === "F8" || event.code === "Digit8")) || (isPlain && event.code === "F8")) {
      event.preventDefault();
      event.stopPropagation();
      openPhaseBox();
      return;
    }
    if ((isCtrlShift && (event.code === "F9" || event.code === "Digit9")) || (isPlain && event.code === "F9")) {
      event.preventDefault();
      event.stopPropagation();
      toggleHidden();
      return;
    }
    if ((isCtrlShift && (event.code === "F10" || event.code === "Digit0")) || (isPlain && event.code === "F10")) {
      event.preventDefault();
      event.stopPropagation();
      flushTyping();
      window.__captureToggleRecording && window.__captureToggleRecording();
      return;
    }
    if (isPlain && ["Enter", "Escape", "Tab"].includes(event.key)) {
      flushTyping();
      emit("await page.keyboard.press(" + quote(event.key) + ");");
    }
  }, true);

  // Subtle hotkey reminder in the bottom-left corner while recording clicks (hidden in --live mode so it is not in the video)
  const showControlsHud = () => {
    if (window.__captureLive) return;
    if (!document.body || document.querySelector("[data-capture-hud]")) return;
    const hud = document.createElement("div");
    hud.setAttribute("data-capture-ui", "");
    hud.setAttribute("data-capture-hud", "");
    hud.style.cssText = "position:fixed;bottom:10px;left:12px;z-index:2147483647;background:rgba(15,23,42,0.84);" +
      "color:rgba(248,250,252,0.92);font:500 12px system-ui,sans-serif;padding:4px 8px;border-radius:999px;" +
      "border:1px solid rgba(255,255,255,0.14);backdrop-filter:blur(6px);display:flex;gap:4px;align-items:center";
    const items = [
      ["Ctrl+Shift+F7 Overlay", openOverlayBox],
      ["Ctrl+Shift+F8 Phase & Voice", openPhaseBox],
      ["Ctrl+Shift+F9 Hide setup", () => toggleHidden()],
      ["Ctrl+Shift+F10 Pause", () => { flushTyping(); window.__captureToggleRecording && window.__captureToggleRecording(); }],
    ];
    for (const [label, action] of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.style.cssText = "background:transparent;border:none;color:inherit;font:inherit;padding:2px 6px;" +
        "border-radius:999px;cursor:pointer";
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        action();
      });
      hud.append(btn);
    }
    document.body.append(hud);
  };
  document.addEventListener("DOMContentLoaded", showControlsHud);
  showControlsHud();

  // Ctrl+Shift+F9 (or F9) starts and ends a hidden part: what you do in between is performed when the video is recorded,
  // but cut from it (setting something up the tutorial is not about). A badge shows while it is on, and stays on across pages.
  const HIDDEN_KEY = "__captureHidden";
  const PENDING_PHASE_KEY = "__capturePendingPhase";
  const showHiddenBadge = () => {
    // Not before the page has a body (a page loading during a hidden part): an error here would stop the rest of this
    // script, F8 and the map recording with it. DOMContentLoaded shows it then.
    if (!document.body) return;
    if (window.__captureLive) {
      if (sessionStorage.getItem(HIDDEN_KEY) === "on" && !document.title.startsWith("[HIDDEN] ")) {
        document.title = "[HIDDEN] " + document.title;
      }
      return;
    }
    if (sessionStorage.getItem(HIDDEN_KEY) !== "on" || document.querySelector("[data-capture-badge]")) return;
    const badge = document.createElement("div");
    badge.setAttribute("data-capture-ui", "");
    badge.setAttribute("data-capture-badge", "");
    badge.textContent = "Hidden from the video (Ctrl+Shift+F9 / F9 to end)";
    badge.style.cssText = "position:fixed;top:12px;right:12px;z-index:2147483647;background:#e11d24;color:white;" +
      "font:600 13px system-ui,sans-serif;padding:6px 12px;border-radius:999px;box-shadow:0 4px 14px rgba(0,0,0,0.35);" +
      "pointer-events:none";
    document.body.append(badge);
  };
  const toggleHidden = () => {
    flushTyping();
    if (sessionStorage.getItem(HIDDEN_KEY) === "on") {
      sessionStorage.removeItem(HIDDEN_KEY);
      document.querySelectorAll("[data-capture-badge]").forEach((badge) => badge.remove());
      document.title = document.title.replace(/^\\[HIDDEN\\]\\s*/, "");
      emit("await endHidden();");
      emit("// ── Shown again ──");
      // A phase marked during the hidden part starts here, where the video comes back (its narration would be cut)
      for (const line of JSON.parse(sessionStorage.getItem(PENDING_PHASE_KEY) || "[]")) emit(line, true);
      sessionStorage.removeItem(PENDING_PHASE_KEY);
    } else {
      sessionStorage.setItem(HIDDEN_KEY, "on");
      emit("");
      emit("// ── Hidden from the video ──");
      emit("await startHidden();");
      showHiddenBadge();
    }
  };
  document.addEventListener("DOMContentLoaded", showHiddenBadge);
  showHiddenBadge();

  // F7 adds an on-screen text overlay card (and optional narration) at this moment in the tutorial
  const openOverlayBox = () => {
    if (document.querySelector("[data-capture-phase-box], [data-capture-overlay-box]")) return;
    flushTyping();
    window.__captureUiOpen && window.__captureUiOpen(true);
    const host = document.createElement("div");
    host.setAttribute("data-capture-ui", "");
    host.setAttribute("data-capture-overlay-box", "");
    host.style.cssText = "position:fixed;inset:0;z-index:2147483647;display:flex;align-items:flex-start;" +
      "justify-content:center;padding-top:80px;background:rgba(0,0,0,0.35)";
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = \`
      <style>
        form { width: 640px; background: #12161d; color: #f8fafc; border-radius: 14px; padding: 22px 24px;
          font: 15px system-ui, sans-serif; box-shadow: 0 20px 60px rgba(0,0,0,0.5); border-top: 4px solid #e11d24; }
        h2 { margin: 0 0 14px; font-size: 18px; }
        .row { display: grid; grid-template-columns: 1fr 220px; gap: 12px; }
        label { display: block; margin: 12px 0 6px; color: #94a3b8; }
        input, select, textarea { width: 100%; box-sizing: border-box; background: #0a0c10; color: #f8fafc;
          border: 1px solid #334155; border-radius: 8px; padding: 9px 11px; font: inherit; }
        textarea { height: 72px; resize: vertical; }
        p { margin: 12px 0 0; color: #94a3b8; font-size: 13px; }
      </style>
      <form>
        <h2>On-screen text overlay</h2>
        <div class="row">
          <div>
            <label for="title">Card heading (optional, e.g. Tip or Key point)</label>
            <input id="title" autocomplete="off" placeholder="Tip">
          </div>
          <div>
            <label for="position">Position</label>
            <select id="position">
              <option value="top-right">Top right (card)</option>
              <option value="top-left">Top left (card)</option>
              <option value="bottom-right">Bottom right (card)</option>
              <option value="bottom-left">Bottom left (card)</option>
              <option value="center">Center (callout)</option>
            </select>
          </div>
        </div>
        <label for="text">Text shown in the overlay card</label>
        <textarea id="text" placeholder="Short, scannable callout shown over the page"></textarea>
        <label for="narration">Optional narration spoken at the same time (may be left empty)</label>
        <textarea id="narration"></textarea>
        <p>Ctrl+Enter to add, Esc to cancel. Not part of the recording.</p>
      </form>\`;
    document.body.append(host);
    const form = root.querySelector("form");
    const title = root.getElementById("title");
    const position = root.getElementById("position");
    const text = root.getElementById("text");
    const narration = root.getElementById("narration");
    const close = () => {
      host.remove();
      requestAnimationFrame(() => requestAnimationFrame(() => window.__captureUiOpen && window.__captureUiOpen(false)));
    };
    const submit = () => {
      const body = text.value.trim();
      const heading = title.value.trim();
      const pos = position.value;
      const spoken = narration.value.trim().replace(/\\s+/g, " ");
      const lines = [];
      if (spoken) lines.push("await say(" + quote(spoken) + ", { wait: false });");
      if (body) {
        const opts = [];
        if (heading) opts.push("title: " + quote(heading));
        if (pos && pos !== "top-right") opts.push("position: " + quote(pos));
        lines.push("await overlay(" + quote(body) + (opts.length ? ", { " + opts.join(", ") + " }" : "") + ");");
      }
      if (sessionStorage.getItem(HIDDEN_KEY) === "on") {
        sessionStorage.setItem(PENDING_PHASE_KEY, JSON.stringify([...JSON.parse(sessionStorage.getItem(PENDING_PHASE_KEY) || "[]"), ...lines]));
      } else {
        for (const line of lines) emit(line, true);
      }
      close();
    };
    form.addEventListener("submit", (event) => { event.preventDefault(); submit(); });
    root.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") close();
      if (event.key === "Enter" && (event.target === title || event.ctrlKey)) { event.preventDefault(); submit(); }
    });
    text.focus();
  };

  // F8 marks the start of a new phase of the tutorial: a box asks for its name and, optionally, the narration to speak
  // while it happens. Written as a chapter() and a say() that does not wait, so the voice runs alongside the clicks.
  const openPhaseBox = () => {
    // Only one box at a time (the badges for a pause or a hidden part are ours too, but do not stop it)
    if (document.querySelector("[data-capture-phase-box], [data-capture-overlay-box]")) return;
    flushTyping();
    window.__captureUiOpen && window.__captureUiOpen(true);
    const host = document.createElement("div");
    host.setAttribute("data-capture-ui", "");
    host.setAttribute("data-capture-phase-box", "");
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
    const close = () => {
      host.remove();
      requestAnimationFrame(() => requestAnimationFrame(() => window.__captureUiOpen && window.__captureUiOpen(false)));
    };
    const submit = () => {
      const name = title.value.trim();
      const text = narration.value.trim().replace(/\\s+/g, " ");
      const lines = ["", "// ── Phase" + (name ? ": " + name : "") + " ──"];
      if (name) lines.push("await chapter(" + quote(name) + ");");
      lines.push(text ? "await say(" + quote(text) + ", { wait: false });" : "// await say(\\"\\", { wait: false });");
      // During a hidden part: written when it ends (F9), so the phase starts where the video comes back
      if (sessionStorage.getItem(HIDDEN_KEY) === "on") {
        sessionStorage.setItem(PENDING_PHASE_KEY, JSON.stringify([...JSON.parse(sessionStorage.getItem(PENDING_PHASE_KEY) || "[]"), ...lines]));
      } else {
        for (const line of lines) emit(line, true);
      }
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

  // Wheel zooming: every tick with its timing, relative to the map, and the zoom it came to (to): Leaflet's zoom depends
  // on the ticks' timing to the millisecond, so the replay zooms to where it came to instead of repeating the ticks
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
      const leafletMap = leaflet();
      const to = leafletMap ? (leafletMap._animatingZoom ? leafletMap._animateToZoom : leafletMap.getZoom()) : null;
      emit("await map.wheel(" + JSON.stringify(wheel.ticks) + (to === null ? "" : ", { to: " + to + " }") + ");");
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

export async function startCapture({
  output,
  url,
  auth,
  viewport = "1440,810",
  geolocation,
  paused = false,
  liveDir,
  onStep = () => {},
  // For testing the recorder itself; recording the clicks needs the window
  headless = false,
}) {
  const [width, height] = viewport.split(",").map(Number);
  // Where the browser says it is (the route editor opens a new route's map there): must match TUTORIAL_GEOLOCATION
  const [latitude, longitude] = geolocation ? geolocation.split(",").map(Number) : [];
  const browser = await chromium.launch({
    headless,
    // Prevent Google / OAuth providers from rejecting the browser as "automated / not trusted"
    ignoreDefaultArgs: ["--enable-automation"],
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const context = await browser.newContext({
    // Steps replayed from a script go to paths on the site ("/...")
    baseURL: new URL(url).origin,
    viewport: { width, height },
    ...(liveDir ? { deviceScaleFactor: 2 } : {}),
    storageState: auth && existsSync(auth) ? auth : undefined,
    ...(geolocation ? { geolocation: { latitude, longitude }, permissions: ["geolocation"] } : {}),
  });
  writeFileSync(
    output,
    `// Recorded ${new Date().toISOString()} from ${url}\n// Paste these lines into run() of the tutorial script` +
      `.\n\n`,
  );
  // While paused (F10, or while the steps before a chapter are replayed) nothing is written
  let recording = !paused;
  let uiOpen = false;

  // Live single-pass recording (--live): captures 2x JPEG screencast frames and timeline.json while you click once
  const tutorialName = liveDir ? path.basename(liveDir) : "recording";
  const defaultTitle = tutorialName
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
  const timeline = liveDir
    ? {
        name: tutorialName,
        title: defaultTitle,
        subtitle: "Air Sports Live Tracking",
        viewport: { width, height },
        durationMs: 0,
        frames: [],
        actions: [],
        highlights: [],
        overlays: [],
        steps: [],
        says: [],
        camera: [],
        holds: [],
        chapters: [],
        hidden: [],
        edit: {},
        captions: true,
      }
    : null;
  let startedAt = 0;
  let chapterName = "Start";
  let stepInChapter = 0;
  let chapterFloor = 0;
  let hiddenSince = null;
  const usedChapterNames = new Set();
  const now = () => (startedAt ? Date.now() - startedAt : 0);

  if (liveDir) {
    rmSync(liveDir, { recursive: true, force: true });
    mkdirSync(path.join(liveDir, "frames"), { recursive: true });
  }

  const recordLiveLine = (line) => {
    if (!timeline) return;
    if (!startedAt) startedAt = Date.now();
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("//")) return;

    const chapterMatch = trimmed.match(/^await chapter\((.+)\);$/);
    if (chapterMatch) {
      const title = JSON.parse(chapterMatch[1]);
      chapterFloor = Math.max(now(), (timeline.steps.at(-1)?.t ?? -1) + 1);
      timeline.chapters.push({ t: chapterFloor, title });
      let count = 1;
      while (usedChapterNames.has(count === 1 ? title : `${title} (${count})`)) count++;
      chapterName = count === 1 ? title : `${title} (${count})`;
      usedChapterNames.add(chapterName);
      stepInChapter = 0;
      return;
    }
    if (trimmed === "await startHidden();") {
      if (hiddenSince === null) hiddenSince = now();
      return;
    }
    if (trimmed === "await endHidden();") {
      if (hiddenSince !== null) {
        timeline.hidden.push({ start: hiddenSince, end: now() });
        hiddenSince = null;
      }
      return;
    }

    const sayMatch = trimmed.match(/^await say\(("(?:\\.|[^"\\])*")(?:,\s*\{\s*wait:\s*(true|false)\s*\})?\);$/);
    if (sayMatch) {
      const text = JSON.parse(sayMatch[1]);
      const wait = sayMatch[2] ? sayMatch[2] === "true" : true;
      const id = `${chapterName} #${++stepInChapter}`;
      const t = Math.max(now(), chapterFloor);
      timeline.steps.push({ t, id, label: `say(${JSON.stringify(text.length > 100 ? `${text.slice(0, 97)}...` : text)})` });
      timeline.says.push({ t, step: id, text, wait });
      return;
    }

    const overlayMatch = trimmed.match(/^await overlay\(("(?:\\.|[^"\\])*")(?:,\s*(\{.*\}))?\);$/);
    if (overlayMatch) {
      const text = JSON.parse(overlayMatch[1]);
      let title;
      let position;
      if (overlayMatch[2]) {
        const titleM = overlayMatch[2].match(/title:\s*("(?:\\.|[^"\\])*")/);
        const posM = overlayMatch[2].match(/position:\s*("(?:\\.|[^"\\])*")/);
        if (titleM) title = JSON.parse(titleM[1]);
        if (posM) position = JSON.parse(posM[1]);
      }
      const id = `${chapterName} #${++stepInChapter}`;
      const t = Math.max(now(), chapterFloor);
      timeline.steps.push({ t, id, label: `overlay(${JSON.stringify(text)})` });
      timeline.overlays.push({ t, step: id, text, title, position, durationMs: 3500 });
      return;
    }

    if (trimmed.startsWith("await ")) {
      const label = trimmed.replace(/^await\s+/, "").replace(/;$/, "");
      const id = `${chapterName} #${++stepInChapter}`;
      const t = Math.max(now(), chapterFloor);
      timeline.steps.push({ t, id, label: label.length > 140 ? `${label.slice(0, 137)}...` : label });
    }
  };

  // A step that picks an element by its position among those that match: another match before it, on a later day,
  // changes which one is used
  const BY_POSITION = /\.(nth\(\d+\)|first\(\)|last\(\))/;
  const write = (line, always = false) => {
    if (!recording && !always) return;
    appendFileSync(output, line + "\n");
    onStep(line);
    recordLiveLine(line);
    if (/^await page\./.test(line) && BY_POSITION.test(line)) {
      const warning = "// ↑ Picks by position: if it may pick the wrong one later, use a name or text only it has";
      appendFileSync(output, warning + "\n");
      onStep(warning);
    }
  };
  await context.exposeBinding("__captureStep", (_source, line, always) => write(line, Boolean(always)));
  await context.exposeBinding("__captureUiOpen", (_source, open) => {
    uiOpen = Boolean(open);
  });
  await context.exposeBinding("__captureAction", (_source, action) => {
    if (!timeline || !recording || uiOpen) return;
    if (!startedAt) startedAt = Date.now();
    timeline.actions.push({ ...action, t: now() });
  });
  // A badge says when nothing is being recorded (in --live mode, shown in the window title so it is not in the video)
  const showRecordingState = (target) =>
    target
      .evaluate((isRecording) => {
        if (window.__captureLive) {
          document.title = isRecording
            ? document.title.replace(/^\[PAUSED\]\s*/, "")
            : "[PAUSED] " + document.title.replace(/^\[PAUSED\]\s*/, "");
          return;
        }
        document.querySelectorAll("[data-capture-paused]").forEach((badge) => badge.remove());
        if (isRecording) return;
        const badge = document.createElement("div");
        badge.setAttribute("data-capture-ui", "");
        badge.setAttribute("data-capture-paused", "");
        badge.textContent = "Not recording (Ctrl+Shift+F10 / F10 to start)";
        badge.style.cssText = "position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:2147483647;" +
          "background:#334155;color:white;font:600 13px system-ui,sans-serif;padding:6px 12px;border-radius:999px;" +
          "box-shadow:0 4px 14px rgba(0,0,0,0.35);pointer-events:none";
        (document.body || document.documentElement).append(badge);
      }, recording)
      .catch(() => undefined);
  const setRecording = async (target, on) => {
    recording = on;
    console.log(on ? "Recording." : "Paused: not recording (Ctrl+Shift+F10 / F10 to start again).");
    // Recording starts from the map's exact view, wherever it was set up
    if (on) {
      const view = await target
        .evaluate(() => {
          const map = window.__routeEditorMap;
          if (!map) return null;
          const center = map.getCenter();
          return [Number(center.lat.toFixed(7)), Number(center.lng.toFixed(7)), Number(map.getZoom().toFixed(3))];
        })
        .catch(() => null);
      if (view) write(`await map.view(${view.join(", ")});`);
    }
    await showRecordingState(target);
  };
  await context.exposeBinding("__captureToggleRecording", ({ page: source }) => setRecording(source, !recording));
  await context.exposeBinding("__captureNote", (_source, note) => console.log(note));
  if (geolocation) {
    await context.addInitScript(`window.__captureStart = ${JSON.stringify({ lat: latitude, lng: longitude })};`);
  }
  if (liveDir) {
    await context.addInitScript(`(() => {
      window.__captureLive = true;
      const interactive =
        "button, a, input, select, textarea, label, summary, [role=button], [role=option], [role=menuitem], [role=tab], " +
        "[role=checkbox], [role=radio], [role=switch], [role=link], [role=combobox], .leaflet-container";
      const boxOf = (element) => {
        const target = (element && element.closest && element.closest(interactive)) || element;
        if (!target || !target.getBoundingClientRect) return undefined;
        const rect = target.getBoundingClientRect();
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
      };
      const isOurs = (event) => Boolean(event.target && event.target.closest && event.target.closest("[data-capture-ui]"));
      const report = (action) => window.__captureAction && window.__captureAction(action);
      let lastTyped = { element: null, at: 0 };
      let lastScroll = 0;
      let lastDrag = { x: 0, y: 0, at: 0 };
      window.addEventListener("pointerdown", (event) => {
        if (isOurs(event)) return;
        lastDrag = { x: event.clientX, y: event.clientY, at: Date.now() };
        report({ kind: "click", x: event.clientX, y: event.clientY, box: boxOf(event.target) });
      }, true);
      window.addEventListener("pointermove", (event) => {
        if (!event.buttons || isOurs(event)) return;
        const now = Date.now();
        if (now - lastDrag.at < 40 || Math.hypot(event.clientX - lastDrag.x, event.clientY - lastDrag.y) < 4) return;
        lastDrag = { x: event.clientX, y: event.clientY, at: now };
        report({ kind: "drag", x: event.clientX, y: event.clientY });
      }, { capture: true, passive: true });
      window.addEventListener("keydown", (event) => {
        if (
          isOurs(event) ||
          event.ctrlKey ||
          event.altKey ||
          event.metaKey ||
          ["Control", "Shift", "Alt", "Meta", "F7", "F8", "F9", "F10"].includes(event.key)
        ) {
          return;
        }
        const element = event.target;
        if (lastTyped.element === element && Date.now() - lastTyped.at < 2000) {
          lastTyped.at = Date.now();
          return;
        }
        lastTyped = { element, at: Date.now() };
        const box = boxOf(element);
        if (box) report({ kind: "type", x: box.x + box.width / 2, y: box.y + box.height / 2, box });
      }, true);
      window.addEventListener("wheel", (event) => {
        if (isOurs(event) || Date.now() - lastScroll < 1000) return;
        lastScroll = Date.now();
        report({ kind: "scroll", x: event.clientX, y: event.clientY });
      }, { capture: true, passive: true });
      document.addEventListener("DOMContentLoaded", () => {
        const style = document.createElement("style");
        style.textContent = "* { caret-color: transparent !important; }";
        document.head.append(style);
      });
    })();`);
  }
  await context.addInitScript(PAGE_SCRIPT);
  // Links and windows that would open a new tab (the live map) open in this one, as when the video is recorded.
  // Keep real popup windows (with window features like width/height, e.g. Google/Firebase OAuth sign-in popups) intact.
  await context.addInitScript(`(() => {
    const origOpen = window.open.bind(window);
    document.addEventListener("click", (event) => {
      const link = event.target && event.target.closest && event.target.closest("a[target]");
      if (link && link.target !== "_self") link.target = "_self";
    }, true);
    window.open = (url, target, features) => {
      if (features) return origOpen(url, target, features);
      if (url) window.location.assign(url);
      return window;
    };
  })();`);
  const page = await context.newPage();
  // The browser Playwright drives shows no dialogs (confirm, alert, "leave this page?"): they are accepted, here and when
  // the video is recorded, so "Save anyway?" saves. nextDialog("dismiss") before the step declines one instead.
  page.on("dialog", (dialog) => {
    write(`// A dialog was accepted: ${JSON.stringify(dialog.message())} (nextDialog("dismiss") before the step declines it)`);
    dialog.accept().catch(() => undefined);
  });
  page.on("domcontentloaded", () => showRecordingState(page));
  await page.goto(url);

  let cdp = null;
  let frameCount = 0;
  let previousFrame = "";
  if (liveDir && timeline) {
    cdp = await context.newCDPSession(page);
    cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
      cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
      if (!recording || uiOpen || data === previousFrame) return;
      previousFrame = data;
      const frameEpoch = Math.round((metadata.timestamp ?? Date.now() / 1000) * 1000);
      if (!startedAt) startedAt = frameEpoch;
      const file = `frames/${String(++frameCount).padStart(6, "0")}.jpg`;
      writeFileSync(path.join(liveDir, file), Buffer.from(data, "base64"));
      const t = Math.max(0, frameEpoch - startedAt);
      timeline.frames.push({ t, file: `recordings/${tutorialName}/${file}` });
    });
    await cdp.send("Page.startScreencast", {
      format: "jpeg",
      quality: 92,
      maxWidth: width * 2,
      maxHeight: height * 2,
    });
  }

  const finishLive = async (scriptPath) => {
    if (!liveDir || !timeline) return;
    if (cdp) await cdp.send("Page.stopScreencast").catch(() => undefined);
    if (hiddenSince !== null) {
      timeline.hidden.push({ start: hiddenSince, end: now() });
      hiddenSince = null;
    }
    timeline.durationMs = startedAt ? now() : 0;
    // Match step.line numbers to scripts/<name>.ts if it was generated
    if (scriptPath && existsSync(scriptPath)) {
      const scriptLines = readFileSync(scriptPath, "utf8").split(/\r?\n/);
      let searchFrom = 0;
      for (const step of timeline.steps) {
        const idx = scriptLines.findIndex((line, i) => i >= searchFrom && line.trim().startsWith("await "));
        if (idx >= 0) {
          step.line = idx + 1;
          searchFrom = idx + 1;
        }
      }
    }
    writeFileSync(path.join(liveDir, "timeline.json"), JSON.stringify(timeline, null, 1));
    console.log(
      `Live recording saved to ${liveDir}: ${(timeline.durationMs / 1000).toFixed(1)}s, ` +
        `${timeline.frames.length} frames, ${timeline.steps.length} steps.`,
    );
  };

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
  return { browser, context, page, setRecording: (on) => setRecording(page, on), finishLive };
}

// The steps of a tutorial script before one of its chapters: the lines of run() above that chapter's
// chapter("...") line (and the phase comment above it). Recorded steps are plain JavaScript, so they run as they are.
export function stepsBeforeChapter(source, title) {
  const lines = source.split(/\r?\n/);
  const runIndex = lines.findIndex((line) => /async\s+run\s*\(/.test(line));
  const quoted = [JSON.stringify(title), `'${title}'`, `\`${title}\``];
  const chapterIndex = lines.findIndex(
    (line, index) => index > runIndex && /chapter\(/.test(line) && quoted.some((text) => line.includes(text)),
  );
  if (runIndex < 0) throw new Error("No run() in the script");
  if (chapterIndex < 0) throw new Error(`No chapter("${title}") in the script`);
  let end = chapterIndex;
  while (end - 1 > runIndex && /^\s*\/\/ ── Phase/.test(lines[end - 1])) end--;
  const startUrl = source.match(/startUrl:\s*["'`]([^"'`]+)["'`]/)?.[1] ?? "/";
  return { steps: lines.slice(runIndex + 1, end).join("\n"), startUrl };
}

// Plays steps back quickly to reach the state a chapter starts from: narration, highlights and pauses are skipped,
// map steps go straight to their result
export async function replaySteps(page, steps) {
  // A map step may come right after the step that opens the route editor: wait for its map
  const mapCall = async (body, argument) => {
    await page.waitForFunction(() => Boolean(window.__routeEditorMap), null, { timeout: 15000 });
    return page.evaluate(body, argument);
  };
  const corner = () =>
    mapCall(() => {
      const rect = window.__routeEditorMap.getContainer().getBoundingClientRect();
      return { x: rect.x, y: rect.y };
    });
  const map = {
    view: (lat, lng, zoom) =>
      mapCall(
        ([lat, lng, zoom]) =>
          new Promise((resolve) => {
            const leaflet = window.__routeEditorMap;
            leaflet.once("moveend", () => resolve());
            leaflet.setView([lat, lng], zoom, { animate: false });
            setTimeout(resolve, 1500);
          }),
        [lat, lng, zoom],
      ),
    click: async (lat, lng) => {
      // Not while the map still moves (a zoom animation, the glide after a pan): the point would land off
      await mapCall(
        () =>
          new Promise((resolve) => {
            const map = window.__routeEditorMap;
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
      );
      const point = await mapCall(
        ([lat, lng]) => {
          const leaflet = window.__routeEditorMap;
          const rect = leaflet.getContainer().getBoundingClientRect();
          const inMap = leaflet.latLngToContainerPoint([lat, lng]);
          return { x: rect.x + inMap.x, y: rect.y + inMap.y };
        },
        [lat, lng],
      );
      await page.mouse.click(point.x, point.y);
      await page.waitForTimeout(150);
    },
    drag: async (path, anchor) => {
      const { x, y } = await corner();
      // Recorded with where it started on the map: start there however the map lies, scaled to the zoom
      let points = path;
      if (anchor) {
        const now = await mapCall(([lat, lng]) => {
          const point = window.__routeEditorMap.latLngToContainerPoint([lat, lng]);
          return { x: point.x, y: point.y, zoom: window.__routeEditorMap.getZoom() };
        }, anchor.at);
        const scale = 2 ** (now.zoom - anchor.zoom);
        points = path.map(([px, py, ms]) => [now.x + (px - path[0][0]) * scale, now.y + (py - path[0][1]) * scale, ms]);
      }
      await page.mouse.move(x + points[0][0], y + points[0][1]);
      await page.mouse.down();
      for (const [px, py] of points.slice(1)) await page.mouse.move(x + px, y + py);
      await page.mouse.up();
    },
    wheel: async (ticks, options) => {
      if (options && options.to !== undefined) {
        // To the zoom the gesture came to, around where it was made
        const [px, py] = ticks[ticks.length - 1];
        await mapCall(
          ([px, py, to]) =>
            new Promise((resolve) => {
              const map = window.__routeEditorMap;
              if (Math.abs(map.getZoom() - to) < 1e-3) return resolve();
              map.once("zoomend", () => resolve());
              // Around the map position under the mouse: a plain [x, y] would be read as a latitude and longitude
              map.setZoomAround(map.containerPointToLatLng([px, py]), to);
              setTimeout(resolve, 1500);
            }),
          [px, py, options.to],
        );
        return;
      }
      const { x, y } = await corner();
      for (const [px, py, deltaY] of ticks) {
        await page.mouse.move(x + px, y + py);
        await page.mouse.wheel(0, deltaY);
        await page.waitForTimeout(60);
      }
      await page.waitForTimeout(400);
    },
  };
  const skip = async () => {};
  const helpers = {
    page,
    map,
    say: skip,
    chapter: skip,
    overlay: skip,
    highlight: skip,
    pause: skip,
    camera: () => {},
    startHidden: skip,
    endHidden: skip,
    showPdf: async () => console.log("  (a showPdf step is not replayed here)"),
    zoomPdf: skip,
    nextDialog: () => {},
    day: (offset = 0) => {
      const date = new Date(Date.now() + offset * 86400000);
      const pad = (number) => String(number).padStart(2, "0");
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
    },
    pdfPage: () => page.locator("body"),
    pdfRegion: async () => page.locator("body"),
  };
  const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
  await new AsyncFunction(...Object.keys(helpers), steps)(...Object.values(helpers));
}

// Writes a ready-to-run tutorial script when recording a new tutorial (so no copy-pasting from recorded/<name>.js is needed)
export function writeTutorialScript(scriptPath, recordedFile, startUrl) {
  if (!scriptPath || existsSync(scriptPath) || !existsSync(recordedFile)) return false;
  const raw = readFileSync(recordedFile, "utf8").split(/\r?\n/);
  // Drop the 2-line header ("// Recorded ... / // Paste these lines ...") and leading/trailing blank lines
  const bodyLines = raw.filter((_, index) => index >= 2);
  while (bodyLines.length > 0 && bodyLines[0].trim() === "") bodyLines.shift();
  while (bodyLines.length > 0 && bodyLines[bodyLines.length - 1].trim() === "") bodyLines.pop();
  if (bodyLines.length === 0) return false;
  const baseName = path.basename(scriptPath, ".ts");
  const defaultTitle = baseName
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
  const parsedUrl = new URL(startUrl);
  const relativeStartUrl = (parsedUrl.pathname || "/") + (parsedUrl.search || "") + (parsedUrl.hash || "");
  const indented = bodyLines.map((line) => (line ? `    ${line}` : "")).join("\n");
  const source = `import { defineTutorial } from "../src/runner/tutorial";

export default defineTutorial({
  title: ${JSON.stringify(defaultTitle)},
  subtitle: "Air Sports Live Tracking",
  startUrl: ${JSON.stringify(relativeStartUrl)},

  async run({ page, map, say, chapter, overlay, highlight, pause, camera, startHidden, endHidden, day, nextDialog }) {
${indented}
  },
});
`;
  mkdirSync(path.dirname(scriptPath), { recursive: true });
  writeFileSync(scriptPath, source);
  return true;
}

if (process.argv[1] && process.argv[1].endsWith("capture.mjs")) {
  const output = option("output");
  const url = option("url");
  const auth = option("auth");
  const script = option("script");
  const chapter = option("chapter");
  const liveDir = option("live");
  if (!output || !url) {
    console.error(
      "Usage: node capture.mjs --output <file.js> --url <start url> [--auth <state.json>] [--viewport w,h]\n" +
        "         [--geolocation lat,lng] [--paused] [--live <recordingDir>] [--script <tutorial.ts> [--chapter <title>]]",
    );
    process.exit(1);
  }
  // Re-recording a chapter: the steps before it are replayed first, while nothing is recorded
  const before = script && chapter ? stepsBeforeChapter(readFileSync(script, "utf8"), chapter) : null;
  const startUrl = before ? new URL(before.startUrl, url).href : url;
  const { browser, context, page, setRecording, finishLive } = await startCapture({
    output,
    url: startUrl,
    auth,
    viewport: option("viewport"),
    geolocation: option("geolocation"),
    paused: Boolean(before) || process.argv.includes("--paused"),
    liveDir,
    onStep: (line) => console.log(line),
  });
  if (before) {
    console.log(`Replaying the steps before "${chapter}"...`);
    try {
      await replaySteps(page, before.steps);
      await setRecording(true);
      console.log(`Now record "${chapter}". Close the browser when you are done.`);
    } catch (error) {
      console.error(`The replay stopped: ${error.message}`);
      console.log("Set the page up by hand, then press Ctrl+Shift+F10 (or F10) to start recording.");
    }
  } else if (process.argv.includes("--paused")) {
    console.log("Not recording yet: set the page up, then press Ctrl+Shift+F10 (or F10) to start (and again to pause).");
  } else {
    console.log(
      `${liveDir ? "LIVE RECORDING (frames + clicks captured in one pass)" : "Recording clicks"}. ` +
        "Hotkeys: Ctrl+Shift+F7 (or Ctrl+Shift+7 / F7) Overlay · Ctrl+Shift+F8 (or Ctrl+Shift+8 / F8) Phase & Voice · " +
        "Ctrl+Shift+F9 (or Ctrl+Shift+9 / F9) Hide setup · Ctrl+Shift+F10 (or Ctrl+Shift+0 / F10) Pause.",
    );
    console.log("Close the browser window when you are done.");
  }
  await page.waitForEvent("close", { timeout: 0 });
  if (auth) await context.storageState({ path: auth });
  if (script && !chapter && writeTutorialScript(script, output, url)) {
    console.log(`Created tutorial script: ${script}`);
  }
  await finishLive(script);
  await browser.close();
  console.log(`Recorded steps: ${output}`);
  if (liveDir) {
    const tutName = path.basename(liveDir);
    console.log(`Next (no second recording pass needed!): npm run timing -- ${tutName}  or  npm run render -- ${tutName}`);
  } else if (script && !chapter) {
    console.log(`Next: npm run record -- ${path.basename(script, ".ts")}`);
  }
}
