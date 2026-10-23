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
  // Panning, or dragging a point: [x, y, ms] for each point of the path. at: where on the map the drag started, and
  // the zoom then (the recorder writes it), so it starts there however the map lies
  drag(path: [number, number, number][], anchor?: { at: [number, number]; zoom: number }): Promise<void>;
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
  chapter(title: string): Promise<void>;
  // The steps between startHidden() and endHidden() are performed but cut from the video, which crossfades from the
  // last picture before to the page as it is after (for setting something up the tutorial is not about). The recorder
  // writes these when you press F9.
  startHidden(): Promise<void>;
  endHidden(): Promise<void>;
  // Shows a PDF's pages in the browser (the headless recording browser cannot): a path on the site such as a flight
  // order's download address, fetched logged in, or a file. Go back to the site with page.goto(...).
  // pages: only these pages (numbered from 1), width: the share of the window a page takes (0.7), or "page" for
  // each page whole.
  showPdf(source: string, options?: { width?: number | "page"; pages?: number[] }): Promise<void>;
  // Zooms a shown PDF page from where it is to the window's full width, with an area of it in the middle: y and
  // height as fractions of the page from its top (as pdfRegion). x and width: the part of the page that fills the
  // width (all of it by default, 0 and 1), such as the map without the page's margins. Over durationMs (1800).
  zoomPdf(
    number: number,
    band: { y: number; height: number; x?: number; width?: number },
    options?: { durationMs?: number },
  ): Promise<void>;
  // A page of the PDF shown, to scroll to or highlight
  pdfPage(number: number): Locator;
  // An area of a PDF page, to highlight: x, y, width and height as fractions of the page (0 to 1, from the top left)
  pdfRegion(number: number, region: { x: number; y: number; width: number; height: number }): Promise<Locator>;
  // Dialogs (confirm, alert, "leave this page?") are accepted; "dismiss" declines the next one instead
  nextDialog(answer: "accept" | "dismiss"): void;
  // The date offset days from the day it runs, as YYYY-MM-DD: for date fields, so what the tutorial creates is never
  // in the past (the recorder writes fill(`${day(7)}T18:00`) for a date picked a week after the day it recorded)
  day(offset?: number): string;
  map: MapSteps;
};

// What an earlier recording created and the next one would create again, removed (by exact name) before every
// recording: the replay then starts from the same state and does not find two of everything
export type CleanUp = {
  routes?: string[];
  navigationTasks?: string[];
  // The contest the tasks are in: only that one is searched (quicker than all contests)
  contest?: string;
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
  cleanUp?: CleanUp;
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
  const zoomPdf: TutorialContext["zoomPdf"];
  const pdfPage: TutorialContext["pdfPage"];
  const pdfRegion: TutorialContext["pdfRegion"];
  const nextDialog: TutorialContext["nextDialog"];
  const day: TutorialContext["day"];
  const map: TutorialContext["map"];
}
