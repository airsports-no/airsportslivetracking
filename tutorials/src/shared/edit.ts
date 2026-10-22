import { CAMERA } from "./camera";
import { DEFAULT_EDIT, type Timeline } from "./timeline";

// Which parts of the recording make it into the video. Anything happening (the screen changing, an action, a
// narration, a highlight, a pause) keeps a stretch; the still stretches between them are shortened, so loading pages,
// voice generation and hesitation disappear.

export type Segment = { srcStart: number; srcEnd: number; outStart: number };

export type Edit = {
  segments: Segment[];
  durationMs: number;
  // Where a hidden part was cut out (video time): the picture crossfades there
  jumps: { outMs: number; fromSrcMs: number }[];
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
  // Hidden parts (startHidden/endHidden) go entirely, whatever happens in them
  const hidden = merge((timeline.hidden ?? []).map((part): Interval => [part.start, part.end]));
  const visible = merge(kept).flatMap(([start, end]) => {
    let pieces: Interval[] = [[start, end]];
    for (const [hiddenStart, hiddenEnd] of hidden) {
      pieces = pieces.flatMap(([a, b]): Interval[] =>
        hiddenEnd <= a || hiddenStart >= b ? [[a, b]] : ([[a, hiddenStart], [hiddenEnd, b]] as Interval[]).filter(([x, y]) => y > x),
      );
    }
    return pieces;
  });
  const segments: Segment[] = [];
  let out = 0;
  for (const [srcStart, srcEnd] of visible) {
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
  const jumps = hidden
    .filter(([start]) => start > 0 && start < timeline.durationMs)
    .map(([start, end]) => ({ outMs: toOut(end), fromSrcMs: start }));
  return { segments, durationMs, jumps, toOut, toSrc };
}
