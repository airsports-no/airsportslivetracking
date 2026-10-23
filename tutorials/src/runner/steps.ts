import { computeEdit } from "../shared/edit";
import { INTRO_MS, TRANSITION_MS } from "../shared/layout";
import { isHidden } from "../shared/timeline";
import { addedLineKeys } from "../shared/timing";
import { tutorialName } from "./config";
import { loadTiming, loadTimeline, loadVoice, timingFile } from "./narrate";

// npm run steps -- <tutorial>
//
// The steps of the recording by the names the timing file uses (scripts/<tutorial>.timing.ts), with where each is in
// the video as it is now and what the timing file changes about it

const name = tutorialName(process.argv.slice(2).find((argument) => !argument.startsWith("--")));
if (!name) {
  console.error("Usage: npm run steps -- <tutorial name>");
  process.exit(1);
}
const timeline = loadTimeline(name);
const timing = await loadTiming(name);
const edit = computeEdit(timeline, loadVoice(name), timing);
const offset = INTRO_MS - TRANSITION_MS;
const clock = (ms: number) => {
  const tenths = Math.round(ms / 100);
  return `${Math.floor(tenths / 600)}:${String(Math.floor(tenths / 10) % 60).padStart(2, "0")}.${tenths % 10}`;
};
const width = Math.max(...timeline.steps.map((step) => step.id.length));
const lineKeys = addedLineKeys(timing.lines ?? []);
for (const step of timeline.steps) {
  // What the timing file adds before the step
  for (const chapter of (timing.chapters ?? []).filter((item) => item.at === step.id)) {
    console.log(`${"".padStart(7)}  ── chapter: ${chapter.title} (added)`);
  }
  (timing.lines ?? []).forEach((line, index) => {
    if (line.at !== step.id) return;
    const placed = edit.narration.find((item) => item.step === lineKeys[index]);
    const where = placed ? clock(offset + placed.start) : "-";
    console.log(`${where.padStart(7)}  ${lineKeys[index].padEnd(width)}  say(${JSON.stringify(line.text)}) (added)`);
  });
  const change = timing.steps?.[step.id];
  // A narration line: where it starts
  const line = edit.narration.find((item) => item.step === step.id);
  const where = isHidden(timeline, step.t) ? "hidden" : clock(offset + (line ? line.start : edit.toOut(step.t)));
  console.log(`${where.padStart(7)}  ${step.id.padEnd(width)}  ${step.label}${change ? `   <- ${JSON.stringify(change)}` : ""}`);
}
console.log(`\nVideo ${clock(offset + edit.durationMs)} plus the end screen. Timing file: ${timingFile(name)}`);
for (const warning of edit.warnings) console.warn(warning);
