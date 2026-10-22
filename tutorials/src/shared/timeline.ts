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

export type Narration = { t: number; durationMs: number; file: string; text: string };

// From camera(): "wide" shows the whole page until the next "auto"
export type CameraDirective = { t: number; mode: "wide" | "auto" };

// From pause(): time kept in the video although nothing happens
export type Hold = { t: number; durationMs: number };

export type Frame = { t: number; file: string };

// From chapter(): the start of a phase of the tutorial
export type Chapter = { t: number; title: string };

export type EditSettings = {
  // A stretch without anything happening (no screen change, action, narration, highlight or pause) longer than this
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
  narration: Narration[];
  camera: CameraDirective[];
  holds: Hold[];
  // Missing in recordings made before chapters existed
  chapters?: Chapter[];
  // The script's own settings, over DEFAULT_EDIT
  edit: Partial<EditSettings>;
  captions: boolean;
};

export const DEFAULT_EDIT: EditSettings = { minGapMs: 700, keepGapMs: 250 };
