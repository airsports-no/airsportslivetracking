import { CAMERA } from "./camera";
import { DEFAULT_EDIT, isHidden, type Say, type Timeline } from "./timeline";
import type { Pause } from "./captions";
import { addedLineKeys, type Timing, type Voice } from "./timing";

// Which parts of the recording make it into the video, at what speed, and where the narration goes. Anything
// happening (the screen changing, an action, a highlight, a pause) keeps a stretch; the still stretches between them
// are shortened, so loading pages and hesitation disappear. The timing file (timing.ts) then speeds stretches up or
// down and holds or shortens the picture before steps. Last, the narration is placed at its say() steps, and the
// picture is held still where a line needs more time than the recording gives it: before the next step when the line
// is waited for, and before the next line, so lines never overlap.

// A stretch of the recording shown from outStart to outEnd (at another speed when the lengths differ), or a hold: the
// picture at srcStart (= srcEnd) held still, for something at holdAt in the recording
export type Segment = { srcStart: number; srcEnd: number; outStart: number; outEnd: number; holdAt?: number };

// A narration line where it is in the video
export type PlacedLine = {
  step: string;
  start: number;
  durationMs: number;
  text: string;
  // Missing until the line's voice has been made (npm run narrate): then its length is estimated
  file?: string;
  pauses: Pause[];
};

// A chapter where it starts in the video, recorded (chapter()) or added in the timing file
export type PlacedChapter = { t: number; title: string };

export type Edit = {
  segments: Segment[];
  durationMs: number;
  // Where a hidden part was cut out (video time): the picture crossfades there
  jumps: { outMs: number; fromSrcMs: number }[];
  narration: PlacedLine[];
  chapters: PlacedChapter[];
  // Steps in the timing file that the recording does not have, and say() lines without a voice yet
  warnings: string[];
  // Recording time to video time (something at a held moment shows after the hold), and back
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
// Silence between two narration lines
export const NARRATION_GAP_MS = 300;
// The length of a line whose voice has not been made yet
const ESTIMATED_MS_PER_CHAR = 65;

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

const subtract = (pieces: Interval[], [cutStart, cutEnd]: Interval): Interval[] =>
  pieces.flatMap(([a, b]): Interval[] =>
    cutEnd <= a || cutStart >= b ? [[a, b]] : ([[a, cutStart], [cutEnd, b]] as Interval[]).filter(([x, y]) => y > x),
  );

export function activeIntervals(timeline: Timeline): Interval[] {
  const intervals: Interval[] = [
    ...timeline.frames.map((frame): Interval => [frame.t, frame.t + SCREEN_CHANGE_AFTER_MS]),
    ...timeline.actions.map((action): Interval => [action.t - ACTION_BEFORE_MS, action.t + ACTION_AFTER_MS]),
    ...timeline.highlights.map((item): Interval => [item.t, item.t + item.durationMs]),
    ...timeline.holds.map((item): Interval => [item.t, item.t + item.durationMs]),
  ];
  return merge(intervals.map(([a, b]): Interval => [Math.max(0, a), Math.min(timeline.durationMs, b)]));
}

// Where something added before a step goes in the recording: where the camera starts moving to the step, though not
// before the step ahead of it
export function stepAnchor(timeline: Timeline, id: string): number | undefined {
  const index = timeline.steps.findIndex((step) => step.id === id);
  if (index < 0) return undefined;
  return Math.max(timeline.steps[index - 1]?.t ?? 0, timeline.steps[index].t - STEP_LEAD_MS);
}

// The timing file's added narration lines as say() lines at their steps (named by addedLineKeys), with what the
// timing file says about each
export function addedSays(timeline: Timeline, timing: Timing): (Say & { delayMs?: number })[] {
  const lines = timing.lines ?? [];
  const keys = addedLineKeys(lines);
  return lines.flatMap((line, index) => {
    const t = stepAnchor(timeline, line.at);
    return t === undefined
      ? []
      : [{ t, step: keys[index], text: line.text, wait: line.wait ?? true, delayMs: line.delayMs }];
  });
}

export function computeEdit(timeline: Timeline, voice: Voice = { lines: {} }, timing: Timing = {}): Edit {
  if (!timeline.steps) throw new Error(`${timeline.name} was recorded before narration was added afterwards: record it again`);
  const { minGapMs, keepGapMs, clickHoldMs } = { ...DEFAULT_EDIT, ...timeline.edit, ...timing.edit };
  const warnings: string[] = [];
  const steps = new Map(timeline.steps.map((step, index) => [step.id, { ...step, index }]));
  const changes = Object.entries(timing.steps ?? {}).filter(([id]) => {
    if (!steps.has(id)) warnings.push(`The timing file names a step the recording does not have: ${id}`);
    return steps.has(id);
  });
  // Where the camera starts moving to a step: the page is still from there on
  const leadOf = (id: string) => Math.max(0, steps.get(id)!.t - STEP_LEAD_MS);

  // Kept stretches: the active ones, plus each gap in full if short or shortened to keepGapMs (half on each side, so
  // the cut falls in the middle of the stillness)
  const kept: Interval[] = [];
  let cursor = 0;
  for (const [start, end] of [...activeIntervals(timeline), [timeline.durationMs, timeline.durationMs] as Interval]) {
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
  let pieces = hidden.reduce(subtract, merge(kept));
  // Shortened waits: the last |holdMs| of what is kept before the step's lead
  for (const [id, change] of changes) {
    let remaining = -(change.holdMs ?? 0);
    const lead = leadOf(id);
    for (const [a, b] of [...pieces].reverse()) {
      if (remaining <= 0) break;
      if (a >= lead) continue;
      const end = Math.min(b, lead);
      const cut = Math.min(remaining, end - a);
      pieces = subtract(pieces, [end - cut, end]);
      remaining -= cut;
    }
  }

  // Speeds: each change from its step's lead to the lead of its `until` step (the next step by default)
  const speeds = changes
    .filter(([, change]) => change.speed && change.speed > 0 && change.speed !== 1)
    .map(([id, change]) => {
      const until = change.until ?? timeline.steps[steps.get(id)!.index + 1]?.id;
      if (change.until && !steps.has(change.until)) warnings.push(`${id}: speed until a step the recording does not have: ${change.until}`);
      const end = until && steps.has(until) ? leadOf(until) : timeline.durationMs;
      return { start: leadOf(id), end, speed: change.speed! };
    });
  const boundaries = speeds.flatMap(({ start, end }) => [start, end]);
  const speedAt = (src: number) => speeds.filter(({ start, end }) => src >= start && src < end).pop()?.speed ?? 1;
  const runs = pieces.flatMap(([a, b]) => {
    const cuts = [a, ...boundaries.filter((point) => point > a && point < b).sort((x, y) => x - y), b];
    return cuts.slice(0, -1).map((start, index) => ({ start, end: cuts[index + 1], speed: speedAt(start) }));
  });

  // Held moments: the picture stops at `at` (in the recording) for ms. Anything at or after `at` shows after the hold.
  const holds: { at: number; ms: number }[] = [];
  let segments: Segment[] = [];
  const layOut = () => {
    const sorted = holds.map((item, index) => ({ ...item, index })).sort((x, y) => x.at - y.at || x.index - y.index);
    segments = [];
    let out = 0;
    let next = 0;
    // A hold in a cut stretch shows the picture the video jumps to
    const pushHold = (frame: number) => {
      const { at, ms } = sorted[next++];
      segments.push({ srcStart: frame, srcEnd: frame, outStart: out, outEnd: (out += ms), holdAt: at });
    };
    for (const run of runs) {
      while (next < sorted.length && sorted[next].at < run.start) pushHold(run.start);
      let cursor = run.start;
      while (next < sorted.length && sorted[next].at < run.end) {
        const at = sorted[next].at;
        if (at > cursor) {
          segments.push({ srcStart: cursor, srcEnd: at, outStart: out, outEnd: (out += (at - cursor) / run.speed) });
          cursor = at;
        }
        pushHold(at);
      }
      segments.push({ srcStart: cursor, srcEnd: run.end, outStart: out, outEnd: (out += (run.end - cursor) / run.speed) });
    }
    const last = runs.length ? runs[runs.length - 1].end : 0;
    while (next < sorted.length) pushHold(last);
  };
  layOut();

  const toOut = (srcMs: number) => {
    for (const segment of segments) {
      if (segment.holdAt !== undefined) {
        if (srcMs < segment.holdAt) return segment.outStart;
        continue;
      }
      // In a cut stretch: where the video jumps over it
      if (srcMs < segment.srcStart) return segment.outStart;
      if (srcMs < segment.srcEnd) {
        const rate = (segment.outEnd - segment.outStart) / (segment.srcEnd - segment.srcStart);
        return segment.outStart + (srcMs - segment.srcStart) * rate;
      }
    }
    return segments.length ? segments[segments.length - 1].outEnd : 0;
  };
  const toSrc = (outMs: number) => {
    for (const segment of segments) {
      if (outMs < segment.outEnd) {
        if (segment.holdAt !== undefined) return segment.srcStart;
        const rate = (segment.srcEnd - segment.srcStart) / (segment.outEnd - segment.outStart);
        return segment.srcStart + Math.max(0, outMs - segment.outStart) * rate;
      }
    }
    return segments.length ? segments[segments.length - 1].srcEnd : 0;
  };
  const hold = (at: number, ms: number) => {
    if (ms <= 0) return;
    holds.push({ at, ms });
    layOut();
  };
  for (const [id, change] of changes) hold(leadOf(id), change.holdMs ?? 0);
  // A click on the page is held for a moment as it was clicked: the page's reaction (a panel opening, a list moving)
  // shows a moment later, so the click is seen on what was clicked. Not on the map (its box is the whole map), where
  // the site marks a click itself. Just after the click, so the cursor presses at the start of the hold.
  for (const action of timeline.actions) {
    const onMap = action.box !== undefined && action.box.width * action.box.height > 250000;
    if (action.kind === "click" && !onMap && !isHidden(timeline, action.t)) hold(action.t + 1, clickHoldMs);
  }

  // The narration, step by step as the script ran: a line starts once the one before has been said, and after a line
  // that is waited for, the next step (its camera move) starts only once it has been said
  const narration: PlacedLine[] = [];
  const says = new Map(timeline.says.map((say) => [say.step, say]));
  for (const line of timing.lines ?? []) {
    if (!steps.has(line.at)) warnings.push(`The timing file adds a line at a step the recording does not have: ${line.at}`);
  }
  const afterLineOf = (step: { id: string; label: string }) =>
    timing.steps?.[step.id]?.afterLine ?? step.label.startsWith("showPdf(");
  // The recorded steps and the added lines, in the order they happen: an added line comes before its step
  const added = addedSays(timeline, timing);
  const events = [
    ...timeline.steps.map((step) => ({ t: step.t, before: 1, step, added: undefined })),
    ...added.map((line) => ({ t: line.t, before: 0, step: undefined, added: line })),
  ].sort((a, b) => a.t - b.t || a.before - b.before);
  let previousEnd = -Infinity;
  let waitedFor: number | null = null;
  let previousT = 0;
  // Where the first line at each moment of the recording starts: a chapter there starts with it
  const lineStarts = new Map<number, number>();
  for (const event of events) {
    const say = event.added ?? (event.step && says.get(event.step.id));
    // A step that waits for the line before: after one that is waited for, or that is set to (afterLine; showPdf by
    // default, as it changes the whole view)
    const waitsFor = event.step && !say ? (afterLineOf(event.step) ? previousEnd : waitedFor) : null;
    // Not in a hidden part: the hold would land where the video comes back
    if (event.step && waitsFor !== null && Number.isFinite(waitsFor) && !isHidden(timeline, event.step.t)) {
      const lead = Math.max(previousT, event.step.t - STEP_LEAD_MS);
      hold(lead, Math.max(waitsFor, waitedFor ?? -Infinity) + NARRATION_GAP_MS - toOut(lead));
    }
    previousT = event.t;
    waitedFor = null;
    if (!say) continue;
    if (isHidden(timeline, say.t)) {
      warnings.push(`${say.step} is in a hidden part, so it is not said: ${say.text}`);
      continue;
    }
    const change = event.added ?? timing.steps?.[say.step] ?? {};
    const text = (event.added ? undefined : timing.steps?.[say.step]?.text) ?? say.text;
    const line = voice.lines[say.step];
    const voiced = line && line.text === text ? line : undefined;
    if (!voiced) warnings.push(`${say.step} has no voice yet (npm run narrate -- ${timeline.name}): ${text}`);
    const durationMs = voiced?.durationMs ?? text.length * ESTIMATED_MS_PER_CHAR;
    const delay = change.delayMs ?? 0;
    hold(say.t, previousEnd + NARRATION_GAP_MS - (toOut(say.t) + delay));
    const start = toOut(say.t) + delay;
    narration.push({ step: say.step, start, durationMs, text, file: voiced?.file, pauses: voiced?.pauses ?? [] });
    if (!lineStarts.has(say.t)) lineStarts.set(say.t, start);
    previousEnd = start + durationMs;
    if ((event.added ? undefined : timing.steps?.[say.step]?.wait) ?? say.wait) waitedFor = previousEnd;
  }
  // The video lasts until the last line has been said
  const end = segments.length ? segments[segments.length - 1].outEnd : 0;
  if (previousEnd + NARRATION_GAP_MS > end) hold(timeline.durationMs, previousEnd + NARRATION_GAP_MS - end);

  const durationMs = segments.length ? segments[segments.length - 1].outEnd : 0;
  const jumps = hidden
    .filter(([start]) => start > 0 && start < timeline.durationMs)
    .map(([start, end]) => ({ outMs: toOut(end), fromSrcMs: start }));
  // The chapters, recorded and added, where they start in the video
  const addedChapters = (timing.chapters ?? []).flatMap((chapter) => {
    const t = stepAnchor(timeline, chapter.at);
    if (t === undefined) warnings.push(`The timing file adds a chapter at a step the recording does not have: ${chapter.at}`);
    return t === undefined ? [] : [{ src: t, title: chapter.title }];
  });
  const recordedChapters = (timeline.chapters ?? []).map((chapter) => ({ src: chapter.t, title: chapter.title }));
  const chapters = [...recordedChapters, ...addedChapters]
    .sort((a, b) => a.src - b.src)
    // Not after the picture held for its first line, which is at the same moment
    .map((chapter) => ({ t: lineStarts.get(chapter.src) ?? toOut(chapter.src), title: chapter.title }));
  return { segments, durationMs, jumps, narration, chapters, warnings, toOut, toSrc };
}
