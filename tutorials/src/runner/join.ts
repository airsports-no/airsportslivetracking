import { existsSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import type { Timeline } from "../shared/timeline";

// record --from "<chapter>": the last recording up to that chapter, and the new recording from it joined after it.
// Times in the new recording start at the chapter; in the joined one they continue from where the chapter started in
// the last one. The steps before the chapter are played again without recording, to bring the site to where the
// chapter starts, so they must be the same steps as the last recording's: their names are kept.

export type Earlier = {
  // The last recording, whole (kept as it is if the new one never gets to the chapter)
  full: Timeline;
  // Where the chapter started in it
  cut: number;
  // Frames are numbered on from the last one, so the kept ones are not overwritten
  lastFrameNumber: number;
  outputDir: string;
};

export function keptRecording(outputDir: string, chapter: string): Earlier {
  const file = path.join(outputDir, "timeline.json");
  if (!existsSync(file)) throw new Error(`There is no recording to record "${chapter}" onto: record it whole first`);
  const full: Timeline = JSON.parse(readFileSync(file, "utf8"));
  if (!full.steps) throw new Error("The last recording is from before narration was added afterwards: record it whole");
  const start = (full.chapters ?? []).find((item) => item.title === chapter);
  if (!start) {
    throw new Error(
      `The last recording did not get to chapter("${chapter}"): record from an earlier chapter, or whole. ` +
        `It has ${(full.chapters ?? []).map((item) => `"${item.title}"`).join(", ") || "no chapters"}.`,
    );
  }
  const lastFrameNumber = Math.max(0, ...full.frames.map((frame) => Number(frame.file.match(/(\d+)\.jpg$/)?.[1] ?? 0)));
  return { full, cut: start.t, lastFrameNumber, outputDir };
}

// The steps played before the chapter must be the last recording's, or the kept part shows another route
export function differenceBeforeChapter(earlier: Earlier, played: { id: string; label: string }[]): string | null {
  const kept = earlier.full.steps.filter((step) => step.t < earlier.cut);
  for (let index = 0; index < Math.max(kept.length, played.length); index++) {
    const before = kept[index];
    const now = played[index];
    if (before?.id !== now?.id || before?.label !== now?.label) {
      return before && now
        ? `${now.id} is now ${now.label}, was ${before.id} ${before.label}`
        : before
          ? `${before.id} (${before.label}) is not in the script any more`
          : `${now!.id} (${now!.label}) is new`;
    }
  }
  return null;
}

export function joinRecordings(earlier: Earlier, recorded: Timeline): Timeline {
  const { full, cut } = earlier;
  const before = <T extends { t: number }>(items: T[] | undefined) => (items ?? []).filter((item) => item.t < cut);
  const after = <T extends { t: number }>(items: T[] | undefined) => (items ?? []).map((item) => ({ ...item, t: item.t + cut }));
  // The last recording's frames from the chapter on are not used any more
  for (const frame of full.frames.filter((item) => item.t >= cut)) {
    rmSync(path.join(earlier.outputDir, "..", "..", frame.file), { force: true });
  }
  return {
    // The script's title, settings and so on as they are now
    ...recorded,
    durationMs: cut + recorded.durationMs,
    frames: [...before(full.frames), ...after(recorded.frames)],
    actions: [...before(full.actions), ...after(recorded.actions)],
    highlights: [...before(full.highlights), ...after(recorded.highlights)],
    steps: [...before(full.steps), ...after(recorded.steps)],
    says: [...before(full.says), ...after(recorded.says)],
    camera: [...before(full.camera), ...after(recorded.camera)],
    holds: [...before(full.holds), ...after(recorded.holds)],
    chapters: [...before(full.chapters), ...after(recorded.chapters)],
    hidden: [
      ...(full.hidden ?? []).filter((part) => part.start < cut).map((part) => ({ ...part, end: Math.min(part.end, cut) })),
      ...(recorded.hidden ?? []).map((part) => ({ start: part.start + cut, end: part.end + cut })),
    ],
  };
}
