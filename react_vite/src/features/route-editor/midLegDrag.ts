// The blue dot at the middle of a straight leg adds a waypoint only when it is dragged. A press and release without
// movement does nothing (no waypoint, nothing removed, no undo step), only a hint.

// Pointer movement (in screen pixels) from which a press on the dot counts as a drag.
export const MID_LEG_DRAG_THRESHOLD_PX = 4;

export const MID_LEG_DOT_HINT = 'Drag the dot to add a waypoint';

interface ScreenPoint {
  x: number;
  y: number;
}

// Whether the pointer has moved from [start] to [current] far enough to count as a drag.
export const hasDraggedPastThreshold = (
  start: ScreenPoint,
  current: ScreenPoint,
  threshold: number = MID_LEG_DRAG_THRESHOLD_PX,
): boolean => Math.hypot(current.x - start.x, current.y - start.y) > threshold;
