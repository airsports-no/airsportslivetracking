import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { OUT_DIR } from "./config";
import { showPdfInPage } from "./pdf-viewer";

// npm run pdf-grid -- <file.pdf>
//
// Writes an image of each page of a PDF with a labelled 10% grid over it, out/<file>-page-<n>-grid.png, to read the
// fractions pdfRegion(n, { x, y, width, height }) takes: x and y where the area starts, width and height how much of
// the page it covers, all from 0 to 1 from the top left of the page.

const file = process.argv[2];
if (!file) {
  console.error("Usage: npm run pdf-grid -- <file.pdf>");
  process.exit(1);
}
mkdirSync(OUT_DIR, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
await showPdfInPage(page, readFileSync(file), { width: 0.9, grid: true });
for (const box of await page.locator("[data-pdf-page]").all()) {
  const number = await box.getAttribute("data-pdf-page");
  const output = path.join(OUT_DIR, `${path.parse(file).name}-page-${number}-grid.png`);
  await box.screenshot({ path: output });
  console.log(`Wrote ${output}`);
}
await browser.close();
