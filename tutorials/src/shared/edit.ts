import { CAMERA } from "./camera";
import { DEFAULT_EDIT, type Timeline } from "./timeline";

// Which parts of the recording make it into the video. Anything happening (the screen changing, an action, a
// narration, a highlight, a pause) keeps a stretch; the still stretches between them are shortened, so loading pages,
// voice generation and hesitation disappear.

export type Segment = { srcStart: number; srcEnd: number; outStart: number };

export type Edit = {
  segments: Segment[];
  durationMs: number;
  // Recording time to video time, and back
  toOut: (srcMs: number) => number;
  toSrc: (outMs: number) => number;
};

// How long around an event counts as "something happening"
const SCREEN_CHANGE_AFTER_MS = 350;
// The recording keeps the page still for this long before each step, while the camera and cursor travel to the
// target, and pauses this long after it, so the steps do not follow each other too fast. Both are kept in the video.
export const STEP_LEAD_MS = CAMERA.transitionMs + 150;
export const STEP_PAUSE_AFTER_MS = 900;
const ACTION_BEFORE_MS = STEP_LEAD_MS;
const ACTION_AFTER_MS = STEP_PAUSE_AFTER_MS;

type Interval = [number, number];

function merge(intervals: Interval[]): Interval[] {
  const sorted = intervals.filter(([a, b]) => b > a).sort((a, b) => a[0] - b[0]);
  const merged: Interval[] = [];
  for (const [start, end] of sorted) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

export function activeIntervals(timeline: Timeline): Interval[] {
  const intervals: Interval[] = [
    ...timeline.frames.map((frame): Interval => [frame.t, frame.t + SCREEN_CHANGE_AFTER_MS]),
    ...timeline.actions.map((action): Interval => [action.t - ACTION_BEFORE_MS, action.t + ACTION_AFTER_MS]),
    ...timeline.narration.map((item): Interval => [item.t, item.t + item.durationMs]),
    ...timeline.highlights.map((item): Interval => [item.t, item.t + item.durationMs]),
    ...timeline.holds.map((item): Interval => [item.t, item.t + item.durationMs]),
  ];
  return merge(intervals.map(([a, b]): Interval => [Math.max(0, a), Math.min(timeline.durationMs, b)]));
}

export function computeEdit(timeline: Timeline): Edit {
  const { minGapMs, keepGapMs } = { ...DEFAULT_EDIT, ...timeline.edit };
  const active = activeIntervals(timeline);
  // Kept stretches: the active ones, plus each gap in full if short or shortened to keepGapMs (half on each side, so
  // the cut falls in the middle of the stillness)
  const kept: Interval[] = [];
  let cursor = 0;
  for (const [start, end] of [...active, [timeline.durationMs, timeline.durationMs] as Interval]) {
    const gap = start - cursor;
    if (gap > minGapMs) {
      kept.push([cursor, cursor + keepGapMs / 2], [start - keepGapMs / 2, start]);
    } else if (gap > 0) {
      kept.push([cursor, start]);
    }
    kept.push([start, end]);
    cursor = Math.max(cursor, end);
  }
  const segments: Segment[] = [];
  let out = 0;
  for (const [srcStart, srcEnd] of merge(kept)) {
    segments.push({ srcStart, srcEnd, outStart: out });
    out += srcEnd - srcStart;
  }
  const durationMs = out;

  const toOut = (srcMs: number) => {
    let previous = segments[0];
    for (const segment of segments) {
      if (srcMs < segment.srcStart) {
        // In a cut stretch: where the video jumps over it
        return previous === segment ? segment.outStart : previous.outStart + (previous.srcEnd - previous.srcStart);
      }
      if (srcMs <= segment.srcEnd) return segment.outStart + (srcMs - segment.srcStart);
      previous = segment;
    }
    return durationMs;
  };
  const toSrc = (outMs: number) => {
    for (const segment of segments) {
      if (outMs <= segment.outStart + (segment.srcEnd - segment.srcStart)) {
        return segment.srcStart + Math.max(0, outMs - segment.outStart);
      }
    }
    const last = segments[segments.length - 1];
    return last ? last.srcEnd : 0;
  };
  return { segments, durationMs, toOut, toSrc };
}
