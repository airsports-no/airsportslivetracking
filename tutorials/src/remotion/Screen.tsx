import { useMemo } from "react";
import { AbsoluteFill, Audio, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { planCamera } from "../shared/camera";
import type { Edit } from "../shared/edit";
import { HEADER_HEIGHT, VIDEO, WINDOW_MARGIN } from "../shared/layout";
import type { Action, Box, Frame, Timeline } from "../shared/timeline";
import { brand } from "./brand";
import { theme } from "./theme";

// The recorded page in a window, with the camera, cursor, highlights, captions and voice. Times are video times
// (after the cuts) unless named src.

const lastAtOrBefore = <T extends { t: number }>(items: T[], t: number): T | undefined => {
  let low = 0;
  let high = items.length - 1;
  let found: T | undefined;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (items[middle].t <= t) {
      found = items[middle];
      low = middle + 1;
    } else high = middle - 1;
  }
  return found;
};

export const Screen = ({ timeline, edit }: { timeline: Timeline; edit: Edit }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const outMs = (frame / fps) * 1000;
  const srcMs = edit.toSrc(outMs);
  const { viewport } = timeline;

  const camera = useMemo(() => planCamera(timeline, edit), [timeline, edit]);
  const pointerActions = useMemo(
    () => timeline.actions.map((action) => ({ ...action, t: edit.toOut(action.t) })),
    [timeline, edit],
  );

  const windowScale = Math.min(
    (VIDEO.width - 2 * WINDOW_MARGIN.x) / viewport.width,
    (VIDEO.height - WINDOW_MARGIN.top - WINDOW_MARGIN.bottom) / viewport.height,
  );
  const windowWidth = viewport.width * windowScale;
  const windowHeight = viewport.height * windowScale;
  const { zoom, cx, cy } = camera(outMs);
  const pageTransform =
    `scale(${windowScale * zoom}) ` +
    `translate(${-(cx - viewport.width / (2 * zoom))}px, ${-(cy - viewport.height / (2 * zoom))}px)`;

  const shownFrame: Frame | undefined = lastAtOrBefore(timeline.frames, srcMs) ?? timeline.frames[0];

  return (
    <AbsoluteFill style={{ background: theme.background, fontFamily: theme.font }}>
      <Header left={(VIDEO.width - windowWidth) / 2} width={windowWidth} series={timeline.series} title={timeline.title} />
      <div
        style={{
          position: "absolute",
          left: (VIDEO.width - windowWidth) / 2,
          top: WINDOW_MARGIN.top,
          width: windowWidth,
          height: windowHeight,
          borderRadius: 18,
          overflow: "hidden",
          boxShadow: "0 30px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)",
          background: "white",
        }}
      >
        <div
          style={{
            position: "absolute",
            width: viewport.width,
            height: viewport.height,
            transformOrigin: "0 0",
            transform: pageTransform,
          }}
        >
          {shownFrame && (
            <Img src={staticFile(shownFrame.file)} style={{ width: viewport.width, height: viewport.height }} />
          )}
          {timeline.highlights.map((item, index) => (
            <HighlightBox
              key={index}
              box={item.box}
              label={item.label}
              startMs={edit.toOut(item.t)}
              durationMs={item.durationMs}
              outMs={outMs}
              viewportHeight={viewport.height}
              zoom={zoom}
            />
          ))}
          <Cursor actions={pointerActions} outMs={outMs} viewport={viewport} zoom={zoom} />
        </div>
      </div>
      {timeline.narration.map((item, index) => (
        <Sequence key={index} from={Math.round((edit.toOut(item.t) / 1000) * fps)}>
          <Audio src={staticFile(item.file)} />
        </Sequence>
      ))}
      {timeline.captions && <Captions timeline={timeline} edit={edit} outMs={outMs} />}
    </AbsoluteFill>
  );
};

const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

// A drawn cursor gliding between the clicks on a slight curve, pressing and rippling on each click
const Cursor = ({
  actions,
  outMs,
  viewport,
  zoom,
}: {
  actions: Action[];
  outMs: number;
  viewport: Timeline["viewport"];
  zoom: number;
}) => {
  const moves = actions;
  if (moves.length === 0) return null;
  let x = viewport.width / 2;
  let y = viewport.height * 0.7;
  let previousT = -Infinity;
  for (const action of moves) {
    const travelMs = Math.max(180, Math.min(700, action.t - previousT - 80));
    const start = action.t - travelMs;
    if (outMs < start) break;
    const progress = easeInOut(Math.min(1, (outMs - start) / travelMs));
    // Quadratic curve bowing a little to the side of the straight line
    const dx = action.x - x;
    const dy = action.y - y;
    const controlX = x + dx / 2 - dy * 0.15;
    const controlY = y + dy / 2 + dx * 0.15;
    const inverse = 1 - progress;
    const nextX = inverse * inverse * x + 2 * inverse * progress * controlX + progress * progress * action.x;
    const nextY = inverse * inverse * y + 2 * inverse * progress * controlY + progress * progress * action.y;
    x = nextX;
    y = nextY;
    previousT = action.t;
  }
  const lastClick = [...moves].reverse().find((action) => action.kind === "click" && action.t <= outMs + 120);
  const sinceClick = lastClick ? outMs - lastClick.t : Infinity;
  const press = sinceClick > -60 && sinceClick < 140 ? 0.82 : 1;
  // Keeps a steady size on screen as the camera zooms
  const size = 30 / Math.sqrt(zoom);
  return (
    <>
      {sinceClick >= 0 && sinceClick < 500 && lastClick && (
        <div
          style={{
            position: "absolute",
            left: lastClick.x,
            top: lastClick.y,
            width: 0,
            height: 0,
          }}
        >
          <div
            style={{
              position: "absolute",
              left: -interpolate(sinceClick, [0, 500], [6, 34]),
              top: -interpolate(sinceClick, [0, 500], [6, 34]),
              width: 2 * interpolate(sinceClick, [0, 500], [6, 34]),
              height: 2 * interpolate(sinceClick, [0, 500], [6, 34]),
              borderRadius: "50%",
              border: `3px solid ${theme.accent}`,
              opacity: interpolate(sinceClick, [0, 500], [0.9, 0]),
            }}
          />
        </div>
      )}
      <svg
        viewBox="0 0 24 24"
        style={{
          position: "absolute",
          left: x - size * 0.18,
          top: y - size * 0.08,
          width: size,
          height: size,
          transform: `scale(${press})`,
          transformOrigin: "18% 8%",
          filter: "drop-shadow(0 2px 3px rgba(0,0,0,0.45))",
        }}
      >
        <path
          d="M4.3 1.8 L19.6 14.4 L12.4 15.1 L16.3 22.4 L13.1 23.8 L9.3 16.5 L4.3 21.3 Z"
          fill="#0f172a"
          stroke="white"
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
      </svg>
    </>
  );
};

// Dims the rest of the page and outlines the element, with an optional label
const HighlightBox = ({
  box,
  label,
  startMs,
  durationMs,
  outMs,
  viewportHeight,
  zoom,
}: {
  box: Box;
  label?: string;
  startMs: number;
  durationMs: number;
  outMs: number;
  viewportHeight: number;
  zoom: number;
}) => {
  const fadeMs = 280;
  const opacity = interpolate(
    outMs,
    [startMs, startMs + fadeMs, startMs + durationMs - fadeMs, startMs + durationMs],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  if (opacity <= 0) return null;
  const pad = 6;
  const below = box.y + box.height + 70 < viewportHeight;
  return (
    <div style={{ opacity }}>
      <div
        style={{
          position: "absolute",
          left: box.x - pad,
          top: box.y - pad,
          width: box.width + 2 * pad,
          height: box.height + 2 * pad,
          borderRadius: 10,
          boxShadow: `0 0 0 ${3 / zoom}px ${theme.highlight}, 0 0 24px 6px ${theme.highlightGlow}, 0 0 0 9999px rgba(10,12,16,0.5)`,
        }}
      />
      {label && (
        <div
          style={{
            position: "absolute",
            left: box.x + box.width / 2,
            top: below ? box.y + box.height + pad + 12 : box.y - pad - 12,
            transform: `translate(-50%, ${below ? "0" : "-100%"}) scale(${1 / Math.sqrt(zoom)})`,
            transformOrigin: below ? "50% 0" : "50% 100%",
            background: theme.highlight,
            color: "white",
            fontFamily: theme.font,
            fontWeight: 600,
            fontSize: 20,
            padding: "8px 16px",
            borderRadius: 10,
            whiteSpace: "nowrap",
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
          }}
        >
          {label}
        </div>
      )}
    </div>
  );
};

const Captions = ({ timeline, edit, outMs }: { timeline: Timeline; edit: Edit; outMs: number }) => {
  const current = timeline.narration.find((item) => {
    const start = edit.toOut(item.t);
    return outMs >= start && outMs <= start + item.durationMs;
  });
  if (!current) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 70,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: 1400,
          background: "rgba(2,6,23,0.82)",
          color: "white",
          fontSize: 36,
          lineHeight: 1.35,
          padding: "14px 28px",
          borderRadius: 14,
          textAlign: "center",
        }}
      >
        {current.text}
      </div>
    </div>
  );
};

// Above the window: the logo, and which tutorial this is
const Header = ({ left, width, series, title }: { left: number; width: number; series?: string; title: string }) => {
  const logoHeight = 34;
  return (
    <div
      style={{
        position: "absolute",
        left,
        width,
        top: 0,
        height: HEADER_HEIGHT,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <Img src={staticFile(brand.wordmark)} style={{ height: logoHeight, width: logoHeight * brand.wordmarkAspect }} />
      <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 24, color: theme.muted }}>
        {series && (
          <>
            <span style={{ color: theme.accent, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", fontSize: 18 }}>
              {series}
            </span>
            <span style={{ opacity: 0.4 }}>|</span>
          </>
        )}
        <span style={{ color: theme.text, fontWeight: 600 }}>{title}</span>
      </div>
    </div>
  );
};
