import type L from 'leaflet';
import type { ObservationMarker, RoutePoint } from '../../../../types';
import { createRouteIntegrityCheck, joinCurvesOverRemovedGates } from '../../routeIntegrity';

// While a waypoint or a curve handle is dragged: the hidden gates and photos that dropping it where it is would remove
// are drawn faded. It works on the Leaflet layers directly (no React state on a mouse move) and only works out the legs
// that moved (see createRouteIntegrityCheck).

export const FADED_OPACITY = 0.35;

interface Fadable {
  options?: { interactive?: boolean; opacity?: number; fillOpacity?: number };
  setStyle?: (style: { opacity?: number; fillOpacity?: number }) => unknown;
  getTooltip?: () => { setOpacity: (opacity: number) => unknown } | undefined | null;
  eachLayer?: (callback: (layer: Fadable) => void) => unknown;
}

// What it takes to put a layer back as it was.
type Restore = () => void;

const fadeLayer = (layer: Fadable, restores: Restore[]) => {
  // The invisible hit areas stay as they are (they are interactive); the marks are not
  if (layer.options?.interactive === false && layer.setStyle) {
    const opacity = layer.options.opacity ?? 1;
    const fillOpacity = layer.options.fillOpacity ?? 0.2;
    layer.setStyle({ opacity: opacity * FADED_OPACITY, fillOpacity: fillOpacity * FADED_OPACITY });
    restores.push(() => layer.setStyle?.({ opacity, fillOpacity }));
  }
  const tooltip = layer.getTooltip?.();
  if (tooltip) {
    tooltip.setOpacity(FADED_OPACITY);
    restores.push(() => tooltip.setOpacity(1));
  }
};

const fade = (layer: Fadable | undefined): Restore[] => {
  const restores: Restore[] = [];
  if (!layer) return restores;
  if (layer.eachLayer) layer.eachLayer((member) => fadeLayer(member, restores));
  else fadeLayer(layer, restores);
  return restores;
};

export interface DragPreview {
  // Fades what the route [after] (the dragged point at its current place) would remove, and shows the rest as it is.
  // Returns the route as the drop will leave it: without the removed hidden gates, and with the curves they split
  // joined into one (so the leg can be drawn as it will be).
  update: (after: RoutePoint[]) => RoutePoint[];
  // Everything as it was.
  clear: () => void;
}

export const createDragPreview = (
  markersRef: { current: { [key: string]: L.Layer } },
  before: RoutePoint[],
  photos: ObservationMarker[],
  maxObsDist: number,
): DragPreview => {
  const check = createRouteIntegrityCheck(before, photos, maxObsDist);
  const faded = new Map<string, Restore[]>();

  const clear = () => {
    faded.forEach((restores) => restores.forEach((restore) => restore()));
    faded.clear();
  };

  const update = (after: RoutePoint[]) => {
    const removal = check(after);
    const wanted = new Map<string, string[]>();
    removal.hiddenGates.forEach((gate) => wanted.set(`point-${gate.id}`, [`point-${gate.id}`]));
    removal.photos.forEach((photo) => wanted.set(`obs-${photo.id}`, [`obs-${photo.id}`, `obs-hit-${photo.id}`]));

    faded.forEach((restores, key) => {
      if (wanted.has(key)) return;
      restores.forEach((restore) => restore());
      faded.delete(key);
    });
    wanted.forEach((layerKeys, key) => {
      if (faded.has(key)) return;
      faded.set(key, layerKeys.flatMap((layerKey) => fade(markersRef.current[layerKey] as unknown as Fadable)));
    });

    if (removal.hiddenGates.length === 0) return after;
    const removedIds = new Set(removal.hiddenGates.map((gate) => gate.id));
    return joinCurvesOverRemovedGates(after.filter((point) => !removedIds.has(point.id)), after, removedIds);
  };

  return { update, clear };
};
