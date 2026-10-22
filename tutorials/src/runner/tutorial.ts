import type { Locator, Page } from "playwright";
import type { EditSettings } from "../shared/timeline";

export type SayOptions = {
  // false: carry on with the next steps while the line is spoken (the next say() waits for it to finish)
  wait?: boolean;
  // How the line should sound when that differs from how it is written (captions show the written text)
  spoken?: string;
};

export type HighlightOptions = {
  label?: string;
  durationMs?: number;
  // false: carry on while the highlight shows
  wait?: boolean;
};

export type TutorialContext = {
  // The browser page. Paste what `npm run codegen` records here: page.getByRole(...).click() and so on.
  page: Page;
  say(text: string, options?: SayOptions): Promise<void>;
  highlight(target: Locator | string, options?: HighlightOptions): Promise<void>;
  // Keep a still moment in the video (stillness is cut otherwise)
  pause(ms: number): Promise<void>;
  // "wide" shows the whole page instead of zooming in, until camera("auto")
  camera(mode: "wide" | "auto"): void;
};

export type Tutorial = {
  title: string;
  subtitle?: string;
  // Path on the site the recording starts from
  startUrl?: string;
  captions?: boolean;
  edit?: Partial<EditSettings>;
  run(context: TutorialContext): Promise<void>;
};

export const defineTutorial = (tutorial: Tutorial) => tutorial;
