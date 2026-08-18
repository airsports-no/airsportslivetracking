import { parseRouteEditorFeatureCollection, createStandalonePointTypeSet } from './routeDataParsing';

function pointFeature(overrides: Record<string, any> = {}) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [11.1, 60.1] },
    properties: {
      id: 'p1',
      featureType: 'route_waypoint',
      pointType: 'tp',
      name: 'WP',
      sequence: 0,
      ...overrides,
    },
  };
}

describe('createStandalonePointTypeSet', () => {
  it('includes the catalogue/circle/dummy/timed-turnpoint standalone types', () => {
    const types = createStandalonePointTypeSet(true);
    expect(types.has('catalogue_turnpoint')).toBe(true);
    expect(types.has('dummy')).toBe(true);
    expect(types.has('timed_turnpoint')).toBe(true);
    expect(types.has('circle_center')).toBe(true);
    expect(types.has('circle_start')).toBe(true);
    expect(types.has('circle_entry')).toBe(true);
    expect(types.has('circle_exit')).toBe(true);
  });

  it('does not include ordinary backbone point types', () => {
    const types = createStandalonePointTypeSet(true);
    expect(types.has('sp')).toBe(false);
    expect(types.has('tp')).toBe(false);
    expect(types.has('fp')).toBe(false);
  });

  it('returns the same set regardless of the isCircleStandaloneTask flag', () => {
    // The flag is currently unused (parameter is prefixed `_`) - the set is
    // always the union of catalogue/dummy/timed_turnpoint/circle-standalone
    // types, not conditional on task type.
    const withCircle = createStandalonePointTypeSet(true);
    const withoutCircle = createStandalonePointTypeSet(false);
    expect(Array.from(withoutCircle).sort()).toEqual(Array.from(withCircle).sort());
  });
});

describe('parseRouteEditorFeatureCollection', () => {
  const standaloneTypes = createStandalonePointTypeSet(true);

  it('returns an all-empty result for a non-FeatureCollection payload', () => {
    const result = parseRouteEditorFeatureCollection({ type: 'Feature' }, standaloneTypes);
    expect(result).toEqual({
      routePoints: [],
      standalonePoints: [],
      gates: [],
      observationMarkers: [],
      polygons: [],
      bounds: null,
    });
  });

  it('returns an all-empty result for null/undefined input', () => {
    expect(parseRouteEditorFeatureCollection(null, standaloneTypes).bounds).toBeNull();
    expect(parseRouteEditorFeatureCollection(undefined, standaloneTypes).routePoints).toEqual([]);
  });

  it('sorts route_waypoint points by sequence and buckets them into routePoints', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        pointFeature({ id: 'fp', pointType: 'fp', name: 'FP', sequence: 2 }),
        pointFeature({ id: 'sp', pointType: 'sp', name: 'SP', sequence: 0 }),
        pointFeature({ id: 'tp', pointType: 'tp', name: 'TP', sequence: 1 }),
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.routePoints.map((p) => p.id)).toEqual(['sp', 'tp', 'fp']);
    expect(result.standalonePoints).toEqual([]);
  });

  it('buckets standalone-lane point types (catalogue/circle markers) into standalonePoints, not routePoints', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        pointFeature({ id: 'sp', pointType: 'sp', sequence: 0 }),
        pointFeature({ id: 'cat', pointType: 'catalogue_turnpoint', featureType: 'catalogue_turnpoint', sequence: 1 }),
        pointFeature({ id: 'cc', pointType: 'circle_center', featureType: 'circle_center_marker', sequence: 2 }),
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.routePoints.map((p) => p.id)).toEqual(['sp']);
    expect(result.standalonePoints.map((p) => p.id)).toEqual(['cat', 'cc']);
  });

  it('ignores Point features whose featureType is not in the known point-feature set', () => {
    const json = {
      type: 'FeatureCollection',
      features: [pointFeature({ id: 'sp', sequence: 0 }), pointFeature({ id: 'weird', featureType: 'something_else', sequence: 1 })],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.routePoints.map((p) => p.id)).toEqual(['sp']);
  });

  it('applies defaults for missing optional point properties', () => {
    const json = {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [11, 60] }, properties: { featureType: 'route_waypoint' } }],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    const point = result.routePoints[0];
    expect(point.name).toBe('Unnamed');
    expect(point.type).toBe('tp');
    expect(point.segmentType).toBe('straight');
    expect(point.width).toBe(1852);
    expect(point.isTiming).toBe(true);
    expect(point.isPassing).toBe(true);
    expect(typeof point.id).toBe('string');
    expect(point.id.length).toBeGreaterThan(0);
  });

  it('parses LineString gate features, defaulting width to 50', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: [[11, 60], [11.01, 60.01]] },
          properties: { id: 'g1', name: 'Landing', gateType: 'landing' },
        },
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.gates).toEqual([
      { id: 'g1', name: 'Landing', type: 'landing', p1: { lng: 11, lat: 60 }, p2: { lng: 11.01, lat: 60.01 }, width: 50 },
    ]);
  });

  it('ignores LineString features without a gateType', () => {
    const json = {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: [[11, 60], [11.01, 60.01]] }, properties: {} }],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.gates).toEqual([]);
  });

  it('parses observation_photo Point features into observationMarkers', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [11, 60] },
          properties: { id: 'o1', featureType: 'observation_photo', name: 'Obs 1', targetName: 'Target A' },
        },
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.observationMarkers).toEqual([{ id: 'o1', lat: 60, lng: 11, name: 'Obs 1', targetName: 'Target A' }]);
  });

  it('parses zone/waypoint_polygon Polygon features, dropping the closing duplicate coordinate', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[[11, 60], [11.1, 60], [11.1, 60.1], [11, 60]]] },
          properties: { id: 'z1', name: 'Zone A', featureType: 'zone', polygonType: 'prohibited' },
        },
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.polygons).toEqual([
      {
        id: 'z1',
        name: 'Zone A',
        type: 'prohibited',
        points: [{ lng: 11, lat: 60 }, { lng: 11.1, lat: 60 }, { lng: 11.1, lat: 60.1 }],
      },
    ]);
  });

  it('excludes polygons whose polygonType is "waypoint" (those describe a route point, not a zone)', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[[11, 60], [11.1, 60], [11.1, 60.1], [11, 60]]] },
          properties: { id: 'z1', featureType: 'waypoint_polygon', polygonType: 'waypoint' },
        },
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.polygons).toEqual([]);
  });

  it('returns null bounds when there are no features', () => {
    const result = parseRouteEditorFeatureCollection({ type: 'FeatureCollection', features: [] }, standaloneTypes);
    expect(result.bounds).toBeNull();
  });

  it('computes bounds spanning route points, gates, observation markers, and polygons', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        pointFeature({ id: 'sp', pointType: 'sp', sequence: 0 }), // lat 60.1, lng 11.1
        {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: [[10, 59], [12, 61]] },
          properties: { id: 'g1', gateType: 'landing' },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [13, 62] },
          properties: { id: 'o1', featureType: 'observation_photo' },
        },
        {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[[9, 58], [9, 58], [9, 58]]] },
          properties: { id: 'z1', featureType: 'zone', polygonType: 'penalty' },
        },
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.bounds).toEqual([[58, 9], [62, 13]]);
  });

  it('parses a full representative mixed-feature payload end to end', () => {
    const json = {
      type: 'FeatureCollection',
      features: [
        pointFeature({ id: 'sp', pointType: 'sp', name: 'SP', sequence: 0 }),
        pointFeature({ id: 'tp1', pointType: 'tp', name: 'TP1', sequence: 1, lat: 60.2 }),
        pointFeature({ id: 'fp', pointType: 'fp', name: 'FP', sequence: 2 }),
        pointFeature({ id: 'cat1', pointType: 'catalogue_turnpoint', featureType: 'catalogue_turnpoint', name: 'CAT1', sequence: 3 }),
        {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: [[11, 60], [11.01, 60.01]] },
          properties: { id: 'gate1', name: 'Takeoff', gateType: 'takeoff', width: 100 },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [11.2, 60.2] },
          properties: { id: 'obs1', featureType: 'observation_photo', name: 'Obs' },
        },
        {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[[11, 60], [11.1, 60], [11.1, 60.1], [11, 60]]] },
          properties: { id: 'zone1', name: 'Danger', featureType: 'zone', polygonType: 'penalty' },
        },
      ],
    };
    const result = parseRouteEditorFeatureCollection(json, standaloneTypes);
    expect(result.routePoints.map((p) => p.id)).toEqual(['sp', 'tp1', 'fp']);
    expect(result.standalonePoints.map((p) => p.id)).toEqual(['cat1']);
    expect(result.gates).toHaveLength(1);
    expect(result.observationMarkers).toHaveLength(1);
    expect(result.polygons).toHaveLength(1);
    expect(result.bounds).not.toBeNull();
  });
});
