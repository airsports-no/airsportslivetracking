import {
  EARTH_RADIUS,
  toRad,
  toDeg,
  getAngleDiff,
  getDistance,
  getBearing,
  getDestinationPoint,
  isCollinear,
  getDistanceFromLine,
  isPointInPolygon,
} from './geoUtils';

describe('toRad / toDeg', () => {
  it('converts degrees to radians', () => {
    expect(toRad(180)).toBeCloseTo(Math.PI);
    expect(toRad(0)).toBe(0);
  });

  it('converts radians to degrees', () => {
    expect(toDeg(Math.PI)).toBeCloseTo(180);
    expect(toDeg(0)).toBe(0);
  });

  it('round-trips', () => {
    expect(toDeg(toRad(37.5))).toBeCloseTo(37.5);
  });
});

describe('getAngleDiff', () => {
  it('returns the plain difference when already within [-180, 180]', () => {
    expect(getAngleDiff(90, 80)).toBe(10);
    expect(getAngleDiff(10, 20)).toBe(-10);
  });

  it('wraps a difference greater than 180 down into range', () => {
    expect(getAngleDiff(350, 10)).toBe(-20);
  });

  it('wraps a difference less than -180 up into range', () => {
    expect(getAngleDiff(10, 350)).toBe(20);
  });

  it('returns 0 for identical angles', () => {
    expect(getAngleDiff(45, 45)).toBe(0);
  });
});

describe('getDistance', () => {
  it('returns 0 for identical points', () => {
    expect(getDistance({ lat: 60, lng: 11 }, { lat: 60, lng: 11 })).toBe(0);
  });

  it('matches the known 1-degree-of-latitude distance (~111.19 km)', () => {
    const distance = getDistance({ lat: 0, lng: 0 }, { lat: 1, lng: 0 });
    expect(distance).toBeCloseTo(111194.9, -1);
  });

  it('is symmetric', () => {
    const p1 = { lat: 60.1, lng: 11.2 };
    const p2 = { lat: 60.3, lng: 11.5 };
    expect(getDistance(p1, p2)).toBeCloseTo(getDistance(p2, p1));
  });
});

describe('getBearing', () => {
  it('returns 0 (due north) for a point directly north', () => {
    expect(getBearing({ lat: 60, lng: 11 }, { lat: 61, lng: 11 })).toBeCloseTo(0, 5);
  });

  it('returns 90 (due east) for a point directly east on the equator', () => {
    expect(getBearing({ lat: 0, lng: 0 }, { lat: 0, lng: 1 })).toBeCloseTo(90, 5);
  });

  it('returns 180 (due south) for a point directly south', () => {
    expect(getBearing({ lat: 60, lng: 11 }, { lat: 59, lng: 11 })).toBeCloseTo(180, 5);
  });

  it('returns 270 (due west) for a point directly west on the equator', () => {
    expect(getBearing({ lat: 0, lng: 1 }, { lat: 0, lng: 0 })).toBeCloseTo(270, 5);
  });

  it('always returns a value in [0, 360)', () => {
    const bearing = getBearing({ lat: 10, lng: 10 }, { lat: 9, lng: 9 });
    expect(bearing).toBeGreaterThanOrEqual(0);
    expect(bearing).toBeLessThan(360);
  });
});

describe('getDestinationPoint', () => {
  it('returns the origin unchanged for distance 0', () => {
    const origin = { lat: 60, lng: 11 };
    const destination = getDestinationPoint(origin, 0, 45);
    expect(destination.lat).toBeCloseTo(origin.lat);
    expect(destination.lng).toBeCloseTo(origin.lng);
  });

  it('moving north by a known distance increases latitude by the expected amount', () => {
    const destination = getDestinationPoint({ lat: 0, lng: 0 }, 111194.9, 0);
    expect(destination.lat).toBeCloseTo(1, 3);
    expect(destination.lng).toBeCloseTo(0, 3);
  });

  it('is the inverse of getDistance/getBearing (round trip)', () => {
    const origin = { lat: 60.2, lng: 11.3 };
    const bearing = 123.4;
    const distance = 5000;
    const destination = getDestinationPoint(origin, distance, bearing);
    expect(getDistance(origin, destination)).toBeCloseTo(distance, 0);
    expect(getBearing(origin, destination)).toBeCloseTo(bearing, 3);
  });
});

describe('isCollinear', () => {
  it('is true for a point exactly on the segment', () => {
    const a = { lat: 60, lng: 11 };
    const c = { lat: 60, lng: 12 };
    const b = getDestinationPoint(a, getDistance(a, c) / 2, getBearing(a, c));
    expect(isCollinear(a, b, c)).toBe(true);
  });

  it('is false for a point far off the segment', () => {
    const a = { lat: 60, lng: 11 };
    const c = { lat: 60, lng: 12 };
    const farPoint = { lat: 65, lng: 11.5 };
    expect(isCollinear(a, farPoint, c)).toBe(false);
  });

  it('respects a wider tolerance', () => {
    const a = { lat: 60, lng: 11 };
    const c = { lat: 60, lng: 12 };
    // isCollinear measures triangle-inequality path excess (distAB + distBC
    // - distAC), not perpendicular distance - for this segment/offset it
    // works out to ~161m, verified numerically rather than assumed.
    const offsetPoint = { lat: 60.02, lng: 11.5 };
    expect(isCollinear(a, offsetPoint, c, 50)).toBe(false);
    expect(isCollinear(a, offsetPoint, c, 200)).toBe(true);
  });
});

describe('getDistanceFromLine', () => {
  const start = { lat: 60, lng: 11 };
  const end = { lat: 60, lng: 12 };

  it('returns the distance to the start point when start and end coincide', () => {
    const point = { lat: 61, lng: 11 };
    expect(getDistanceFromLine(point, start, start)).toBeCloseTo(getDistance(point, start));
  });

  it('returns ~0 for a point on the line', () => {
    const midpoint = getDestinationPoint(start, getDistance(start, end) / 2, getBearing(start, end));
    expect(getDistanceFromLine(midpoint, start, end)).toBeCloseTo(0, -1);
  });

  it('falls back to distance-to-start when the closest approach is before the segment starts', () => {
    const beforeStart = getDestinationPoint(start, 10000, getBearing(end, start));
    expect(getDistanceFromLine(beforeStart, start, end)).toBeCloseTo(getDistance(beforeStart, start), -1);
  });

  it('falls back to distance-to-end when the closest approach is past the segment end', () => {
    const pastEnd = getDestinationPoint(end, 10000, getBearing(start, end));
    expect(getDistanceFromLine(pastEnd, start, end)).toBeCloseTo(getDistance(pastEnd, end), -1);
  });

  it('returns a meaningful positive distance for a point off to the side', () => {
    const midpoint = getDestinationPoint(start, getDistance(start, end) / 2, getBearing(start, end));
    const offToTheSide = getDestinationPoint(midpoint, 500, getBearing(start, end) + 90);
    expect(getDistanceFromLine(offToTheSide, start, end)).toBeCloseTo(500, -1);
  });
});

describe('isPointInPolygon', () => {
  const square = [
    { lat: 0, lng: 0 },
    { lat: 0, lng: 10 },
    { lat: 10, lng: 10 },
    { lat: 10, lng: 0 },
  ];

  it('is true for a point well inside the polygon', () => {
    expect(isPointInPolygon({ lat: 5, lng: 5 }, square)).toBe(true);
  });

  it('is false for a point well outside the polygon', () => {
    expect(isPointInPolygon({ lat: 20, lng: 20 }, square)).toBe(false);
  });

  it('is false for an empty polygon', () => {
    expect(isPointInPolygon({ lat: 5, lng: 5 }, [])).toBe(false);
  });
});

describe('EARTH_RADIUS', () => {
  it('is the standard mean Earth radius in meters', () => {
    expect(EARTH_RADIUS).toBe(6371e3);
  });
});
