import type { RouteRequirementTool } from './api';
import { allRequiredMet, autoAdvance, doneButtonLabel, findStep, nextUnmetRequiredStep, resolveStepEnd, shouldOfferTaskChoice } from './guideProgress';
import type { WizardChecklist, WizardStepState } from './taskRequirements';

const step = (key: RouteRequirementTool, overrides: Partial<WizardStepState> = {}): WizardStepState => ({
  key,
  tools: [key],
  label: key,
  help: '',
  requirements: [],
  required: true,
  count: 0,
  primary: null,
  satisfied: null,
  met: false,
  message: null,
  maximum: null,
  fixedCount: null,
  ...overrides,
});

const checklist = (steps: WizardStepState[], generic: WizardChecklist['generic'] = [], confirmed = false): WizardChecklist => ({
  steps,
  generic,
  confirmed,
  structureKnown: true,
});

describe('nextUnmetRequiredStep', () => {
  const steps = [
    step('route_waypoint', { met: true }),
    step('hidden_gate', { required: false, met: true }),
    step('curved_leg'),
    step('landing_area'),
  ];

  it('is the first unmet required step, never an optional one', () => {
    expect(nextUnmetRequiredStep(steps)?.key).toBe('curved_leg');
  });

  it('starts after the given step and wraps round', () => {
    expect(nextUnmetRequiredStep(steps, 'curved_leg')?.key).toBe('landing_area');
    expect(nextUnmetRequiredStep(steps, 'landing_area')?.key).toBe('curved_leg');
  });

  it('never returns the step itself, even when it is the only one unmet', () => {
    expect(nextUnmetRequiredStep([step('curved_leg')], 'curved_leg')).toBeNull();
  });

  it('is null when every required step is met', () => {
    expect(nextUnmetRequiredStep([step('route_waypoint', { met: true }), step('hidden_gate', { required: false })])).toBeNull();
  });
});

describe('resolveStepEnd', () => {
  it('starts the next unmet required step', () => {
    const list = checklist([step('route_waypoint', { met: true }), step('curved_leg')]);
    expect(resolveStepEnd(list, 'route_waypoint')).toEqual({ kind: 'start', tool: 'curved_leg' });
  });

  it('says all required steps are done when only optional steps are left, which it does not start', () => {
    const list = checklist([step('route_waypoint', { met: true }), step('hidden_gate', { required: false, met: true })]);
    expect(resolveStepEnd(list, 'route_waypoint')).toEqual({ kind: 'all_done' });
  });

  it('only stops when the step that ended is itself still unmet and nothing else is', () => {
    expect(resolveStepEnd(checklist([step('route_waypoint')]), 'route_waypoint')).toEqual({ kind: 'stop' });
  });

  it('is not all done while the backend has an unmet generic requirement', () => {
    const generic = [{ key: 'x', satisfied: false }] as WizardChecklist['generic'];
    const list = checklist([step('route_waypoint', { met: true })], generic, true);
    expect(allRequiredMet(list)).toBe(false);
    expect(resolveStepEnd(list, 'route_waypoint')).toEqual({ kind: 'stop' });
  });

  it('finds the step of an any-of requirement through any of its tools', () => {
    const anyOf = step('hidden_gate', { tools: ['hidden_gate', 'known_time_gate', 'photo'], met: true });
    expect(findStep([anyOf], 'photo')).toBe(anyOf);
    expect(resolveStepEnd(checklist([anyOf]), 'photo')).toEqual({ kind: 'all_done' });
  });
});

describe('autoAdvance', () => {
  it('ends a fixed-count step when the last one is placed and starts the next unmet required step', () => {
    const list = checklist([
      step('circle_start', { fixedCount: 1, maximum: 1, count: 1, met: true }),
      step('circle_center', { fixedCount: 1, maximum: 1 }),
    ]);
    expect(autoAdvance(list, 'circle_start', 'add_point')).toEqual({ kind: 'start', tool: 'circle_center' });
  });

  it('does not end a fixed-count step before the last one is placed', () => {
    const list = checklist([step('known_time_gate', { fixedCount: 3, maximum: 3, count: 2 }), step('catalogue_turnpoint')]);
    expect(autoAdvance(list, 'known_time_gate', 'add_point')).toBeNull();
  });

  it('never ends an open-ended step by itself', () => {
    const list = checklist([step('route_waypoint', { count: 12, met: true }), step('curved_leg')]);
    expect(autoAdvance(list, 'route_waypoint', 'add_point')).toBeNull();
  });

  it('says all done when the last fixed-count step was the last required one', () => {
    const list = checklist([
      step('circle_exit', { fixedCount: 1, maximum: 1, count: 1, met: true }),
      step('photo', { required: false, met: true }),
    ]);
    expect(autoAdvance(list, 'circle_exit', 'add_point')).toEqual({ kind: 'all_done' });
  });

  it('skips optional steps: the next one is the next required one', () => {
    const list = checklist([
      step('known_time_gate', { fixedCount: 3, maximum: 3, count: 3, met: true }),
      step('photo', { required: false, met: true }),
      step('catalogue_turnpoint'),
    ]);
    expect(autoAdvance(list, 'known_time_gate', 'add_point')).toEqual({ kind: 'start', tool: 'catalogue_turnpoint' });
  });

  it('ends a single-shot tool (polygon, gate) when the mode is back to select, not before', () => {
    const list = checklist([step('landing_area', { count: 1, met: true }), step('route_waypoint')]);
    expect(autoAdvance(list, 'landing_area', 'add_polygon')).toBeNull();
    expect(autoAdvance(list, 'landing_area', 'view')).toEqual({ kind: 'start', tool: 'route_waypoint' });
  });

  it('does nothing without an active step', () => {
    expect(autoAdvance(checklist([step('route_waypoint', { fixedCount: 1, count: 1 })]), null, 'view')).toBeNull();
  });
});

describe('doneButtonLabel', () => {
  it('is "Done, next step" for an open-ended step and "Stop" for a fixed count', () => {
    expect(doneButtonLabel(step('route_waypoint'))).toBe('Done, next step');
    expect(doneButtonLabel(step('circle_start', { fixedCount: 1 }))).toBe('Stop');
  });
});

describe('shouldOfferTaskChoice', () => {
  it('is for a new route (no id in the URL) only', () => {
    expect(shouldOfferTaskChoice(undefined)).toBe(true);
    expect(shouldOfferTaskChoice(null)).toBe(true);
    expect(shouldOfferTaskChoice('')).toBe(true);
    expect(shouldOfferTaskChoice('42')).toBe(false);
  });
});
