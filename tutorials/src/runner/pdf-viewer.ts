import { readFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "playwright";
import { ROOT } from "./config";

// Shows a PDF in a page with pdf.js: the headless recording browser has no PDF viewer. Served from a made-up address
// so the pdf.js module and its worker load like any page's. Each page is a box of its own (data-pdf-page="n", numbered
// as in the PDF), which pdfPage(n) and pdfRegion(n, ...) find. With grid, a labelled 10% grid lies over each page, to
// read the fractions pdfRegion takes (npm run pdf-grid).

const PDF_VIEWER_ORIGIN = "https://tutorial-pdf.local";
const PDFJS_BUILD = path.join(ROOT, "node_modules", "pdfjs-dist", "build");

export type PdfViewOptions = {
  // The share of the window's width a page takes
  width?: number;
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
    const width = window.innerWidth * ${width};
    const pages = ${JSON.stringify(pages ?? null)} ?? Array.from({ length: document_.numPages }, (_, index) => index + 1);
    for (const number of pages) {
      if (number < 1 || number > document_.numPages) continue;
      const pdfPage = await document_.getPage(number);
      const scale = width / pdfPage.getViewport({ scale: 1 }).width;
      const viewport = pdfPage.getViewport({ scale: scale * window.devicePixelRatio });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = width + "px";
      const box = document.createElement("div");
      box.className = "pdf-page";
      box.dataset.pdfPage = String(number);
      box.append(canvas);
      document.body.append(box);
      await pdfPage.render({ canvas, canvasContext: canvas.getContext("2d"), viewport }).promise;
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
    window.__pdfShown = true;
  </script></body></html>`;

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
