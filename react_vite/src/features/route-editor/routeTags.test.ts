import { describe, expect, it } from 'vitest';
import { buildRouteTags, routeMatchesTaskFilter, routesMadeForFirst, taskTypeKeysInUse } from './routeTags';

const subtypes = {
  a1: { coarse_family: 'precision', display_name: 'Precision' },
  a2: { coarse_family: 'anr_corridor', display_name: 'ANR' },
  a3: { coarse_family: 'airsports', display_name: 'Air Sports' },
  cima1: { coarse_family: 'airsports', display_name: 'CIMA 2.A1' },
};
const order = ['precision', 'anr_corridor', 'airsports'];
const all = new Set(Object.keys(subtypes));

describe('buildRouteTags', () => {
  it('shows only "suitable" for a route without intent', () => {
    const tags = buildRouteTags({ intended_task_types: [], compatible_task_types: ['a3', 'a1'] }, subtypes, all, order);
    expect(tags.madeFor).toEqual([]);
    expect(tags.alsoSuitable).toEqual([]);
    expect(tags.suitable.map((group) => group.family)).toEqual(['precision', 'airsports']);
  });

  it('splits made for and the other compatible families', () => {
    const tags = buildRouteTags({ intended_task_types: ['a1'], compatible_task_types: ['a1', 'a2', 'a3'] }, subtypes, all, order);
    expect(tags.madeFor).toEqual([{ family: 'precision', subtypeNames: ['Precision'], unmetNames: [] }]);
    expect(tags.alsoSuitable.map((group) => group.family)).toEqual(['anr_corridor', 'airsports']);
    expect(tags.suitable).toEqual([]);
  });

  it('marks an intended type the route does not meet yet', () => {
    const tags = buildRouteTags({ intended_task_types: ['a2'], compatible_task_types: ['a1'] }, subtypes, all, order);
    expect(tags.madeFor).toEqual([{ family: 'anr_corridor', subtypeNames: ['ANR'], unmetNames: ['ANR'] }]);
    expect(tags.alsoSuitable.map((group) => group.family)).toEqual(['precision']);
  });

  it('leaves a family that is made for out of the also suitable chips', () => {
    const tags = buildRouteTags({ intended_task_types: ['a3'], compatible_task_types: ['a3', 'cima1'] }, subtypes, all, order);
    expect(tags.madeFor[0].subtypeNames).toEqual(['Air Sports']);
    expect(tags.alsoSuitable).toEqual([]);
  });

  it('never shows a type the viewer may not see', () => {
    const visible = new Set(['a1']);
    const tags = buildRouteTags({ intended_task_types: ['cima1'], compatible_task_types: ['a1', 'cima1'] }, subtypes, visible, order);
    expect(tags.madeFor).toEqual([]);
    expect(tags.suitable.map((group) => group.family)).toEqual(['precision']);
  });
});

describe('task type filter', () => {
  const route = { intended_task_types: ['a1'], compatible_task_types: ['a1', 'a2'] };

  it('matches on what the route suits by default and on intent in made for mode', () => {
    expect(routeMatchesTaskFilter(route, 'a2', 'suitable')).toBe(true);
    expect(routeMatchesTaskFilter(route, 'a2', 'made_for')).toBe(false);
    expect(routeMatchesTaskFilter(route, 'a1', 'made_for')).toBe(true);
    expect(routeMatchesTaskFilter(route, '', 'made_for')).toBe(true);
  });

  it('offers only the types in use for the mode', () => {
    expect([...taskTypeKeysInUse([route], 'suitable')]).toEqual(['a1', 'a2']);
    expect([...taskTypeKeysInUse([route, { compatible_task_types: ['a3'] }], 'made_for')]).toEqual(['a1']);
  });
});

describe('routesMadeForFirst', () => {
  it('puts routes made for the task first and keeps the order otherwise', () => {
    const routes = [
      { id: 1, intended_task_types: [] },
      { id: 2, intended_task_types: ['a1'] },
      { id: 3, intended_task_types: ['a2'] },
      { id: 4, intended_task_types: ['a1', 'a2'] },
    ];
    expect(routesMadeForFirst(routes, 'a1').map((route) => route.id)).toEqual([2, 4, 1, 3]);
  });
});
