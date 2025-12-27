export const EARTH_RADIUS = 6371e3; // meters

export const toRad = (val) => (val * Math.PI) / 180;
export const toDeg = (val) => (val * 180) / Math.PI;

// Calculate distance between two lat/lng points in meters
export const getDistance = (p1, p2) => {
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

export const getBearing = (p1, p2) => {
  const φ1 = toRad(p1.lat);
  const φ2 = toRad(p2.lat);
  const Δλ = toRad(p2.lng - p1.lng);

  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) -
            Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  const θ = Math.atan2(y, x);
  return (toDeg(θ) + 360) % 360;
};

export const getDestinationPoint = (p, distance, bearing) => {
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

// Check if point B is roughly on the line segment AC
export const isCollinear = (a, b, c, toleranceMeters = 50) => {
  const distAC = getDistance(a, c);
  const distAB = getDistance(a, b);
  const distBC = getDistance(b, c);
  // If AB + BC is roughly equal to AC, then B is on the line
  return Math.abs((distAB + distBC) - distAC) < toleranceMeters;
};

export const getDistanceFromLine = (p, start, end) => {
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
export const isPointInPolygon = (point, vs) => {
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

export function getQuadraticBezierPoints(p1, p2, control, numPoints = 20) {
  const points = [];
  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints;
    const lat = (1 - t) * (1 - t) * p1.lat + 2 * (1 - t) * t * control.lat + t * t * p2.lat;
    const lng = (1 - t) * (1 - t) * p1.lng + 2 * (1 - t) * t * control.lng + t * t * p2.lng;
    points.push(L.latLng(lat, lng));
  }
  return points;
}