# Tutorial Video System — User Manual

This manual covers everything you need to create, edit, and publish tutorial videos for **Air Sports Live Tracking**—from quick website flows with voiceover and text callouts to multi-part tutorials that combine real-world camera footage with screen recordings in DaVinci Resolve.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [One-Time Setup (Linux & Windows/WSL)](#2-one-time-setup-linux--windowswsl)
3. [Workflow A: Two-Phase Script Generation & Recording (Standard Repeatable Flows)](#3-workflow-a-two-phase-script-generation--recording-standard-repeatable-flows)
4. [Workflow B: Single-Pass Live Recording (Heavy Downloads / One-Off Tasks)](#4-workflow-b-single-pass-live-recording-heavy-downloads--one-off-tasks)
5. [Workflow C: Hybrid Real Video + Screen Recording in DaVinci Resolve](#5-workflow-c-hybrid-real-video--screen-recording-in-davinci-resolve)
6. [Click Recorder Reference, Hotkeys (`F7`–`F10`) & Chapter Re-Recording](#6-click-recorder-reference-hotkeys-f7f10--chapter-re-recording)
7. [Script Reference (`scripts/<name>.ts`)](#7-script-reference-scriptsnamets)
8. [The Timing Editor (`npm run timing`)](#8-the-timing-editor-npm-run-timing)
9. [Voice, Pronunciations & Background Music](#9-voice-pronunciations--background-music)
10. [Command Reference Cheat Sheet](#10-command-reference-cheat-sheet)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. System Overview

Both capture modes—**Two-Phase Script Generation & Recording** and **Single-Pass Live Recording**—work identically on **Linux** (native desktop or WSLg) and **Windows** (PowerShell + WSL):

- **Workflow A — Two-Phase Script Generation & Recording (Standard Repeatable Flows)**:
  1. **Phase 1 — Capture Clicks & Generate Script (`npm run codegen` on Linux / `codegen.ps1` on Windows)**: You click through the website once in a browser. Your clicks, typing, map gestures (`map.click`, `map.drag`, `map.wheel`), phases (`F8`), on-screen text overlays (`F7`), and hidden setup steps (`F9`) are saved directly into `recorded/<name>.js` and `scripts/<name>.ts`.
  2. **Phase 2 — Replay Script to Record Screen & Voice (`npm run record -- <name>`)**: Playwright replays `scripts/<name>.ts` headlessly at 2× resolution, capturing crisp frames, exact element bounding boxes, cursor paths, and step timestamps into `public/recordings/<name>/`, and synthesises the voiceover for every `say()` line. Because the video is generated from a repeatable script, you can fix a click or re-record after a UI change anytime.
- **Workflow B — Single-Pass Live Recording (`npm run live` on Linux / `codegen.ps1 -Live` on Windows)**:
  For tasks that download gigabytes of data or shouldn't be executed twice (like the background map generator), the browser captures **both** the 2× high-DPI video frames (`public/recordings/<name>/frames/`) and `timeline.json` **in real time while you click once**, so you skip `npm run record` completely.
- **Fine-Tune & Render (`npm run timing` / `npm run render`)**:
  Without touching the website again, the system cuts dead waiting time, pans and zooms the camera smoothly onto active elements, draws a smooth cursor and click ripples, overlays chapter banners, callout cards, and 2-line captions, mixes ducked background music, and outputs `out/<name>.mp4` plus a ready-to-import DaVinci Resolve timeline (`out/<name>-resolve.fcpxml`).

---

## 2. One-Time Setup (Linux & Windows/WSL)

### On Linux (Native Desktop or inside WSL)

```bash
cd tutorials
npm ci
npx playwright install chromium
cp .env.example .env
npm run fetch-assets   # Downloads background music & sample PDFs (requires gcloud auth login)
```

- **Native Linux desktop**: Everything—interactive browser capture (`npm run codegen`, `npm run live`), headless recording (`npm run record`), the Timing Editor (`npm run timing`), and rendering (`npm run render`)—runs directly in Linux with no Windows setup needed.
- **WSL on Windows**: You can either open the interactive capture browser on the **Windows host** via `windows\codegen.ps1` (see below) **or** run `npm run codegen` / `npm run live` directly inside WSL using WSLg.

Check `tutorials/.env` before recording:

| Variable | Default | Purpose |
|---|---|---|
| `TUTORIAL_BASE_URL` | `http://localhost:8002` | Address of the local site to record against |
| `TUTORIAL_WIDTH` / `TUTORIAL_HEIGHT` | `1440` / `810` | Browser viewport size (keep 16:9, e.g. `1440×810` or `1920×1080`) |
| `TUTORIAL_GEOLOCATION` | *(empty)* | `"lat,lng"` reported by the browser (where a new route map opens, e.g. `"60.8,11.1"`) |
| `TTS_PROVIDER` | `kokoro` | `kokoro` (free local model), `openai`, or `elevenlabs` |
| `TTS_VOICE` | *(provider default)* | Voice name/ID (e.g. `af_heart`, `bm_george`, `coral`) |
| `TTS_SPEED` | `1` | Speech rate multiplier |
| `TUTORIAL_CAPTURE_OS` | *(auto)* | On native Linux, always uses Linux Chromium. In WSL, the Timing Editor's **redo clicks** button defaults to Windows PowerShell; set `TUTORIAL_CAPTURE_OS=linux` in `.env` to use Linux/WSLg Chromium instead |

### On Windows (optional, when running WSL + Windows browser)

1. Install Node.js LTS on Windows (`winget install OpenJS.NodeJS.LTS`).
2. The first time you run `windows\codegen.ps1`, it automatically installs Playwright into `%LOCALAPPDATA%\aslt-tutorial-recorder`.

---

## 3. Workflow A: Two-Phase Script Generation & Recording (Standard Repeatable Flows)

Use this two-phase workflow when your tutorial is a normal website walkthrough that you may want to tweak or re-record later when the UI changes.

### Phase 1: Click through the flow in the browser to generate the script

**On Linux (or WSL with WSLg):**
```bash
npm run codegen -- my-tutorial

# Optional flags:
# npm run codegen -- my-tutorial /routeeditor/        # start on a specific path
# npm run codegen -- my-tutorial --paused             # start paused (press F10 when ready to record)
```

**On Windows PowerShell (with WSL):**
```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 my-tutorial

# Optional flags:
# ...\codegen.ps1 my-tutorial -Path /routeeditor/     # start on a specific path
# ...\codegen.ps1 my-tutorial -Paused                 # start paused (press F10 when ready to record)
```

While clicking through the website:
- **Log in once** if prompted (or run `npm run login` beforehand)—your session is saved to `.auth/state.json` when you close the browser.
- Press **`Ctrl+Shift+F8`** (or **`Ctrl+Shift+8`** / **`F8`**) at the start of each logical phase to name the chapter and type the voiceover sentence spoken during that phase.
- Press **`Ctrl+Shift+F7`** (or **`Ctrl+Shift+7`** / **`F7`**) whenever you want a floating **on-screen text overlay card** (e.g. a tip, keyboard shortcut, or rule summary) to appear on screen.
- Press **`Ctrl+Shift+F9`** (or **`Ctrl+Shift+9`** / **`F9`**) before and after any setup actions that should be executed during replay but **cut from the video** (the video crossfades across the hidden section).
- Press **`Ctrl+Shift+F10`** (or **`Ctrl+Shift+0`** / **`F10`**) to pause/resume recording clicks while you inspect the page.
- *(In `codegen` mode, you can also click the buttons directly on the bottom-left HUD pill without recording a click.)*
- **Close the browser** when finished.

Closing the browser saves `recorded/my-tutorial.js` and **automatically creates `scripts/my-tutorial.ts`** if it does not exist yet.

### Step 2: Review `scripts/my-tutorial.ts`

Open `scripts/my-tutorial.ts` to set the `title`, `subtitle`, `series`, `next`, and `cleanUp` options, and tweak any `say()` or `overlay()` lines if needed:

```ts
import { defineTutorial } from "../src/runner/tutorial";

export default defineTutorial({
  title: "Creating a Contest",
  subtitle: "Setting up tasks and competitors",
  series: "Getting started",
  next: "Creating a 2.A3 route",
  startUrl: "/",
  cleanUp: { contest: "Demo Contest" },

  async run({ page, say, chapter, overlay, highlight }) {
    await say("Welcome! In this tutorial we will set up a new contest.");

    // ── Phase: Opening My Contests ──
    await chapter("Opening My Contests");
    await overlay("All contest settings live under My Contests in the top bar.", {
      title: "Quick tip",
      position: "top-right",
    });
    await say("Open My Contests from the navigation bar.", { wait: false });
    await page.getByRole("link", { name: "My contests" }).click();
  },
});
```

### Phase 2: Replay the script to record the screen & generate voice

```bash
npm run record -- my-tutorial
```

This runs `scripts/my-tutorial.ts` headlessly in Playwright, records the 2× high-DPI screen frames (`public/recordings/my-tutorial/frames/`), element bounding boxes, and cursor actions (`timeline.json`), synthesises all `say()` voice lines, and creates `scripts/my-tutorial.timing.ts`. (Pass `--headed` if you want to watch the browser window during replay, or `--from "<Chapter>"` to only re-record from a specific chapter onward.)

### Step 4: Preview & polish in the Timing Editor

```bash
npm run timing -- my-tutorial
```

Open **http://localhost:3100**:
- Click any step on the right to jump the video player to that moment.
- Adjust **hold time**, **playback speed** (`×0.25` to `×4`), **narration delay/wait**, or **edit spoken text and overlay cards** with instant live preview.
- Add missing chapters (**New chapter here**), voice lines (**New line here**), or callout cards (**New overlay here**) without re-recording.
- Click **Save** (`Ctrl+S`), and click **Make voice** if you edited any spoken text.

### Step 5: Render the final MP4

```bash
# Fast half-resolution draft preview (no separate audio stems):
npm run render -- my-tutorial --draft

# Full-quality 1080p render:
npm run render -- my-tutorial
```

Your finished video is at `out/my-tutorial.mp4`, with YouTube chapters in `out/my-tutorial-chapters.txt` and subtitles in `out/my-tutorial.srt`.

---

## 4. Workflow B: Single-Pass Live Recording (Heavy Downloads / One-Off Tasks)

When a task downloads gigabytes of files from the internet (such as the **background map generator**) or performs an expensive operation that should not be executed twice, **do not use a generic screen recorder like OBS**—doing so would lose smart camera zooming onto buttons/inputs, the smooth vector cursor + click ripples, automatic dead-time cutting, the Timing Editor (`×4` fast-forward), 2-line captions, ducked music, and DaVinci Resolve `.fcpxml` export.

Instead, use **Single-Pass Live Mode (`npm run live` on Linux / `-Live` on Windows)**, which captures both the 2× high-DPI video frames (`public/recordings/<name>/frames/`) and the step timeline (`timeline.json`) **in real time while you click once**:

### Step 1: Start a single-pass live recording

**On Linux (or WSL with WSLg):**
```bash
npm run live -- bg-map-generator

# Optional flags:
# npm run live -- bg-map-generator /mapgenerator/     # start on a specific path
# npm run live -- bg-map-generator --paused           # start paused (press F10 when ready to record)
```

**On Windows PowerShell (with WSL):**
```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 bg-map-generator -Live

# Optional flags:
# ...\codegen.ps1 bg-map-generator -Live -Path /mapgenerator/
# ...\codegen.ps1 bg-map-generator -Live -Paused
```

### Step 2: Perform the task once in real time

- **2× High-DPI frames & actions are captured live** directly into `public/recordings/bg-map-generator/frames/` and `timeline.json` (while also writing `scripts/bg-map-generator.ts` for reference).
- **All hotkeys (`Ctrl+Shift+F7`–`F10`, `Ctrl+Shift+7`–`0`, or `F7`–`F10`) work without appearing in the captured video frames**:
  - **`Ctrl+Shift+F7` / `Ctrl+Shift+7` / `F7` (Overlay)** and **`Ctrl+Shift+F8` / `Ctrl+Shift+8` / `F8` (Phase & Voice)**: Frame capture automatically pauses while the input dialog is on screen and resumes after it closes, so the dialog never appears in a single recorded frame.
  - **`Ctrl+Shift+F9` / `Ctrl+Shift+9` / `F9` (Hide setup / long wait)** and **`Ctrl+Shift+F10` / `Ctrl+Shift+0` / `F10` (Pause recording)**: Status indicators are shown in the browser window's title bar (`[HIDDEN]`, `[PAUSED]`) instead of floating on the page, keeping the video frames 100% clean.
- **How to handle a long download (two options)**:
  - **Option A — Cut the middle of the download with a crossfade (`Ctrl+Shift+F9` / `F9`)**: Once the download starts and you have shown the progress indicator for a couple of seconds, press **`Ctrl+Shift+F9`** (or `Ctrl+Shift+9` / `F9`), let the download run, and press it again right before it finishes. The rendered video will crossfade smoothly from the start of the download to completion.
  - **Option B — Fast-forward in the Timing Editor (`×4`)**: Let the download run normally, and in Step 3 select the download step in `npm run timing` and set **Speed to `×4`** (any stretches where the screen is completely still are already shortened automatically by the dead-time cutter).
- **Close the browser** when done.

### Step 3: Skip `npm run record` — go straight to `npm run timing` & `npm run render`!

Because `-Live` / `npm run live` already wrote `public/recordings/bg-map-generator/timeline.json` and `frames/*.jpg`, **no second `npm run record` pass is needed**:

1. *(Optional)* Open `scripts/bg-map-generator.ts` and edit `title`, `subtitle`, `series`, or `next` at the top—these are synced automatically into the video without re-recording.
2. Open the Timing Editor to add/edit voiceover (`New line here`), add callout cards (`New overlay here`), add chapters (`New chapter here`), or speed up the download step (`×4`):
   ```bash
   npm run timing -- bg-map-generator
   ```
3. Render the finished MP4 (and DaVinci Resolve `.fcpxml` timeline):
   ```bash
   npm run render -- bg-map-generator
   ```

---

## 5. Workflow C: Hybrid Real Video + Screen Recording in DaVinci Resolve

Use this workflow when you want to tie together real-world camera footage (e.g. briefing room, cockpit, or presenter intro/outro) with website screen recordings in DaVinci Resolve.

### Option 1: Importing a rendered tutorial into DaVinci Resolve

1. Render the tutorial with `--clean-picture` so `out/<name>-picture.mp4` has **no burned-in captions** (while `out/<name>.mp4` still has captions for quick review):
   ```bash
   npm run render -- my-tutorial --clean-picture
   ```
2. In `out/` you get:
   - `my-tutorial-resolve.fcpxml` — **DaVinci Resolve timeline (FCPXML 1.9)**
   - `my-tutorial-picture.mp4` — Clean 1080p30 picture track (with camera zooms, cursor, highlights, chapter banners, and overlay cards)
   - `my-tutorial-voice.wav` — Full combined voice stem (if you want a single track)
   - `my-tutorial-music.wav` — Ducked background music stem
   - `my-tutorial.srt` — Subtitles timed to the voice
3. In DaVinci Resolve, choose **File → Import → Timeline…** and select `out/my-tutorial-resolve.fcpxml`:
   - **Video 1** has `my-tutorial-picture.mp4`.
   - **Audio 1** has **every individual `say()` sentence placed as its own discrete, labelled WAV clip** at its exact frame-aligned timestamp.
   - **Audio 2** has `my-tutorial-music.wav`.
   - **Timeline Markers** mark every **Chapter** and **Overlay**.
4. Because each sentence is its own clip on Audio 1 and every phase is marked with a Chapter marker, you can razor-split the timeline at any chapter boundary and insert real camera footage without cutting through a single monolithic audio file.
5. If you want captions across both your camera footage and screen recording, drag `out/my-tutorial.srt` onto the Subtitle track in Resolve.

### Option 2: Generating AI voiceover & Resolve timeline for real-world camera footage (`npm run voice`)

When you have a section of real-world camera footage that needs matching AI voiceover and subtitles:

1. Create a plain text file (e.g. `briefing-intro.txt`):
   ```text
   # Chapter: Briefing Room Intro
   Welcome to the morning briefing for Task 2.A5.
   [pause 1.5s]
   Before we step out to the aircraft, let's look at the flight order and the route editor.

   # Chapter: Cockpit Check
   Make sure your tracker is switched on five minutes before takeoff.
   ```
   - Blank lines and `#` comments are ignored.
   - `# Chapter: <title>` or `## <title>` places a chapter marker on the Resolve timeline.
   - `[pause 1.5s]` or `[pause 800ms]` inserts extra silence before the next sentence (default spacing between sentences is `0.6s`).
2. Run:
   ```bash
   npm run voice -- briefing-intro.txt
   ```
3. In `out/briefing-intro-voice/` you get:
   - `01.wav`, `02.wav`, `03.wav`, … — Individual sentence clips
   - `combined.wav` — All clips combined with pauses
   - `subtitles.srt` — Two-line captions timed to each clip's pauses
   - `resolve.fcpxml` — A DaVinci Resolve timeline with all voice clips and chapter markers already laid out, ready for you to drop your camera footage onto Video 1!
   - `index.txt` — Clip filenames, start times (`@0.0s`), durations, and text

---

## 6. Click Recorder Reference, Hotkeys (`Ctrl+Shift+F7`–`F10` / `F7`–`F10`) & Chapter Re-Recording

When running `npm run codegen` / `npm run live` (Linux) or `windows\codegen.ps1` (Windows), a subtle HUD pill in the bottom-left corner reminds you of the four recorder hotkeys (and in `codegen` mode, you can also click the buttons directly on the HUD pill).

To avoid window-manager, laptop media-key, and Chrome DevTools shortcut conflicts on Linux (GNOME/X11) and Windows, each action supports **`Ctrl+Shift+F7`–`F10`**, **`Ctrl+Shift+7`–`0`**, and plain **`F7`–`F10`**:

| Hotkey | Action | What it writes to the script |
|---|---|---|
| **`Ctrl+Shift+F7`** *(or `Ctrl+Shift+7` / `F7`)* | **On-Screen Text Overlay** — Opens a dialog for card heading (e.g. `Tip`), position (`top-right`, `top-left`, `bottom-right`, `bottom-left`, `center`), overlay text, and optional simultaneous narration. | `await overlay("...", { title: "Tip", position: "top-right" });` (plus `await say("...", { wait: false });` if narration is entered) |
| **`Ctrl+Shift+F8`** *(or `Ctrl+Shift+8` / `F8`)* | **New Phase & Voice** — Opens a dialog for the chapter title and the narration spoken during the phase. | `await chapter("...");` and `await say("...", { wait: false });` |
| **`Ctrl+Shift+F9`** *(or `Ctrl+Shift+9` / `F9`)* | **Toggle Hidden Setup** — Shows a red badge while active. Actions performed while hidden run during `npm run record` to set up state, but are cut from the rendered video with a crossfade. | `await startHidden();` … `await endHidden();` |
| **`Ctrl+Shift+F10`** *(or `Ctrl+Shift+0` / `F10`)* | **Pause / Resume Recording** — Lets you inspect the page or set things up manually without writing steps. | *(nothing written while paused; on resume, logs `map.view` if on a map)* |

### Re-recording a single chapter's clicks

If one chapter of an existing tutorial needs new clicks:

**On Linux (or WSL with WSLg):**
```bash
npm run codegen -- my-tutorial --chapter "Placing the points"
```

**On Windows PowerShell (with WSL):**
```powershell
powershell -ExecutionPolicy Bypass -File ...\windows\codegen.ps1 my-tutorial -Chapter "Placing the points"
```

*(Or simply click **redo clicks** next to that chapter header inside `npm run timing -- my-tutorial`—it works automatically on both Linux and Windows!)*

1. The browser replays all steps before `"Placing the points"` automatically, then enables recording.
2. Click through that chapter again and close the browser.
3. Run `npm run replace-chapter -- my-tutorial "Placing the points"` (or click **Use the new clicks** in the Timing Editor) to splice the new clicks into `scripts/my-tutorial.ts`, then run `npm run record -- my-tutorial --from "Placing the points"`.

---

## 7. Script Reference (`scripts/<name>.ts`)

Inside `run()`, all helpers are available both on the destructured context argument and as globals (so pasted lines work directly):

### Narration & Structure
- **`await say(text, { wait, spoken })`**
  Speaks `text` and displays synchronized 2-line captions.
  - `wait: true` (default): the next step waits in the video until the sentence finishes speaking.
  - `wait: false`: the sentence speaks while the following steps happen on screen.
  - `spoken: "..."`: custom phonetic text sent to TTS while captions still show `text`.
- **`await chapter(title)`**
  Starts a named phase: slides in a chapter banner at the bottom-left, updates the top header strip, exports a YouTube chapter in `<name>-chapters.txt`, and places a marker in `<name>-resolve.fcpxml`.

### Visual Callouts & Camera
- **`await overlay(text, { title, position, durationMs })`**
  Shows a floating glassmorphic callout card without dimming the page or needing a DOM element.
  - `position`: `"top-right"` (default), `"top-left"`, `"bottom-right"`, `"bottom-left"`, or `"center"`.
  - `title`: optional uppercase accent header above the text (e.g. `"Tip"`, `"Keyboard shortcut"`).
  - `durationMs`: how long the card stays on screen (defaults to automatic reading time between `3.2s` and `7s`).
  - Supports multi-line text using `\n`.
- **`await highlight(locator, { label, durationMs })`**
  Dims the page around `locator`, draws an accent frame around the element, shows an optional `label` pill, and zooms the camera onto it.
- **`camera("wide")` / `camera("auto")`**
  `camera("wide")` locks the camera to the full viewport (useful when drawing a wide route on the map); `camera("auto")` returns to automatic target framing.
- **`await pause(ms)`**
  Keeps a still moment for `ms` milliseconds so the automatic dead-time cutter does not shorten it.
- **`await startHidden()` / `await endHidden()`**
  Executes the steps between them during recording, but cuts that time span from the video and crossfades across the cut.

### Route Editor Map Helpers (`map.*`)
- **`await map.view(lat, lng, zoom)`** — Sets the Leaflet map to an exact center and zoom.
- **`await map.click(lat, lng)`** — Clicks the exact geographic coordinate on the route editor map.
- **`await map.drag([[x, y, ms], ...], { at: [lat, lng], zoom })`** — Replays a smooth pan or waypoint drag with its original timing, while the video cursor follows the drag path.
- **`await map.wheel([[x, y, deltaY, ms], ...], { to: zoom })`** — Replays mouse-wheel zooming and settles on zoom `to`.

### PDF Helpers (Flight Orders & Maps)
- **`await showPdf(source, { pages, width })`** — Renders a local PDF (e.g. `"pdfs/flight-order-2a5.pdf"`) or authenticated site URL using `pdf.js`. `width: "page"` fits each page; `pages: [4]` shows only specific pages.
- **`await zoomPdf(pageNumber, { y, height, x, width, durationMs })`** — Smoothly zooms a rendered PDF page to fill the screen width around the vertical band `y .. y + height`.
- **`pdfPage(pageNumber)` / `await pdfRegion(pageNumber, { x, y, width, height })`** — Returns a locator for a whole PDF page or a fractional rectangle on it (use `npm run pdf-grid -- pdfs/file.pdf` to render a 10% coordinate grid over each page).

### Dates, Dialogs & Clean-up
- **`day(offset)`** — Returns `"YYYY-MM-DD"` relative to the day the recording runs (`day(0)` is today, `day(7)` is one week ahead) so date inputs never fall in the past.
- **`nextDialog("dismiss")`** — Declines the next browser `confirm`/`alert` dialog (by default all dialogs are accepted).
- **`cleanUp: { routes: [...], navigationTasks: [...], contest: "..." }`** — Top-level option in `defineTutorial({...})` that deletes routes and tasks created by previous runs before recording starts.

---

## 8. The Timing Editor (`npm run timing`)

Run:
```bash
npm run timing -- <name>
```
and open **http://localhost:3100**.

- **Instant Live Preview**: Every change you make to step holds, playback speed, narration timing, captions, or overlay cards updates the Remotion player immediately—no re-recording required.
- **Per-Step Controls**:
  - **Hold the picture before the step (`holdMs`)**: Positive holds the frame longer; negative trims waiting time before the step.
  - **Speed (`speed` & `until`)**: Speed up (`×1.5`, `×2`, `×3`, `×4`) or slow down (`×0.25`, `×0.5`, `×0.75`) from this step up to any later step.
  - **Before this step (`afterLine`)**: Force a step to wait (or not wait) until the previous narration line has finished speaking.
  - **For `say()` steps**: Shift when the line starts (`delayMs`), toggle whether the next step waits (`wait`), or rewrite the spoken text (`text`) and click **Make voice**.
  - **For `overlay()` steps**: Shift start time (`delayMs`), change duration (`durationMs`), switch corner/center `position`, edit the card `title`, or edit the `text`.
- **Add Without Re-recording**:
  - **New chapter here** — Inserts a chapter before the selected step.
  - **New line here** — Inserts a spoken `say()` line before the selected step.
  - **New overlay here** — Inserts an on-screen `overlay()` card before the selected step.
  - **Write into the script** — Permanently writes all added chapters, lines, and overlays into `scripts/<name>.ts` (saving a `.bak` backup) and updates step numbering in `scripts/<name>.timing.ts`.

---

## 9. Voice, Pronunciations & Background Music

### Custom Pronunciations (`pronunciations.json`)
If the TTS voice mispronounces an acronym, task code, or Norwegian name, add it to [`pronunciations.json`](file:///home/kolaf/dev/airsportslivetracking/tutorials/pronunciations.json):
```json
{
  "2.A3": "two point eh three",
  "2.A5": "two point eh five",
  "NM": "nautical miles"
}
```
Captions still display the original written text (`2.A3`), while the voice speaks the phonetic replacement. Run `npm run narrate -- <name>` (or click **Make voice** in the Timing Editor) to regenerate only affected lines.

### Background Music
- Configured in [`src/remotion/brand.ts`](file:///home/kolaf/dev/airsportslivetracking/tutorials/src/remotion/brand.ts): plays at full level on the title/end cards, ducks between sentences, and ducks ~17 dB below the voice during narration.
- Disable music for a specific tutorial with `music: false` in `defineTutorial({ ... })`.
- To level a new music track with EBU R128 loudness normalization:
  ```bash
  npm run music -- "public/brand/music/my-track.mp3"
  ```

---

## 10. Command Reference Cheat Sheet

| Command (Linux / WSL) | Windows PowerShell Equivalent | Description |
|---|---|---|
| `npm run codegen -- <name> [startPath]` | `codegen.ps1 <name> [-Path <startPath>]` | **Two-Phase (Phase 1)**: Open browser to record clicks, `F7` overlays, `F8` chapters/voice, `F9` hidden steps; auto-creates `scripts/<name>.ts` |
| `npm run codegen -- <name> --chapter "<title>"` | `codegen.ps1 <name> -Chapter "<title>"` | Replay steps before `<title>`, then record replacement clicks for that chapter |
| `npm run codegen -- <name> --paused` | `codegen.ps1 <name> -Paused` | Open recorder paused so you can set up the page manually before pressing `F10` |
| `npm run live -- <name> [startPath]` | `codegen.ps1 <name> -Live [-Path <startPath>]` | **Single-pass live recording**: captures 2× video frames + `timeline.json` + `scripts/<name>.ts` while you click once (no `npm run record` needed) |
| `npm run record -- <name>` | *(run in Linux / WSL)* | **Two-Phase (Phase 2)**: Run `scripts/<name>.ts` headlessly, capture frames/actions, and generate voice |
| `npm run record -- <name> --from "<chapter>"` | *(run in Linux / WSL)* | Re-record only from `<chapter>` onward, keeping earlier recorded chapters |
| `npm run record -- <name> --headed` | *(run in Linux / WSL)* | Record while watching the browser window |
| `npm run timing -- <name>` | *(run in Linux / WSL)* | Launch the interactive Timing Editor at `http://localhost:3100` |
| `npm run studio` | *(run in Linux / WSL)* | Launch Remotion Studio at `http://localhost:3000` |
| `npm run steps -- <name>` | *(run in Linux / WSL)* | List all chapters, steps, voice lines, and overlays with their video timestamps |
| `npm run narrate -- <name>` | *(run in Linux / WSL)* | Synthesise new or changed voice lines for `<name>` |
| `npm run render -- <name>` | *(run in Linux / WSL)* | Render `out/<name>.mp4`, stems (`-picture.mp4`, `-voice.wav`, `-music.wav`), `.srt`, `-chapters.txt`, and `-resolve.fcpxml` |
| `npm run render -- <name> --draft` | *(run in Linux / WSL)* | Fast half-resolution preview render of `out/<name>.mp4` (skips separate stems) |
| `npm run render -- <name> --clean-picture` | *(run in Linux / WSL)* | Render `out/<name>-picture.mp4` without burned-in captions for DaVinci Resolve |
| `npm run voice -- <script.txt> [outDir]` | *(run in Linux / WSL)* | Generate `01.wav..NN.wav`, `combined.wav`, `subtitles.srt`, and `resolve.fcpxml` from a plain text script |
| `npm run cleanup -- <name>` | *(run in Linux / WSL)* | Delete routes/tasks listed in `cleanUp` of `scripts/<name>.ts` |
| `npm run replace-chapter -- <name> "<chapter>"` | *(run in Linux / WSL)* | Replace `<chapter>` in `scripts/<name>.ts` with re-recorded clicks from `recorded/<name>.chapter.js` |
| `npm run pdf-grid -- <file.pdf>` | *(run in Linux / WSL)* | Render each page of `<file.pdf>` with a 10% coordinate grid into `out/` |
| `npm run fetch-assets` | *(run in Linux / WSL)* | Download background music and PDFs from the team's GCS bucket |

---

## 11. Troubleshooting

- **A step fails with `"strict mode violation: locator resolved to 2 elements"`**:
  An earlier run left behind a route or task with the same name. Add its name to `cleanUp: { routes: [...], navigationTasks: [...] }` in `scripts/<name>.ts` or run `npm run cleanup -- <name>`.
- **A recording fails mid-way through a long script**:
  Check the failure screenshot path printed in the terminal, fix the locator in `scripts/<name>.ts`, and resume from that chapter without re-recording the beginning:
  `npm run record -- <name> --from "<Chapter Title>"`.
- **Changed a sentence in `.timing.ts`, and captions updated in Studio, but the old voice still plays**:
  Click **Make voice** in `npm run timing` or run `npm run narrate -- <name>`.
- **`npm run render` says background music is missing**:
  Run `npm run fetch-assets` (after `gcloud auth login`), or set `music: false` in `defineTutorial({ ... })`.
- **Want to edit subtitles in DaVinci Resolve instead of having them baked into the video track**:
  Run `npm run render -- <name> --clean-picture`, then import `out/<name>-resolve.fcpxml` and drag `out/<name>.srt` onto a Resolve subtitle track.
