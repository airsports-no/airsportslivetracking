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

// The route editor's map, as the click recorder writes it (windows/capture.mjs). Positions in drag() and wheel() are
// pixels from the map's top left corner, times are milliseconds since the previous point.
export type MapSteps = {
  // Moves the map to exactly this view (after a gesture it is usually there already, or very nearly)
  view(lat: number, lng: number, zoom: number): Promise<void>;
  // Clicks the map at this point, wherever it is on screen
  click(lat: number, lng: number): Promise<void>;
  // Panning, or dragging a point: [x, y, ms] for each point of the path
  drag(path: [number, number, number][]): Promise<void>;
  // Wheel zooming: [x, y, deltaY, ms] for each tick
  wheel(ticks: [number, number, number, number][]): Promise<void>;
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
  // The start of a phase of the tutorial ("Placing the points"): a label in the video, and a chapter in
  // out/<name>-chapters.txt. The recorder writes these when you press F8.
  chapter(title: string): void;
  // The steps between startHidden() and endHidden() are performed but cut from the video, which crossfades from the
  // last picture before to the page as it is after (for setting something up the tutorial is not about). The recorder
  // writes these when you press F9.
  startHidden(): Promise<void>;
  endHidden(): Promise<void>;
  // Shows a PDF's pages in the browser (the headless recording browser cannot): a path on the site such as a flight
  // order's download address, fetched logged in, or a file. Go back to the site with page.goto(...).
  showPdf(source: string, options?: { width?: number }): Promise<void>;
  map: MapSteps;
};

export type Tutorial = {
  title: string;
  subtitle?: string;
  // Which series the tutorial belongs to ("Route editor"): above the title, and in the header during the video
  series?: string;
  // The title of the tutorial to watch next, on the end screen
  next?: string;
  // Background music: the brand's track by default (src/remotion/brand.ts), false for none, or a file in public/
  music?: false | string;
  // Path on the site the recording starts from
  startUrl?: string;
  captions?: boolean;
  edit?: Partial<EditSettings>;
  run(context: TutorialContext): Promise<void>;
};

export const defineTutorial = (tutorial: Tutorial) => tutorial;

// While a tutorial is recorded, everything in TutorialContext is also a global: steps pasted from the recorder work in
// run() without listing page, say, map, ... in its parameters
declare global {
  const page: TutorialContext["page"];
  const say: TutorialContext["say"];
  const highlight: TutorialContext["highlight"];
  const pause: TutorialContext["pause"];
  const camera: TutorialContext["camera"];
  const chapter: TutorialContext["chapter"];
  const startHidden: TutorialContext["startHidden"];
  const endHidden: TutorialContext["endHidden"];
  const showPdf: TutorialContext["showPdf"];
  const map: TutorialContext["map"];
}
