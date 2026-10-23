# Making a tutorial video: the workflow

This guide walks through making a tutorial video, from idea to finished video. It leaves out how the tools work
inside; for that, and for the one-time setup, see [README.md](README.md).

## Getting the music

The background music is not in git. Once, after the setup in the README, fetch it from the team's storage:

```
cd tutorials
npm run fetch-assets
```

(This needs `gcloud`, logged in with `gcloud auth login`. If a render stops saying the music is missing, run it.)

## The idea in short

You click through the task once, the way you would show it to someone. The clicks are saved as a script. You add
what should be said, and the toolset does the rest in two steps. First it plays the clicks back in a browser and
records the site. Then, as often as you like and without touching the site again, it generates the voice, cuts out
the dead time, zooms in on what matters and puts it all together with title screen, logo, music and end screen.

Because the video is made from the script, you can fix a sentence or a click and simply make the video again. The
timing (what goes faster or slower, how long a moment is held, when a sentence starts) is in a separate timing file,
which you can change and try without recording again.

## Before you start

- **Plan the phases.** Most tutorials fall into a few phases: finding the right place in the menus, placing the
  points on the map, switching to the next mode, saving. Note them down with a sentence or two of what to say in
  each. Short tutorials (2–4 minutes) with one clear goal work best.
- **Use demo data.** Record on the local site, logged in as a demo user, so no real contests or people appear and the
  video looks the same every time you make it again.
- **Check the settings in `tutorials/.env`.** They apply to recording the clicks and the video alike:
  - `TUTORIAL_GEOLOCATION`: where a new route's map opens, for example `60.8,11.1` near Hamar.
  - `TUTORIAL_WIDTH` and `TUTORIAL_HEIGHT`: the size of the page, 16:9, for example `1920` and `1080`. A bigger page
    gives more room; text looks a little smaller in the video, but the camera zooms in where you work. Resizing the
    browser window while recording does not change it.

## Step 1: Record the clicks (Windows)

In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 my-tutorial
```

A browser opens on the site. Click through the task calmly, as in the finished video.

- **Mark each phase with F8.** A box asks for the phase's name ("Placing the points") and, if you like, what should
  be said during it. Type it right away while you know what you are doing, or leave it empty and write it later.
  The box itself is not recorded.
- **Hide what the tutorial is not about with F9.** Press F9, do the setup (create a task for the route, generate
  the flight orders, ...), press F9 again. Those steps are performed when the video is made, but cut from it: the
  video crossfades straight from where you were to where you end up. A red badge shows while hiding is on.
- **Zoom and pan freely on the map.** Zooming, panning and the points you place are recorded exactly.
- **Typing is fine.** Text you type into fields is typed out again, letter by letter, in the video.
- **Pause with F10.** F10 stops recording until you press it again, for example while you look something up. F8
  works while paused too: the phase you mark then starts with what you do after you press F10 again.
- **Close the browser** when you are done. The steps are in `tutorials/recorded/my-tutorial.js`.

The first time, log in in that browser window; the login is remembered from then on.

## Step 2: Write the script

Make a copy of `tutorials/scripts/example.ts` called `tutorials/scripts/my-tutorial.ts`, fill in the title and
paste the recorded steps into it. Then go through it and polish the narration:

```ts
export default defineTutorial({
  title: "Creating a 2.A3 route",
  subtitle: "Contract navigation with time controls",
  series: "Route editor",
  next: "Creating a 2.A5 route",
  startUrl: "/",
  async run() {
    await say("In this tutorial you will create the route for a contract navigation task.");

    // ── Phase: Opening the route editor ──
    await chapter("Opening the route editor");
    await say("Open the route editor from the menu, and start a new route.", { wait: false });
    await page.getByRole("link", { name: "Route editor" }).click();
    ...
  },
});
```

What you can use in a script:

| Line | What it does |
|---|---|
| `await say("...")` | Speaks a sentence, and the next step waits until it is finished (in the video: the recording only marks it) |
| `await say("...", { wait: false })` | Speaks while the next steps happen (most narration should be like this) |
| `await chapter("...")` | Starts a new phase: its name appears in the video and becomes a chapter |
| `await highlight(page.getByText("Save Route"), { label: "Save when done" })` | Dims the page around something and points it out |
| `await pause(2000)` | Keeps a still moment of 2 seconds, for example to let something sink in |
| `await startHidden()` … `await endHidden()` | The steps in between are performed but cut from the video (F9 writes these) |
| `await showPdf("pdfs/flight-order-2a3.pdf")` | Shows a PDF's pages, for example a flight order (see below) |
| `await zoomPdf(4, { y: 0.31, height: 0.36 })` | Zooms in on part of a shown PDF page, to the full width (see below) |
| `await highlight(await pdfRegion(2, { x: 0.55, y: 0.54, width: 0.3, height: 0.14 }))` | Points out an area of a PDF page (see below) |
| `camera("wide")` … `camera("auto")` | Shows the whole page instead of zooming in, for example while working on the map |

**Showing a flight order or another PDF.** The browser that records the video cannot display PDFs, so a PDF opened
by clicking will not show. Use `showPdf` instead: it shows the pages on screen, and you can scroll and highlight as
usual.

The simplest is a saved file. Generate the flight order on the site once, download it, and save it in
`tutorials/pdfs/` (for example `pdfs/flight-order-2a3.pdf`). It does not change between recordings, so the video is
the same every time:

```ts
await showPdf("pdfs/flight-order-2a3.pdf");
await say("This is the navigation map the pilots get. Note the curved leg after the start.", { wait: false });
await pause(3000);
await page.mouse.wheel(0, 900);   // scroll to the next page
await pause(3000);
await page.goto("/");             // back to the site
```

Only some pages: `showPdf("pdfs/flight-order-2a3.pdf", { pages: [2] })`.

**Zooming in on the map.** Show the map page whole, then zoom in so the map fills the video's width, cropped above and
below to the route. The numbers are fractions of the page, read from `npm run pdf-grid` (see below):

```ts
await showPdf("pdfs/flight-order-2a5.pdf", { pages: [4], width: "page" });   // the whole page
await say("This is the navigation map the contestants fly with.", { wait: false });
await pause(1200);
await zoomPdf(4, { y: 0.31, height: 0.36, x: 0.048, width: 0.904 });
```

`y` and `height` are the part of the page from top to bottom that should be in the middle (the route), `x` and
`width` the part from left to right that fills the width (here the map without the page's white margins; leave
them out for the whole page width).

**Pointing out part of a PDF page.** `highlight` dims everything else, outlines what it is given, adds an optional
label and lets the camera zoom in on it, for as long as `durationMs` (2.5 seconds by default). On a web page you give
it the element, for example `page.getByRole("button", { name: "Save Route" })`. A PDF page is one picture, so give
it an area of the page instead, with `pdfRegion(page number, { x, y, width, height })`, all as fractions of the page
from its top left corner:

```ts
await highlight(await pdfRegion(2, { x: 0.55, y: 0.54, width: 0.3, height: 0.14 }), { label: "The curved leg" });
await highlight(pdfPage(3), { label: "The observation photos" });   // a whole page
```

To find the fractions, run `npm run pdf-grid -- pdfs/flight-order-2a3.pdf`: it writes an image of each page with a
labelled grid over it (`out/flight-order-2a3-page-2-grid.png`, ...), where you read off where the area starts and how
much it covers. Open them from Windows in `tutorials\out`.

`showPdf` can also fetch a PDF from the site, logged in: a contestant's flight order is at
`/display/navigationtask/<task id>/downloadflightorders/?contestant_pks=<contestant id>` (exactly one contestant:
with several the site sends a zip). That only works for a task and contestant that already exist with generated
flight orders, not for ones the tutorial creates, whose ids change with every recording. Use a narrower page with
`showPdf(source, { width: 0.5 })` to see a whole A4 page at once.

Tips for the narration:

- Say **why** as well as what: "Place the start point where the pilots enter the route" rather than "Click here".
- Keep sentences short. One idea per sentence.
- If a word is pronounced wrongly, add it to `tutorials/pronunciations.json` with how it should sound
  (`"2.A3": "two A three"`). The captions keep the written form.
- If a sentence is longer than what happens on screen, the picture is held still until it is finished, and the next
  sentence waits for it: nothing is cut off.

### Tutorials that create things

A tutorial that creates a route or a navigation task creates it again every time it is recorded, and recording the
clicks created it once already. Two routes with the same name confuse the replay (it finds two of everything), so name
what the tutorial creates in the script, and it is deleted before every recording:

```ts
export default defineTutorial({
  title: "Creating a 2.A3 route",
  cleanUp: { routes: ["Task 2.A3"], navigationTasks: ["Task 2.A3"], contest: "Tutorial demo" },
  ...
```

- Routes and navigation tasks with exactly those names are deleted. Use names that only the tutorial uses.
- `contest` is optional: with it, only that contest is searched for the tasks, which is quicker.
- What a recording creates is left in place afterwards, so you can look at it; the next recording removes it.
- Before recording the clicks again on Windows, clean up by hand: `npm run cleanup -- my-tutorial`.
- It only runs against the local site, never against the real one.

### Re-recording one chapter

To redo the clicks of one chapter without recording the whole tutorial again:

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 my-tutorial -Chapter "Placing the points"
```

The browser plays back the script's steps before that chapter, quickly and without narration, so the page is in the
state the chapter starts from. Then recording starts: click through the chapter again and close the browser. The new
steps are in `recorded/my-tutorial.chapter.js`. Put them into the script, in WSL:

```
npm run replace-chapter -- my-tutorial "Placing the points"
```

The chapter keeps its `chapter(...)` line and the narration right after it; its other steps are replaced by the new
ones. The old script is kept as `scripts/my-tutorial.ts.bak`. Run `npm run cleanup -- my-tutorial` first if the steps
before the chapter create things.

If the playback stops (for example because the page changed), set the page up by hand and press **F10** to start
recording. To set everything up by hand from the start, use `-Paused` instead of `-Chapter`: nothing is recorded until
you press F10, and F10 pauses again.

## Step 3: Make the recording (WSL)

```
cd tutorials
npm run record -- my-tutorial
```

The script plays in a browser in the background while the site is recorded: the screen, the clicks and each step
of the script. This is the only part that clicks through the site. It does not wait for the narration, so it is
quicker than the video. At the end it generates the narration (sentences that did not change are reused), and the
first time it creates the timing file `scripts/my-tutorial.timing.ts` for step 4.

If the script stops with an error, the message says which line, and where to find a picture of the page as it was
then: often a button was renamed, the page was not ready yet, or a panel was closed. Fix the script, then record again
**from the chapter that failed** instead of from the start:

```
npm run record -- my-tutorial --from "Save"
```

The steps before that chapter are played as when recording, so the site is where the chapter starts, but not
recorded: that takes as long as before, but the recording keeps its earlier part and only replaces the rest. That only works while the steps before the chapter are the
same as in the last recording (it says so if they are not: then record the whole tutorial).

While recording, the script warns about steps that pick something by its position, such as
`getByRole('button', { name: 'Create task' }).first()`: the first of several that match. If another one turns up
before it, the step picks the wrong one. Where you can, change it to a name or text only that element has.

Dialogs ("Route has validation errors. Save anyway?", "Leave this page?") are answered OK, both while recording the
clicks and while recording the video. To answer Cancel, put `nextDialog("dismiss");` before the step that opens one.

## Step 4: Watch it

```
npm run studio
```

and open the address it shows (http://localhost:3000) in your browser. Pick the tutorial in the list and watch it
from start to end. Listen for: narration that is too fast or too slow for what happens, phases that drag, places
where the zoom is distracting.

Studio shows the latest recording. After changing the script, record again (step 3) and reload the page.

**Changing the timing without recording again: the timing editor.** In WSL:

```
npm run timing -- my-tutorial
```

and open http://localhost:3100 in your browser. The video plays on the left, with every step of the recording on the
right, grouped by phase. Click a step: the video jumps to it, and below the video you can hold the picture longer or
shorter before it, play a stretch faster or slower (up to a later step), start a sentence earlier or later, choose
whether the next step waits for it, and change what is said. The video shows every change at once. **Save**
(Ctrl+S) writes them to `scripts/my-tutorial.timing.ts`, which every render uses; **Make voice** makes the voice for
changed sentences, which until then are shown as captions only. Saving rewrites the timing file, so comments written
in it by hand are not kept (the file as it was is kept as `my-tutorial.timing.ts.bak`).

**Recording again from the editor.** Each chapter's heading in the list has two buttons:

- **record from here** records the video again from that chapter (as `npm run record -- my-tutorial --from "..."`):
  for after you changed that chapter's steps in the script, or when a recording stopped there.
- **redo clicks** opens the click recorder on Windows for that chapter (as `codegen.ps1 ... -Chapter "..."`): the
  steps before it are played first, then you click through the chapter again and close the browser. **Use the new
  clicks** then puts them into the script (the old one is kept as `.bak`) and records the video from that chapter.

**Record all** at the top records the whole tutorial again. What a recording prints shows below the video, with
**Stop**; the editor loads the new recording when it is done.

**Adding chapters and sentences without recording again.** Recorded one long session? Choose a step and press **New
chapter here** or **New line here**: the chapter or sentence starts as the camera moves to that step, just as a
`chapter("...")` or `await say("...")` line before that step in the script would. Added chapters show in the list in
blue, with **rename** and **delete**; added sentences show as their own rows, with the same settings as the others
and **Delete line**. They are saved in the timing file:

```ts
chapters: [{ at: "Start #14", title: "Placing the points" }],
lines: [{ at: "Start #14", text: "Now click on the map where the start point should be." }],
```

The steps keep the names the recording gave them, even inside an added chapter. Once you are happy, press **Write
into the script**: the added chapters and sentences become `chapter("...")` and `await say("...")` lines in the
script, just before their steps (the old script is kept as `.bak`), the timing file's changes move to the names the
steps will have, and the editor offers to record again from the first chapter they are in. From then on those
chapters are real chapters, with **record from here** and **redo clicks**. (This needs a recording that knows the
script's lines: one made since this button exists. A step on a line that runs more than once, in a loop, is refused:
put that one in by hand.)

**Or by hand.** The top left of the picture in Studio (not in the video) shows the name of the step being shown, such
as `Backbone creation #3`: the third step since `chapter("Backbone creation")`. `npm run steps -- my-tutorial` lists
all of them with their times. Write the changes into `scripts/my-tutorial.timing.ts`, and Studio shows them as soon
as you save:

| In the timing file | What it does |
| --- | --- |
| `"Backbone creation #3": { speed: 2 }` | Plays that step twice as fast, up to the next step (`until: "Backbone creation #12"`: up to that step). `0.5` is half speed |
| `"Backbone creation #12": { holdMs: 1500 }` | Holds the picture 1.5 seconds longer before the step |
| `"Backbone creation #14": { holdMs: -800 }` | Takes 0.8 seconds off the wait before the step |
| `"Select unknown waypoint #1": { delayMs: -500 }` | A sentence (`say`) starts 0.5 seconds earlier (positive: later) |
| `"Select unknown waypoint #1": { wait: true }` | The next step waits until the sentence is finished (`false`: it carries on while it is spoken) |
| `"Flight order #1": { afterLine: true }` | This step waits until the sentence before it is finished, even when that sentence does not make steps wait. Showing a PDF (`showPdf`) does this by default, so the view does not change mid-sentence; `false` turns it off. In the editor: "Before this step" |
| `"Select unknown waypoint #1": { text: "..." }` | Says something else. Run `npm run narrate -- my-tutorial` to hear it in Studio |
| `edit: { minGapMs: 700, keepGapMs: 250 }` | How much stillness is cut (see the table under "What to change where") |

The timing file is in git and is used by every render, also after recording again: the steps keep their names as long
as the chapter's own lines stay the same. If you change a line in a chapter, check the names of the steps after it
in that chapter; Studio, `npm run steps` and the render warn about names the recording no longer has.

## Step 5: Make the video

```
npm run render -- my-tutorial
```

In `tutorials/out/` you get:

- `my-tutorial.mp4`: the finished video with voice and music, ready to publish
- `my-tutorial-chapters.txt`: the chapters with their times, to paste into the YouTube description (when the script
  has phases)
- `my-tutorial.srt`: subtitles (a long line is split into parts of at most two lines, timed to the voice)
- `my-tutorial-picture.mp4`, `my-tutorial-voice.wav` and `my-tutorial-music.wav`: picture, voice and music
  separately, for fine tuning

Rendering does not click through the site again: it makes the video from the last recording, the narration and the
timing file, so you can render as often as you like.

## Step 6 (optional): Fine tuning in DaVinci Resolve

Import the picture, voice and music files; they all start at the same moment and line up. Use Resolve for touches
the toolset cannot do, such as trimming a moment, adding a sound or adjusting the music by hand. Anything done in
Resolve is lost when the video is made again from the script, so fix what you can in the script and the timing file
first (trimming a moment is `holdMs` with a minus, see step 4) and keep Resolve for the very last step.

## Where to make which change

| You want to change | Where | Then |
|---|---|---|
| Clicks, typing, narration text, highlights, pauses | `scripts/<name>.ts` | `npm run record -- <name>`, then render |
| Faster or slower parts, longer or shorter waits, when a sentence starts, a sentence's text | `npm run timing -- <name>` (the timing editor), or `scripts/<name>.timing.ts` by hand | render (both show it live; a new text needs Make voice, or `npm run narrate -- <name>`) |
| Phases and their names | `chapter(...)` lines in `scripts/<name>.ts` | record again |
| What is cut from the video | `startHidden()` … `endHidden()` in `scripts/<name>.ts` (F9 when recording the clicks) | record again |
| What is deleted before each recording | `cleanUp` in `scripts/<name>.ts` | record again |
| Title, subtitle, series, next tutorial | top of `scripts/<name>.ts` | record again (they are saved with the recording) |
| Captions on or off | `captions: false` in the script | record again |
| How much stillness is cut, for one tutorial | `edit: { minGapMs, keepGapMs }` in the timing file | render |
| How much stillness is cut, for all tutorials | `DEFAULT_EDIT` in `src/shared/timeline.ts` | render |
| Music on or off, or another track for one video | `music: false` or `music: "..."` in the script | record again |
| Pronunciation of a word | `pronunciations.json` | render (only the affected sentences are regenerated; `npm run narrate -- <name>` to hear it in Studio) |
| Voice | `.env` (`TTS_PROVIDER`, `TTS_VOICE`) | render (`npm run narrate -- <name>` to hear it in Studio) |
| Where a new route's map starts | `TUTORIAL_GEOLOCATION` in `.env` | record the clicks and the video again |
| Page size (room on screen) | `TUTORIAL_WIDTH`, `TUTORIAL_HEIGHT` in `.env` | record the clicks and the video again |
| Pace: pause before and after each step | `STEP_LEAD_MS`, `STEP_PAUSE_AFTER_MS` in `src/shared/edit.ts` | record again |
| Camera: how far it zooms in, how fast, when it zooms out | `CAMERA` in `src/shared/camera.ts` | render |
| Music levels (title, between sentences, under the voice) | `brand.music.levels` in `src/remotion/brand.ts` | render |
| Background track for every video | `brand.music.file` in `src/remotion/brand.ts` (level a new track with `npm run music -- <file>`) | render |
| Logo, colours, end screen links | `src/remotion/brand.ts` | render |
| Font and background | `src/remotion/theme.ts` | render |
| Title and end screen layout | `src/remotion/TutorialVideo.tsx` | render |
| Cursor, highlight style, chapter label, captions style | `src/remotion/Screen.tsx` | render |
| Caption line length (at most two lines are shown at a time) | `CAPTION_LINE_CHARS` in `src/shared/captions.ts` | render |

Changes that only need a render show up live in Studio (step 4) while you edit, except changes to the voice (a
sentence's text in the timing file, pronunciations, the voice itself): run `npm run narrate -- <name>` for those.

## When something goes wrong

| What you see | What to do |
|---|---|
| Studio shows an old version | Record again (`npm run record -- <name>`) and reload Studio; restart it if a new tutorial does not appear |
| Studio or the render says a tutorial "was recorded before narration was added afterwards" | Record it again: recordings from before the timing file cannot be used |
| A sentence shows as a caption but is not heard in Studio | Its text was changed in the timing file: `npm run narrate -- <name>` |
| The timing file "names a step the recording does not have" | A line of that chapter was added or removed: find the new name with `npm run steps -- <name>` |
| The map starts in the wrong place | Set `TUTORIAL_GEOLOCATION` in `tutorials/.env` (it is used for both recordings) |
| A click lands in the wrong place on the map | Record the clicks again with the latest recorder: map clicks should appear as `map.click(...)` lines |
| A step fails because something is not found | Look at the picture of the page the message names. The page changed (a button renamed or moved): re-record that chapter's clicks (`-Chapter "..."`, see "Re-recording one chapter"), then `npm run record -- <name> --from "<chapter>"` |
| A recording stopped half way | Fix the step, then `npm run record -- <name> --from "<chapter it stopped in>"`: only that chapter and the rest are recorded again |
| A step fails because it finds two of something ("strict mode violation") | An earlier recording left it behind: add it to `cleanUp` in the script, or run `npm run cleanup -- <name>` |
| The narration sounds wrong | Rephrase the sentence (in the script, or with `text` in the timing file to skip recording again), or add the word to `pronunciations.json` |
| A render stops saying the music is missing | Fetch it: `npm run fetch-assets` |
| A sentence is missing from the video | It was spoken inside a hidden part, which is cut with it (the recording, Studio and `npm run steps` warn about this): move the `say` after `endHidden()` |
| A PDF does not show | PDFs opened by clicking cannot be shown: save the PDF in `tutorials/pdfs/` and use `showPdf("pdfs/<file>.pdf")` |
| A step fails with "... is not defined" | Check the spelling: `page`, `say`, `map`, `chapter`, `highlight`, `pause`, `camera`, `startHidden`, `endHidden`, `showPdf`, `zoomPdf`, `pdfPage` and `pdfRegion` are available as they are |
