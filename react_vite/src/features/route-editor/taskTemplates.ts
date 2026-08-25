import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../types';

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

export type WizardStepKind = 'route' | 'point' | 'observation' | 'takeoff_gate' | 'landing_gate' | 'polygon';
export type WizardStepCountMode = 'strict' | 'route_waypoints';

export interface WizardStep {
  key: string;
  label: string;
  help: string;
  kind: WizardStepKind;
  minCount: number;
  maxCount?: number;
  pointType?: RoutePoint['type'];
  featureType?: NonNullable<RoutePoint['featureType']>;
  polygonType?: Polygon['type'];
  placement?: 'route_insert' | 'free_map';
  countMode?: WizardStepCountMode;
}

export interface TaskTemplate {
  id: TaskTemplateId;
  label: string;
  group: TaskTemplateGroup;
  // Backend task_subtype key (e.g. 'circle') for CIMA templates - used to
  // check fine-grained per-subtype access ('cima:<subtype>'). Legacy
  // templates have no subtype and are always visible.
  subtype?: string;
  description: string;
  steps: WizardStep[];
  guideOnly?: boolean;
  guideSummary?: string;
}

const routeStep = (help: string): WizardStep => ({
  key: 'route_waypoint',
  label: 'Route path',
  help,
  kind: 'route',
  minCount: 3,
  pointType: 'tp',
  featureType: 'route_waypoint',
  countMode: 'strict',
});

const pointStep = (
  key: string,
  label: string,
  help: string,
  pointType: RoutePoint['type'],
  featureType: NonNullable<RoutePoint['featureType']>,
  placement: 'route_insert' | 'free_map',
  minCount = 1,
  maxCount?: number,
  countMode: WizardStepCountMode = 'strict',
): WizardStep => ({
  key,
  label,
  help,
  kind: 'point',
  minCount,
  maxCount,
  pointType,
  featureType,
  placement,
  countMode,
});

const observationStep = (help: string, minCount = 1): WizardStep => ({
  key: 'observation_photo',
  label: 'Observation photos',
  help,
  kind: 'observation',
  minCount,
  countMode: 'strict',
});

const takeoffGateStep = (help: string, minCount = 1): WizardStep => ({
  key: 'takeoff_gate',
  label: 'Take-off gate',
  help,
  kind: 'takeoff_gate',
  minCount,
  countMode: 'strict',
});

const landingGateStep = (help: string, minCount = 1): WizardStep => ({
  key: 'landing_gate',
  label: 'Landing gate',
  help,
  kind: 'landing_gate',
  minCount,
  countMode: 'strict',
});

const polygonStep = (
  key: string,
  label: string,
  help: string,
  polygonType: Polygon['type'],
  minCount = 1,
): WizardStep => ({
  key,
  label,
  help,
  kind: 'polygon',
  minCount,
  polygonType,
  countMode: 'strict',
});

export const TASK_TEMPLATES: TaskTemplate[] = [
  {
    id: 'precision',
    label: 'Precision',
    group: 'Legacy',
    description: 'Build a regular precision route with start, visible turn points, finish, and optional secret points.',
    guideOnly: true,
    guideSummary: 'Build a normal precision route with the usual point tools. Use the point editor to convert intermediate points to secret points where needed.',
    steps: [
      routeStep('Build a normal precision route. Use curved legs if needed. Add secret points by clicking the route line in View mode.'),
    ],
  },
  {
    id: 'anr',
    label: 'ANR',
    group: 'Legacy',
    description: 'Build the ANR base route first. Auxiliary ANR paths are still outside this first guided flow.',
    guideOnly: true,
    guideSummary: 'Build the main ANR route first with the normal point tools. Auxiliary ANR paths still need separate authoring later.',
    steps: [routeStep('Build the ANR route path with start, route waypoints, and finish.')],
  },
  {
    id: 'airsports_challenge',
    label: 'Air Sports Challenge',
    group: 'Legacy',
    description: 'Build the challenge base route first.',
    guideOnly: true,
    guideSummary: 'Build the challenge route with the normal route tools, then refine any task-specific details afterwards.',
    steps: [routeStep('Build the challenge route path with start, route waypoints, and finish.')],
  },
  {
    id: 'cima_a1',
    label: '2.A1 Curve navigation with time estimation',
    group: 'CIMA',
    subtype: 'curve_navigation_time_estimation',
    description: 'This is still a precision route, but it must include at least one curved leg. Route waypoints are the visible time/turn points; curved legs use the normal curved-leg feature. Hidden gates are optional but recommended.',
    guideOnly: true,
    guideSummary: 'Build a normal precision route first. The ordinary visible route points are the known points, curved legs use the existing curved-leg feature. Hidden gates are not required, but consider adding a few along the route for spatial-precision scoring.',
    steps: [
      routeStep('Build the precision route first. This task requires at least one curved leg - use the curve tool (hold the curve modifier while placing a point, or convert a leg in the point editor) for at least one section.'),
      pointStep('known_time_gate', 'Visible known time points', 'Your visible route points are the known time points for this task. Use route geometry first; add explicit known-time markers only if you need extra authored markers beyond the normal route points.', 'tp', 'route_waypoint', 'route_insert', 1, 'route_waypoints'),
      pointStep('hidden_gate', 'Hidden gates (optional)', 'Not required, but consider inserting a few hidden gates along the route to add spatial-precision scoring. You can insert points on the route and convert them to hidden gates in the point editor.', 'secret', 'route_waypoint', 'route_insert', 0),
    ],
  },
  {
    id: 'cima_a2',
    label: '2.A2 Precision navigation',
    group: 'CIMA',
    subtype: 'precision_navigation',
    description: 'This is a standard precision route with visible turn points. Hidden gates along the corridor are optional but recommended.',
    guideOnly: true,
    guideSummary: 'Build the visible precision route first. Hidden gates are not required, but consider adding a few along the route corridor for spatial-precision scoring.',
    steps: [
      routeStep('Build the visible route with start, visible turn points, and finish.'),
      pointStep('hidden_gate', 'Hidden gates (optional)', 'Not required, but consider inserting a few hidden gates along the route corridor to add spatial-precision scoring. You can insert points on the route and convert them to hidden gates in the point editor.', 'secret', 'route_waypoint', 'route_insert', 0),
    ],
  },
  {
    id: 'cima_a3',
    label: '2.A3 Contract navigation with time controls',
    group: 'CIMA',
    subtype: 'contract_navigation_time_controls',
    description: 'Base route plus catalogue turnpoints; declaration ordering happens later in contestant configuration.',
    steps: [
      routeStep('Build exactly three route waypoints representing SP, MP, and FP.'),
      pointStep('catalogue_turnpoint', 'Catalogue turnpoints', 'Place the turnpoints that the pilot may later declare in sequence.', 'catalogue_turnpoint', 'catalogue_turnpoint', 'free_map'),
      observationStep('Optionally add photo markers and associate them with specific catalogue turnpoints.', 0),
    ],
  },
  {
    id: 'cima_a4',
    label: '2.A4 Navigation over a known circuit',
    group: 'CIMA',
    subtype: 'known_circuit',
    description: 'Known circuit route. Hidden gates and observation/photo evidence are both optional but recommended - the task typically uses at least one form of evidence.',
    guideOnly: true,
    guideSummary: 'Build the known circuit first. Neither hidden gates nor observation/photo markers are required, but consider adding at least one of the two as evidence for scoring.',
    steps: [
      routeStep('Build the known circuit route first.'),
      pointStep('hidden_gate', 'Hidden gates (optional)', 'Not required, but consider inserting a few hidden gates on the circuit as evidence for scoring.', 'secret', 'route_waypoint', 'route_insert', 0),
      observationStep('Not required, but consider adding a few observation/photo markers as evidence for scoring.', 0),
    ],
  },
  {
    id: 'cima_a5',
    label: '2.A5 Navigation with unknown legs',
    group: 'CIMA',
    subtype: 'unknown_legs',
    description: 'True backbone route plus unknown-leg trigger points and separate dummy branches. Hidden route-backbone gates and observation/photo evidence are both optional but recommended.',
    guideSummary: 'Build the true backbone first. Convert existing backbone points into unknown-leg triggers, then add dummy-branch waypoints from those triggers.',
    steps: [
      routeStep('Build the true route backbone first. This backbone is the actual route flown by the contestant.'),
      pointStep('unknown_leg', 'Unknown-leg triggers', 'Select an existing backbone waypoint and change its type to Unknown Leg so it becomes a trigger.', 'ul', 'route_waypoint', 'route_insert'),
      pointStep('dummy', 'Dummy branch waypoints', 'Select an unknown-leg trigger first, then add one or more dummy waypoints as a separate visible branch from that trigger.', 'dummy', 'dummy_branch_waypoint', 'free_map', 1),
      pointStep('hidden_gate', 'Hidden gates (optional)', 'Not required, but consider inserting a few hidden gates directly on the true route backbone as evidence for scoring.', 'secret', 'route_waypoint', 'route_insert', 0),
      observationStep('Not required, but consider adding a few observation/photo markers as evidence for scoring.', 0),
    ],
  },
  {
    id: 'cima_a6',
    label: '2.A6 Turnpoint hunt',
    group: 'CIMA',
    subtype: 'turnpoint_hunt',
    description: 'No route backbone. Exactly three standalone timed turnpoints, plus any number of untimed catalogue turnpoints. The contestant declares the order.',
    steps: [
      pointStep('timed_turnpoint', 'Timed turnpoints', 'Place exactly three standalone timed turnpoints (CP1/CP2/CP3). Their crossing times and order are declared per contestant, not fixed here.', 'timed_turnpoint', 'known_time_gate', 'free_map', 3, 3),
      pointStep('catalogue_turnpoint', 'Catalogue turnpoints', 'Place the untimed turnpoint catalogue the pilot may choose from.', 'catalogue_turnpoint', 'catalogue_turnpoint', 'free_map'),
      observationStep('Optionally add photo markers and associate them with catalogue turnpoints as evidence targets.', 0),
    ],
  },
  {
    id: 'cima_a7',
    label: '2.A7 Circle',
    group: 'CIMA',
    subtype: 'circle',
    description: 'Explicit circle markers: start, center, entry, and exit.',
    steps: [
      pointStep('circle_start', 'Circle start', 'Place the circle start marker (SP).', 'circle_start', 'circle_start_marker', 'free_map', 1, 1),
      pointStep('circle_center', 'Circle center', 'Place the circle center marker (CM).', 'circle_center', 'circle_center_marker', 'free_map', 1, 1),
      pointStep('circle_entry', 'Circle entry', 'Place the circle entry marker (X).', 'circle_entry', 'circle_entry_marker', 'free_map', 1, 1),
      pointStep('circle_exit', 'Circle exit', 'Place the circle exit marker (WP).', 'circle_exit', 'circle_exit_marker', 'free_map', 1, 1),
    ],
  },
  {
    id: 'cima_a8',
    label: '2.A8 Precision navigation ANR',
    group: 'CIMA',
    subtype: 'anr_catalogue',
    description: 'ANR-based route. Build the route path first; auxiliary ANR paths may still need separate handling.',
    guideOnly: true,
    guideSummary: 'Build the ANR route first. Route-to-SP and route-from-FP auxiliary paths still need separate handling.',
    steps: [routeStep('Build the ANR route path with start and finish.')],
  },
  {
    id: 'cima_b2',
    label: '2.B2 Limited fuel turnpoint hunt',
    group: 'CIMA',
    subtype: 'limited_fuel_turnpoint_hunt',
    description: 'No route backbone. Exactly three standalone timed turnpoints, plus any number of untimed catalogue turnpoints, and a fuel-endurance declaration later. Not a precision task: all gate crossings score.',
    steps: [
      pointStep('timed_turnpoint', 'Timed turnpoints', 'Place exactly three standalone timed turnpoints (CP1/CP2/CP3). Only their crossing times are declared per contestant; there is no required order.', 'timed_turnpoint', 'known_time_gate', 'free_map', 3, 3),
      pointStep('catalogue_turnpoint', 'Catalogue turnpoints', 'Place the untimed turnpoint catalogue.', 'catalogue_turnpoint', 'catalogue_turnpoint', 'free_map'),
      observationStep('Optionally add photo markers and associate them with catalogue turnpoints as evidence targets.', 0),
    ],
  },
  {
    id: 'cima_b3',
    label: '2.B3 Duration',
    group: 'CIMA',
    subtype: 'duration',
    description: 'Not required, but placing take-off and landing gates gives the most precise measured duration. Without them, take-off/landing is inferred from the tracked speed profile instead. The landing area polygon defines the allowed touchdown area.',
    guideSummary: 'Use the steps below to place the take-off and landing gates that mark the start and end of the measured duration, and to draw the landing area.',
    steps: [
      takeoffGateStep('Place a take-off gate to mark exactly when the measured duration starts. Not required - if left unplaced, take-off is instead inferred from a sustained near-zero-speed hold followed by a rise in tracked speed, which is less precise.', 0),
      landingGateStep('Place a landing gate to mark exactly when the measured duration ends. Not required - if left unplaced, landing is instead inferred from a sustained drop to near-zero tracked speed, which is less precise.', 0),
      polygonStep('duration_landing_area', 'Duration landing area', 'Draw the specified landing area polygon for the task.', 'duration_landing_area'),
    ],
  },
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

export const getTaskTemplateById = (id: string | null | undefined): TaskTemplate | undefined =>
  TASK_TEMPLATES.find((template) => template.id === id);

export const countWizardStepMatches = (
  step: WizardStep,
  routePoints: RoutePoint[],
  standalonePoints: RoutePoint[],
  gates: Gate[],
  observationMarkers: ObservationMarker[],
  polygons: Polygon[],
): number => {
  const routeInsertBackboneTypes = new Set<RoutePoint['type']>([
    'sp',
    'tp',
    'fp',
    'secret',
    'anrtp',
    'ul',
    'unknown_leg',
    'dummy',
  ]);

  if (step.kind === 'route') {
    return routePoints.filter((point) => point.featureType !== 'dummy_branch_waypoint' && routeInsertBackboneTypes.has(point.type)).length;
  }
  if (step.kind === 'point') {
    if (step.countMode === 'route_waypoints') {
      return routePoints.filter((point) => point.type === 'sp' || point.type === 'tp' || point.type === 'fp').length;
    }
    const pointPool = step.placement === 'free_map' ? standalonePoints : routePoints;
    if (step.featureType === 'dummy_branch_waypoint') {
      return pointPool.filter((point) => point.featureType === 'dummy_branch_waypoint' && point.type === step.pointType).length;
    }
    return pointPool.filter((point) => point.type === step.pointType).length;
  }
  if (step.kind === 'observation') {
    return observationMarkers.length;
  }
  if (step.kind === 'takeoff_gate') {
    return gates.filter((gate) => gate.type === 'takeoff').length;
  }
  if (step.kind === 'landing_gate') {
    return gates.filter((gate) => gate.type === 'landing').length;
  }
  if (step.kind === 'polygon') {
    return polygons.filter((polygon) => polygon.type === step.polygonType).length;
  }
  return 0;
};

export const getWizardRouteInsertLabel = (step: WizardStep): string => {
  if (step.key === 'hidden_gate') return 'Click the existing true backbone route line to insert a hidden gate.';
  if (step.key === 'known_time_gate') return 'Click the existing route line to insert a known time gate.';
  if (step.pointType === 'ul') return 'Select an existing backbone waypoint and change its type to Unknown Leg in the point editor.';
  if (step.featureType === 'dummy_branch_waypoint') return 'Select an unknown-leg trigger waypoint first, then click the map to add dummy-branch waypoints.';
  return 'Click the existing route line to insert the required point.';
};
