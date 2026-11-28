import requirementKeys from './routeRequirementKeys.json';
import { ROUTE_REQUIREMENT_TOOLS, type RouteRequirementResult, type RouteRequirementTool, type TaskCompatibilityResult } from './api';
import { buildWizardChecklist, getRouteEditorFlags, NO_ROUTE_EDITOR_FLAGS } from './taskRequirements';
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

const subtypeFor = (backendKey: string, requirements: RouteRequirementResult[]) => ({
  key: backendKey,
  display_name: backendKey,
  group: 'CIMA' as const,
  coarse_family: 'precision',
  compatible: false,
  missing_reasons: [],
  requirements,
});

const compatibilityFor = (backendKey: string, requirements: RouteRequirementResult[]): TaskCompatibilityResult => ({
  compatible_task_types: [],
  subtypes: [subtypeFor(backendKey, requirements)],
});

const checklist = (
  templateId: string,
  requirements: RouteRequirementResult[],
  status: 'pending' | 'ready' | 'failed' = 'ready',
  local: (tool: RouteRequirementTool) => number = () => 0,
) => {
  const template = getTaskTemplateById(templateId)!;
  return buildWizardChecklist(template, compatibilityFor(template.backendKey, requirements), null, status, local);
};

const stepOf = (result: ReturnType<typeof checklist>, key: string) => result.steps.find((state) => state.key === key)!;

describe('requirement keys', () => {
  it('shows every backend requirement of every template somewhere, whatever its key', () => {
    for (const template of TASK_TEMPLATES) {
      const requirements = [...requirementKeys.requirementKeys, 'some_future_rule'].map((key) => requirement(key));
      const result = buildWizardChecklist(template, compatibilityFor(template.backendKey, requirements), null, 'ready', () => 0);
      const shown = [...result.steps.flatMap((state) => state.requirements), ...result.generic].map((item) => item.key);
      expect(shown.sort()).toEqual(requirements.map((item) => item.key).sort());
      expect(result.generic.map((item) => item.key)).toContain('some_future_rule');
    }
  });

  it('makes a step of every requirement that names a tool, and a generic row of every one that does not', () => {
    const tools = ROUTE_REQUIREMENT_TOOLS.map((tool) => requirement(`req_${tool}`, { tool }));
    const result = checklist('cima_a1', [...tools, requirement('no_tool')]);
    expect(result.steps.map((state) => state.key)).toEqual([...ROUTE_REQUIREMENT_TOOLS]);
    expect(result.generic.map((item) => item.key)).toEqual(['no_tool']);
  });
});

describe('buildWizardChecklist', () => {
  it('takes required, count and satisfied from the backend when confirmed', () => {
    const result = checklist('cima_a7', [
      requirement('circle_start_marker', { tool: 'circle_start', minimum: 1, maximum: 1, found: 1, satisfied: true }),
      requirement('circle_center_marker', { tool: 'circle_center', minimum: 1, maximum: 1, found: 0 }),
      requirement('circle_entry_marker', { tool: 'circle_entry', minimum: 1, maximum: 1, found: 2, message: 'too many' }),
      requirement('circle_exit_marker', { tool: 'circle_exit', minimum: 1, maximum: 1, found: 1, satisfied: true }),
    ], 'ready', () => 9);
    expect(result.confirmed).toBe(true);
    expect(stepOf(result, 'circle_start')).toMatchObject({ required: true, satisfied: true, met: true, count: 1, maximum: 1, fixedCount: 1, message: null, label: 'Label of circle_start_marker', help: 'Help of circle_start_marker' });
    expect(stepOf(result, 'circle_center')).toMatchObject({ satisfied: false, met: false, count: 0, message: 'Message of circle_center_marker' });
    expect(stepOf(result, 'circle_entry')).toMatchObject({ satisfied: false, count: 2, message: 'too many' });
    expect(result.generic).toEqual([]);
  });

  it('makes an optional requirement an optional step: always met, counted locally, no numbers', () => {
    const result = checklist('cima_a2', [
      requirement('route_path', { tool: 'route_waypoint', found: 1, satisfied: true }),
      requirement('route_waypoints', { tool: 'route_waypoint', minimum: 3, found: 3, satisfied: true }),
      requirement('route_waypoint_order', { minimum: 0, maximum: 0, found: 0, satisfied: true }),
      requirement('hidden_gate', { tool: 'hidden_gate', minimum: 0, maximum: null, required: false, satisfied: true, help: 'Optional. Use the Hidden gate tool.' }),
    ], 'ready', () => 4);
    const route = stepOf(result, 'route_waypoint');
    const hidden = stepOf(result, 'hidden_gate');
    expect(route).toMatchObject({ required: true, satisfied: true, count: 3 });
    expect(route.primary?.key).toBe('route_waypoints');
    expect(route.requirements.map((item) => item.key)).toEqual(['route_path', 'route_waypoints', 'route_waypoint_order']);
    expect(hidden).toMatchObject({ required: false, satisfied: null, met: true, count: 4, primary: null, help: 'Optional. Use the Hidden gate tool.' });
    expect(result.generic).toEqual([]);
  });

  it('is unsatisfied when any requirement sharing a step is unsatisfied and reports its message', () => {
    const result = checklist('cima_a2', [
      requirement('route_path', { tool: 'route_waypoint', found: 1, satisfied: true }),
      requirement('route_waypoints', { tool: 'route_waypoint', minimum: 3, found: 3, satisfied: true }),
      requirement('route_waypoint_order', { minimum: 0, maximum: 0, found: 1, satisfied: false, message: 'start at SP' }),
    ]);
    const route = stepOf(result, 'route_waypoint');
    expect(route.satisfied).toBe(false);
    expect(route.met).toBe(false);
    expect(route.message).toBe('start at SP');
  });

  it('makes one step of the at-least-one-of requirement with a tool each, counted together', () => {
    const result = checklist('cima_a4', [
      requirement('known_circuit_evidence', { tool: 'hidden_gate', other_tools: ['known_time_gate', 'photo'], found: 0 }),
    ], 'pending', (tool) => (tool === 'photo' ? 1 : 0));
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0]).toMatchObject({ key: 'hidden_gate', tools: ['hidden_gate', 'known_time_gate', 'photo'], count: 1, met: true });
  });

  it('guides the curved leg of 2.A1 and the extension waypoints of 2.A5 from the backend', () => {
    const a1 = checklist('cima_a1', [requirement('curved_leg', { tool: 'curved_leg', found: 0, message: 'needs a curved leg' })], 'ready', () => 5);
    expect(stepOf(a1, 'curved_leg')).toMatchObject({ required: true, satisfied: false, message: 'needs a curved leg', count: 0 });

    const a5 = checklist('cima_a5', [
      requirement('unknown_leg', { tool: 'unknown_leg_point', found: 1, satisfied: true }),
      requirement('unknown_leg_extension', { tool: 'extension_waypoint', minimum: 0, maximum: 0, found: 1, message: 'needs an extension' }),
    ]);
    expect(stepOf(a5, 'unknown_leg_point').satisfied).toBe(true);
    expect(stepOf(a5, 'extension_waypoint')).toMatchObject({ required: true, satisfied: false, message: 'needs an extension', fixedCount: null });
    expect(a5.generic).toEqual([]);
  });

  it('has a fixed count when minimum equals maximum above zero, and no other step does', () => {
    const result = checklist('cima_a6', [
      requirement('known_time_gate', { tool: 'known_time_gate', minimum: 3, maximum: 3 }),
      requirement('catalogue_turnpoint', { tool: 'catalogue_turnpoint' }),
      requirement('unknown_leg_extension', { tool: 'extension_waypoint', minimum: 0, maximum: 0 }),
    ]);
    expect(stepOf(result, 'known_time_gate').fixedCount).toBe(3);
    expect(stepOf(result, 'catalogue_turnpoint').fixedCount).toBeNull();
    expect(stepOf(result, 'extension_waypoint').fixedCount).toBeNull();
  });

  it('shows prohibitions and requirements without a tool as generic rows', () => {
    const hunt = checklist('cima_a6', [
      requirement('route_path', { minimum: 0, maximum: 0, found: 2, message: 'no backbone please' }),
      requirement('known_time_gate', { tool: 'known_time_gate', minimum: 3, maximum: 3, found: 3, satisfied: true }),
    ]);
    expect(hunt.generic.map((item) => item.key)).toEqual(['route_path']);
    expect(stepOf(hunt, 'known_time_gate')).toMatchObject({ required: true, satisfied: true, maximum: 3 });

    const legacy = checklist('anr', [
      requirement('route_waypoint', { tool: 'route_waypoint', found: 2, satisfied: true }),
      requirement('unknown_leg', { minimum: 0, maximum: 0, found: 0, satisfied: true }),
      requirement('dummy_waypoint', { minimum: 0, maximum: 0, found: 0, satisfied: true }),
    ]);
    expect(legacy.generic.map((item) => item.key)).toEqual(['unknown_leg', 'dummy_waypoint']);
  });

  it('marks nothing satisfied while the check is pending or failed, and judges from local counts', () => {
    const requirements = [requirement('duration_landing_area', { tool: 'landing_area', found: 1, satisfied: true })];
    for (const status of ['pending', 'failed'] as const) {
      const none = checklist('cima_b3', requirements, status, () => 0);
      expect(none.confirmed).toBe(false);
      expect(stepOf(none, 'landing_area')).toMatchObject({ satisfied: null, count: 0, met: false, message: null });
      const some = checklist('cima_b3', requirements, status, () => 2);
      expect(stepOf(some, 'landing_area')).toMatchObject({ satisfied: null, count: 2, met: true });
    }
  });

  it('judges a prohibition from its local count: met at zero violations', () => {
    const requirements = [requirement('unknown_leg_extension', { tool: 'extension_waypoint', minimum: 0, maximum: 0 })];
    expect(stepOf(checklist('cima_a5', requirements, 'pending', () => 0), 'extension_waypoint').met).toBe(true);
    expect(stepOf(checklist('cima_a5', requirements, 'pending', () => 1), 'extension_waypoint').met).toBe(false);
  });

  it('takes the steps from the subtype catalogue while the backend has not answered for the route', () => {
    const template = getTaskTemplateById('cima_a7')!;
    const catalogue = [subtypeFor('circle', [requirement('circle_start_marker', { tool: 'circle_start', minimum: 1, maximum: 1 })])];
    const result = buildWizardChecklist(template, null, catalogue, 'pending', () => 1);
    expect(result.structureKnown).toBe(true);
    expect(result.confirmed).toBe(false);
    expect(stepOf(result, 'circle_start')).toMatchObject({ required: true, satisfied: null, met: true, count: 1, help: 'Help of circle_start_marker' });
  });

  it('works without any backend answer or catalogue: no steps', () => {
    const template = getTaskTemplateById('cima_a7')!;
    const result = buildWizardChecklist(template, null, null, 'pending', () => 1);
    expect(result.structureKnown).toBe(false);
    expect(result.confirmed).toBe(false);
    expect(result.steps).toEqual([]);
    expect(result.generic).toEqual([]);
  });

  it('treats a backend without requirements in the response as having none', () => {
    const template = getTaskTemplateById('cima_a7')!;
    const compat: TaskCompatibilityResult = {
      compatible_task_types: [],
      subtypes: [{ key: 'circle', display_name: 'Circle', group: 'CIMA', coarse_family: 'precision', compatible: false, missing_reasons: [] }],
    };
    expect(buildWizardChecklist(template, compat, null, 'ready', () => 0).steps).toEqual([]);
  });
});

describe('route requirement tools', () => {
  it('are a list without duplicates that contains the tools the guide acts on', () => {
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
