import { describe, expect, it } from 'vitest';
import { hasDraggedPastThreshold, MID_LEG_DRAG_THRESHOLD_PX } from './midLegDrag';

describe('hasDraggedPastThreshold', () => {
  const start = { x: 100, y: 100 };

  it('is not a drag when the pointer has not moved', () => {
    expect(hasDraggedPastThreshold(start, start)).toBe(false);
  });

  it('is not a drag within the threshold, in any direction', () => {
    expect(hasDraggedPastThreshold(start, { x: 100 + MID_LEG_DRAG_THRESHOLD_PX, y: 100 })).toBe(false);
    expect(hasDraggedPastThreshold(start, { x: 98, y: 98 })).toBe(false);
  });

  it('is a drag beyond the threshold, measured as a distance', () => {
    expect(hasDraggedPastThreshold(start, { x: 100, y: 100 + MID_LEG_DRAG_THRESHOLD_PX + 1 })).toBe(true);
    expect(hasDraggedPastThreshold(start, { x: 103, y: 103 })).toBe(true);
  });
});
