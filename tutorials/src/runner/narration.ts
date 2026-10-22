import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { CACHE_DIR, PRONUNCIATIONS_FILE, settings } from "./config";

// Text to speech, cached by provider, voice and text: re-recording a tutorial only generates the lines that changed.
//
// Providers (TTS_PROVIDER in .env):
// - kokoro (default): Kokoro-82M, runs locally, free, good quality. The model (~90 MB) downloads on first use.
// - openai: gpt-4o-mini-tts, steerable with TTS_INSTRUCTIONS ("calm, friendly, instructional").
// - elevenlabs: the most natural voices.

export type Speech = { wav: Buffer; durationMs: number };

type Provider = (text: string) => Promise<Buffer>;

let kokoro: Promise<any> | null = null;

const providers: Record<string, Provider> = {
  async kokoro(text) {
    const { KokoroTTS } = await import("kokoro-js");
    kokoro ??= KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", { dtype: "q8", device: "cpu" });
    const tts = await kokoro;
    const audio = await tts.generate(text, { voice: settings.ttsVoice || "af_heart", speed: settings.ttsSpeed });
    return Buffer.from(audio.toWav());
  },
  async openai(text) {
    const response = await fetch("https://api.openai.com/v1/audio/speech", {
      method: "POST",
      headers: { Authorization: `Bearer ${requireEnv("OPENAI_API_KEY")}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: process.env.OPENAI_TTS_MODEL || "gpt-4o-mini-tts",
        voice: settings.ttsVoice || "coral",
        input: text,
        instructions: settings.ttsInstructions,
        speed: settings.ttsSpeed,
        response_format: "wav",
      }),
    });
    if (!response.ok) throw new Error(`OpenAI speech failed: ${response.status} ${await response.text()}`);
    return Buffer.from(await response.arrayBuffer());
  },
  async elevenlabs(text) {
    const voice = settings.ttsVoice || "21m00Tcm4TlvDq8ikWAM";
    const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voice}?output_format=pcm_44100`, {
      method: "POST",
      headers: { "xi-api-key": requireEnv("ELEVENLABS_API_KEY"), "Content-Type": "application/json" },
      body: JSON.stringify({ text, model_id: process.env.ELEVENLABS_MODEL || "eleven_multilingual_v2" }),
    });
    if (!response.ok) throw new Error(`ElevenLabs speech failed: ${response.status} ${await response.text()}`);
    return pcmToWav(Buffer.from(await response.arrayBuffer()), 44100, 1, 16);
  },
};

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set (see .env.example)`);
  return value;
}

// Words the voice gets wrong, spelled the way they should sound. Only the voice uses them, captions keep the text.
function applyPronunciations(text: string): string {
  if (!existsSync(PRONUNCIATIONS_FILE)) return text;
  const replacements: Record<string, string> = JSON.parse(readFileSync(PRONUNCIATIONS_FILE, "utf8"));
  return Object.entries(replacements).reduce(
    (result, [written, spoken]) =>
      result.replace(new RegExp(`(?<![\\w.])${written.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w])`, "g"), spoken),
    text,
  );
}

export async function synthesise(text: string, spoken?: string): Promise<Speech> {
  const input = spoken ?? applyPronunciations(text);
  const provider = providers[settings.ttsProvider];
  if (!provider) throw new Error(`Unknown TTS_PROVIDER ${settings.ttsProvider}`);
  const key = createHash("sha1")
    .update(JSON.stringify([settings.ttsProvider, settings.ttsVoice, settings.ttsSpeed, settings.ttsInstructions, input]))
    .digest("hex");
  const directory = path.join(CACHE_DIR, "narration");
  const file = path.join(directory, `${key}.wav`);
  if (!existsSync(file)) {
    mkdirSync(directory, { recursive: true });
    writeFileSync(file, await provider(input));
  }
  const wav = readFileSync(file);
  return { wav, durationMs: wavDurationMs(wav) };
}

export function wavDurationMs(wav: Buffer): number {
  let offset = 12;
  let byteRate = 0;
  while (offset + 8 <= wav.length) {
    const id = wav.toString("ascii", offset, offset + 4);
    const size = wav.readUInt32LE(offset + 4);
    if (id === "fmt ") byteRate = wav.readUInt32LE(offset + 16);
    // Streamed WAVs may leave the data size unset (0 or 0xFFFFFFFF): then the data runs to the end
    if (id === "data") {
      const dataSize = size === 0 || size === 0xffffffff ? wav.length - offset - 8 : size;
      return (dataSize / byteRate) * 1000;
    }
    offset += 8 + size + (size % 2);
  }
  throw new Error("Not a WAV file");
}

function pcmToWav(pcm: Buffer, sampleRate: number, channels: number, bitsPerSample: number): Buffer {
  const header = Buffer.alloc(44);
  const byteRate = (sampleRate * channels * bitsPerSample) / 8;
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(channels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE((channels * bitsPerSample) / 8, 32);
  header.writeUInt16LE(bitsPerSample, 34);
  header.write("data", 36);
  header.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([header, pcm]);
}
