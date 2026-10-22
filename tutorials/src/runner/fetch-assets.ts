import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { ASSETS_BUCKET, ROOT } from "./config";

// npm run fetch-assets
//
// Fetches the files that cannot be in git (the background music: its licence covers using it in the videos, not
// passing it on) from the team's private bucket into public/brand/music/. Needs gcloud, logged in with access to the
// project (gcloud auth login). Only changed files are downloaded.

const music = path.join(ROOT, "public", "brand", "music");
mkdirSync(music, { recursive: true });
const result = spawnSync("gcloud", ["storage", "rsync", `${ASSETS_BUCKET}/music`, music], { stdio: "inherit" });
if (result.status !== 0) {
  console.error("Could not fetch the music: is gcloud installed and logged in (gcloud auth login)?");
  process.exit(result.status ?? 1);
}
console.log(`Music is in ${music}`);
