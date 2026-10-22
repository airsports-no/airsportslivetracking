import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { computeEdit } from "../shared/edit";
import { INTRO_MS, OUTRO_MS, TRANSITION_MS } from "../shared/layout";
import type { Timeline } from "../shared/timeline";
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
          <Card title={timeline.title} subtitle={timeline.subtitle} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transition} />
        <TransitionSeries.Sequence durationInFrames={frames(edit.durationMs, fps)}>
          <Screen timeline={timeline} edit={edit} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transition} />
        <TransitionSeries.Sequence durationInFrames={frames(OUTRO_MS, fps)}>
          <Card title="Air Sports Live Tracking" subtitle="airsports.no" />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};

const Card = ({ title, subtitle }: { title: string; subtitle?: string }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rise = interpolate(frame, [0, fps * 0.8], [24, 0], { extrapolateRight: "clamp", easing: theme.ease });
  const opacity = interpolate(frame, [0, fps * 0.6], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill
      style={{ background: theme.background, alignItems: "center", justifyContent: "center", fontFamily: theme.font }}
    >
      <div style={{ transform: `translateY(${rise}px)`, opacity, textAlign: "center", maxWidth: 1400 }}>
        <div style={{ color: theme.accent, fontSize: 30, fontWeight: 600, letterSpacing: 4, textTransform: "uppercase" }}>
          Tutorial
        </div>
        <div style={{ color: "white", fontSize: 84, fontWeight: 700, lineHeight: 1.1, marginTop: 24 }}>{title}</div>
        {subtitle && <div style={{ color: theme.muted, fontSize: 40, marginTop: 28 }}>{subtitle}</div>}
      </div>
    </AbsoluteFill>
  );
};
