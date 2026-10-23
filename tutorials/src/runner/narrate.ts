import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { findPauses } from "../shared/captions";
import type { Timeline } from "../shared/timeline";
import type { Timing, Voice } from "../shared/timing";
import { RECORDINGS_DIR, ROOT, SCRIPTS_DIR, settings, tutorialName } from "./config";
import { synthesise } from "./narration";

// npm run narrate -- <tutorial>
//
// Makes the voice for every say() of the recording, with the timing file's text where it gives one, into
// public/recordings/<tutorial>/voice.json and narration/. Recording and rendering run this themselves: on its own it
// is for hearing a changed line in Studio. Only new or changed lines take time (the voice is cached).

export const timingFile = (name: string) => path.join(SCRIPTS_DIR, `${name}.timing.ts`);

export function loadTimeline(name: string): Timeline {
  const file = path.join(RECORDINGS_DIR, name, "timeline.json");
  if (!existsSync(file)) throw new Error(`${name} has not been recorded: npm run record -- ${name}`);
  const timeline: Timeline = JSON.parse(readFileSync(file, "utf8"));
  if (!timeline.steps) throw new Error(`${name} was recorded before narration was added afterwards: record it again`);
  return timeline;
}

export async function loadTiming(name: string): Promise<Timing> {
  const file = timingFile(name);
  if (!existsSync(file)) return {};
  // A new address each time, so a changed file is read again
  return (await import(`${pathToFileURL(file).href}?${Date.now()}`)).default ?? {};
}

export function loadVoice(name: string): Voice {
  const file = path.join(RECORDINGS_DIR, name, "voice.json");
  return existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : { lines: {} };
}

export async function narrate(name: string): Promise<Voice> {
  const timeline = loadTimeline(name);
  const timing = await loadTiming(name);
  const directory = path.join(RECORDINGS_DIR, name, "narration");
  mkdirSync(directory, { recursive: true });
  const voice: Voice = { lines: {} };
  for (const say of timeline.says) {
    const text = timing.steps?.[say.step]?.text ?? say.text;
    // The script's spoken form only belongs to the script's text
    const spoken = text === say.text ? say.spoken : undefined;
    const speech = await synthesise(text, spoken);
    const key = createHash("sha1")
      .update(JSON.stringify([settings.ttsProvider, settings.ttsVoice, settings.ttsSpeed, text, spoken]))
      .digest("hex")
      .slice(0, 16);
    const file = `${key}.wav`;
    writeFileSync(path.join(directory, file), speech.wav);
    voice.lines[say.step] = {
      text,
      file: `recordings/${name}/narration/${file}`,
      durationMs: speech.durationMs,
      pauses: findPauses(speech.wav),
    };
  }
  const used = new Set(Object.values(voice.lines).map((line) => path.basename(line.file)));
  for (const file of readdirSync(directory)) if (!used.has(file)) rmSync(path.join(directory, file));
  writeFileSync(path.join(RECORDINGS_DIR, name, "voice.json"), JSON.stringify(voice, null, 1));
  console.log(`Narration of ${name}: ${timeline.says.length} lines`);
  return voice;
}

// A timing file to start from, when the tutorial has none. Returns its path when it wrote one.
export function writeTimingTemplate(name: string): string | null {
  const file = timingFile(name);
  if (existsSync(file)) return null;
  writeFileSync(
    file,
    `import { defineTiming } from "../src/shared/timing";

// Timing changes for ${name}, applied when the video is made: no new recording is needed to try them, and a new
// recording gets them too. Steps are named "<chapter> #<n>" (the n-th step since that chapter() line): list them with
// npm run steps -- ${name}, or see the current one at the top left of the picture in Remotion Studio.
export default defineTiming({
  // How still stretches are cut: longer than minGapMs is shortened to keepGapMs
  // edit: { minGapMs: 700, keepGapMs: 250 },
  steps: {
    // Twice as fast from this step until the step "until" (by default the next one):
    // "Placing the points #3": { speed: 2, until: "Placing the points #12" },
    // The picture held 1.5 s longer before this step (negative: that much less of the wait before it):
    // "Placing the points #12": { holdMs: 1500 },
    // A say() step: start the line 0.5 s earlier, let the next step wait for it, and say something else:
    // "Placing the points #1": { delayMs: -500, wait: true, text: "..." },
  },
});
`,
  );
  return path.relative(ROOT, file);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  const name = tutorialName(process.argv.slice(2).find((argument) => !argument.startsWith("--")));
  if (!name) {
    console.error("Usage: npm run narrate -- <tutorial name>");
    process.exit(1);
  }
  await narrate(name);
}
