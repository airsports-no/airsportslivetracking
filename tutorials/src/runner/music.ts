import { spawnSync } from "node:child_process";
import path from "node:path";
import { ROOT } from "./config";

// npm run music -- <track.mp3>
//
// Evens out a background track's level (quiet openings, loud choruses), so the music sits at the same distance below
// the voice all through the video, and writes public/brand/music/<name>.levelled.mp3. Point brand.music.file (or a
// script's music:) at that file.

const input = process.argv[2];
if (!input) {
  console.error("Usage: npm run music -- <track.mp3>");
  process.exit(1);
}
const output = path.join(ROOT, "public", "brand", "music", `${path.parse(input).name}.levelled.mp3`);
const result = spawnSync(
  "ffmpeg",
  [
    "-hide_banner", "-loglevel", "error", "-y", "-i", input,
    // Slow, gentle levelling (so the music still breathes), then the same loudness for every track
    "-af", "dynaudnorm=f=750:g=41:m=6:p=0.9,loudnorm=I=-18:TP=-2:LRA=6",
    "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "256k", output,
  ],
  { stdio: "inherit" },
);
if (result.status !== 0) process.exit(result.status ?? 1);
console.log(`Wrote ${output}: set brand.music.file to "brand/music/${path.basename(output)}"`);
