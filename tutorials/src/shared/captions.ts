// Narration lines as subtitles the way films and TV show them: at most two lines on screen at a time. A long line is
// still spoken in one go, but its text is shown in parts, one after the other, in step with the voice. A part ends at
// a sentence or clause where it can; it is switched at the pause the voice makes there (found in the voice's WAV), or
// failing that at the point its share of the characters says.

// Characters per caption line: the usual limit for subtitles
export const CAPTION_LINE_CHARS = 42;

// A pause in the voice: a stretch of silence inside the line (not before or after it), ms from the line's start
export type Pause = { start: number; end: number };

export type CaptionCue = { start: number; end: number; lines: string[] };

const SENTENCE_END = /[.!?…]["')\]]*$/;
const CLAUSE_END = /[,;:–—]["')\]]*$/;

// The best place to break the words into two lines (the index of the first word on the second line), or null when
// they do not fit on two lines. Lines are kept close to equal, and a break after a comma is preferred.
function lineBreak(words: string[], maxChars: number): number | null {
  let best: number | null = null;
  let bestScore = Infinity;
  for (let index = 1; index < words.length; index++) {
    const first = words.slice(0, index).join(" ").length;
    const second = words.slice(index).join(" ").length;
    if (first > maxChars || second > maxChars) continue;
    const score = Math.abs(first - second) - (CLAUSE_END.test(words[index - 1]) || SENTENCE_END.test(words[index - 1]) ? 12 : 0);
    if (score < bestScore) {
      bestScore = score;
      best = index;
    }
  }
  return best;
}

export function captionLines(text: string, maxChars = CAPTION_LINE_CHARS): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.join(" ").length <= maxChars) return [words.join(" ")];
  const index = lineBreak(words, maxChars);
  // A word longer than a line: the parts are chosen so this does not happen except for such a word
  if (index === null) return [words.join(" ")];
  return [words.slice(0, index).join(" "), words.slice(index).join(" ")];
}

const fits = (words: string[], maxChars: number) =>
  words.join(" ").length <= maxChars || lineBreak(words, maxChars) !== null;

// A sentence too long for two lines in parts that each fit: few parts, ending after a clause where possible, and of
// even length (a short part only flashes by)
const PART_COST = 30;
const PLAIN_BREAK_COST = 40;
function splitSentence(words: string[], maxChars: number): string[][] {
  // best[i]: the cheapest way to show the first i words, and where its last part starts
  const best: { cost: number; from: number }[] = [{ cost: 0, from: 0 }];
  for (let end = 1; end <= words.length; end++) {
    best[end] = { cost: Infinity, from: end - 1 };
    for (let start = end - 1; start >= 0; start--) {
      const part = words.slice(start, end);
      // A word longer than two lines stands alone
      if (part.length > 1 && !fits(part, maxChars)) break;
      const slack = Math.max(0, 2 * maxChars - part.join(" ").length);
      const cost =
        best[start].cost + PART_COST + 0.015 * slack ** 2 + (end < words.length && !CLAUSE_END.test(words[end - 1]) ? PLAIN_BREAK_COST : 0);
      if (cost < best[end].cost) best[end] = { cost, from: start };
    }
  }
  const parts: string[][] = [];
  for (let end = words.length; end > 0; end = best[end].from) parts.unshift(words.slice(best[end].from, end));
  return parts;
}

// The text in parts that each fit on two lines: whole sentences, together while they fit, and a sentence too long
// for two lines split
export function captionParts(text: string, maxChars = CAPTION_LINE_CHARS): string[] {
  const sentences: string[][] = [[]];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    sentences[sentences.length - 1].push(word);
    if (SENTENCE_END.test(word)) sentences.push([]);
  }
  const parts: string[][] = [];
  for (const sentence of sentences.filter((words) => words.length > 0)) {
    const last = parts[parts.length - 1];
    if (last && fits([...last, ...sentence], maxChars)) parts[parts.length - 1] = [...last, ...sentence];
    else if (fits(sentence, maxChars)) parts.push(sentence);
    else parts.push(...splitSentence(sentence, maxChars));
  }
  return parts.map((part) => part.join(" "));
}

// How long a part takes to say, roughly: its characters, with the pauses after punctuation
const spokenWeight = (part: string) =>
  part.length + 6 * (part.match(/[.!?…](?=\s|$)/g)?.length ?? 0) + 3 * (part.match(/[,;:–—](?=\s|$)/g)?.length ?? 0);

// Where the voice switches from one part to the next: the pause nearest the estimate, when one is close enough. The
// next part appears just as its words start.
function switchTimes(parts: string[], durationMs: number, pauses: Pause[]): number[] {
  const weights = parts.map(spokenWeight);
  const times: number[] = [];
  let remaining = weights.reduce((sum, weight) => sum + weight, 0);
  let previous = 0;
  let unused = [...pauses];
  for (let index = 0; index < parts.length - 1; index++) {
    // The part's share of the time left after the previous switch
    const share = ((durationMs - previous) * weights[index]) / remaining;
    remaining -= weights[index];
    const estimate = previous + share;
    const window = Math.max(700, 0.35 * share);
    const nearest = unused
      .filter((pause) => pause.start > previous && Math.abs((pause.start + pause.end) / 2 - estimate) <= window)
      .sort((a, b) => Math.abs((a.start + a.end) / 2 - estimate) - Math.abs((b.start + b.end) / 2 - estimate))[0];
    const time = nearest ? nearest.end - Math.min(80, (nearest.end - nearest.start) / 2) : estimate;
    previous = Math.max(previous, time);
    times.push(previous);
    if (nearest) unused = unused.filter((pause) => pause.start > nearest.end);
  }
  return times;
}

// The captions of one narration line, in ms from its start
export function captionCues(
  item: { text: string; durationMs: number; pauses?: Pause[] },
  maxChars = CAPTION_LINE_CHARS,
): CaptionCue[] {
  const parts = captionParts(item.text, maxChars);
  const times = [0, ...switchTimes(parts, item.durationMs, item.pauses ?? []), item.durationMs];
  return parts.map((part, index) => ({ start: times[index], end: times[index + 1], lines: captionLines(part, maxChars) }));
}

// The pauses inside a line of speech, from its WAV (16-bit or float PCM, as every voice provider gives): stretches of
// at least MIN_PAUSE_MS clearly quieter than the speech, not counting the silence before and after it
const WINDOW_MS = 10;
const MIN_PAUSE_MS = 120;
export function findPauses(wav: Uint8Array): Pause[] {
  const view = new DataView(wav.buffer, wav.byteOffset, wav.byteLength);
  const tag = (offset: number) => String.fromCharCode(...wav.subarray(offset, offset + 4));
  let offset = 12;
  let format = 0;
  let channels = 1;
  let sampleRate = 0;
  let bits = 16;
  while (offset + 8 <= wav.length) {
    const id = tag(offset);
    const size = view.getUint32(offset + 4, true);
    if (id === "fmt ") {
      format = view.getUint16(offset + 8, true);
      channels = view.getUint16(offset + 10, true);
      sampleRate = view.getUint32(offset + 12, true);
      bits = view.getUint16(offset + 22, true);
    }
    if (id === "data") {
      const dataSize = size === 0 || size === 0xffffffff ? wav.length - offset - 8 : Math.min(size, wav.length - offset - 8);
      const bytes = bits / 8;
      const sample =
        format === 3 && bits === 32
          ? (i: number) => view.getFloat32(offset + 8 + i * bytes * channels, true)
          : bits === 16
            ? (i: number) => view.getInt16(offset + 8 + i * bytes * channels, true) / 32768
            : null;
      if (!sample || !sampleRate) return [];
      const count = Math.floor(dataSize / (bytes * channels));
      const perWindow = Math.max(1, Math.round((sampleRate * WINDOW_MS) / 1000));
      const levels: number[] = [];
      for (let start = 0; start + perWindow <= count; start += perWindow) {
        let sum = 0;
        for (let i = start; i < start + perWindow; i++) sum += sample(i) ** 2;
        levels.push(Math.sqrt(sum / perWindow));
      }
      const peak = Math.max(0, ...levels);
      if (peak === 0) return [];
      const quiet = levels.map((level) => level < peak * 0.04);
      const firstSound = quiet.indexOf(false);
      const lastSound = quiet.lastIndexOf(false);
      const pauses: Pause[] = [];
      let runStart: number | null = null;
      for (let index = firstSound; index <= lastSound + 1; index++) {
        if (index <= lastSound && quiet[index]) runStart ??= index;
        else if (runStart !== null) {
          if ((index - runStart) * WINDOW_MS >= MIN_PAUSE_MS) pauses.push({ start: runStart * WINDOW_MS, end: index * WINDOW_MS });
          runStart = null;
        }
      }
      return pauses;
    }
    offset += 8 + size + (size % 2);
  }
  return [];
}
