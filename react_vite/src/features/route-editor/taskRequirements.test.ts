import requirementKeys from './routeRequirementKeys.json';
import { ROUTE_REQUIREMENT_TOOLS, type RouteRequirementResult, type TaskCompatibilityResult } from './api';
import { buildWizardChecklist, getRouteEditorFlags, NO_ROUTE_EDITOR_FLAGS, REQUIREMENT_STEP_KEYS } from './taskRequirements';
import { getTaskTemplateById, TASK_TEMPLATES } from './taskTemplates';

const requirement = (key: string, overrides: Partial<RouteRequirementResult> = {}): RouteRequirementResult => ({
  key,
  label: `Label of ${key}`,
  minimum: 1,
  maximum: null,
  found: 0,
  satisfied: false,
  message: `Message of ${key}`,
  required: true,
  help: `Help of ${key}`,
  tool: null,
  other_tools: [],
  ...overrides,
});

const compatibilityFor = (backendKey: string, requirements: RouteRequirementResult[]): TaskCompatibilityResult => ({
  compatible_task_types: [],
  subtypes: [
    { key: backendKey, display_name: backendKey, group: 'CIMA', coarse_family: 'precision', compatible: false, missing_reasons: [], requirements },
  ],
});

const checklist = (
  templateId: string,
  requirements: RouteRequirementResult[],
  status: 'pending' | 'ready' | 'failed' = 'ready',
  local = 0,
) => {
  const template = getTaskTemplateById(templateId)!;
  return buildWizardChecklist(template, compatibilityFor(template.backendKey, requirements), status, () => local);
};

describe('requirement keys', () => {
  it('maps every key the registry can produce to a wizard step or renders it generically', () => {
    const stepKeys = new Set(TASK_TEMPLATES.flatMap((template) => template.steps.map((step) => step.key)));
    for (const key of requirementKeys.requirementKeys) {
      const stepKey = REQUIREMENT_STEP_KEYS[key];
      if (stepKey !== undefined) expect(stepKeys.has(stepKey), `${key} -> ${stepKey}`).toBe(true);
    }
    // Keys without a step are the generic rows.
    expect(requirementKeys.requirementKeys.filter((key) => !(key in REQUIREMENT_STEP_KEYS)).sort()).toEqual(['dummy_waypoint', 'known_circuit_evidence']);
  });

  it('never maps a key that the registry does not produce', () => {
    for (const key of Object.keys(REQUIREMENT_STEP_KEYS)) {
      expect(requirementKeys.requirementKeys).toContain(key);
    }
  });

  it('shows every backend requirement of every template somewhere, whatever its key', () => {
    for (const template of TASK_TEMPLATES) {
      const requirements = [...requirementKeys.requirementKeys, 'some_future_rule'].map((key) => requirement(key));
      const result = buildWizardChecklist(template, compatibilityFor(template.backendKey, requirements), 'ready', () => 0);
      const shown = [...result.steps.flatMap((state) => state.requirements), ...result.generic].map((item) => item.key);
      expect(shown.sort()).toEqual(requirements.map((item) => item.key).sort());
      expect(result.generic.map((item) => item.key)).toContain('some_future_rule');
    }
  });
});

describe('buildWizardChecklist', () => {
  it('takes required, count and satisfied from the backend when confirmed', () => {
    const result = checklist('cima_a7', [
      requirement('circle_start_marker', { minimum: 1, maximum: 1, found: 1, satisfied: true }),
      requirement('circle_center_marker', { minimum: 1, maximum: 1, found: 0 }),
      requirement('circle_entry_marker', { minimum: 1, maximum: 1, found: 2, message: 'too many' }),
      requirement('circle_exit_marker', { minimum: 1, maximum: 1, found: 1, satisfied: true }),
    ], 'ready', 9);
    const byKey = Object.fromEntries(result.steps.map((state) => [state.step.key, state]));
    expect(result.confirmed).toBe(true);
    expect(byKey.circle_start).toMatchObject({ required: true, satisfied: true, count: 1, maximum: 1, message: null });
    expect(byKey.circle_center).toMatchObject({ satisfied: false, count: 0, message: 'Message of circle_center_marker' });
    expect(byKey.circle_entry).toMatchObject({ satisfied: false, count: 2, message: 'too many' });
    expect(result.generic).toEqual([]);
  });

  it('keeps optional steps optional and counted locally', () => {
    const result = checklist('cima_a2', [
      requirement('route_path', { found: 1, satisfied: true }),
      requirement('route_waypoints', { minimum: 3, found: 3, satisfied: true }),
      requirement('route_waypoint_order', { minimum: 0, maximum: 0, found: 0, satisfied: true }),
    ], 'ready', 4);
    const route = result.steps.find((state) => state.step.key === 'route_waypoint')!;
    const hidden = result.steps.find((state) => state.step.key === 'hidden_gate')!;
    expect(route).toMatchObject({ required: true, satisfied: true, count: 3 });
    expect(route.primary?.key).toBe('route_waypoints');
    expect(hidden).toMatchObject({ required: false, satisfied: null, count: 4, primary: null });
  });

  it('is unsatisfied when any requirement sharing a step is unsatisfied and reports its message', () => {
    const result = checklist('cima_a2', [
      requirement('route_path', { found: 1, satisfied: true }),
      requirement('route_waypoints', { minimum: 3, found: 3, satisfied: true }),
      requirement('route_waypoint_order', { minimum: 0, maximum: 0, found: 1, satisfied: false, message: 'start at SP' }),
    ]);
    const route = result.steps.find((state) => state.step.key === 'route_waypoint')!;
    expect(route.satisfied).toBe(false);
    expect(route.message).toBe('start at SP');
  });

  it('guides the curved leg of 2.A1 and the extension waypoints of 2.A5 from the backend', () => {
    const a1 = checklist('cima_a1', [requirement('curved_leg', { found: 0, message: 'needs a curved leg' })], 'ready', 5);
    expect(a1.steps.find((state) => state.step.key === 'curved_leg')).toMatchObject({ required: true, satisfied: false, message: 'needs a curved leg', count: 0 });

    const a5 = checklist('cima_a5', [
      requirement('unknown_leg', { found: 1, satisfied: true }),
      requirement('unknown_leg_extension', { minimum: 0, maximum: 0, found: 1, message: 'needs an extension' }),
    ]);
    expect(a5.steps.find((state) => state.step.key === 'unknown_leg')?.satisfied).toBe(true);
    expect(a5.steps.find((state) => state.step.key === 'dummy')).toMatchObject({ required: true, satisfied: false, message: 'needs an extension' });
    expect(a5.generic).toEqual([]);
  });

  it('shows prohibitions and requirements without a step as generic rows', () => {
    const hunt = checklist('cima_a6', [
      requirement('route_path', { minimum: 0, maximum: 0, found: 2, message: 'no backbone please' }),
      requirement('known_time_gate', { minimum: 3, maximum: 3, found: 3, satisfied: true }),
    ]);
    expect(hunt.generic.map((item) => item.key)).toEqual(['route_path']);
    expect(hunt.steps.find((state) => state.step.key === 'timed_turnpoint')).toMatchObject({ required: true, satisfied: true, maximum: 3 });

    const legacy = checklist('anr', [
      requirement('route_waypoint', { found: 2, satisfied: true }),
      requirement('unknown_leg', { minimum: 0, maximum: 0, found: 0, satisfied: true }),
      requirement('dummy_waypoint', { minimum: 0, maximum: 0, found: 0, satisfied: true }),
    ]);
    expect(legacy.generic.map((item) => item.key)).toEqual(['unknown_leg', 'dummy_waypoint']);
  });

  it('marks nothing satisfied while the check is pending or failed, and falls back to local counts', () => {
    const requirements = [requirement('duration_landing_area', { found: 1, satisfied: true })];
    for (const status of ['pending', 'failed'] as const) {
      const result = checklist('cima_b3', requirements, status, 2);
      expect(result.confirmed).toBe(false);
      expect(result.steps.every((state) => state.satisfied !== true)).toBe(true);
      expect(result.steps.find((state) => state.step.key === 'duration_landing_area')).toMatchObject({ satisfied: null, count: 2, message: null });
    }
  });

  it('works without any backend answer: no requirement structure, local counts, nothing satisfied', () => {
    const template = getTaskTemplateById('cima_a7')!;
    const result = buildWizardChecklist(template, null, 'pending', () => 1);
    expect(result.structureKnown).toBe(false);
    expect(result.confirmed).toBe(false);
    expect(result.steps.every((state) => state.satisfied === null && !state.required && state.count === 1)).toBe(true);
    expect(result.generic).toEqual([]);
  });

  it('treats a backend without requirements in the response as having none', () => {
    const template = getTaskTemplateById('cima_a7')!;
    const compat: TaskCompatibilityResult = {
      compatible_task_types: [],
      subtypes: [{ key: 'circle', display_name: 'Circle', group: 'CIMA', coarse_family: 'precision', compatible: false, missing_reasons: [] }],
    };
    const result = buildWizardChecklist(template, compat, 'ready', () => 0);
    expect(result.steps.every((state) => !state.required)).toBe(true);
  });
});

describe('optional requirements', () => {
  it('are not part of the checklist: they are always satisfied and only describe a step of the guide', () => {
    const optional = requirement('hidden_gate', { minimum: 0, maximum: null, required: false, satisfied: true });
    const result = checklist('cima_a1', [requirement('route_path'), optional]);
    const shown = [...result.steps.flatMap((state) => state.requirements), ...result.generic].map((item) => item.key);
    expect(shown).toEqual(['route_path']);
    const hiddenGateStep = result.steps.find((state) => state.step.key === 'hidden_gate')!;
    expect(hiddenGateStep.required).toBe(false);
    expect(hiddenGateStep.satisfied).toBeNull();
  });

  it('knows the tools the backend can name', () => {
    expect(new Set(ROUTE_REQUIREMENT_TOOLS).size).toBe(ROUTE_REQUIREMENT_TOOLS.length);
    expect(ROUTE_REQUIREMENT_TOOLS).toContain('hidden_gate');
  });
});

describe('route editor flags', () => {
  const flags = { ...NO_ROUTE_EDITOR_FLAGS, circle_markers: true };
  const subtypes = [
    { key: 'circle', display_name: 'Circle', group: 'CIMA' as const, coarse_family: 'precision', compatible: false, missing_reasons: [], flags },
    { key: 'duration', display_name: 'Duration', group: 'CIMA' as const, coarse_family: 'precision', compatible: false, missing_reasons: [] },
  ];

  it('are looked up through the subtype of the selected template', () => {
    expect(getRouteEditorFlags(subtypes, getTaskTemplateById('cima_a7')!.subtype).circle_markers).toBe(true);
    expect(getRouteEditorFlags(subtypes, getTaskTemplateById('cima_a1')!.subtype).circle_markers).toBe(false);
  });

  it('are all false for a template without a subtype, a subtype without flags, or before the backend answered', () => {
    expect(getRouteEditorFlags(subtypes, getTaskTemplateById('precision')!.subtype)).toEqual(NO_ROUTE_EDITOR_FLAGS);
    expect(getRouteEditorFlags(subtypes, 'duration')).toEqual(NO_ROUTE_EDITOR_FLAGS);
    expect(getRouteEditorFlags(null, 'circle')).toEqual(NO_ROUTE_EDITOR_FLAGS);
  });
});
