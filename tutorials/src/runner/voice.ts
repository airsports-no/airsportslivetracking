import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { captionCues, findPauses } from "../shared/captions";
import { OUT_DIR, settings } from "./config";
import { synthesise } from "./narration";
import { buildVoiceStemWav, type TimelineMarker, type VoiceClipPlacement, writeResolveFcpxml } from "./resolve";

// npm run voice -- <script.txt> [output folder]
//
// Narration for a video made elsewhere (a phone recording or real-world camera footage edited in DaVinci Resolve):
// - One WAV file per spoken line: 01.wav, 02.wav, ... in the voice from .env (TTS_PROVIDER, TTS_VOICE, TTS_SPEED),
//   with the pronunciations of pronunciations.json.
// - Lines starting with "# Chapter: <title>" or "## <title>" mark a chapter on the DaVinci Resolve timeline.
// - Lines like "[pause 1.5s]" add extra silence before the next line (default gap between lines: 0.6s).
// - Writes:
//   * 01.wav, 02.wav, ...   individual clips
//   * index.txt             clip filenames, durations, start times, and text
//   * combined.wav          all voice clips combined with natural spacing
//   * subtitles.srt         matching 2-line captions for DaVinci Resolve / YouTube
//   * resolve.fcpxml        DaVinci Resolve timeline with every clip and chapter marker placed on the timeline

const [scriptFile, outputArgument] = process.argv.slice(2);
if (!scriptFile) {
  console.error("Usage: npm run voice -- <script.txt> [output folder]");
  process.exit(1);
}

const rawLines = readFileSync(scriptFile, "utf8")
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter(Boolean);

const baseName = path.basename(scriptFile, path.extname(scriptFile));
const outputDirectory = outputArgument ?? path.join(OUT_DIR, `${baseName}-voice`);
mkdirSync(outputDirectory, { recursive: true });

const DEFAULT_GAP_MS = 600;
let cursorMs = 0;
let clipIndex = 0;
const indexLines: string[] = [];
const placements: VoiceClipPlacement[] = [];
const markers: TimelineMarker[] = [];
const srtEntries: string[] = [];

const stamp = (ms: number) => {
  const date = new Date(Math.max(0, Math.round(ms)));
  return `${date.toISOString().slice(11, 19)},${String(date.getUTCMilliseconds()).padStart(3, "0")}`;
};

const spokenCount = rawLines.filter((line) => !line.startsWith("#") && !/^\[pause\s+[\d.]+s?\]$/i.test(line)).length;
console.log(`${spokenCount} lines, ${settings.ttsProvider} voice ${settings.ttsVoice || "(default)"}`);

for (const line of rawLines) {
  const chapterMatch = line.match(/^(?:#\s*chapter:\s*|##\s*)(.+)$/i);
  if (chapterMatch) {
    markers.push({ startMs: cursorMs, title: `Chapter: ${chapterMatch[1].trim()}` });
    continue;
  }
  if (line.startsWith("#")) continue;

  const pauseMatch = line.match(/^\[pause\s+([\d.]+)\s*(ms|s)?\]$/i);
  if (pauseMatch) {
    const amount = Number(pauseMatch[1]);
    const unit = (pauseMatch[2] || "s").toLowerCase();
    cursorMs += unit === "ms" ? amount : amount * 1000;
    continue;
  }

  clipIndex++;
  const speech = await synthesise(line);
  const name = `${String(clipIndex).padStart(2, "0")}.wav`;
  const wavPath = path.join(outputDirectory, name);
  writeFileSync(wavPath, speech.wav);

  const startMs = cursorMs;
  const durationMs = speech.durationMs;
  const seconds = (durationMs / 1000).toFixed(1);
  const atSeconds = (startMs / 1000).toFixed(1);
  indexLines.push(`${name}\t@${atSeconds}s\t${seconds}s\t${line}`);
  console.log(`${name}  @${atSeconds}s  (${seconds}s)  ${line}`);

  placements.push({
    name: `${String(clipIndex).padStart(2, "0")} - ${line.slice(0, 48)}`,
    wavPath,
    startMs,
    durationMs,
  });

  const cues = captionCues({
    text: line,
    durationMs,
    pauses: findPauses(speech.wav),
  });
  for (const cue of cues) {
    srtEntries.push(`${stamp(startMs + cue.start)} --> ${stamp(startMs + cue.end)}\n${cue.lines.join("\n")}\n`);
  }

  cursorMs += durationMs + DEFAULT_GAP_MS;
}

const totalDurationMs = Math.max(1000, cursorMs);
writeFileSync(path.join(outputDirectory, "index.txt"), indexLines.join("\n") + "\n");

if (placements.length > 0) {
  writeFileSync(
    path.join(outputDirectory, "combined.wav"),
    buildVoiceStemWav(
      placements.map((clip) => ({ startMs: clip.startMs, wavPath: clip.wavPath })),
      totalDurationMs,
    ),
  );
  const srt = srtEntries.map((entry, idx) => `${idx + 1}\n${entry}`).join("\n");
  writeFileSync(path.join(outputDirectory, "subtitles.srt"), srt);
  writeResolveFcpxml(path.join(outputDirectory, "resolve.fcpxml"), {
    title: `${baseName} voice`,
    durationMs: totalDurationMs,
    voiceClips: placements,
    markers,
  });
}

console.log(
  `Written to ${outputDirectory} (01..${String(clipIndex).padStart(2, "0")}.wav, combined.wav, subtitles.srt, resolve.fcpxml, index.txt)`,
);
