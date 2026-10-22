import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { ROOT, SCRIPTS_DIR, tutorialName } from "./config";

// npm run replace-chapter -- <tutorial> "<chapter title>" [recorded file]
//
// Puts newly recorded steps for a chapter into the tutorial script (windows/codegen.ps1 <tutorial> -Chapter "<title>"
// records them into recorded/<tutorial>.chapter.js). The chapter keeps its chapter("...") line and the narration
// right after it; its other steps, up to the next chapter or the end of run(), are replaced. The script is saved as
// scripts/<tutorial>.ts.bak first.

const name = tutorialName(process.argv[2]);
const title = process.argv[3];
if (!name || !title) {
  console.error('Usage: npm run replace-chapter -- <tutorial> "<chapter title>" [recorded file]');
  process.exit(1);
}
const scriptFile = path.join(SCRIPTS_DIR, `${name}.ts`);
const recordedFile = process.argv[4] ?? path.join(ROOT, "recorded", `${name}.chapter.js`);
if (!existsSync(recordedFile)) {
  console.error(`No recorded steps in ${recordedFile}`);
  process.exit(1);
}

const lines = readFileSync(scriptFile, "utf8").split(/\r?\n/);
const quoted = [JSON.stringify(title), `'${title}'`, `\`${title}\``];
const chapterIndex = lines.findIndex((line) => /chapter\(/.test(line) && quoted.some((text) => line.includes(text)));
if (chapterIndex < 0) {
  console.error(`No chapter("${title}") in ${scriptFile}`);
  process.exit(1);
}
const indent = lines[chapterIndex].match(/^\s*/)?.[0] ?? "";

// Kept: the chapter line and the narration right after it
let first = chapterIndex + 1;
while (first < lines.length && /^\s*(\/\/\s*)?await say\(/.test(lines[first])) first++;

// The chapter ends at the next chapter (or its phase comment), or at the end of run()
let end = lines.findIndex(
  (line, index) => index >= first && (/^\s*\/\/ ── Phase/.test(line) || /^\s*await chapter\(/.test(line)),
);
if (end < 0) {
  const closing = lines.findLastIndex((line) => /^\s*},?\s*$/.test(line) && line.match(/^\s*/)![0].length < indent.length);
  end = closing >= 0 ? closing : lines.length;
}
while (end > first && lines[end - 1].trim() === "") end--;

const recorded = readFileSync(recordedFile, "utf8")
  .split(/\r?\n/)
  .filter((line) => !/^\/\/ (Recorded |Paste these lines)/.test(line))
  .join("\n")
  .trim()
  .split("\n")
  .map((line) => (line.trim() ? indent + line.trim() : ""));

copyFileSync(scriptFile, `${scriptFile}.bak`);
const replaced = end - first;
lines.splice(first, end - first, ...recorded);
writeFileSync(scriptFile, lines.join("\n"));
console.log(
  `Replaced ${replaced} lines of "${title}" in ${path.relative(ROOT, scriptFile)} with ${recorded.length} recorded ` +
    `lines (the old script is in ${path.relative(ROOT, scriptFile)}.bak)`,
);
