import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { captionCues } from "../shared/captions";
import { computeEdit } from "../shared/edit";
import { compositionId, INTRO_MS, OUTRO_MS, TRANSITION_MS } from "../shared/layout";
import { brand } from "../remotion/brand";
import { OUT_DIR, ROOT, tutorialName } from "./config";
import { loadTiming, loadTimeline, narrate } from "./narrate";
import { buildVoiceStemWav, writeResolveFcpxml } from "./resolve";

// npm run render -- <tutorial> [--draft] [--clean-picture] [--no-captions]
//
// Makes the video from the recording (npm run record), with the narration (made here when it is new or changed) and
// the timing file's changes (scripts/<tutorial>.timing.ts): changing either needs no new recording.
//
// out/<tutorial>.mp4              the finished video with voice, music, captions, and overlays
// out/<tutorial>-picture.mp4      the picture without sound (--clean-picture: also without burned-in captions)
// out/<tutorial>-voice.wav        the voice alone, lined up from 0:00
// out/<tutorial>-music.wav        the music alone, already ducked under the voice
// out/<tutorial>.srt              the narration as subtitles
// out/<tutorial>-resolve.fcpxml   ready-to-import DaVinci Resolve timeline (picture + individual voice clips + music + markers)
// out/<tutorial>-chapters.txt     the chapters, for a YouTube description

const args = process.argv.slice(2);
const draft = args.includes("--draft");
const cleanPicture = args.includes("--clean-picture");
const noCaptions = args.includes("--no-captions");
const name = tutorialName(args.find((argument) => !argument.startsWith("--")));
if (!name) {
  console.error("Usage: npm run render -- <tutorial name> [--draft] [--clean-picture] [--no-captions]");
  process.exit(1);
}
mkdirSync(OUT_DIR, { recursive: true });
const video = path.join(OUT_DIR, `${name}.mp4`);
const picture = path.join(OUT_DIR, `${name}-picture.mp4`);
const voiceStem = path.join(OUT_DIR, `${name}-voice.wav`);
const musicStem = path.join(OUT_DIR, `${name}-music.wav`);
const resolveXml = path.join(OUT_DIR, `${name}-resolve.fcpxml`);

const timeline = loadTimeline(name);
const voice = await narrate(name);
const edit = computeEdit(timeline, voice, await loadTiming(name));
for (const warning of edit.warnings) console.warn(`  ${warning}`);

// The music is not in git: without it Remotion fails with a bare "404"
if (timeline.music !== false) {
  const musicFile = path.join(ROOT, "public", timeline.music ?? brand.music.file);
  if (!existsSync(musicFile)) {
    console.error(`The background music ${musicFile} is missing: fetch it with npm run fetch-assets`);
    process.exit(1);
  }
}

const run = (command: string, commandArgs: string[]) => {
  const result = spawnSync(command, commandArgs, { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
};

const renderArgs = [
  "remotion",
  "render",
  compositionId(name),
  video,
  "--image-format=jpeg",
  draft ? "--jpeg-quality=80" : "--jpeg-quality=95",
  draft ? "--crf=24" : "--crf=16",
  ...(draft ? ["--scale=0.5"] : []),
  ...(noCaptions ? [`--props=${JSON.stringify({ captions: false })}`] : []),
];
run("npx", renderArgs);

const offset = INTRO_MS - TRANSITION_MS;
const totalDurationMs = INTRO_MS + edit.durationMs + OUTRO_MS - 2 * TRANSITION_MS;

if (!draft) {
  if (cleanPicture && !noCaptions) {
    // Render a caption-free picture stream for DaVinci Resolve so subtitles can be styled/cut from the .srt in Resolve
    run("npx", [
      "remotion",
      "render",
      compositionId(name),
      picture,
      "--image-format=jpeg",
      "--jpeg-quality=95",
      "--crf=16",
      "--muted",
      `--props=${JSON.stringify({ captions: false })}`,
    ]);
  } else {
    run("ffmpeg", ["-y", "-loglevel", "error", "-i", video, "-an", "-c:v", "copy", picture]);
  }

  // Synthesise the voice stem directly in memory from the cached WAV clips (instant, no Remotion pass needed)
  const spokenLines = edit.narration.filter((line): line is typeof line & { file: string } => Boolean(line.file));
  if (spokenLines.length > 0) {
    const clips = spokenLines.map((line) => ({
      startMs: offset + line.start,
      wavPath: path.join(ROOT, "public", line.file),
    }));
    writeFileSync(voiceStem, buildVoiceStemWav(clips, totalDurationMs));
  }

  if (timeline.music !== false) {
    run("npx", [
      "remotion",
      "render",
      compositionId(name),
      musicStem,
      "--codec=wav",
      `--props=${JSON.stringify({ audio: "music" })}`,
      "--log=error",
    ]);
  }

  // DaVinci Resolve timeline (.fcpxml): picture + each individual voice clip on its own + music + chapter/overlay markers
  writeResolveFcpxml(resolveXml, {
    title: timeline.title,
    durationMs: totalDurationMs,
    picturePath: picture,
    musicPath: timeline.music !== false && existsSync(musicStem) ? musicStem : undefined,
    voiceClips: spokenLines.map((line, index) => ({
      name: `${String(index + 1).padStart(2, "0")} - ${line.text.slice(0, 48)}`,
      wavPath: path.join(ROOT, "public", line.file),
      startMs: offset + line.start,
      durationMs: line.durationMs,
    })),
    markers: [
      ...edit.chapters.map((chapter) => ({
        startMs: offset + chapter.t,
        title: `Chapter: ${chapter.title}`,
      })),
      ...edit.overlays.map((overlay) => ({
        startMs: offset + overlay.start,
        title: `Overlay: ${overlay.title ?? overlay.text.slice(0, 40)}`,
        note: overlay.text,
      })),
    ],
  });
}

const stamp = (ms: number) => {
  const date = new Date(Math.max(0, Math.round(ms)));
  return `${date.toISOString().slice(11, 19)},${String(date.getUTCMilliseconds()).padStart(3, "0")}`;
};
// Subtitles, on the video's own timeline (after the cuts and the title card), at most two lines at a time like the
// captions in the picture
const srt = edit.narration
  .flatMap((line) =>
    captionCues(line).map((cue) => {
      const start = offset + line.start;
      return `${stamp(start + cue.start)} --> ${stamp(start + cue.end)}\n${cue.lines.join("\n")}\n`;
    }),
  )
  .map((cue, index) => `${index + 1}\n${cue}`)
  .join("\n");
writeFileSync(path.join(OUT_DIR, `${name}.srt`), srt);

// Chapters in the form YouTube reads from a video's description: the first must start at 0:00
const minutesSeconds = (ms: number) => {
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
};
const chapters = edit.chapters.map((chapter) => `${minutesSeconds(offset + chapter.t)} ${chapter.title}`);
if (chapters.length > 0) {
  writeFileSync(path.join(OUT_DIR, `${name}-chapters.txt`), ["0:00 Introduction", ...chapters].join("\n") + "\n");
}
if (draft) {
  console.log(`Rendered draft preview ${video} and ${name}.srt`);
} else {
  console.log(
    `Rendered ${video}, with ${name}-picture.mp4, ${name}-voice.wav, ${name}-music.wav, ${name}.srt, and DaVinci Resolve timeline ${name}-resolve.fcpxml`,
  );
}
