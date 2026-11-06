import { LatLng } from "../types";

export const EARTH_RADIUS = 6371e3; // meters

export const toRad = (val: number) => (val * Math.PI) / 180;
export const toDeg = (val: number) => (val * 180) / Math.PI;

// Calculate distance between two lat/lng points in meters

export function getAngleDiff(a: number, b: number) {
  let diff = a - b;
  while (diff > 180) diff -= 360;
  while (diff < -180) diff += 360;
  return diff;
}

export const getDistance = (p1: LatLng, p2: LatLng) => {
  const R = EARTH_RADIUS;
  const φ1 = toRad(p1.lat);
  const φ2 = toRad(p2.lat);
  const Δφ = toRad(p2.lat - p1.lat);
  const Δλ = toRad(p2.lng - p1.lng);

  const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
};

export const getBearing = (p1: LatLng, p2: LatLng) => {
  const φ1 = toRad(p1.lat);
  const φ2 = toRad(p2.lat);
  const Δλ = toRad(p2.lng - p1.lng);

  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) -
            Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  const θ = Math.atan2(y, x);
  return (toDeg(θ) + 360) % 360;
};

export const getDestinationPoint = (p: LatLng, distance: number, bearing: number) => {
  const R = EARTH_RADIUS;
  const δ = distance / R;
  const θ = toRad(bearing);
  const φ1 = toRad(p.lat);
  const λ1 = toRad(p.lng);

  const φ2 = Math.asin(Math.sin(φ1) * Math.cos(δ) +
                       Math.cos(φ1) * Math.sin(δ) * Math.cos(θ));
  const λ2 = λ1 + Math.atan2(Math.sin(θ) * Math.sin(δ) * Math.cos(φ1),
                             Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2));
  
  return { lat: toDeg(φ2), lng: toDeg(λ2) };
};

/** The point a fraction (0 to 1) of the way along the great circle from a to b. */
export const getIntermediatePoint = (a: LatLng, b: LatLng, fraction: number): LatLng => {
  const δ = getDistance(a, b) / EARTH_RADIUS;
  if (δ < 1e-12) return { lat: a.lat, lng: a.lng };
  const φ1 = toRad(a.lat);
  const λ1 = toRad(a.lng);
  const φ2 = toRad(b.lat);
  const λ2 = toRad(b.lng);
  const A = Math.sin((1 - fraction) * δ) / Math.sin(δ);
  const B = Math.sin(fraction * δ) / Math.sin(δ);
  const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
  const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
  const z = A * Math.sin(φ1) + B * Math.sin(φ2);
  return { lat: toDeg(Math.atan2(z, Math.sqrt(x * x + y * y))), lng: toDeg(Math.atan2(y, x)) };
};

/**
 * The great circle from one point to another, as the points after `from` up to and including `to`. A leg of the route
 * is the great circle between its gates (that is what is scored), but a map draws a line between two points straight on
 * the flat map, which is up to tens of metres off it on a long leg: a gate placed on the leg then looks like a bend.
 * Drawing the leg through points along the great circle shows it where it is.
 */
export const getGreatCirclePoints = (from: LatLng, to: LatLng, maxSegmentMeters = 1000): LatLng[] => {
  const segments = Math.min(200, Math.max(1, Math.ceil(getDistance(from, to) / maxSegmentMeters)));
  const points: LatLng[] = [];
  for (let step = 1; step < segments; step += 1) {
    points.push(getIntermediatePoint(from, to, step / segments));
  }
  points.push({ lat: to.lat, lng: to.lng });
  return points;
};

// Check if point B is roughly on the line segment AC
export const isCollinear = (a: LatLng, b: LatLng, c: LatLng, toleranceMeters = 50) => {
  const distAC = getDistance(a, c);
  const distAB = getDistance(a, b);
  const distBC = getDistance(b, c);
  // If AB + BC is roughly equal to AC, then B is on the line
  return Math.abs((distAB + distBC) - distAC) < toleranceMeters;
};

export const getDistanceFromLine = (p: LatLng, start: LatLng, end: LatLng) => {
  const dStart = getDistance(p, start);
  const dLine = getDistance(start, end);
  
  if (dLine === 0) return dStart;

  const R = EARTH_RADIUS;
  const dStartRad = dStart / R;
  const bearingLine = toRad(getBearing(start, end));
  const bearingPoint = toRad(getBearing(start, p));
  
  // Cross-track distance
  const crossTrackDist = Math.asin(Math.sin(dStartRad) * Math.sin(bearingPoint - bearingLine)) * R;
  
  // Along-track distance
  const alongTrackDist = Math.atan(Math.tan(dStartRad) * Math.cos(bearingPoint - bearingLine)) * R;

  if (alongTrackDist < 0) return dStart;
  if (alongTrackDist > dLine) return getDistance(p, end);
  
  return Math.abs(crossTrackDist);
};

// Check if a point is inside a polygon (Ray Casting Algorithm)
export const isPointInPolygon = (point: LatLng, vs: LatLng[]) => {
  const x = point.lat, y = point.lng;
  let inside = false;
  for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
    const xi = vs[i].lat, yi = vs[i].lng;
    const xj = vs[j].lat, yj = vs[j].lng;
    
    const intersect = ((yi > y) !== (yj > y))
        && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
};

