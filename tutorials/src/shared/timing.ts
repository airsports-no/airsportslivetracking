import type { Pause } from "./captions";
import type { EditSettings } from "./timeline";

// Changes to a tutorial's timing, in scripts/<name>.timing.ts (in git). They are applied when the video is made, so
// trying them needs no new recording, and a new recording gets them too. Steps are named as in Step (timeline.ts):
// `npm run steps -- <name>` lists them, and Remotion Studio shows the current one at the top left of the picture.

export type StepTiming = {
  // Keep the picture still this much longer before the step (ms). Negative: that much less of the wait before it.
  holdMs?: number;
  // Play from this step until the step `until` (by default the next one) at this speed: 2 twice as fast, 0.5 half
  speed?: number;
  until?: string;
  // For a say() step: start the line this much later (ms; negative: earlier)
  delayMs?: number;
  // For a say() step: whether the next step waits until the line has been said (the script's say() decides otherwise)
  wait?: boolean;
  // For a say() step: say and show this instead of the script's text (then npm run narrate, or render)
  text?: string;
};

export type Timing = {
  // How still stretches are cut, over the script's edit settings
  edit?: Partial<EditSettings>;
  steps?: Record<string, StepTiming>;
};

export const defineTiming = (timing: Timing) => timing;

// The voice made for each say() step (public/recordings/<name>/voice.json, written by npm run narrate)
export type VoiceLine = { text: string; file: string; durationMs: number; pauses: Pause[] };
export type Voice = { lines: Record<string, VoiceLine> };
