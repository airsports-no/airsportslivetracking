import { isHidden, type Box, type Timeline } from "./timeline";
import type { Edit } from "./edit";

// The automatic zoom: the camera moves in on what is being clicked, typed in or highlighted, stays while the work
// continues nearby, and zooms back out when nothing happens for a while, the next target is far away, or the element
// is large anyway (a map). Times here are video times (after the cuts).

export type CameraState = { zoom: number; cx: number; cy: number };
type Keyframe = CameraState & { t: number };

export const CAMERA = {
  maxZoom: 1.9,
  // Space kept around the framed element, as a factor of its size
  padding: 3.2,
  // A clicked point with no element box is framed as this area
  pointBox: { width: 360, height: 220 },
  transitionMs: 750,
  // Zoom out when the next target is further off than this
  idleZoomOutMs: 2600,
  holdAfterMs: 1400,
};

const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

function framing(box: Box, viewport: Timeline["viewport"]): CameraState {
  const zoom = Math.max(
    1,
    Math.min(
      CAMERA.maxZoom,
      viewport.width / (box.width * CAMERA.padding),
      viewport.height / (box.height * CAMERA.padding),
    ),
  );
  return clamp({ zoom, cx: box.x + box.width / 2, cy: box.y + box.height / 2 }, viewport);
}

function clamp(state: CameraState, viewport: Timeline["viewport"]): CameraState {
  const halfWidth = viewport.width / (2 * state.zoom);
  const halfHeight = viewport.height / (2 * state.zoom);
  return {
    zoom: state.zoom,
    cx: Math.min(viewport.width - halfWidth, Math.max(halfWidth, state.cx)),
    cy: Math.min(viewport.height - halfHeight, Math.max(halfHeight, state.cy)),
  };
}

export function planCamera(timeline: Timeline, edit: Edit): (outMs: number) => CameraState {
  const { viewport } = timeline;
  const wide: CameraState = { zoom: 1, cx: viewport.width / 2, cy: viewport.height / 2 };
  const isWide = (srcT: number) => {
    const last = timeline.camera.filter((directive) => directive.t <= srcT).pop();
    return last?.mode === "wide";
  };
  const targets = [
    // Scrolling moves the page under the camera, it is not something to look at
    ...timeline.actions
      .filter((action) => action.kind !== "scroll" && !isHidden(timeline, action.t))
      .map((action) => ({
      t: action.t,
      box: action.box ?? {
        x: action.x - CAMERA.pointBox.width / 2,
        y: action.y - CAMERA.pointBox.height / 2,
        ...CAMERA.pointBox,
      },
      endT: action.t,
    })),
    ...timeline.highlights
      .filter((item) => !isHidden(timeline, item.t))
      .map((item) => ({ t: item.t, box: item.box, endT: item.t + item.durationMs })),
  ].sort((a, b) => a.t - b.t);

  const keyframes: Keyframe[] = [{ t: 0, ...wide }];
  targets.forEach((target, index) => {
    const t = edit.toOut(target.t);
    const state = isWide(target.t) ? wide : framing(target.box, viewport);
    keyframes.push({ t, ...state });
    const next = targets[index + 1];
    const endT = edit.toOut(target.endT);
    if (!next || edit.toOut(next.t) - endT > CAMERA.idleZoomOutMs) {
      keyframes.push({ t: endT + CAMERA.holdAfterMs + CAMERA.transitionMs, ...wide });
    }
  });

  keyframes.sort((a, b) => a.t - b.t);

  // Each keyframe is reached at its time, moving there over the transition before it, from wherever the camera is
  // when that transition starts (a previous move may not have finished)
  const startStates: CameraState[] = [keyframes[0]];
  const evaluate = (index: number, outMs: number): CameraState => {
    const current = keyframes[index];
    if (index === 0) return current;
    const start = current.t - CAMERA.transitionMs;
    const from = startStates[index];
    const progress = easeInOut(Math.min(1, Math.max(0, (outMs - start) / CAMERA.transitionMs)));
    // Zoom moves in log space so zooming in and out feel equally fast
    const zoom = Math.exp(Math.log(from.zoom) + (Math.log(current.zoom) - Math.log(from.zoom)) * progress);
    return clamp(
      { zoom, cx: from.cx + (current.cx - from.cx) * progress, cy: from.cy + (current.cy - from.cy) * progress },
      viewport,
    );
  };
  for (let index = 1; index < keyframes.length; index++) {
    startStates[index] = evaluate(index - 1, keyframes[index].t - CAMERA.transitionMs);
  }
  return (outMs: number) => {
    let index = 0;
    while (index + 1 < keyframes.length && keyframes[index + 1].t - CAMERA.transitionMs <= outMs) index++;
    return evaluate(index, outMs);
  };
}
