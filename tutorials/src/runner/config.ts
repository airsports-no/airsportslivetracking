import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const CACHE_DIR = path.join(ROOT, ".cache");
export const AUTH_FILE = path.join(ROOT, ".auth", "state.json");
export const SCRIPTS_DIR = path.join(ROOT, "scripts");
export const RECORDINGS_DIR = path.join(ROOT, "public", "recordings");
export const OUT_DIR = path.join(ROOT, "out");
export const PRONUNCIATIONS_FILE = path.join(ROOT, "pronunciations.json");
// The team's private bucket for files that cannot be in git (npm run fetch-assets)
export const ASSETS_BUCKET = process.env.TUTORIAL_ASSETS_BUCKET || "gs://airsports-tutorial-assets";

// .env.local holds keys written by provider CLIs (the ElevenLabs one: ELEVENLABS_API_KEY). It is loaded first because a
// variable that is already set is never overridden, so an empty ELEVENLABS_API_KEY= in .env cannot hide the key.
if (existsSync(path.join(ROOT, ".env.local"))) process.loadEnvFile(path.join(ROOT, ".env.local"));
if (existsSync(path.join(ROOT, ".env"))) process.loadEnvFile(path.join(ROOT, ".env"));

export const settings = {
  baseUrl: process.env.TUTORIAL_BASE_URL || "http://localhost:8002",
  ttsProvider: process.env.TTS_PROVIDER || "kokoro",
  ttsVoice: process.env.TTS_VOICE || "",
  ttsSpeed: Number(process.env.TTS_SPEED || 1),
  ttsInstructions:
    process.env.TTS_INSTRUCTIONS ||
    "Calm, friendly and clear, like a patient instructor showing a colleague how to use a web application.",
  // The browser window size the tutorials are recorded in (CSS pixels). The video is 16:9, so keep this 16:9.
  viewport: { width: Number(process.env.TUTORIAL_WIDTH || 1440), height: Number(process.env.TUTORIAL_HEIGHT || 810) },
  // "latitude,longitude" the browser reports (a new route's map opens there); the same as -Geolocation when recording
  // the clicks
  geolocation: process.env.TUTORIAL_GEOLOCATION || "",
};

// A tutorial is named by its script: "task2.a3", "scripts/task2.a3.ts" and "task2.a3.ts" all mean scripts/task2.a3.ts
export const tutorialName = (argument: string | undefined) =>
  argument ? path.basename(argument).replace(/\.ts$/, "") : undefined;
