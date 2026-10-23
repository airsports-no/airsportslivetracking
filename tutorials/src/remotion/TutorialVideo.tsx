import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { useMemo } from "react";
import { AbsoluteFill, Audio, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { computeEdit, type Edit } from "../shared/edit";
import { INTRO_MS, OUTRO_MS, TRANSITION_MS } from "../shared/layout";
import type { Timeline } from "../shared/timeline";
import type { Timing, Voice } from "../shared/timing";
import { brand } from "./brand";
import { Screen } from "./Screen";
import { theme } from "./theme";

// audio: "voice" or "music" renders only that, for the separate tracks npm run render exports
// voice and timing: the narration made for the recording, and the timing file's changes (scripts/<name>.timing.ts)
export type TutorialProps = {
  name: string;
  timeline: Timeline;
  voice: Voice;
  timing: Timing;
  audio?: "all" | "voice" | "music";
};

const frames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

export const TutorialVideo = ({ timeline, voice, timing, audio = "all" }: TutorialProps) => {
  const { fps } = useVideoConfig();
  const edit = useMemo(() => computeEdit(timeline, voice, timing), [timeline, voice, timing]);
  const transition = linearTiming({ durationInFrames: frames(TRANSITION_MS, fps) });
  return (
    <AbsoluteFill style={{ background: theme.background }}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={frames(INTRO_MS, fps)}>
          <TitleScreen timeline={timeline} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transition} />
        <TransitionSeries.Sequence durationInFrames={frames(edit.durationMs, fps)}>
          <Screen timeline={timeline} edit={edit} voice={audio !== "music"} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transition} />
        <TransitionSeries.Sequence durationInFrames={frames(OUTRO_MS, fps)}>
          <EndScreen timeline={timeline} />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      {audio !== "voice" && timeline.music !== false && (
        <Music timeline={timeline} edit={edit} file={timeline.music ?? brand.music.file} />
      )}
    </AbsoluteFill>
  );
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

// The background music: at full level on the title and end screens, low between narration lines, and lower still under
// the narration (down shortly before a line, back up after it), fading in and out at the ends of the video
const Music = ({ timeline, edit, file }: { timeline: Timeline; edit: Edit; file: string }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const { levels, startAtMs } = brand.music;
  const totalMs = (durationInFrames / fps) * 1000;
  const tutorialStart = INTRO_MS - TRANSITION_MS;
  const endScreenStart = totalMs - OUTRO_MS;
  const lines = useMemo(
    () =>
      edit.narration.map((line) => {
        const start = tutorialStart + line.start;
        return [start, start + line.durationMs] as const;
      }),
    [edit, tutorialStart],
  );
  const volume = (frame: number) => {
    const t = (frame / fps) * 1000;
    const inTutorial = Math.min(clamp01((t - tutorialStart) / 900), clamp01((endScreenStart + TRANSITION_MS - t) / 900));
    let ducked = 0;
    for (const [start, end] of lines) {
      ducked = Math.max(ducked, t < start ? clamp01(1 - (start - t) / 400) : t > end ? clamp01(1 - (t - end) / 800) : 1);
    }
    const tutorialLevel = levels.between + (levels.underVoice - levels.between) * ducked;
    const level = levels.full * (1 - inTutorial) + tutorialLevel * inTutorial;
    return level * Math.min(clamp01(t / 600), clamp01((totalMs - t) / 2500));
  };
  return (
    <Audio
      src={staticFile(file)}
      volume={volume}
      loop
      loopVolumeCurveBehavior="extend"
      trimBefore={startAtMs ? Math.round((startAtMs / 1000) * fps) : undefined}
    />
  );
};

// Fades and rises into place, starting delayMs into the scene
const useEntrance = (delayMs: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = (delayMs / 1000) * fps;
  return {
    opacity: interpolate(frame, [start, start + fps * 0.5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(frame, [start, start + fps * 0.7], [28, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: theme.ease,
    })}px)`,
  };
};

const Wordmark = ({ height }: { height: number }) => (
  <Img src={staticFile(brand.wordmark)} style={{ height, width: height * brand.wordmarkAspect }} />
);

// A red line growing from the left, under the logo
const Rule = ({ delayMs, width }: { delayMs: number; width: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = (delayMs / 1000) * fps;
  const grown = interpolate(frame, [start, start + fps * 0.6], [0, width], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: theme.ease,
  });
  return <div style={{ width: grown, height: 4, background: theme.accent, borderRadius: 2 }} />;
};

const Scene = ({ children }: { children: React.ReactNode }) => (
  <AbsoluteFill style={{ background: theme.background, fontFamily: theme.font, padding: "0 160px", justifyContent: "center" }}>
    {children}
  </AbsoluteFill>
);

const TitleScreen = ({ timeline }: { timeline: Timeline }) => (
  <Scene>
    <div style={useEntrance(0)}>
      <Wordmark height={64} />
    </div>
    <div style={{ marginTop: 44, marginBottom: 40 }}>
      <Rule delayMs={250} width={160} />
    </div>
    <div style={useEntrance(400)}>
      <div style={{ color: theme.accent, fontSize: 30, fontWeight: 700, letterSpacing: 5, textTransform: "uppercase" }}>
        {timeline.series ? `Tutorial · ${timeline.series}` : "Tutorial"}
      </div>
    </div>
    <div style={useEntrance(550)}>
      <div style={{ color: theme.text, fontSize: 96, fontWeight: 800, lineHeight: 1.05, marginTop: 20, maxWidth: 1500 }}>
        {timeline.title}
      </div>
    </div>
    {timeline.subtitle && (
      <div style={useEntrance(750)}>
        <div style={{ color: theme.muted, fontSize: 40, marginTop: 28, maxWidth: 1400 }}>{timeline.subtitle}</div>
      </div>
    )}
  </Scene>
);

const EndScreen = ({ timeline }: { timeline: Timeline }) => (
  <Scene>
    <div style={useEntrance(0)}>
      <Wordmark height={56} />
    </div>
    <div style={{ marginTop: 40, marginBottom: 44 }}>
      <Rule delayMs={200} width={160} />
    </div>
    <div style={useEntrance(350)}>
      {timeline.next ? (
        <>
          <div style={{ color: theme.accent, fontSize: 28, fontWeight: 700, letterSpacing: 5, textTransform: "uppercase" }}>
            Next tutorial
          </div>
          <div style={{ color: theme.text, fontSize: 64, fontWeight: 800, marginTop: 14 }}>{timeline.next}</div>
        </>
      ) : (
        <div style={{ color: theme.text, fontSize: 64, fontWeight: 800 }}>Thanks for watching</div>
      )}
    </div>
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: "30px 60px",
        marginTop: 64,
      }}
    >
      {brand.endScreen.links.map((link, index) => (
        <div key={link.label} style={useEntrance(600 + index * 120)}>
          <div style={{ color: theme.muted, fontSize: 24, fontWeight: 600 }}>{link.label}</div>
          <div style={{ color: theme.text, fontSize: 30, fontWeight: 500, marginTop: 6 }}>{link.value}</div>
        </div>
      ))}
    </div>
  </Scene>
);
