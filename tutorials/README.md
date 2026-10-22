# Tutorial videos

Short tutorial videos of the site, made from a script: you click through a task once to record the steps, write
the narration beside them, and the toolset records the screen, generates the voice, cuts the dead time and renders a
video with automatic zoom, a smooth cursor, highlights and captions.

**New to this? Start with [GUIDE.md](GUIDE.md)**, the workflow from idea to finished video without the technical
details. This README covers the setup and how the toolset works.

The interactive part, clicking through the site to record the steps, happens in a browser on **Windows**.
Everything else (recording the video, previewing, rendering) runs in **WSL**, headless.

## Setup

**In WSL**, once:

```
cd tutorials
npm ci
npx playwright install chromium
cp .env.example .env       # site address, page size, start location, voice (see the comments in it)
npm run fetch-assets       # the background music, from the team's private bucket (needs gcloud auth login)
```

**On Windows**, once:

1. Install Node.js (LTS), for example `winget install OpenJS.NodeJS.LTS`, and open a new PowerShell.
2. Nothing else: the first run of the recording script below installs Playwright and its browser into
   `%LOCALAPPDATA%\aslt-tutorial-recorder`.
3. Check that the local site opens on Windows at http://localhost:8002 (WSL passes `localhost` through). If it
   does not, set the address that works as `TUTORIAL_BASE_URL` in `.env`: both recordings use it.

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

   **Mark the phases as you go.** Press **F8** whenever a new phase starts (finding the right mode in the menus,
   placing the points, switching to the next mode, ...). A box asks for the phase's name and, if you like, the
   narration to speak during it; it is not part of the recording. Each phase is written as:

   ```ts
   // ── Phase: Placing the points ──
   await chapter("Placing the points");
   await say("Now click on the map where the start point should be.", { wait: false });
   ```

   so the narration is spoken while the phase's clicks happen. Leave the narration empty and a commented-out
   `say` marks the spot to fill in later.

   **Hide setup with F9.** Press **F9**, do what the tutorial is not about (create a task for the route, generate
   the flight orders, ...), press **F9** again; a red badge shows while hiding is on. The steps are written between
   `await startHidden();` and `await endHidden();`: they are performed when the video is recorded, but cut from it.

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
   positions on the map, which replay correctly only if the map opens at the same place and zoom each time.

   The page size, where a new route's map opens (where the browser says it is) and the site address come from
   `.env` (`TUTORIAL_WIDTH`/`TUTORIAL_HEIGHT`, `TUTORIAL_GEOLOCATION`, `TUTORIAL_BASE_URL`), which `npm run record`
   uses too, so both recordings always match. `-Viewport "1920,1080"`, `-Geolocation "60.8,11.1"` and `-BaseUrl`
   override them for one run (in quotes: PowerShell turns 60.8,11.1 into a list). Resizing the browser window while
   recording does not change the page size. Log in as a demo user with demo data, since the session file is what the
   recordings use.
2. **Write the script (WSL).** Copy `scripts/example.ts` to `scripts/<name>.ts` (kebab-case), paste the steps
   from `recorded/<name>.js` (everything below its header comment) into `run()`, and add or polish the narration
   between the steps:

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
   - `startHidden()` and `endHidden()` (F9 when recording the clicks) cut the steps between them from the video:
     they are performed, and the video crossfades from the last picture before to the page after. For setup the
     tutorial is not about, such as creating a task to show a route on the live map.
   - `showPdf(source, { width })` shows a PDF's pages with pdf.js (the headless recording browser has no PDF viewer):
     a file relative to `tutorials/` (such as a flight order saved in `pdfs/`), or a path on the site fetched logged
     in (`/display/navigationtask/<task>/downloadflightorders/?contestant_pks=<one contestant>`). `width` is the share
     of the window a page takes (0.7). Go back with `page.goto(...)`.
   - `chapter(title)` starts a phase: its name slides in at the bottom of the video and shows in the header, and
     it becomes a chapter in `out/<name>-chapters.txt`.
   - `pause(ms)` keeps a still moment that would otherwise be cut.
   - `map.view`, `map.click`, `map.drag` and `map.wheel` are the recorder's map steps (step 1).
   - `page`, `say`, `map` and the rest are available in `run()` as they are: pasted steps work without listing them.
   - `camera("wide")` shows the whole page (for example while drawing on the map) until `camera("auto")`.
   - `fill()` from the recorder is typed out visibly, key by key.

   Besides `run()`, the tutorial definition (`defineTutorial({ ... })`) takes:

   - `title`, `subtitle`, `series`, `next`: the title screen, the header during the video and the end screen (see
     "The look").
   - `startUrl`: the path on the site the recording starts from (`/` by default).
   - `cleanUp: { routes, navigationTasks, contest }`: what the tutorial creates, deleted by exact name through the
     site's API before every recording (and with `npm run cleanup -- <name>`), so it starts from the same state each
     time and the replay does not find two of anything. `contest` limits the search for tasks to that contest. Local
     site only, unless `TUTORIAL_ALLOW_CLEANUP=1`.
   - `captions: false`: no captions.
   - `music: false`, or `music: "brand/music/<file>.mp3"`: no background music, or another track.
   - `edit: { minGapMs, keepGapMs }`: how much stillness this tutorial's cutting removes (see "How it works").
3. **Record (WSL).** `npm run record -- <name>` first removes what an earlier recording created (`cleanUp`), then
   plays the script in a headless browser, hidden parts included, and records everything into
   `public/recordings/<name>/`. Nothing needs to be on screen. (`--headed` shows the browser through WSLg, if you
   want to watch.)
4. **Preview.** `npm run studio` starts Remotion Studio: open the address it prints (http://localhost:3000) in a
   Windows browser to scrub through every recorded tutorial.
5. **Render (WSL).** `npm run render -- <name>` writes to `out/`:
   - `<name>.mp4`: the finished video with voice and music
   - `<name>-picture.mp4`, `<name>-voice.wav` and `<name>-music.wav`: picture, voice and music separately, all
     starting at 0, for fine tuning in DaVinci Resolve (the voice only when there is narration, the music only when
     there is music)
   - `<name>.srt`: the narration as subtitles
   - `<name>-chapters.txt`: the chapters with their start times, ready for a YouTube description (only when the
     script has `chapter(...)` steps)

   Rendering never runs the steps again: it makes the video from the last recording, as often as you like.

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
  disappear. The defaults are `DEFAULT_EDIT` in `src/shared/timeline.ts`, applied when rendering; a tutorial's own
  `edit: { minGapMs, keepGapMs }` is saved with its recording. Hidden parts (`startHidden`/`endHidden`) are cut
  entirely, and the video crossfades over the cut; their steps do not move the camera or the cursor.
- **Camera** (`src/shared/camera.ts`): moves in on the element clicked, typed in or highlighted, stays while the
  work continues, and zooms out after a quiet spell or for large elements such as the map. Tune with `CAMERA`.
- **Video** (`src/remotion/`): title card, the page in a window on a background, the camera, a drawn cursor
  gliding on a slight curve with a ripple on each click, highlights, chapter labels, captions, the voice and the
  music. Change the look in `brand.ts`, `theme.ts`, `TutorialVideo.tsx` and `Screen.tsx`.
- **Clean-up** (`src/runner/cleanup.ts`): deletes a tutorial's `cleanUp` routes and navigation tasks through the
  site's API, logged in with `.auth/state.json`.

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

## Background music

Every video has the same background track, set in `brand.music` (`src/remotion/brand.ts`): at full level on the
title and end screens, low between narration lines, and lower still under the narration, about 17 dB below the
voice, fading down just before each line and back up after it. Tune the three levels in `brand.music.levels`.

The music file is not in git, since the repository is public and the licence covers using the track in the videos,
not passing the file on. It is kept in the team's private bucket `gs://airsports-tutorial-assets/music/`, and
`npm run fetch-assets` downloads it into `public/brand/music/` (with `gcloud` logged in to the project).

A new track is levelled once, so quiet and loud passages sit at the same distance below the voice:

```
npm run music -- "public/brand/music/<track>.mp3"
```

which writes `<track>.levelled.mp3` beside it (point `brand.music.file` at it) and prints the command that uploads
both files to the bucket for the rest of the team. The current
track is "New Morning" by TrackTribe from the YouTube Audio Library (no attribution required). A script can turn the
music off with `music: false`, or use another levelled file with `music: "brand/music/<file>.mp3"`.

`npm run render` also writes `<name>-music.wav`, the music as mixed, beside the picture and the voice.

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
- Map steps in the route editor replay exactly (`map.view` and `map.click` are coordinates). Mouse steps elsewhere
  (`page.mouse...`, such as dragging a slider) are positions on the page: they replay correctly only at the same
  page size (`TUTORIAL_WIDTH`/`TUTORIAL_HEIGHT`) as when the clicks were recorded.
- Remotion's licence is free for individuals and companies of up to three people; check it if that changes.
