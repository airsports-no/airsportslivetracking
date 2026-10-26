import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { OUT_DIR, settings } from "./config";
import { synthesise } from "./narration";

// npm run voice -- <script.txt> [output folder]
//
// Narration for a video made elsewhere (a phone recording edited in DaVinci Resolve, say): one WAV file per line of
// the script, in the voice from .env (TTS_PROVIDER, TTS_VOICE, TTS_SPEED), with the pronunciations of
// pronunciations.json. Blank lines and lines starting with # are skipped. Files are numbered in script order:
// 01.wav, 02.wav, ... and listed with their lengths in index.txt. Lines that did not change are not generated again.

const [scriptFile, outputArgument] = process.argv.slice(2);
if (!scriptFile) {
  console.error("Usage: npm run voice -- <script.txt> [output folder]");
  process.exit(1);
}

const lines = readFileSync(scriptFile, "utf8")
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith("#"));
const outputDirectory = outputArgument ?? path.join(OUT_DIR, `${path.basename(scriptFile, path.extname(scriptFile))}-voice`);
mkdirSync(outputDirectory, { recursive: true });

console.log(`${lines.length} lines, ${settings.ttsProvider} voice ${settings.ttsVoice || "(default)"}`);
const index: string[] = [];
for (const [position, text] of lines.entries()) {
  const speech = await synthesise(text);
  const name = `${String(position + 1).padStart(2, "0")}.wav`;
  writeFileSync(path.join(outputDirectory, name), speech.wav);
  const seconds = (speech.durationMs / 1000).toFixed(1);
  index.push(`${name}\t${seconds}s\t${text}`);
  console.log(`${name}  ${seconds}s  ${text}`);
}
writeFileSync(path.join(outputDirectory, "index.txt"), index.join("\n") + "\n");
console.log(`Written to ${outputDirectory}`);
