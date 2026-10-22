# Tutorial videos

Short tutorial videos of the site, made from a script: you click through a task once to record the steps, write
the narration beside them, and the toolset records the screen, generates the voice, cuts the dead time and renders a
video with automatic zoom, a smooth cursor, highlights and captions.

The interactive part, clicking through the site to record the steps, happens in a browser on **Windows**.
Everything else (recording the video, previewing, rendering) runs in **WSL**, headless.

## Setup

**In WSL**, once:

```
cd tutorials
npm ci
npx playwright install chromium
cp .env.example .env       # optional: site address, voice
```

**On Windows**, once:

1. Install Node.js (LTS), for example `winget install OpenJS.NodeJS.LTS`, and open a new PowerShell.
2. Nothing else: the first run of the recording script below installs Playwright and its browser into
   `%LOCALAPPDATA%\aslt-tutorial-recorder`.
3. Check that the local site opens on Windows at http://localhost:8002 (WSL passes `localhost` through). If it
   does not, use the address that works with `-BaseUrl` below and set the same `TUTORIAL_BASE_URL` in `.env`.

The tutorials folder is at `\\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials` on Windows
(`wslpath -w .` in WSL prints it).

## Making a tutorial

1. **Record the clicks (Windows).** In PowerShell:

   ```powershell
   powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 task2.a3
   ```

   A browser opens on the site (with developer tools, which you can close). The first time, log in there: the
   session is saved to `.auth/state.json` when you close the browser, and every later recording, in Windows or WSL,
   starts logged in. Click through the task; each step is written live to `recorded/task2.a3.js` and shown in the
   PowerShell window. Close the browser when done. Options: `-Path /some/page` to start elsewhere, `-BaseUrl` for
   another site address.

   The recorder (`windows/capture.mjs`) writes the same readable steps as Playwright's codegen, and records the
   route editor's map so it replays exactly, however much you zoom and pan to find your spots:

   ```ts
   await map.wheel([[700, 400, -100, 0], [700, 400, -100, 83]]);   // each wheel tick, with its timing
   await map.view(60.7953122, 11.0912345, 14);                     // the exact view the map came to rest at
   await map.drag([[800, 500, 0], [760, 485, 17], [720, 470, 27]]); // a pan or a dragged point, in full
   await map.click(60.8012034, 11.1034001);                         // a map click, as coordinates
   ```

   Your zooming and panning play back at your own speed, and after each move the map settles on exactly the view
   you had, so every point lands on the coordinates you clicked. You can edit a `map.click` coordinate by hand.
   This needs the route editor's map handle (`window.__routeEditorMap`); without it, map clicks are recorded as
   positions on the map, which replay correctly only if the map opens at the same place and zoom each time. A new route's map opens where the browser says it is: give a location with `-Geolocation
   "60.8,11.1"` here (in quotes: PowerShell turns 60.8,11.1 into a list) and the same `TUTORIAL_GEOLOCATION` in `.env` (otherwise it opens at the editor's default, in
   London). Log in as a demo user with demo data, since the session file is what the recordings use.
2. **Write the script (WSL).** Copy `scripts/example.ts` to `scripts/<name>.ts` (kebab-case), paste the
   `page.` lines from `recorded/<name>.js` into `run()`, and add the narration between the
   steps:

   ```ts
   await say("Open the contest you want to add the task to.");
   await page.getByRole("link", { name: "Norwegian Championship" }).click();
   await say("Pick the task type.", { wait: false });   // spoken while the next steps happen
   await page.getByRole("button", { name: "New task" }).click();
   await highlight(page.getByLabel("Task type"), { label: "2.A3 Contract navigation" });
   ```

   - `say(text)` speaks a line and waits for it to finish. With `{ wait: false }` the following steps happen while
     it is spoken; the next `say` waits for it. `{ spoken: "..." }` changes how a line sounds without changing
     its caption.
   - `highlight(locator, { label, durationMs })` dims the page around an element and outlines it.
   - `pause(ms)` keeps a still moment that would otherwise be cut.
   - `map.view`, `map.click`, `map.drag` and `map.wheel` are the recorder's map steps (step 1); `run()` takes `map`
     beside `page`.
   - `camera("wide")` shows the whole page (for example while drawing on the map) until `camera("auto")`.
   - `fill()` from the recorder is typed out visibly, key by key.
3. **Record (WSL).** `npm run record -- <name>` plays the script in a headless browser and records everything
   into `public/recordings/<name>/`. Nothing needs to be on screen. (`--headed` shows the browser through WSLg,
   if you want to watch.)
4. **Preview.** `npm run studio` starts Remotion Studio: open the address it prints (http://localhost:3000) in a
   Windows browser to scrub through every recorded tutorial.
5. **Render (WSL).** `npm run render -- <name>` writes to `out/`:
   - `<name>.mp4`: the finished video with the voice
   - `<name>-picture.mp4` and `<name>-voice.wav`: picture and voice separately, both starting at 0, for fine
     tuning in DaVinci Resolve
   - `<name>.srt`: the narration as subtitles

Re-recording only regenerates narration lines that changed: the voice is cached in `.cache/`.

On Linux or macOS with a desktop, `npm run login` and `npm run codegen` (Playwright's codegen, without map positions)
or `node windows/capture.mjs --output recorded/<name>.js --url http://localhost:8002/ --auth .auth/state.json` work
too.

## How it works

- **Recording** (`src/runner/record.ts`): the browser itself streams a sharp JPEG of every screen change (at twice
  the resolution, so zooming in stays crisp). A script inside the page reports where every click and keystroke
  lands, so the camera and cursor follow whatever the script does.
- **Pacing** (`src/runner/record.ts`): before each step the recording waits until the page has stopped changing,
  then holds it still while the camera moves to the target (`STEP_LEAD_MS`), so nothing happens while the view
  moves; after each step it pauses (`STEP_PAUSE_AFTER_MS`, 0.9 s). Both are in `src/shared/edit.ts`.
- **Cutting** (`src/shared/edit.ts`): stretches where nothing happens (no screen change, action, narration,
  highlight or pause) longer than 0.7 s are shortened to 0.25 s. Page loads, voice generation and hesitation
  disappear. Tune per tutorial with `edit: { minGapMs, keepGapMs }`.
- **Camera** (`src/shared/camera.ts`): moves in on the element clicked, typed in or highlighted, stays while the
  work continues, and zooms out after a quiet spell or for large elements such as the map. Tune with `CAMERA`.
- **Video** (`src/remotion/`): title card, the page in a window on a background, the camera, a drawn cursor
  gliding on a slight curve with a ripple on each click, highlights, captions and the voice. Change the look in
  `theme.ts` and `TutorialVideo.tsx`.

## The look

Every video shares the same profile, set in `src/remotion/brand.ts` (logo, colours, end screen links) and
`src/remotion/theme.ts` (font, background):

- **Title screen**: the logo, `series` and `title`, and `subtitle`, from the tutorial script.
- **During the tutorial**: a header strip above the page with the logo on the left and the series and title on the
  right, so the logo stays visible when the camera zooms in.
- **End screen**: "Next tutorial: …" when the script sets `next`, otherwise "Thanks for watching", and the links in
  `brand.endScreen.links` (the app, the guides, more tutorials, the FAQ).

```ts
export default defineTutorial({
  title: "Creating a 2.A3 route",
  subtitle: "Contract navigation with time controls",
  series: "Route editor",
  next: "Creating a 2.A5 route",
  ...
```

Changing `series` or `next` in a script needs `npm run record` again (they are saved with the recording); changing
the brand files only needs a render, and shows live in `npm run studio`.

## Narration voices

Set `TTS_PROVIDER` in `.env`:

- `kokoro` (default): runs locally and is free. Good quality; the model (~90 MB) downloads on first use. Try
  `TTS_VOICE` `af_heart`, `af_bella`, `am_michael`, `bf_emma` or `bm_george`.
- `openai`: `gpt-4o-mini-tts`, whose tone follows `TTS_INSTRUCTIONS`. Needs `OPENAI_API_KEY`.
- `elevenlabs`: the most natural voices. Needs `ELEVENLABS_API_KEY`; `TTS_VOICE` is a voice id.

Words the voice says wrong go in `pronunciations.json`, spelled the way they should sound.

## Tips

- Record against demo data on the local site, so names and numbers look the same every time and no real
  contestants appear.
- Map clicks in the route editor are recorded as positions on the map: they replay correctly only if the map opens
  at the same place and zoom, and the window size (`TUTORIAL_WIDTH`/`TUTORIAL_HEIGHT`) is unchanged.
- Remotion's licence is free for individuals and companies of up to three people; check it if that changes.
