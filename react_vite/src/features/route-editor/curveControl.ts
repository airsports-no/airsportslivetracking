import type { RoutePoint } from '../../types';

type WithControl<T> = T & { controlLat: number; controlLng: number };

// Whether the leg that ends at [point] has a control point. Zero is a coordinate like any other (a curve can have its
// control on the equator or the prime meridian), so the test is for a value, not for a truthy one.
export const hasControl = <T extends Pick<RoutePoint, 'controlLat' | 'controlLng'>>(point: T): point is WithControl<T> =>
  point.controlLat != null && point.controlLng != null;
