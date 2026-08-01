import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../types';

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
  group: 'Legacy' | 'CIMA';
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

const takeoffGateStep = (help: string): WizardStep => ({
  key: 'takeoff_gate',
  label: 'Take-off gate',
  help,
  kind: 'takeoff_gate',
  minCount: 1,
  countMode: 'strict',
});

const landingGateStep = (help: string): WizardStep => ({
  key: 'landing_gate',
  label: 'Landing gate',
  help,
  kind: 'landing_gate',
  minCount: 1,
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
    description: 'This is still a precision route. Route waypoints are the visible time/turn points; curved legs use the normal curved-leg feature.',
    guideOnly: true,
    guideSummary: 'Build a normal precision route first. The ordinary visible route points are the known points, curved legs use the existing curved-leg feature, and hidden gates are inserted on the route afterwards.',
    steps: [
      routeStep('Build the precision route first. Use the existing curved-leg feature for curved sections.'),
      pointStep('known_time_gate', 'Visible known time points', 'Your visible route points are the known time points for this task. Use route geometry first; add explicit known-time markers only if you need extra authored markers beyond the normal route points.', 'known_time_gate', 'known_time_gate', 'route_insert', 1, 'route_waypoints'),
      pointStep('hidden_gate', 'Hidden gates', 'Insert hidden gates along the existing route where needed. You can insert points on the route and convert them to hidden gates in the point editor.', 'hidden_gate', 'hidden_gate', 'route_insert'),
    ],
  },
  {
    id: 'cima_a2',
    label: '2.A2 Precision navigation',
    group: 'CIMA',
    description: 'This is a standard precision route with visible turn points and hidden gates along the corridor.',
    guideOnly: true,
    guideSummary: 'Build the visible precision route first, then insert hidden gates along the existing route corridor.',
    steps: [
      routeStep('Build the visible route with start, visible turn points, and finish.'),
      pointStep('hidden_gate', 'Hidden gates', 'Insert hidden gates along the existing route corridor. You can insert points on the route and convert them to hidden gates in the point editor.', 'hidden_gate', 'hidden_gate', 'route_insert'),
    ],
  },
  {
    id: 'cima_a3',
    label: '2.A3 Contract navigation with time controls',
    group: 'CIMA',
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
    description: 'Known circuit plus hidden gates and observation/photo evidence.',
    guideOnly: true,
    guideSummary: 'Build the known circuit first, then add hidden gates along the route and observation/photo markers as evidence points.',
    steps: [
      routeStep('Build the known circuit route first.'),
      pointStep('hidden_gate', 'Hidden gates', 'Insert hidden gates on the existing circuit where needed.', 'hidden_gate', 'hidden_gate', 'route_insert'),
      observationStep('Add observation/photo markers associated with the task.'),
    ],
  },
  {
    id: 'cima_a5',
    label: '2.A5 Navigation with unknown legs',
    group: 'CIMA',
    description: 'Base route plus unknown-leg markers and observation/photo evidence.',
    guideOnly: true,
    guideSummary: 'Build the visible route first, then place unknown-leg markers and any supporting observation/photo markers.',
    steps: [
      routeStep('Build the visible base route first.'),
      pointStep('unknown_leg', 'Unknown legs', 'Place unknown-leg markers where the route becomes uncertain.', 'ul', 'route_waypoint', 'free_map'),
      observationStep('Add observation/photo markers used for scoring or evidence.'),
    ],
  },
  {
    id: 'cima_a6',
    label: '2.A6 Turnpoint hunt',
    group: 'CIMA',
    description: 'Three-point compulsory route backbone plus unordered catalogue turnpoints and optional photo evidence.',
    steps: [
      routeStep('Build exactly three route waypoints representing CP1/CP2/CP3 as SP, MP, and FP on the route backbone.'),
      pointStep('catalogue_turnpoint', 'Catalogue turnpoints', 'Place the turnpoint catalogue the pilot may choose from.', 'catalogue_turnpoint', 'catalogue_turnpoint', 'free_map'),
      observationStep('Optionally add photo markers and associate them with catalogue turnpoints as evidence targets.', 0),
    ],
  },
  {
    id: 'cima_a7',
    label: '2.A7 Circle',
    group: 'CIMA',
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
    description: 'ANR-based route. Build the route path first; auxiliary ANR paths may still need separate handling.',
    guideOnly: true,
    guideSummary: 'Build the ANR route first. Route-to-SP and route-from-FP auxiliary paths still need separate handling.',
    steps: [routeStep('Build the ANR route path with start and finish.')],
  },
  {
    id: 'cima_b2',
    label: '2.B2 Limited fuel turnpoint hunt',
    group: 'CIMA',
    description: 'Three-point compulsory route backbone plus unordered catalogue turnpoints, optional photo evidence, and fuel declaration later.',
    steps: [
      routeStep('Build exactly three route waypoints representing CP1/CP2/CP3 as SP, MP, and FP on the route backbone.'),
      pointStep('catalogue_turnpoint', 'Catalogue turnpoints', 'Place the turnpoint catalogue.', 'catalogue_turnpoint', 'catalogue_turnpoint', 'free_map'),
      observationStep('Optionally add photo markers and associate them with catalogue turnpoints as evidence targets.', 0),
    ],
  },
  {
    id: 'cima_b3',
    label: '2.B3 Duration',
    group: 'CIMA',
    description: 'Take-off and landing gates define the measured duration, and the landing area polygon defines the allowed touchdown area.',
    steps: [
      takeoffGateStep('Place the take-off gate.'),
      landingGateStep('Place the landing gate.'),
      polygonStep('duration_landing_area', 'Duration landing area', 'Draw the specified landing area polygon for the task.', 'duration_landing_area'),
    ],
  },
];

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
  if (step.kind === 'route') {
    return routePoints.filter((point) => (point.featureType || 'route_waypoint') === 'route_waypoint').length;
  }
  if (step.kind === 'point') {
    if (step.countMode === 'route_waypoints') {
      return routePoints.filter((point) => point.type === 'sp' || point.type === 'tp' || point.type === 'fp').length;
    }
    const pointPool = step.placement === 'free_map' ? standalonePoints : routePoints;
    return pointPool.filter((point) => {
      if (step.featureType) return point.featureType === step.featureType;
      return point.type === step.pointType;
    }).length;
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
  if (step.pointType === 'hidden_gate') return 'Click the existing route line to insert a hidden gate.';
  if (step.pointType === 'known_time_gate') return 'Click the existing route line to insert a known time gate.';
  return 'Click the existing route line to insert the required point.';
};
