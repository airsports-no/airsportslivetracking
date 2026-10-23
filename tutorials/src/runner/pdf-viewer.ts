import { readFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "playwright";
import { ROOT } from "./config";

// Shows a PDF in a page with pdf.js: the headless recording browser has no PDF viewer. Served from a made-up address
// so the pdf.js module and its worker load like any page's. Each page is a box of its own (data-pdf-page="n", numbered
// as in the PDF), which pdfPage(n) and pdfRegion(n, ...) find. With grid, a labelled 10% grid lies over each page, to
// read the fractions pdfRegion takes (npm run pdf-grid). zoomPdfInPage zooms a page from where it is to the window's
// full width, onto a band of it, drawing it sharp enough for that first (window.__sharpenPdfPage).

const PDF_VIEWER_ORIGIN = "https://tutorial-pdf.local";
const PDFJS_BUILD = path.join(ROOT, "node_modules", "pdfjs-dist", "build");

export type PdfViewOptions = {
  // The share of the window's width a page takes, or "page": each page whole, as high as the window
  width?: number | "page";
  // Only these pages, numbered from 1
  pages?: number[];
  grid?: boolean;
};

const viewerHtml = ({ width = 0.7, pages, grid = false }: PdfViewOptions) => `<!doctype html><html><head>
  <meta charset="utf-8"><title>PDF</title><style>
    body { margin: 0; background: #525659; display: flex; flex-direction: column; align-items: center; gap: 24px;
      padding: 32px 0; }
    .pdf-page { position: relative; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.5); }
    canvas { display: block; background: white; }
    .pdf-region { position: absolute; pointer-events: none; }
    .grid-line { position: absolute; background: rgba(225, 29, 36, 0.55); }
    .grid-label { position: absolute; font: 600 13px sans-serif; color: #e11d24; background: rgba(255, 255, 255, 0.85);
      padding: 0 3px; }
  </style></head><body><script type="module">
    import * as pdfjs from "/pdf.min.mjs";
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
    const document_ = await pdfjs.getDocument("/document.pdf").promise;
    const share = ${JSON.stringify(width)};
    // Draws a page into a canvas as many pixels wide as given, shown as wide as cssWidth
    const draw = async (pdfPage, cssWidth, pixelWidth) => {
      const viewport = pdfPage.getViewport({ scale: pixelWidth / pdfPage.getViewport({ scale: 1 }).width });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = cssWidth + "px";
      await pdfPage.render({ canvas, canvasContext: canvas.getContext("2d"), viewport }).promise;
      return canvas;
    };
    const shown = new Map();
    // Before zooming in: the page drawn again for the width it will have, swapped in unchanged on screen
    window.__sharpenPdfPage = async (number, cssWidthZoomed) => {
      const item = shown.get(number);
      if (!item) return;
      const sharp = await draw(item.pdfPage, item.width, cssWidthZoomed * window.devicePixelRatio);
      item.box.querySelector("canvas").replaceWith(sharp);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    };
    const pages = ${JSON.stringify(pages ?? null)} ?? Array.from({ length: document_.numPages }, (_, index) => index + 1);
    for (const number of pages) {
      if (number < 1 || number > document_.numPages) continue;
      const pdfPage = await document_.getPage(number);
      const natural = pdfPage.getViewport({ scale: 1 });
      // "page": as high as the window, less the margin above and below
      const width = share === "page" ? ((window.innerHeight - 64) * natural.width) / natural.height : window.innerWidth * share;
      // Drawn for the size it is shown at (zoomPdf draws it sharper when it zooms in): a much larger canvas is slow to
      // appear, and the recording would show a blank page for a while
      const box = document.createElement("div");
      box.className = "pdf-page";
      box.dataset.pdfPage = String(number);
      box.append(await draw(pdfPage, width, width * window.devicePixelRatio));
      document.body.append(box);
      shown.set(number, { pdfPage, box, width });
      if (${grid}) {
        for (let tenth = 1; tenth < 10; tenth++) {
          const vertical = document.createElement("div");
          vertical.className = "grid-line";
          vertical.style.cssText = "left:" + tenth * 10 + "%;top:0;bottom:0;width:1px";
          const horizontal = document.createElement("div");
          horizontal.className = "grid-line";
          horizontal.style.cssText = "top:" + tenth * 10 + "%;left:0;right:0;height:1px";
          const xLabel = document.createElement("div");
          xLabel.className = "grid-label";
          xLabel.style.cssText = "left:calc(" + tenth * 10 + "% + 2px);top:2px";
          xLabel.textContent = "x " + (tenth / 10).toFixed(1);
          const yLabel = document.createElement("div");
          yLabel.className = "grid-label";
          yLabel.style.cssText = "top:calc(" + tenth * 10 + "% + 2px);left:2px";
          yLabel.textContent = "y " + (tenth / 10).toFixed(1);
          box.append(vertical, horizontal, xLabel, yLabel);
        }
      }
    }
    // Once the pages are on the screen, not only drawn
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    window.__pdfShown = true;
  </script></body></html>`;

// Zooms page n of the shown PDF so its part from x to x + width (fractions of the page from its left; all of it by
// default) fills the window's width, with the band from y to y + height (from its top) in the middle of the window,
// over durationMs. The page's regions (pdfRegion) move with it.
export async function zoomPdfInPage(
  page: Page,
  number: number,
  band: { y: number; height: number; x?: number; width?: number },
  durationMs: number,
): Promise<void> {
  // Sharp for the zoom first: the page drawn as wide as it is going to be
  await page.evaluate(
    async ([number, bandWidth]) => {
      const box = document.querySelector<HTMLElement>(`[data-pdf-page="${number}"]`);
      const sharpen = (window as unknown as { __sharpenPdfPage?: (n: number, w: number) => Promise<void> })
        .__sharpenPdfPage;
      if (box && sharpen) await sharpen(number, window.innerWidth / bandWidth);
    },
    [number, band.width ?? 1 - (band.x ?? 0)] as const,
  );
  await page.evaluate(
    ([number, band, durationMs]) =>
      new Promise<void>((resolve, reject) => {
        const box = document.querySelector<HTMLElement>(`[data-pdf-page="${number}"]`);
        if (!box) return reject(new Error(`Page ${number} of the PDF is not shown`));
        // The page grows past the window: no scroll bars, and nothing scrolls under it
        document.documentElement.style.overflow = "hidden";
        document.body.style.overflow = "hidden";
        box.style.transform = "";
        const rect = box.getBoundingClientRect();
        const left = band.x ?? 0;
        const scale = window.innerWidth / (rect.width * (band.width ?? 1 - left));
        const height = rect.height * scale;
        // The band's middle in the middle of the window, without showing past the page's top or bottom
        const middle = (band.y + band.height / 2) * height;
        const top = Math.min(0, Math.max(window.innerHeight - height, window.innerHeight / 2 - middle));
        box.style.transformOrigin = "0 0";
        box.style.transition = `transform ${durationMs}ms cubic-bezier(0.65, 0, 0.35, 1)`;
        box.getBoundingClientRect();
        box.style.transform = `translate(${-rect.left - left * rect.width * scale}px, ${top - rect.top}px) scale(${scale})`;
        setTimeout(resolve, durationMs + 100);
      }),
    [number, band, durationMs] as const,
  );
}

export async function showPdfInPage(page: Page, pdf: Buffer, options: PdfViewOptions = {}): Promise<void> {
  await page.route(`${PDF_VIEWER_ORIGIN}/**`, (route) => {
    const file = new URL(route.request().url()).pathname;
    if (file === "/document.pdf") return route.fulfill({ body: pdf, contentType: "application/pdf" });
    if (file === "/pdf.min.mjs" || file === "/pdf.worker.min.mjs") {
      return route.fulfill({ body: readFileSync(path.join(PDFJS_BUILD, file.slice(1))), contentType: "text/javascript" });
    }
    return route.fulfill({ body: viewerHtml(options), contentType: "text/html" });
  });
  await page.goto(`${PDF_VIEWER_ORIGIN}/viewer.html`);
  await page.waitForFunction(() => (window as unknown as { __pdfShown?: boolean }).__pdfShown === true, null, {
    timeout: 30000,
  });
}
