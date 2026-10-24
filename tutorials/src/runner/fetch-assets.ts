import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { ASSETS_BUCKET, ROOT } from "./config";

// npm run fetch-assets
//
// Fetches the files that are not in git from the team's private bucket: the background music (its licence covers
// using it in the videos, not passing it on) into public/brand/music/, and the PDFs the scripts show (showPdf, too large
// for git) into pdfs/. Needs gcloud, logged in with access to the project (gcloud auth login). Only changed files are
// downloaded. A new PDF goes to the bucket with: gcloud storage cp pdfs/<file>.pdf gs://airsports-tutorial-assets/pdfs/

const folders = [
  { name: "music", from: `${ASSETS_BUCKET}/music`, to: path.join(ROOT, "public", "brand", "music") },
  { name: "PDFs", from: `${ASSETS_BUCKET}/pdfs`, to: path.join(ROOT, "pdfs") },
];
for (const folder of folders) {
  mkdirSync(folder.to, { recursive: true });
  const result = spawnSync("gcloud", ["storage", "rsync", folder.from, folder.to], { stdio: "inherit" });
  if (result.status !== 0) {
    console.error(`Could not fetch the ${folder.name}: is gcloud installed and logged in (gcloud auth login)?`);
    process.exit(result.status ?? 1);
  }
  console.log(`The ${folder.name} are in ${folder.to}`);
}
