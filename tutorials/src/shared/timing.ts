import type { Pause } from "./captions";
import type { EditSettings, OverlayPosition } from "./timeline";

// Changes to a tutorial's timing, in scripts/<name>.timing.ts (in git). They are applied when the video is made, so
// trying them needs no new recording, and a new recording gets them too. Steps are named as in Step (timeline.ts):
// `npm run steps -- <name>` lists them, and Remotion Studio shows the current one at the top left of the picture.

export type StepTiming = {
  // Keep the picture still this much longer before the step (ms). Negative: that much less of the wait before it.
  holdMs?: number;
  // Play from this step until the step `until` (by default the next one) at this speed: 2 twice as fast, 0.5 half
  speed?: number;
  until?: string;
  // Wait until the narration before it has been said (true by default for showPdf, which changes the whole view)
  afterLine?: boolean;
  // For a say() or overlay() step: start it this much later (ms; negative: earlier)
  delayMs?: number;
  // For a say() step: whether the next step waits until the line has been said (the script's say() decides otherwise)
  wait?: boolean;
  // For a say() or overlay() step: say or show this instead of the script's text (then npm run narrate, or render)
  text?: string;
  // For an overlay() step: change its title, position or duration without recording again
  title?: string;
  position?: OverlayPosition;
  durationMs?: number;
};

// A chapter, narration line or text overlay added without recording again, starting where the camera starts moving to
// the step `at` (before that step happens). They work as chapter(), say() and overlay() in the script would there.
export type AddedChapter = { at: string; title: string };
export type AddedLine = {
  at: string;
  text: string;
  // Whether the step after it (`at`) waits until it has been said (by default it does, as say() does)
  wait?: boolean;
  // Start it this much later (ms; negative: earlier)
  delayMs?: number;
};
export type AddedOverlay = {
  at: string;
  text: string;
  title?: string;
  position?: OverlayPosition;
  durationMs?: number;
  // true: hold the picture still before the step while the overlay is shown
  wait?: boolean;
  delayMs?: number;
};

export type Timing = {
  // How still stretches are cut, over the script's edit settings
  edit?: Partial<EditSettings>;
  steps?: Record<string, StepTiming>;
  chapters?: AddedChapter[];
  lines?: AddedLine[];
  overlays?: AddedOverlay[];
};

// The name of an added line, for its voice and in the timing editor: "<step> +<n>", the n-th line added before that
// step
export const addedLineKeys = (lines: AddedLine[]) =>
  lines.map((line, index) => `${line.at} +${lines.slice(0, index + 1).filter((other) => other.at === line.at).length}`);

// The name of an added overlay in the timing editor: "<step> *<n>"
export const addedOverlayKeys = (overlays: AddedOverlay[]) =>
  overlays.map(
    (item, index) => `${item.at} *${overlays.slice(0, index + 1).filter((other) => other.at === item.at).length}`,
  );

export const defineTiming = (timing: Timing) => timing;

// The voice made for each say() step (public/recordings/<name>/voice.json, written by npm run narrate)
export type VoiceLine = { text: string; file: string; durationMs: number; pauses: Pause[] };
export type Voice = { lines: Record<string, VoiceLine> };
