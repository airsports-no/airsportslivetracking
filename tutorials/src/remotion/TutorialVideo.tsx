import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { useMemo } from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { computeEdit } from "../shared/edit";
import { INTRO_MS, OUTRO_MS, TRANSITION_MS } from "../shared/layout";
import type { Timeline } from "../shared/timeline";
import { brand } from "./brand";
import { Screen } from "./Screen";
import { theme } from "./theme";

export type TutorialProps = { name: string; timeline: Timeline };

const frames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

export const TutorialVideo = ({ timeline }: TutorialProps) => {
  const { fps } = useVideoConfig();
  const edit = useMemo(() => computeEdit(timeline), [timeline]);
  const transition = linearTiming({ durationInFrames: frames(TRANSITION_MS, fps) });
  return (
    <AbsoluteFill style={{ background: theme.background }}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={frames(INTRO_MS, fps)}>
          <TitleScreen timeline={timeline} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transition} />
        <TransitionSeries.Sequence durationInFrames={frames(edit.durationMs, fps)}>
          <Screen timeline={timeline} edit={edit} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transition} />
        <TransitionSeries.Sequence durationInFrames={frames(OUTRO_MS, fps)}>
          <EndScreen timeline={timeline} />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
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
