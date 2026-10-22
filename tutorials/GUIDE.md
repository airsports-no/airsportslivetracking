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
what should be said, and the toolset does the rest: it plays the clicks back in a browser, records the screen,
generates the voice, cuts out the dead time, zooms in on what matters and puts it all together with title screen,
logo, music and end screen.

Because the video is made from the script, you can fix a sentence or a click and simply make the video again.

## Before you start

- **Plan the phases.** Most tutorials fall into a few phases: finding the right place in the menus, placing the
  points on the map, switching to the next mode, saving. Note them down with a sentence or two of what to say in
  each. Short tutorials (2–4 minutes) with one clear goal work best.
- **Use demo data.** Record on the local site, logged in as a demo user, so no real contests or people appear and the
  video looks the same every time you make it again.
- **Pick the start location.** A new route's map opens where the browser says you are. Choose a place that fits the
  tutorial, for example `60.8,11.1` near Hamar, and use the same one every time (see step 1, and
  `TUTORIAL_GEOLOCATION` in `tutorials/.env`).

## Step 1: Record the clicks (Windows)

In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 my-tutorial -Geolocation "60.8,11.1"
```

A browser opens on the site. Click through the task calmly, as in the finished video.

- **Mark each phase with F8.** A box asks for the phase's name ("Placing the points") and, if you like, what should
  be said during it. Type it right away while you know what you are doing, or leave it empty and write it later.
  The box itself is not recorded.
- **Zoom and pan freely on the map.** Zooming, panning and the points you place are recorded exactly.
- **Typing is fine.** Text you type into fields is typed out again, letter by letter, in the video.
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
  async run({ page, say, highlight, camera, chapter, map }) {
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
| `await say("...")` | Speaks a sentence and waits until it is finished before the next step |
| `await say("...", { wait: false })` | Speaks while the next steps happen (most narration should be like this) |
| `await chapter("...")` | Starts a new phase: its name appears in the video and becomes a chapter |
| `await highlight(page.getByText("Save Route"), { label: "Save when done" })` | Dims the page around something and points it out |
| `await pause(2000)` | Keeps a still moment of 2 seconds, for example to let something sink in |
| `camera("wide")` … `camera("auto")` | Shows the whole page instead of zooming in, for example while working on the map |

Tips for the narration:

- Say **why** as well as what: "Place the start point where the pilots enter the route" rather than "Click here".
- Keep sentences short. One idea per sentence.
- If a word is pronounced wrongly, add it to `tutorials/pronunciations.json` with how it should sound
  (`"2.A3": "two A three"`). The captions keep the written form.
- If a sentence is longer than what happens on screen, the next sentence simply waits for it: nothing is cut off.

## Step 3: Make the recording (WSL)

```
cd tutorials
npm run record -- my-tutorial
```

The script plays in a browser in the background while everything is recorded. It takes as long as the tutorial
itself, plus a little time to generate new narration (sentences that did not change are reused).

If the script stops with an error, the message says which line; often a button was renamed, or the page was not
ready yet.

## Step 4: Watch it

```
npm run studio
```

and open the address it shows (http://localhost:3000) in your browser. Pick the tutorial in the list and watch it
from start to end. Listen for: narration that is too fast or too slow for what happens, phases that drag, places
where the zoom is distracting.

Studio shows the latest recording. After changing the script, record again (step 3) and reload the page.

## Step 5: Make the video

```
npm run render -- my-tutorial
```

In `tutorials/out/` you get:

- `my-tutorial.mp4`: the finished video, ready to publish
- `my-tutorial-chapters.txt`: the chapters with their times, to paste into the YouTube description
- `my-tutorial.srt`: subtitles
- `my-tutorial-picture.mp4`, `my-tutorial-voice.wav` and `my-tutorial-music.wav`: picture, voice and music
  separately, for fine tuning

## Step 6 (optional): Fine tuning in DaVinci Resolve

Import the picture, voice and music files; they all start at the same moment and line up. Use Resolve for touches
the toolset cannot do, such as trimming a moment, adding a sound or adjusting the music by hand. Anything done in
Resolve is lost when the video is made again from the script, so fix what you can in the script first and keep
Resolve for the very last step.

## Where to make which change

| You want to change | Where | Then |
|---|---|---|
| Clicks, typing, narration text, highlights, pauses | `scripts/<name>.ts` | `npm run record -- <name>`, then render |
| Phases and their names | `chapter(...)` lines in `scripts/<name>.ts` | record again |
| Title, subtitle, series, next tutorial | top of `scripts/<name>.ts` | record again (they are saved with the recording) |
| Captions on or off | `captions: false` in the script | record again |
| How much stillness is cut, for one tutorial | `edit: { minGapMs, keepGapMs }` in the script | record again |
| How much stillness is cut, for all tutorials | `DEFAULT_EDIT` in `src/shared/timeline.ts` | render |
| Music on or off, or another track for one video | `music: false` or `music: "..."` in the script | record again |
| Pronunciation of a word | `pronunciations.json` | record again (only the affected sentences are regenerated) |
| Voice | `.env` (`TTS_PROVIDER`, `TTS_VOICE`) | record again |
| Where a new route's map starts | `-Geolocation` when recording clicks and `TUTORIAL_GEOLOCATION` in `.env` (same value) | record the clicks and the video again |
| Pace: pause before and after each step | `STEP_LEAD_MS`, `STEP_PAUSE_AFTER_MS` in `src/shared/edit.ts` | record again |
| Camera: how far it zooms in, how fast, when it zooms out | `CAMERA` in `src/shared/camera.ts` | render |
| Music levels (title, between sentences, under the voice) | `brand.music.levels` in `src/remotion/brand.ts` | render |
| Background track for every video | `brand.music.file` in `src/remotion/brand.ts` (level a new track with `npm run music -- <file>`) | render |
| Logo, colours, end screen links | `src/remotion/brand.ts` | render |
| Font and background | `src/remotion/theme.ts` | render |
| Title and end screen layout | `src/remotion/TutorialVideo.tsx` | render |
| Cursor, highlight style, chapter label, captions style | `src/remotion/Screen.tsx` | render |

Changes that only need a render show up live in Studio (step 4) while you edit.

## When something goes wrong

| What you see | What to do |
|---|---|
| Studio shows an old version | Record again (`npm run record -- <name>`) and reload Studio; restart it if a new tutorial does not appear |
| `map is not defined` (or `chapter`, `highlight`, ...) | Add the name to the `run({ page, say, ... })` line at the top of the script |
| The map starts in the wrong place | Use the same location for recording clicks (`-Geolocation "60.8,11.1"`, in quotes) and in `.env` |
| A click lands in the wrong place on the map | Record the clicks again with the latest recorder: map clicks should appear as `map.click(...)` lines |
| A step fails because something is not found | The page changed (a button renamed or moved): record that part of the clicks again |
| The narration sounds wrong | Rephrase the sentence, or add the word to `pronunciations.json` |
