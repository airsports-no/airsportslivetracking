// What a recording leaves behind for the video (public/recordings/<name>/timeline.json). Every time is in
// milliseconds from the start of the recording, every position in CSS pixels of the page's viewport.

export type Box = { x: number; y: number; width: number; height: number };

export type Action = {
  t: number;
  kind: "click" | "type" | "scroll";
  x: number;
  y: number;
  // The element acted on, which the camera frames
  box?: Box;
};

export type Highlight = { t: number; durationMs: number; box: Box; label?: string };

// Every line of the script that does something (a click, typing, a map gesture, say, highlight, pause, showPdf), named
// "<chapter> #<n>": the n-th such line since the chapter("...") line ("Start #<n>" before the first chapter). The
// timing file (scripts/<name>.timing.ts) refers to steps by these names, which stay the same when the script is
// recorded again, as long as the chapter's own lines are not changed.
export type Step = { t: number; id: string; label: string };

// From say(): where a narration line belongs. The voice is made afterwards (npm run narrate), and the video makes
// room for it, so the recording does not wait for it.
export type Say = { t: number; step: string; text: string; spoken?: string; wait: boolean };

// From camera(): "wide" shows the whole page until the next "auto"
export type CameraDirective = { t: number; mode: "wide" | "auto" };

// From pause(): time kept in the video although nothing happens
export type Hold = { t: number; durationMs: number };

export type Frame = { t: number; file: string };

// From chapter(): the start of a phase of the tutorial
export type Chapter = { t: number; title: string };

// From startHidden()/endHidden(): steps that are performed but cut from the video
export type HiddenPart = { start: number; end: number };

export type EditSettings = {
  // A stretch without anything happening (no screen change, action, highlight or pause) longer than this
  // is shortened to keepGapMs
  minGapMs: number;
  keepGapMs: number;
};

export type Timeline = {
  name: string;
  title: string;
  subtitle?: string;
  series?: string;
  next?: string;
  // false: no background music; a path in public/: this track instead of the brand's
  music?: false | string;
  viewport: { width: number; height: number };
  durationMs: number;
  frames: Frame[];
  actions: Action[];
  highlights: Highlight[];
  // Missing in recordings made before narration was added afterwards: those are recorded again
  steps: Step[];
  says: Say[];
  camera: CameraDirective[];
  holds: Hold[];
  // Missing in recordings made before chapters existed
  chapters?: Chapter[];
  // Missing in recordings made before hidden parts existed
  hidden?: HiddenPart[];
  // The script's own settings, over DEFAULT_EDIT
  edit: Partial<EditSettings>;
  captions: boolean;
};

export const DEFAULT_EDIT: EditSettings = { minGapMs: 700, keepGapMs: 250 };

// Whether something at recording time t happened in a hidden part (it is cut from the video)
// The end is where the video comes back: what happens right then (the next chapter's first line) is shown
export const isHidden = (timeline: Timeline, t: number) =>
  (timeline.hidden ?? []).some((part) => t >= part.start && t < part.end);
