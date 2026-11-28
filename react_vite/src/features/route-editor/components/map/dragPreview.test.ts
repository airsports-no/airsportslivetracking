import { describe, expect, it, vi } from 'vitest';
import type L from 'leaflet';
import type { ObservationMarker, RoutePoint } from '../../../../types';
import { createDragPreview, FADED_OPACITY } from './dragPreview';

const point = (id: string, lat: number, lng: number, type: RoutePoint['type'] = 'tp'): RoutePoint => ({
  id, name: id, lat, lng, type, width: 1852, isTiming: true, isPassing: true, segmentType: 'straight',
});

// A mark as Leaflet has it, as far as the preview uses it
const mark = () => {
  const layer = { options: { interactive: false, opacity: 1, fillOpacity: 0.8 }, setStyle: vi.fn(), getTooltip: () => null };
  return layer;
};

describe('the preview of what a drag removes', () => {
  const before = [point('a', 60, 11, 'sp'), point('s', 60, 11.05, 'secret'), point('b', 60, 11.1, 'fp')];
  const photo: ObservationMarker = { id: 'p', name: 'Obs 1', lat: 59.995, lng: 11.05 };

  it('fades the hidden gate and the photo that dropping the point there would remove, and restores them', () => {
    const gateMark = mark();
    const photoMark = mark();
    const markers = {
      'point-s': { eachLayer: (callback: (layer: unknown) => void) => callback(gateMark) },
      'obs-p': photoMark,
    } as unknown as { [key: string]: L.Layer };
    const preview = createDragPreview({ current: markers }, before, [photo], 926);

    // Still on the same line: nothing is faded
    preview.update(before);
    expect(gateMark.setStyle).not.toHaveBeenCalled();

    preview.update(before.map((item) => (item.id === 'b' ? { ...item, lat: 60.1 } : item)));
    expect(gateMark.setStyle).toHaveBeenLastCalledWith({ opacity: FADED_OPACITY, fillOpacity: 0.8 * FADED_OPACITY });
    expect(photoMark.setStyle).toHaveBeenCalledTimes(1);

    // Moved back: shown as before
    preview.update(before);
    expect(gateMark.setStyle).toHaveBeenLastCalledWith({ opacity: 1, fillOpacity: 0.8 });
    expect(photoMark.setStyle).toHaveBeenLastCalledWith({ opacity: 1, fillOpacity: 0.8 });
  });
});
