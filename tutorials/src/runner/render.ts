import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { computeEdit } from "../shared/edit";
import type { Timeline } from "../shared/timeline";
import { compositionId, INTRO_MS, TRANSITION_MS } from "../shared/layout";
import { OUT_DIR, RECORDINGS_DIR, tutorialName } from "./config";

// npm run render -- <tutorial>
//
// out/<tutorial>.mp4          the finished video with the voice
// out/<tutorial>-picture.mp4  the same picture without sound   } for fine tuning in DaVinci Resolve:
// out/<tutorial>-voice.wav    the voice track alone            } both start at 0 and line up
// out/<tutorial>.srt          the narration as subtitles

const name = tutorialName(process.argv.slice(2).find((argument) => !argument.startsWith("--")));
if (!name) {
  console.error("Usage: npm run render -- <tutorial name>");
  process.exit(1);
}
mkdirSync(OUT_DIR, { recursive: true });
const video = path.join(OUT_DIR, `${name}.mp4`);

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
const timeline: Timeline = JSON.parse(readFileSync(path.join(RECORDINGS_DIR, name, "timeline.json"), "utf8"));
// A tutorial without narration has no sound to take out
if (timeline.narration.length > 0) {
  run("ffmpeg", ["-y", "-loglevel", "error", "-i", video, "-vn", "-c:a", "pcm_s16le", path.join(OUT_DIR, `${name}-voice.wav`)]);
}

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
console.log(`Rendered ${video}, with -picture.mp4, -voice.wav and .srt beside it`);
