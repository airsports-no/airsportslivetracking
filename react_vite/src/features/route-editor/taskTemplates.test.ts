import { countWizardStepMatches, getVisibleTaskTemplates, getTaskTemplateById, getWizardRouteInsertLabel, isTaskSubtypeVisible, TASK_TEMPLATES } from './taskTemplates';
import type { RoutePoint } from '../../types';
import type { WizardStep } from './taskTemplates';

describe('countWizardStepMatches', () => {
  it('counts 2.A5 route-insert steps by point type, not generic route_waypoint feature type', () => {
    const a5 = TASK_TEMPLATES.find((item) => item.id === 'cima_a5');
    expect(a5).toBeTruthy();

    const routeStep = a5!.steps.find((step) => step.key === 'route_waypoint');
    const triggerStep = a5!.steps.find((step) => step.key === 'unknown_leg');
    const dummyStep = a5!.steps.find((step) => step.key === 'dummy');
    const hiddenGateStep = a5!.steps.find((step) => step.key === 'hidden_gate');

    // D1 (the dummy branch waypoint) is NOT part of the route backbone -
    // since the 2.A5 backbone/map split (commit 978683ea onward) it's
    // authored as a free-map standalone point with
    // featureType: 'dummy_branch_waypoint', matching what
    // parseRouteEditorFeatureCollection actually produces, not a
    // route_waypoint like the other five points.
    const routePoints: RoutePoint[] = [
      { id: '1', name: 'SP', type: 'sp', featureType: 'route_waypoint', lat: 60, lng: 11, width: 1852, isTiming: true, isPassing: true, segmentType: 'straight' },
      { id: '2', name: 'A', type: 'tp', featureType: 'route_waypoint', lat: 60.1, lng: 11.1, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '3', name: 'TRG1', type: 'ul', featureType: 'route_waypoint', lat: 60.2, lng: 11.2, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '5', name: 'HG1', type: 'hidden_gate', featureType: 'route_waypoint', lat: 60.4, lng: 11.4, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '6', name: 'FP', type: 'fp', featureType: 'route_waypoint', lat: 60.5, lng: 11.5, width: 1852, isTiming: true, isPassing: true, segmentType: 'straight' },
    ];
    const standalonePoints: RoutePoint[] = [
      { id: '4', name: 'D1', type: 'dummy', featureType: 'dummy_branch_waypoint', lat: 60.3, lng: 11.3, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight', triggerPointId: '3', branchSequence: 0 },
    ];

    expect(countWizardStepMatches(routeStep!, routePoints, standalonePoints, [], [], [])).toBe(5);
    expect(countWizardStepMatches(triggerStep!, routePoints, standalonePoints, [], [], [])).toBe(1);
    expect(countWizardStepMatches(dummyStep!, routePoints, standalonePoints, [], [], [])).toBe(1);
    expect(countWizardStepMatches(hiddenGateStep!, routePoints, standalonePoints, [], [], [])).toBe(1);
  });
});

describe('getVisibleTaskTemplates', () => {
  it('always includes Legacy templates, even with no groups granted', () => {
    const visible = getVisibleTaskTemplates(undefined);
    const legacyIds = visible.filter((t) => t.group === 'Legacy').map((t) => t.id);
    expect(legacyIds.sort()).toEqual(['airsports_challenge', 'anr', 'precision']);
    // No CIMA templates without any 'cima' or 'cima:<subtype>' grant.
    expect(visible.some((t) => t.group === 'CIMA')).toBe(false);
  });

  it('unlocks every CIMA template when the coarse "cima" group is granted', () => {
    const visible = getVisibleTaskTemplates(['legacy', 'cima']);
    const cimaIds = visible.filter((t) => t.group === 'CIMA').map((t) => t.id);
    const allCimaIds = TASK_TEMPLATES.filter((t) => t.group === 'CIMA').map((t) => t.id);
    expect(cimaIds.sort()).toEqual(allCimaIds.sort());
  });

  it('unlocks only the matching CIMA template for a fine-grained "cima:<subtype>" grant', () => {
    const visible = getVisibleTaskTemplates(['legacy', 'cima:circle']);
    const cimaIds = visible.filter((t) => t.group === 'CIMA').map((t) => t.id);
    expect(cimaIds).toEqual(['cima_a7']);
  });

  it('grants for one subtype do not leak into other CIMA templates', () => {
    const visible = getVisibleTaskTemplates(['cima:circle']);
    expect(visible.some((t) => t.id === 'cima_a3')).toBe(false);
    expect(visible.some((t) => t.id === 'cima_a7')).toBe(true);
  });
});

describe('isTaskSubtypeVisible', () => {
  it('always shows Legacy regardless of groups', () => {
    expect(isTaskSubtypeVisible('Legacy', undefined, [])).toBe(true);
    expect(isTaskSubtypeVisible('Legacy', 'legacy_precision', undefined)).toBe(true);
  });

  it('hides CIMA with no matching group', () => {
    expect(isTaskSubtypeVisible('CIMA', 'circle', [])).toBe(false);
    expect(isTaskSubtypeVisible('CIMA', 'circle', ['legacy'])).toBe(false);
  });

  it('shows every CIMA subtype with the coarse "cima" group', () => {
    expect(isTaskSubtypeVisible('CIMA', 'circle', ['cima'])).toBe(true);
    expect(isTaskSubtypeVisible('CIMA', 'unknown_legs', ['cima'])).toBe(true);
  });

  it('shows only the matching subtype for a fine-grained "cima:<subtype>" group', () => {
    expect(isTaskSubtypeVisible('CIMA', 'circle', ['cima:circle'])).toBe(true);
    expect(isTaskSubtypeVisible('CIMA', 'unknown_legs', ['cima:circle'])).toBe(false);
  });
});

describe('getTaskTemplateById', () => {
  it('finds a template by id', () => {
    expect(getTaskTemplateById('cima_a7')?.label).toBe('2.A7 Circle');
  });

  it('returns undefined for an unknown, null, or undefined id', () => {
    expect(getTaskTemplateById('not_a_real_id')).toBeUndefined();
    expect(getTaskTemplateById(null)).toBeUndefined();
    expect(getTaskTemplateById(undefined)).toBeUndefined();
  });
});

describe('getWizardRouteInsertLabel', () => {
  const baseStep: WizardStep = { key: 'k', label: 'L', help: 'H', kind: 'point', minCount: 0 };

  it('gives the hidden-gate-specific instruction for a hidden_gate step key', () => {
    expect(getWizardRouteInsertLabel({ ...baseStep, key: 'hidden_gate', pointType: 'secret' })).toBe(
      'Click the existing true backbone route line to insert a hidden gate.',
    );
  });

  it('gives the known-time-gate-specific instruction for a known_time_gate step key', () => {
    expect(getWizardRouteInsertLabel({ ...baseStep, key: 'known_time_gate', pointType: 'tp' })).toBe(
      'Click the existing route line to insert a known time gate.',
    );
  });

  it('gives the unknown-leg-specific instruction for a ul pointType', () => {
    expect(getWizardRouteInsertLabel({ ...baseStep, pointType: 'ul' })).toBe(
      'Select an existing backbone waypoint and change its type to Unknown Leg in the point editor.',
    );
  });

  it('gives the dummy-branch-specific instruction for a dummy_branch_waypoint featureType', () => {
    expect(getWizardRouteInsertLabel({ ...baseStep, featureType: 'dummy_branch_waypoint' })).toBe(
      'Select an unknown-leg trigger waypoint first, then click the map to add dummy-branch waypoints.',
    );
  });

  it('falls back to the generic instruction for any other step', () => {
    expect(getWizardRouteInsertLabel({ ...baseStep, pointType: 'tp' })).toBe(
      'Click the existing route line to insert the required point.',
    );
  });
});