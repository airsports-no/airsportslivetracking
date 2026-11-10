import { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  getRemotionEnvironment,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { planCamera } from "../shared/camera";
import { captionCues } from "../shared/captions";
import { STEP_LEAD_MS, type Edit, type PlacedOverlay } from "../shared/edit";
import { HEADER_HEIGHT, VIDEO, WINDOW_MARGIN } from "../shared/layout";
import { isHidden, type Action, type Box, type Frame, type Timeline } from "../shared/timeline";
import { brand } from "./brand";
import { theme } from "./theme";

// The recorded page in a window, with the camera, cursor, highlights, captions and voice. Times are video times
// (after the cuts) unless named src.

const JUMP_FADE_MS = 500;

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

export const Screen = ({
  timeline,
  edit,
  voice = true,
  showCaptions,
}: {
  timeline: Timeline;
  edit: Edit;
  voice?: boolean;
  showCaptions?: boolean;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const outMs = (frame / fps) * 1000;
  const srcMs = edit.toSrc(outMs);
  const { viewport } = timeline;

  const camera = useMemo(() => planCamera(timeline, edit), [timeline, edit]);
  const pointerActions = useMemo(
    () =>
      timeline.actions
        .filter((action) => !isHidden(timeline, action.t))
        .map((action) => ({ ...action, t: edit.toOut(action.t) })),
    [timeline, edit],
  );
  // Where a hidden part was cut out, the last picture before it fades out over the page as it is after
  const jump = edit.jumps.find((item) => outMs >= item.outMs && outMs < item.outMs + JUMP_FADE_MS);
  const jumpFromFrame = jump ? lastAtOrBefore(timeline.frames, jump.fromSrcMs) : undefined;

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
  // Recorded and added in the timing file, in video time
  const chapter = lastAtOrBefore(edit.chapters, outMs);

  return (
    <AbsoluteFill style={{ background: theme.background, fontFamily: theme.font }}>
      <Header
        left={(VIDEO.width - windowWidth) / 2}
        width={windowWidth}
        series={timeline.series}
        title={timeline.title}
        chapter={chapter?.title}
      />
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
          {jump && jumpFromFrame && (
            <Img
              src={staticFile(jumpFromFrame.file)}
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                width: viewport.width,
                height: viewport.height,
                opacity: 1 - (outMs - jump.outMs) / JUMP_FADE_MS,
              }}
            />
          )}
          {timeline.highlights.map((item, index) => (
            <HighlightBox
              key={index}
              box={item.box}
              label={item.label}
              startMs={edit.toOut(item.t)}
              durationMs={edit.toOut(item.t + item.durationMs) - edit.toOut(item.t)}
              outMs={outMs}
              viewportHeight={viewport.height}
              zoom={zoom}
            />
          ))}
          <Cursor actions={pointerActions} outMs={outMs} viewport={viewport} zoom={zoom} />
        </div>
      </div>
      {voice &&
        edit.narration.map(
          (line) =>
            line.file && (
              // Only while it is said: a line left mounted to the end of the video counts against the player's audio
              // tags (5), and the player stops with an error at the sixth line
              <Sequence
                key={line.step}
                from={Math.round((line.start / 1000) * fps)}
                durationInFrames={Math.ceil((line.durationMs / 1000) * fps) + 1}
              >
                <Audio src={staticFile(line.file)} />
              </Sequence>
            ),
        )}
      {chapter && (
        <ChapterLabel
          title={chapter.title}
          sinceMs={outMs - chapter.t}
          left={(VIDEO.width - windowWidth) / 2 + 36}
          bottom={WINDOW_MARGIN.bottom + 205}
        />
      )}
      {edit.overlays.map((overlay) => (
        <OverlayCard
          key={overlay.step}
          overlay={overlay}
          outMs={outMs}
          windowLeft={(VIDEO.width - windowWidth) / 2}
          windowWidth={windowWidth}
        />
      ))}
      {(showCaptions ?? timeline.captions) && <Captions edit={edit} outMs={outMs} />}
      {getRemotionEnvironment().isStudio && <StepBadge timeline={timeline} edit={edit} srcMs={srcMs} />}
    </AbsoluteFill>
  );
};

const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

// How long a click's ripple lasts (the picture is held for the first part of it: clickHoldMs, edit.ts)
const CLICK_RIPPLE_MS = 700;
const CURSOR_IDLE_FADE_START_MS = 3200;
const CURSOR_IDLE_FADE_MS = 500;

// A drawn cursor gliding between the clicks on a slight curve, pressing and rippling on each click, and following drags
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
  let nextMoveStart = Infinity;
  let dragging = false;
  for (const action of moves) {
    const isDrag = action.kind === "drag" && action.t - previousT < 600;
    const travelMs = isDrag
      ? Math.max(16, action.t - previousT)
      : Math.max(180, Math.min(700, action.t - previousT - 80));
    const start = action.t - travelMs;
    if (outMs < start) {
      nextMoveStart = start;
      break;
    }
    if (isDrag) {
      const progress = Math.min(1, Math.max(0, (outMs - start) / travelMs));
      x = x + (action.x - x) * progress;
      y = y + (action.y - y) * progress;
      dragging = outMs <= action.t + 80;
    } else {
      const progress = easeInOut(Math.min(1, (outMs - start) / travelMs));
      // Quadratic curve bowing a little to the side of the straight line
      const dx = action.x - x;
      const dy = action.y - y;
      const controlX = x + dx / 2 - dy * 0.15;
      const controlY = y + dy / 2 + dx * 0.15;
      const inverse = 1 - progress;
      x = inverse * inverse * x + 2 * inverse * progress * controlX + progress * progress * action.x;
      y = inverse * inverse * y + 2 * inverse * progress * controlY + progress * progress * action.y;
      dragging = false;
    }
    previousT = action.t;
  }
  // Fade out when the cursor has been idle for a while (or before the first move) so it does not sit frozen over maps or PDFs
  const sinceLast = previousT === -Infinity ? Infinity : Math.max(0, outMs - previousT);
  const untilNext = nextMoveStart - outMs;
  const idleOut =
    previousT === -Infinity
      ? 0
      : interpolate(
          sinceLast,
          [CURSOR_IDLE_FADE_START_MS, CURSOR_IDLE_FADE_START_MS + CURSOR_IDLE_FADE_MS],
          [1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
  const wakeIn = interpolate(untilNext, [0, 350], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const cursorOpacity = Math.max(idleOut, wakeIn);
  if (cursorOpacity <= 0.01) return null;

  const lastClick = [...moves].reverse().find((action) => action.kind === "click" && action.t <= outMs + 120);
  const sinceClick = lastClick ? outMs - lastClick.t : Infinity;
  // Pressed while the picture is held at the click (clickHoldMs, edit.ts) or while dragging
  const press = (sinceClick > -60 && sinceClick < 380) || dragging ? 0.82 : 1;
  // Keeps a steady size on screen as the camera zooms
  const size = 30 / Math.sqrt(zoom);
  return (
    <div style={{ opacity: cursorOpacity }}>
      {sinceClick >= 0 && sinceClick < CLICK_RIPPLE_MS && lastClick && (
        <div
          style={{
            position: "absolute",
            left: lastClick.x,
            top: lastClick.y,
            width: 0,
            height: 0,
          }}
        >
          {/* A soft disc where it was clicked, and a ring spreading from it: clear on a small button too */}
          <div
            style={{
              position: "absolute",
              left: -14,
              top: -14,
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: theme.accent,
              opacity: interpolate(sinceClick, [0, CLICK_RIPPLE_MS], [0.35, 0]),
            }}
          />
          <div
            style={{
              position: "absolute",
              left: -interpolate(sinceClick, [0, CLICK_RIPPLE_MS], [8, 44]),
              top: -interpolate(sinceClick, [0, CLICK_RIPPLE_MS], [8, 44]),
              width: 2 * interpolate(sinceClick, [0, CLICK_RIPPLE_MS], [8, 44]),
              height: 2 * interpolate(sinceClick, [0, CLICK_RIPPLE_MS], [8, 44]),
              borderRadius: "50%",
              border: `4px solid ${theme.accent}`,
              opacity: interpolate(sinceClick, [0, CLICK_RIPPLE_MS], [0.95, 0]),
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
    </div>
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

// At most two lines at a time: a long narration line is shown in parts, in step with the voice
const Captions = ({ edit, outMs }: { edit: Edit; outMs: number }) => {
  const cues = useMemo(
    () =>
      edit.narration.flatMap((line) =>
        captionCues(line).map((cue) => ({ ...cue, start: line.start + cue.start, end: line.start + cue.end })),
      ),
    [edit],
  );
  const current = cues.find((cue) => outMs >= cue.start && outMs <= cue.end);
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
          background: "rgba(10,12,16,0.88)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,0.12)",
          boxShadow: "0 14px 36px rgba(0,0,0,0.45)",
          color: "white",
          fontSize: 36,
          lineHeight: 1.35,
          padding: "14px 28px",
          borderRadius: 14,
          textAlign: "center",
        }}
      >
        {current.lines.map((line, index) => (
          <div key={index} style={{ whiteSpace: "nowrap" }}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
};

// Only in Remotion Studio, never in the video: the step being shown, by the name the timing file uses
// (scripts/<name>.timing.ts), and what the edit warns about
const StepBadge = ({ timeline, edit, srcMs }: { timeline: Timeline; edit: Edit; srcMs: number }) => {
  const step = lastAtOrBefore(timeline.steps, srcMs + STEP_LEAD_MS);
  return (
    <div
      style={{
        position: "absolute",
        left: 12,
        top: 12,
        maxWidth: 900,
        background: "rgba(2,6,23,0.85)",
        color: "white",
        fontFamily: "monospace",
        fontSize: 18,
        padding: "8px 12px",
        borderRadius: 8,
        pointerEvents: "none",
      }}
    >
      <div style={{ fontWeight: 700 }}>{step ? step.id : "before the first step"}</div>
      {step && <div style={{ opacity: 0.75, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{step.label}</div>}
      {edit.warnings.map((warning) => (
        <div key={warning} style={{ color: "#fbbf24", marginTop: 4 }}>
          {warning}
        </div>
      ))}
    </div>
  );
};

// Above the window: the logo, and which tutorial this is
const Header = ({
  left,
  width,
  series,
  title,
  chapter,
}: {
  left: number;
  width: number;
  series?: string;
  title: string;
  chapter?: string;
}) => {
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
        {chapter && <span style={{ color: theme.muted, fontWeight: 500 }}>› {chapter}</span>}
      </div>
    </div>
  );
};

// When a phase starts: its name slides in at the bottom left for a few seconds
const CHAPTER_LABEL_MS = 3200;
const ChapterLabel = ({ title, sinceMs, left, bottom }: { title: string; sinceMs: number; left: number; bottom: number }) => {
  if (sinceMs < 0 || sinceMs > CHAPTER_LABEL_MS) return null;
  const enter = interpolate(sinceMs, [0, 450], [0, 1], { extrapolateRight: "clamp", easing: theme.ease });
  const leave = interpolate(sinceMs, [CHAPTER_LABEL_MS - 400, CHAPTER_LABEL_MS], [1, 0], { extrapolateLeft: "clamp" });
  return (
    <div
      style={{
        position: "absolute",
        left,
        bottom,
        opacity: Math.min(enter, leave),
        transform: `translateX(${(1 - enter) * -40}px)`,
        display: "flex",
        alignItems: "stretch",
        boxShadow: "0 16px 40px rgba(0,0,0,0.45)",
        border: "1px solid rgba(255,255,255,0.12)",
        borderRadius: 12,
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      <div style={{ width: 8, background: theme.accent }} />
      <div style={{ background: "rgba(10,12,16,0.92)", backdropFilter: "blur(12px)", padding: "16px 28px" }}>
        <div style={{ color: theme.accent, fontSize: 18, fontWeight: 700, letterSpacing: 3, textTransform: "uppercase" }}>
          Next step
        </div>
        <div style={{ color: theme.text, fontSize: 38, fontWeight: 700, marginTop: 4 }}>{title}</div>
      </div>
    </div>
  );
};

// A text overlay or callout card over the page (without dimming the whole page), from overlay() or added in the timing editor
const OverlayCard = ({
  overlay,
  outMs,
  windowLeft,
  windowWidth,
}: {
  overlay: PlacedOverlay;
  outMs: number;
  windowLeft: number;
  windowWidth: number;
}) => {
  const sinceMs = outMs - overlay.start;
  if (sinceMs < 0 || sinceMs > overlay.durationMs) return null;
  const fadeMs = Math.min(350, overlay.durationMs / 4);
  const enter = interpolate(sinceMs, [0, fadeMs], [0, 1], { extrapolateRight: "clamp", easing: theme.ease });
  const leave = interpolate(sinceMs, [overlay.durationMs - fadeMs, overlay.durationMs], [1, 0], {
    extrapolateLeft: "clamp",
  });
  const opacity = Math.min(enter, leave);
  const isCenter = overlay.position === "center";
  const isLeft = overlay.position === "top-left" || overlay.position === "bottom-left";
  const isTop = overlay.position === "top-left" || overlay.position === "top-right";
  const slideX = isCenter ? 0 : (1 - enter) * (isLeft ? -32 : 32);
  const slideY = isCenter ? (1 - enter) * 20 : 0;

  const lines = overlay.text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (isCenter) {
    return (
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            maxWidth: 920,
            minWidth: 480,
            background: "rgba(10,12,16,0.94)",
            backdropFilter: "blur(16px)",
            border: "1px solid rgba(255,255,255,0.14)",
            borderTop: `6px solid ${theme.accent}`,
            borderRadius: 18,
            padding: "32px 44px",
            boxShadow: "0 28px 80px rgba(0,0,0,0.65)",
            transform: `translateY(${slideY}px)`,
          }}
        >
          {overlay.title && (
            <div
              style={{
                color: theme.accent,
                fontSize: 20,
                fontWeight: 700,
                letterSpacing: 3,
                textTransform: "uppercase",
                marginBottom: 10,
              }}
            >
              {overlay.title}
            </div>
          )}
          <div style={{ color: theme.text, fontSize: 34, fontWeight: 600, lineHeight: 1.38 }}>
            {lines.map((line, index) => (
              <div key={index} style={{ marginTop: index > 0 ? 10 : 0 }}>
                {line}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "absolute",
        ...(isLeft ? { left: windowLeft + 36 } : { left: windowLeft + windowWidth - 36 }),
        ...(isTop ? { top: WINDOW_MARGIN.top + 32 } : { bottom: WINDOW_MARGIN.bottom + 205 }),
        transform: `translate(${isLeft ? "0" : "-100%"}, 0) translateX(${slideX}px)`,
        opacity,
        maxWidth: 620,
        display: "flex",
        alignItems: "stretch",
        boxShadow: "0 18px 48px rgba(0,0,0,0.5)",
        border: "1px solid rgba(255,255,255,0.14)",
        borderRadius: 14,
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      <div style={{ width: 7, background: theme.accent, flexShrink: 0 }} />
      <div style={{ background: "rgba(10,12,16,0.92)", backdropFilter: "blur(14px)", padding: "18px 26px" }}>
        {overlay.title && (
          <div
            style={{
              color: theme.accent,
              fontSize: 17,
              fontWeight: 700,
              letterSpacing: 2.5,
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            {overlay.title}
          </div>
        )}
        <div style={{ color: theme.text, fontSize: 28, fontWeight: 600, lineHeight: 1.35 }}>
          {lines.map((line, index) => (
            <div key={index} style={{ marginTop: index > 0 ? 6 : 0 }}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
