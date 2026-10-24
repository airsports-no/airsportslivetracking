import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { copyFileSync, createReadStream, existsSync, statSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import path from "node:path";
import { build } from "esbuild";
import type { Timing } from "../shared/timing";
import { ROOT, tutorialName } from "../runner/config";
import { loadTimeline, loadTiming, loadVoice, narrate, timingFile } from "../runner/narrate";
import { timingFileSource, writeIntoScript } from "../runner/write-script";

// npm run timing -- <tutorial> [--port 3100]
//
// The timing editor: the video in a player beside the steps of the recording, with the timing file's changes for the
// chosen step (hold, speed, when a line starts, whether the next step waits for it, its text). Every change shows in
// the player straight away; Save writes scripts/<tutorial>.timing.ts, which render uses as before, and "Make voice"
// makes the voice for changed texts. Nothing is recorded again, unless asked: the page can also start recording again
// (all of it, or from a chapter), recording a chapter's clicks again on Windows and putting them into the script.

const name = tutorialName(process.argv.slice(2).find((argument) => !argument.startsWith("--")));
if (!name) {
  console.error("Usage: npm run timing -- <tutorial name> [--port 3100]");
  process.exit(1);
}
const portArgument = process.argv.indexOf("--port");
const port = portArgument > 0 ? Number(process.argv[portArgument + 1]) : 3100;
const PUBLIC_DIR = path.join(ROOT, "public");

// The page's code, bundled once at start: the editor and the video's own components
const bundle = await build({
  entryPoints: [path.join(ROOT, "src/editor/main.tsx")],
  bundle: true,
  write: false,
  format: "esm",
  jsx: "automatic",
  minify: true,
  sourcemap: "inline",
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "warning",
});
const editorScript = bundle.outputFiles[0].contents;

const page = `<!doctype html><html><head><meta charset="utf-8"><title>Timing: ${name}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><div id="root"></div><script type="module" src="/editor.js"></script></body></html>`;

const TYPES: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".json": "application/json",
  ".woff2": "font/woff2",
};

const send = (response: ServerResponse, status: number, body: string | Uint8Array, type = "application/json") => {
  response.writeHead(status, { "Content-Type": type, "Cache-Control": "no-store" });
  response.end(body);
};

const readBody = (request: IncomingMessage) =>
  new Promise<string>((resolve, reject) => {
    let body = "";
    request.on("data", (chunk) => (body += chunk));
    request.on("end", () => resolve(body));
    request.on("error", reject);
  });

// One job at a time: recording, recording a chapter's clicks (on Windows), putting them into the script
type Job = { kind: string; chapter?: string; log: string[]; running: boolean; code: number | null };
let job: Job | null = null;
let jobProcess: ChildProcess | null = null;
const startJob = (kind: string, chapter: string | undefined, command: string, args: string[]) => {
  if (job?.running) throw new Error(`Something is running already: ${job.kind}`);
  const started: Job = { kind, chapter, log: [`$ ${[command, ...args].join(" ")}`], running: true, code: null };
  job = started;
  const child = spawn(command, args, { cwd: ROOT, env: process.env });
  jobProcess = child;
  const add = (chunk: Buffer) => {
    // Without the terminal colours, and only the last lines
    for (const line of chunk.toString().replace(/\x1b\[[0-9;]*m/g, "").split(/\r?\n/)) {
      if (line.trim()) started.log.push(line);
    }
    if (started.log.length > 400) started.log.splice(0, started.log.length - 400);
  };
  child.stdout.on("data", add);
  child.stderr.on("data", add);
  child.on("error", (error) => {
    started.log.push(String(error));
    started.running = false;
  });
  child.on("close", (code) => {
    started.code = code;
    started.running = false;
    started.log.push(code === 0 ? "Done." : `Stopped (${code}).`);
  });
};
const tsx = (script: string, args: string[]) => ["tsx", path.join(ROOT, "src", "runner", script), name, ...args];
// The click recorder runs on Windows (codegen.ps1), from WSL through powershell.exe
const windowsPath = (file: string) => execFileSync("wslpath", ["-w", file]).toString().trim();

let backedUp = false;
const saveTiming = (timing: Timing) => {
  const file = timingFile(name);
  // The file as it was before the editor first saved it (its comments are not kept)
  if (existsSync(file) && !backedUp) {
    copyFileSync(file, `${file}.bak`);
    backedUp = true;
  }
  writeFileSync(file, timingFileSource(name, timing));
};

// The editor writes files and starts recordings, so only this computer's browser, on the editor's own address, may use
// it: it listens on the loopback address only (Windows reaches it through WSL's localhost forwarding), and a request
// naming another host (DNS rebinding) or sent from another site's page (a cross-origin POST) is refused.
const ownHosts = new Set([`localhost:${port}`, `127.0.0.1:${port}`]);
const ownOrigins = new Set([...ownHosts].map((host) => `http://${host}`));
const isOwnRequest = (request: IncomingMessage) => {
  if (!ownHosts.has(request.headers.host ?? "")) return false;
  const origin = request.headers.origin;
  return request.method === "GET" || origin === undefined || ownOrigins.has(origin);
};

createServer(async (request, response) => {
  try {
    if (!isOwnRequest(request)) {
      return send(response, 403, JSON.stringify({ error: `Only http://localhost:${port}/ on this computer may use the editor` }));
    }
    const url = new URL(request.url ?? "/", "http://localhost");
    if (url.pathname === "/") return send(response, 200, page, "text/html; charset=utf-8");
    if (url.pathname === "/editor.js") return send(response, 200, editorScript, "text/javascript");
    if (url.pathname === "/api/data") {
      return send(
        response,
        200,
        JSON.stringify({ name, timeline: loadTimeline(name), voice: loadVoice(name), timing: await loadTiming(name) }),
      );
    }
    if (url.pathname === "/api/timing" && request.method === "POST") {
      saveTiming(JSON.parse(await readBody(request)));
      return send(response, 200, JSON.stringify({ ok: true }));
    }
    if (url.pathname === "/api/job") return send(response, 200, JSON.stringify(job));
    if (url.pathname === "/api/write-script" && request.method === "POST") {
      // From the saved timing file: the page saves first
      return send(response, 200, JSON.stringify(writeIntoScript(name, loadTimeline(name), await loadTiming(name))));
    }
    if (url.pathname.startsWith("/api/job/") && request.method === "POST") {
      const { chapter } = JSON.parse((await readBody(request)) || "{}") as { chapter?: string };
      const kind = url.pathname.slice("/api/job/".length);
      if (kind === "record") startJob(kind, chapter, "npx", tsx("record.ts", chapter ? ["--from", chapter] : []));
      else if (kind === "clicks" && chapter) {
        startJob(kind, chapter, "powershell.exe", [
          "-ExecutionPolicy",
          "Bypass",
          "-File",
          windowsPath(path.join(ROOT, "windows", "codegen.ps1")),
          name,
          "-Chapter",
          chapter,
        ]);
      } else if (kind === "replace" && chapter) startJob(kind, chapter, "npx", tsx("replace-chapter.ts", [chapter]));
      else if (kind === "stop") jobProcess?.kill();
      else return send(response, 400, JSON.stringify({ error: `Unknown job ${kind}` }));
      return send(response, 200, JSON.stringify(job));
    }
    if (url.pathname === "/api/narrate" && request.method === "POST") {
      // The texts come from the timing file: the page saves first
      return send(response, 200, JSON.stringify({ voice: await narrate(name) }));
    }
    // The recording's frames and voice, the logo and the music: what the video's staticFile() asks for
    const file = path.join(PUBLIC_DIR, decodeURIComponent(url.pathname));
    if (!file.startsWith(PUBLIC_DIR + path.sep) || !existsSync(file) || !statSync(file).isFile()) {
      return send(response, 404, "Not found", "text/plain");
    }
    // Ranges, so the player can seek in the voice and the music
    const size = statSync(file).size;
    const type = TYPES[path.extname(file).toLowerCase()] ?? "application/octet-stream";
    const range = /^bytes=(\d*)-(\d*)$/.exec(request.headers.range ?? "");
    if (range && (range[1] || range[2])) {
      const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]));
      const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
      if (start > end || start >= size) {
        response.writeHead(416, { "Content-Range": `bytes */${size}` });
        return response.end();
      }
      response.writeHead(206, {
        "Content-Type": type,
        "Content-Length": end - start + 1,
        "Content-Range": `bytes ${start}-${end}/${size}`,
        "Accept-Ranges": "bytes",
      });
      return createReadStream(file, { start, end }).pipe(response);
    }
    response.writeHead(200, { "Content-Type": type, "Content-Length": size, "Accept-Ranges": "bytes" });
    createReadStream(file).pipe(response);
  } catch (error) {
    console.error(error);
    send(response, 500, JSON.stringify({ error: error instanceof Error ? error.message : String(error) }));
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`Timing editor for ${name}: http://localhost:${port}/ (Ctrl+C to stop)`);
});
console.log(`Editing ${path.relative(ROOT, timingFile(name))}${existsSync(timingFile(name)) ? "" : " (Save makes it)"}`);
