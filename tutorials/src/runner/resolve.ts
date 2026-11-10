import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { VIDEO } from "../shared/layout";

// Helpers for DaVinci Resolve workflows:
// 1. Direct in-memory WAV stem synthesis (replaces a full Remotion render pass for voice stems).
// 2. Final Cut Pro XML (FCPXML 1.9) timeline export that DaVinci Resolve imports directly (File -> Import -> Timeline...),
//    with the picture, individual narration clips (so editors can split and insert real camera footage between sentences
//    or chapters), background music, and chapter/overlay timeline markers.

export type VoiceClipPlacement = {
  name: string;
  wavPath: string;
  startMs: number;
  durationMs: number;
};

export type TimelineMarker = {
  startMs: number;
  title: string;
  note?: string;
};

export type ResolveTimelineOptions = {
  title: string;
  durationMs: number;
  fps?: number;
  width?: number;
  height?: number;
  picturePath?: string;
  musicPath?: string;
  voiceClips: VoiceClipPlacement[];
  markers?: TimelineMarker[];
};

type ParsedWav = {
  audioFormat: number;
  channels: number;
  sampleRate: number;
  bitsPerSample: number;
  dataOffset: number;
  dataLength: number;
};

function parseWav(wav: Buffer): ParsedWav {
  let offset = 12;
  let audioFormat = 1;
  let channels = 1;
  let sampleRate = 44100;
  let bitsPerSample = 16;
  while (offset + 8 <= wav.length) {
    const id = wav.toString("ascii", offset, offset + 4);
    const size = wav.readUInt32LE(offset + 4);
    if (id === "fmt ") {
      audioFormat = wav.readUInt16LE(offset + 8);
      channels = wav.readUInt16LE(offset + 10);
      sampleRate = wav.readUInt32LE(offset + 12);
      bitsPerSample = wav.readUInt16LE(offset + 22);
    }
    if (id === "data") {
      const dataOffset = offset + 8;
      const dataLength =
        size === 0 || size === 0xffffffff ? wav.length - dataOffset : Math.min(size, wav.length - dataOffset);
      return { audioFormat, channels, sampleRate, bitsPerSample, dataOffset, dataLength };
    }
    offset += 8 + size + (size % 2);
  }
  throw new Error("Not a valid WAV file");
}

function readMonoFloatSamples(wav: Buffer): { sampleRate: number; samples: Float32Array } {
  const info = parseWav(wav);
  const bytesPerSample = info.bitsPerSample / 8;
  const frameSize = bytesPerSample * info.channels;
  const frameCount = Math.floor(info.dataLength / frameSize);
  const samples = new Float32Array(frameCount);
  for (let i = 0; i < frameCount; i++) {
    let sum = 0;
    for (let ch = 0; ch < info.channels; ch++) {
      const pos = info.dataOffset + i * frameSize + ch * bytesPerSample;
      if (info.audioFormat === 3 && info.bitsPerSample === 32) {
        sum += wav.readFloatLE(pos);
      } else if (info.bitsPerSample === 16) {
        sum += wav.readInt16LE(pos) / 32768;
      } else if (info.bitsPerSample === 24) {
        const b0 = wav[pos];
        const b1 = wav[pos + 1];
        const b2 = wav[pos + 2];
        const val = (b2 << 24) | (b1 << 16) | (b0 << 8);
        sum += val / 2147483648;
      } else if (info.bitsPerSample === 32) {
        sum += wav.readInt32LE(pos) / 2147483648;
      }
    }
    samples[i] = sum / info.channels;
  }
  return { sampleRate: info.sampleRate, samples };
}

// Mixes placed WAV clips into a single 44.1 kHz 16-bit mono WAV buffer in memory
export function buildVoiceStemWav(clips: Array<{ startMs: number; wavPath: string }>, totalDurationMs: number): Buffer {
  const targetRate = 44100;
  const totalSamples = Math.max(1, Math.ceil((totalDurationMs / 1000) * targetRate));
  const mixed = new Float32Array(totalSamples);

  for (const clip of clips) {
    const wav = readFileSync(clip.wavPath);
    const { sampleRate, samples } = readMonoFloatSamples(wav);
    const startSample = Math.max(0, Math.round((clip.startMs / 1000) * targetRate));
    if (sampleRate === targetRate) {
      const end = Math.min(totalSamples, startSample + samples.length);
      for (let i = startSample; i < end; i++) {
        mixed[i] += samples[i - startSample];
      }
    } else {
      const outLength = Math.round((samples.length * targetRate) / sampleRate);
      const end = Math.min(totalSamples, startSample + outLength);
      for (let i = startSample; i < end; i++) {
        const srcIndex = ((i - startSample) * sampleRate) / targetRate;
        const i0 = Math.floor(srcIndex);
        const i1 = Math.min(samples.length - 1, i0 + 1);
        const frac = srcIndex - i0;
        mixed[i] += samples[i0] * (1 - frac) + samples[i1] * frac;
      }
    }
  }

  const pcm = Buffer.alloc(totalSamples * 2);
  for (let i = 0; i < totalSamples; i++) {
    const clamped = Math.max(-1, Math.min(1, mixed[i]));
    pcm.writeInt16LE(Math.round(clamped * 32767), i * 2);
  }

  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(targetRate, 24);
  header.writeUInt32LE(targetRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([header, pcm]);
}

const escapeXml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");

// Frame-aligned rational time in FCPXML ("<frames>/<fps>s") so DaVinci Resolve never warns about non-frame boundaries
const rationalTime = (ms: number, fps: number) => {
  const frames = Math.max(0, Math.round((ms / 1000) * fps));
  return `${frames}/${fps}s`;
};

export function writeResolveFcpxml(outputFile: string, options: ResolveTimelineOptions) {
  const fps = options.fps ?? VIDEO.fps;
  const width = options.width ?? VIDEO.width;
  const height = options.height ?? VIDEO.height;
  const totalTime = rationalTime(options.durationMs, fps);

  const assets: string[] = [];
  let nextId = 2;

  let pictureId: string | null = null;
  if (options.picturePath) {
    pictureId = `r${nextId++}`;
    const src = pathToFileURL(path.resolve(options.picturePath)).href;
    assets.push(
      `    <asset id="${pictureId}" name="${escapeXml(path.basename(options.picturePath))}" start="0s" duration="${totalTime}" hasVideo="1" format="r1">\n` +
        `      <media-rep kind="original-media" src="${escapeXml(src)}"/>\n` +
        `    </asset>`,
    );
  }

  let musicId: string | null = null;
  if (options.musicPath) {
    musicId = `r${nextId++}`;
    const src = pathToFileURL(path.resolve(options.musicPath)).href;
    assets.push(
      `    <asset id="${musicId}" name="${escapeXml(path.basename(options.musicPath))}" start="0s" duration="${totalTime}" hasAudio="1" audioSources="1" audioChannels="2">\n` +
        `      <media-rep kind="original-media" src="${escapeXml(src)}"/>\n` +
        `    </asset>`,
    );
  }

  // De-duplicate asset declarations if two clips share the same WAV file
  const clipAssetIds = new Map<string, string>();
  for (const clip of options.voiceClips) {
    const abs = path.resolve(clip.wavPath);
    if (!clipAssetIds.has(abs)) {
      const id = `r${nextId++}`;
      clipAssetIds.set(abs, id);
      const src = pathToFileURL(abs).href;
      const clipDuration = rationalTime(Math.max(100, clip.durationMs), fps);
      assets.push(
        `    <asset id="${id}" name="${escapeXml(path.basename(abs))}" start="0s" duration="${clipDuration}" hasAudio="1" audioSources="1" audioChannels="1">\n` +
          `      <media-rep kind="original-media" src="${escapeXml(src)}"/>\n` +
          `    </asset>`,
      );
    }
  }

  const attachedAudio: string[] = [];
  for (const clip of options.voiceClips) {
    const ref = clipAssetIds.get(path.resolve(clip.wavPath))!;
    const offset = rationalTime(clip.startMs, fps);
    const duration = rationalTime(Math.max(100, clip.durationMs), fps);
    attachedAudio.push(
      `              <asset-clip name="${escapeXml(clip.name)}" ref="${ref}" lane="-1" offset="${offset}" start="0s" duration="${duration}" audioRole="dialogue"/>`,
    );
  }
  if (musicId) {
    attachedAudio.push(
      `              <asset-clip name="${escapeXml(path.basename(options.musicPath!))}" ref="${musicId}" lane="-2" offset="0s" start="0s" duration="${totalTime}" audioRole="music"/>`,
    );
  }

  const markerElements = (options.markers ?? []).map((marker) => {
    const start = rationalTime(marker.startMs, fps);
    const noteAttr = marker.note ? ` note="${escapeXml(marker.note)}"` : "";
    return `              <marker start="${start}" duration="1/${fps}s" value="${escapeXml(marker.title)}"${noteAttr}/>`;
  });

  const children = [...attachedAudio, ...markerElements].join("\n");
  const primaryClip = pictureId
    ? `            <asset-clip name="${escapeXml(options.title)}" ref="${pictureId}" offset="0s" start="0s" duration="${totalTime}" format="r1">\n${children}\n            </asset-clip>`
    : `            <gap name="${escapeXml(options.title)}" offset="0s" start="0s" duration="${totalTime}">\n${children}\n            </gap>`;

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
    <format id="r1" name="FFVideoFormat${height}p${fps}" frameDuration="1/${fps}s" width="${width}" height="${height}" colorSpace="1-1-1 (Rec. 709)"/>
${assets.join("\n")}
  </resources>
  <library>
    <event name="Tutorials">
      <project name="${escapeXml(options.title)}">
        <sequence format="r1" duration="${totalTime}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
${primaryClip}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
`;

  writeFileSync(outputFile, xml);
}
