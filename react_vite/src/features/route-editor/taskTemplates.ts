export type TaskTemplateGroup = 'Legacy' | 'CIMA';

export type TaskTemplateId =
  | 'precision'
  | 'anr'
  | 'airsports_challenge'
  | 'cima_a1'
  | 'cima_a2'
  | 'cima_a3'
  | 'cima_a4'
  | 'cima_a5'
  | 'cima_a6'
  | 'cima_a7'
  | 'cima_a8'
  | 'cima_b2'
  | 'cima_b3';

// The route editor's task choice. What a task needs of the route (its steps, their help texts and tools, the flags)
// is the backend's task type registry, returned by the compatibility API; this file only says which task types are
// offered as templates, in which group and order, and how they are named and described.
export interface TaskTemplate {
  id: TaskTemplateId;
  label: string;
  group: TaskTemplateGroup;
  // Backend task_subtype key (e.g. 'circle') for CIMA templates - used to
  // check fine-grained per-subtype access ('cima:<subtype>'). Legacy
  // templates have no subtype and are always visible.
  subtype?: string;
  // Task type registry key whose route requirements drive this template's checklist. Equal to
  // `subtype` for CIMA templates; the legacy templates have no `subtype` but do have a backend key.
  backendKey: string;
  // One line.
  description: string;
}

export const TASK_TEMPLATES: TaskTemplate[] = [
  { id: 'precision', backendKey: 'legacy_precision', label: 'Precision', group: 'Legacy', description: 'Start, turn points and finish, with optional hidden gates.' },
  { id: 'anr', backendKey: 'legacy_anr_corridor', label: 'ANR', group: 'Legacy', description: 'An air navigation race route flown in a corridor.' },
  { id: 'airsports_challenge', backendKey: 'legacy_airsport_challenge', label: 'Air Sports Challenge', group: 'Legacy', description: 'A challenge route with start, waypoints and finish.' },
  { id: 'cima_a1', backendKey: 'curve_navigation_time_estimation', label: '2.A1 Curve navigation with time estimation', group: 'CIMA', subtype: 'curve_navigation_time_estimation', description: 'A precision route with at least one curved leg.' },
  { id: 'cima_a2', backendKey: 'precision_navigation', label: '2.A2 Precision navigation', group: 'CIMA', subtype: 'precision_navigation', description: 'A precision route scored on its hidden gates.' },
  { id: 'cima_a3', backendKey: 'contract_navigation_time_controls', label: '2.A3 Contract navigation with time controls', group: 'CIMA', subtype: 'contract_navigation_time_controls', description: 'SP, MP and FP, with free catalogue turn points.' },
  { id: 'cima_a4', backendKey: 'known_circuit', label: '2.A4 Navigation over a known circuit', group: 'CIMA', subtype: 'known_circuit', description: 'A known circuit with time gates, hidden gates or photos.' },
  { id: 'cima_a5', backendKey: 'unknown_legs', label: '2.A5 Navigation with unknown legs', group: 'CIMA', subtype: 'unknown_legs', description: 'A true route with unknown-leg points and extension waypoints.' },
  { id: 'cima_a6', backendKey: 'turnpoint_hunt', label: '2.A6 Turnpoint hunt', group: 'CIMA', subtype: 'turnpoint_hunt', description: 'No route: three timed turn points and free catalogue turn points.' },
  { id: 'cima_a7', backendKey: 'circle', label: '2.A7 Circle', group: 'CIMA', subtype: 'circle', description: 'Circle start, centre, entry and exit markers.' },
  { id: 'cima_a8', backendKey: 'anr_catalogue', label: '2.A8 Precision navigation ANR', group: 'CIMA', subtype: 'anr_catalogue', description: 'Precision navigation on an air navigation race route.' },
  { id: 'cima_b2', backendKey: 'limited_fuel_turnpoint_hunt', label: '2.B2 Limited fuel turnpoint hunt', group: 'CIMA', subtype: 'limited_fuel_turnpoint_hunt', description: 'No route: three timed turn points and catalogue turn points, on limited fuel.' },
  { id: 'cima_b3', backendKey: 'duration', label: '2.B3 Duration', group: 'CIMA', subtype: 'duration', description: 'A landing area, with optional take-off and landing gates.' },
];

// Filters templates against the raw visible-task-type-group strings the
// backend computes per user (e.g. ['legacy', 'cima'] or, for a fine-grained
// grant, ['legacy', 'cima:circle']). Legacy templates are always visible; a
// coarse 'cima' entry unlocks every CIMA template; otherwise a CIMA template
// is only visible if its own 'cima:<subtype>' entry is present - so a user
// granted only cima:circle sees Circle but not the other CIMA templates,
// rather than either all of them (coarse-only check) or none (an exact
// 'cima' string match would incorrectly hide everything for a fine-only grant).
// A CIMA subtype is visible if the caller's visible-task-type-groups include the coarse 'cima'
// group (full CIMA access) or the fine-grained 'cima:<subtypeKey>' group (access to just this
// one). Legacy is always visible. Shared by the route editor's guide/checklist and anywhere else
// (e.g. the route list) that needs to hide CIMA task types from a user without CIMA access.
export const isTaskSubtypeVisible = (
  group: TaskTemplateGroup,
  subtypeKey: string | null | undefined,
  visibleTaskTypeGroups: string[] | undefined,
): boolean => {
  if (group === 'Legacy') return true;
  const groups = new Set(visibleTaskTypeGroups ?? []);
  if (groups.has('cima')) return true;
  return subtypeKey != null && groups.has(`cima:${subtypeKey}`);
};

export const getVisibleTaskTemplates = (visibleTaskTypeGroups: string[] | undefined): TaskTemplate[] =>
  TASK_TEMPLATES.filter((template) => isTaskSubtypeVisible(template.group, template.subtype, visibleTaskTypeGroups));

// The templates the user may see, grouped as the task choice and the guide show them (Legacy first, then CIMA).
export const groupTemplates = (templates: TaskTemplate[]): Array<[TaskTemplateGroup, TaskTemplate[]]> => {
  const groups: Array<[TaskTemplateGroup, TaskTemplate[]]> = [];
  for (const template of templates) {
    const existing = groups.find(([group]) => group === template.group);
    if (existing) existing[1].push(template);
    else groups.push([template.group, [template]]);
  }
  return groups;
};

export const getTaskTemplateById = (id: string | null | undefined): TaskTemplate | undefined =>
  TASK_TEMPLATES.find((template) => template.id === id);

// Human-readable labels for the coarse task-type families (display.utilities.
// navigation_task_type_definitions's PRECISION/ANR_CORRIDOR/AIRSPORTS/AIRSPORT_CHALLENGE/
// POKER/LANDING string values) - matching the labels already established in the Django model's
// historic choices, spaced for readability (e.g. "Air Sports Challenge", not "AirSport Challenge").
export const COARSE_FAMILY_LABELS: Record<string, string> = {
  precision: 'Precision',
  anr_corridor: 'ANR Corridor',
  airsports: 'Air Sports Race',
  airsportchallenge: 'Air Sports Challenge',
  poker: 'Poker Run',
  landing: 'Landing',
};

// A distinct DaisyUI badge color per family, so a route's footer badges are visually
// distinguishable at a glance instead of reading as one undifferentiated block.
export const COARSE_FAMILY_BADGE_CLASS: Record<string, string> = {
  precision: 'badge-primary',
  anr_corridor: 'badge-info',
  airsports: 'badge-accent',
  airsportchallenge: 'badge-secondary',
  poker: 'badge-warning',
  landing: 'badge-neutral',
};

// Fixed display order so a given family always lands in the same visual position across cards.
export const COARSE_FAMILY_ORDER: string[] = ['precision', 'anr_corridor', 'airsports', 'airsportchallenge', 'poker', 'landing'];

export interface TaskTypeFamilyGroup {
  family: string;
  subtypeNames: string[];
}

// Collapses a route's (possibly many) specific task-subtype keys down to their coarse families,
// so a card can show a handful of short, distinctly-colored chips instead of a wall of long
// subtype names - the full subtype list per family remains available (e.g. as a tooltip) via
// subtypeNames. Families are returned in COARSE_FAMILY_ORDER; any family not in that fixed order
// (e.g. one the backend added before the frontend's static maps above were updated) is appended
// at the end rather than silently dropped.
export const groupTaskTypesByFamily = (
  taskTypeKeys: string[],
  subtypeByKey: Record<string, { coarse_family: string; display_name: string }>,
): TaskTypeFamilyGroup[] => {
  const namesByFamily = new Map<string, string[]>();
  for (const key of taskTypeKeys) {
    const subtype = subtypeByKey[key];
    if (!subtype) continue;
    const names = namesByFamily.get(subtype.coarse_family) ?? [];
    names.push(subtype.display_name);
    namesByFamily.set(subtype.coarse_family, names);
  }

  const orderedFamilies = [
    ...COARSE_FAMILY_ORDER.filter((family) => namesByFamily.has(family)),
    ...[...namesByFamily.keys()].filter((family) => !COARSE_FAMILY_ORDER.includes(family)),
  ];
  return orderedFamilies.map((family) => ({ family, subtypeNames: namesByFamily.get(family)! }));
};
