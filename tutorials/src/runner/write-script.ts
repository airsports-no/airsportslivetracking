import { copyFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Timeline } from "../shared/timeline";
import { addedLineKeys, type StepTiming, type Timing } from "../shared/timing";
import { SCRIPTS_DIR } from "./config";
import { timingFile } from "./narrate";

// The timing file's added chapters and narration lines written into the tutorial script, as chapter("...") and
// say("...") lines before the steps they are at, so the next recording has them (and the chapters can be recorded
// from). Each step's line in the script is in the recording (Step.line). The timing file's changes are moved to the
// names the steps will have then: a new chapter renames the steps after it, a new line is a step of its own.

// The timing file as code, as the first recording starts it: the header, then the changes
export const timingFileSource = (name: string, timing: Timing) => `import { defineTiming } from "../src/shared/timing";

// Timing changes for ${name}, applied when the video is made: no new recording is needed to try them, and a new
// recording gets them too. Steps are named "<chapter> #<n>" (the n-th step since that chapter() line). Written by the
// timing editor (npm run timing -- ${name}), which can be used to change them, or change them here.
export default defineTiming(${
  // Plain names without quotes, as written by hand; step names keep theirs
  JSON.stringify(timing, null, 2).replace(/^(\s*)"([A-Za-z_]\w*)":/gm, "$1$2:")
});
`;

export type Written = {
  chapters: number;
  lines: number;
  // The recorded chapter the first of them is in: recording from it is enough (null: from the start)
  recordFrom: string | null;
};

const chapterOf = (id: string) => id.replace(/ #\d+$/, "");
const baseTitle = (chapter: string) => chapter.replace(/ \(\d+\)$/, "");

export function writeIntoScript(name: string, timeline: Timeline, timing: Timing): Written {
  const chapters = timing.chapters ?? [];
  const lines = timing.lines ?? [];
  if (chapters.length === 0 && lines.length === 0) throw new Error("The timing file adds no chapters or lines");
  if (timeline.steps.some((step) => step.line === undefined)) {
    throw new Error("The recording does not know the script's lines yet: record it again first, then write");
  }
  const byId = new Map(timeline.steps.map((step) => [step.id, step]));
  const usesOfLine = new Map<number, number>();
  for (const step of timeline.steps) usesOfLine.set(step.line!, (usesOfLine.get(step.line!) ?? 0) + 1);
  for (const at of [...chapters.map((item) => item.at), ...lines.map((item) => item.at)]) {
    const step = byId.get(at);
    if (!step) throw new Error(`The timing file adds something at a step the recording does not have: ${at}`);
    if (usesOfLine.get(step.line!)! > 1) {
      throw new Error(`${at} is on a line of the script that runs more than once (a loop?): put it in by hand`);
    }
  }

  // The names the steps get in the next recording: added chapters start a new count, added lines are steps too
  const lineKeys = addedLineKeys(lines);
  const renamed = new Map<string, string>();
  const used = new Set<string>();
  const nameFor = (title: string) => {
    let count = 1;
    while (used.has(count === 1 ? title : `${title} (${count})`)) count++;
    const chosen = count === 1 ? title : `${title} (${count})`;
    used.add(chosen);
    return chosen;
  };
  let current = "Start";
  let recordedChapter = "Start";
  let count = 0;
  for (const step of timeline.steps) {
    // A recorded chapter() before this step
    if (chapterOf(step.id) !== recordedChapter) {
      recordedChapter = chapterOf(step.id);
      current = nameFor(baseTitle(recordedChapter));
      count = 0;
    }
    for (const chapter of chapters.filter((item) => item.at === step.id)) {
      current = nameFor(chapter.title);
      count = 0;
    }
    lines.forEach((line, index) => {
      if (line.at === step.id) renamed.set(lineKeys[index], `${current} #${++count}`);
    });
    renamed.set(step.id, `${current} #${++count}`);
  }

  // The script, with the new lines before their steps' lines (from the bottom up, so the line numbers hold)
  const scriptFile = path.join(SCRIPTS_DIR, `${name}.ts`);
  const source = readFileSync(scriptFile, "utf8").split(/\r?\n/);
  const targets = [...new Set([...chapters, ...lines].map((item) => byId.get(item.at)!.line!))].sort((a, b) => b - a);
  for (const lineNumber of targets) {
    const indent = source[lineNumber - 1].match(/^\s*/)![0];
    const inserted: string[] = [];
    for (const step of timeline.steps.filter((item) => item.line === lineNumber)) {
      for (const chapter of chapters.filter((item) => item.at === step.id)) {
        inserted.push("", `${indent}// ── Phase: ${chapter.title} ──`, `${indent}await chapter(${JSON.stringify(chapter.title)});`);
      }
      for (const line of lines.filter((item) => item.at === step.id)) {
        const options = line.wait === false ? ", { wait: false }" : "";
        inserted.push(`${indent}await say(${JSON.stringify(line.text)}${options});`);
      }
    }
    source.splice(lineNumber - 1, 0, ...inserted);
  }
  copyFileSync(scriptFile, `${scriptFile}.bak`);
  writeFileSync(scriptFile, source.join("\n"));

  // The timing file under the new names; an added line's start moves to its step
  const steps: Record<string, StepTiming> = {};
  for (const [id, change] of Object.entries(timing.steps ?? {})) {
    const moved = { ...change };
    if (moved.until) moved.until = renamed.get(moved.until) ?? moved.until;
    steps[renamed.get(id) ?? id] = moved;
  }
  lines.forEach((line, index) => {
    if (line.delayMs) steps[renamed.get(lineKeys[index])!] = { delayMs: line.delayMs };
  });
  const rest: Timing = { ...timing, steps };
  delete rest.chapters;
  delete rest.lines;
  if (Object.keys(steps).length === 0) delete rest.steps;
  writeFileSync(timingFile(name), timingFileSource(name, rest));

  const first = [...chapters, ...lines]
    .map((item) => timeline.steps.findIndex((step) => step.id === item.at))
    .sort((a, b) => a - b)[0];
  const firstChapter = chapterOf(timeline.steps[first].id);
  return {
    chapters: chapters.length,
    lines: lines.length,
    recordFrom: firstChapter === "Start" ? null : baseTitle(firstChapter),
  };
}
