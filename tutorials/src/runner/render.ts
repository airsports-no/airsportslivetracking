import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { computeEdit } from "../shared/edit";
import type { Timeline } from "../shared/timeline";
import { compositionId, INTRO_MS, TRANSITION_MS } from "../shared/layout";
import { brand } from "../remotion/brand";
import { OUT_DIR, RECORDINGS_DIR, ROOT, tutorialName } from "./config";

// npm run render -- <tutorial>
//
// out/<tutorial>.mp4          the finished video with voice and music
// out/<tutorial>-picture.mp4  the same picture without sound   } for fine tuning in DaVinci Resolve:
// out/<tutorial>-voice.wav    the voice alone                  } all start at 0 and line up
// out/<tutorial>-music.wav    the music alone, already mixed   }
// out/<tutorial>.srt          the narration as subtitles
// out/<tutorial>-chapters.txt the chapters, for a YouTube description (when the script has chapter() steps)

const name = tutorialName(process.argv.slice(2).find((argument) => !argument.startsWith("--")));
if (!name) {
  console.error("Usage: npm run render -- <tutorial name>");
  process.exit(1);
}
mkdirSync(OUT_DIR, { recursive: true });
const video = path.join(OUT_DIR, `${name}.mp4`);

// The music is not in git: without it Remotion fails with a bare "404"
const timeline: Timeline = JSON.parse(readFileSync(path.join(RECORDINGS_DIR, name, "timeline.json"), "utf8"));
if (timeline.music !== false) {
  const musicFile = path.join(ROOT, "public", timeline.music ?? brand.music.file);
  if (!existsSync(musicFile)) {
    console.error(`The background music ${musicFile} is missing: fetch it with npm run fetch-assets`);
    process.exit(1);
  }
}

const run = (command: string, args: string[]) => {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
};

run("npx", [
  "remotion",
  "render",
  compositionId(name),
  video,
  "--image-format=jpeg",
  "--jpeg-quality=95",
  "--crf=16",
]);
run("ffmpeg", ["-y", "-loglevel", "error", "-i", video, "-an", "-c:v", "copy", path.join(OUT_DIR, `${name}-picture.mp4`)]);
// The voice and the music each on their own (rendered again with only that sound: audio only, quick)
const stem = (audio: "voice" | "music") =>
  run("npx", ["remotion", "render", compositionId(name), path.join(OUT_DIR, `${name}-${audio}.wav`), "--codec=wav",
    `--props=${JSON.stringify({ audio })}`, "--log=error"]);
if (timeline.narration.length > 0) stem("voice");
if (timeline.music !== false) stem("music");

// Subtitles, on the video's own timeline (after the cuts and the title card)
const edit = computeEdit(timeline);
const offset = INTRO_MS - TRANSITION_MS;
const stamp = (ms: number) => {
  const date = new Date(Math.max(0, Math.round(ms)));
  return `${date.toISOString().slice(11, 19)},${String(date.getUTCMilliseconds()).padStart(3, "0")}`;
};
const srt = timeline.narration
  .map((item, index) => {
    const start = offset + edit.toOut(item.t);
    return `${index + 1}\n${stamp(start)} --> ${stamp(start + item.durationMs)}\n${item.text}\n`;
  })
  .join("\n");
writeFileSync(path.join(OUT_DIR, `${name}.srt`), srt);

// Chapters in the form YouTube reads from a video's description: the first must start at 0:00
const minutesSeconds = (ms: number) => {
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
};
const chapters = (timeline.chapters ?? []).map((chapter) => `${minutesSeconds(offset + edit.toOut(chapter.t))} ${chapter.title}`);
if (chapters.length > 0) {
  writeFileSync(path.join(OUT_DIR, `${name}-chapters.txt`), ["0:00 Introduction", ...chapters].join("\n") + "\n");
}
console.log(`Rendered ${video}, with the picture, voice and music separately and the subtitles beside it`);
