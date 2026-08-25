import { getWizardTransition, getWizardStep } from './routeEditorWizardTransitions';
import type { WizardStep, TaskTemplate } from './taskTemplates';

function makeStep(overrides: Partial<WizardStep> & { key: string; kind: WizardStep['kind'] }): WizardStep {
  return {
    label: overrides.key,
    help: `Help for ${overrides.key}`,
    minCount: 0,
    ...overrides,
  };
}

const label = (step: WizardStep) => `insert: ${step.key}`;

describe('getWizardTransition', () => {
  it('returns the default (no-op) transition when no step is given', () => {
    const result = getWizardTransition(undefined, label);
    expect(result.mode).toBeNull();
    expect(result.currentWizardActionLabel).toBeNull();
  });

  it('route-kind steps switch to add_point mode', () => {
    const step = makeStep({ key: 'route_waypoint', kind: 'route' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe('add_point');
    expect(result.currentWizardActionLabel).toBe(step.help);
  });

  it('a route_insert "ul" point step goes to view mode and asks the user to select an existing route point', () => {
    const step = makeStep({ key: 'unknown_leg', kind: 'point', placement: 'route_insert', pointType: 'ul', featureType: 'route_waypoint' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe('view');
    expect(result.nextSelectionType).toBe('point');
    expect(result.selectExistingRouteType).toBe('ul');
    expect(result.routeInsertPrompt).toBe('insert: unknown_leg');
  });

  it('a route_insert point step of any other type switches to add_point mode with the insert type/prompt set', () => {
    const step = makeStep({ key: 'hidden_gate', kind: 'point', placement: 'route_insert', pointType: 'secret', featureType: 'route_waypoint' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe('add_point');
    expect(result.wizardRouteInsertType).toBe('secret');
    expect(result.routeInsertPrompt).toBe('insert: hidden_gate');
  });

  it('a catalogue_turnpoint point step switches to add_catalogue_turnpoint mode and clears selection', () => {
    const step = makeStep({ key: 'catalogue', kind: 'point', featureType: 'catalogue_turnpoint' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe('add_catalogue_turnpoint');
    expect(result.clearSelectionType).toBe(true);
    expect(result.nextSelectionType).toBe('wizard');
  });

  it('a free_map dummy_branch_waypoint step preserves the current selection instead of clearing it', () => {
    const step = makeStep({ key: 'dummy', kind: 'point', placement: 'free_map', pointType: 'dummy', featureType: 'dummy_branch_waypoint' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe('add_point');
    expect(result.clearSelectionType).toBe(false);
    expect(result.preserveSelectedPoint).toBe(true);
    expect(result.nextSelectionType).toBe('point');
  });

  it('a free_map step of any other feature type clears selection normally', () => {
    const step = makeStep({ key: 'circle_center', kind: 'point', placement: 'free_map', pointType: 'circle_center', featureType: 'circle_center_marker' });
    const result = getWizardTransition(step, label);
    expect(result.clearSelectionType).toBe(true);
    expect(result.preserveSelectedPoint).toBe(false);
    expect(result.nextSelectionType).toBe('wizard');
  });

  it('a point step with neither route_insert/catalogue/free_map returns the default transition', () => {
    const step = makeStep({ key: 'weird', kind: 'point' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBeNull();
  });

  it.each([
    ['observation', 'add_observation'],
    ['takeoff_gate', 'add_takeoff'],
    ['landing_gate', 'add_landing'],
  ] as const)('%s-kind steps switch to %s mode', (kind, expectedMode) => {
    const step = makeStep({ key: kind, kind });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe(expectedMode);
  });

  it('polygon-kind steps switch to add_polygon mode and reset temp polygon points', () => {
    const step = makeStep({ key: 'prohibited', kind: 'polygon', polygonType: 'prohibited' });
    const result = getWizardTransition(step, label);
    expect(result.mode).toBe('add_polygon');
    expect(result.wizardPolygonType).toBe('prohibited');
    expect(result.resetTempPolygonPoints).toBe(true);
  });
});

describe('getWizardStep', () => {
  const template = { steps: [makeStep({ key: 'a', kind: 'point' }), makeStep({ key: 'b', kind: 'route' })] } as unknown as TaskTemplate;

  it('finds the step by key', () => {
    expect(getWizardStep(template, 'b')?.key).toBe('b');
  });

  it('returns undefined when the key is not found', () => {
    expect(getWizardStep(template, 'missing')).toBeUndefined();
  });

  it('returns undefined when no template is given', () => {
    expect(getWizardStep(undefined, 'a')).toBeUndefined();
  });
});
