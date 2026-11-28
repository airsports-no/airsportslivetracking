import type { Gate, ObservationMarker, Polygon, RoutePoint } from '../../types';
import type { RouteRequirementTool } from './api';
import { routeLegs } from './routeIntegrity';

// How the guide acts on a requirement. The registry (display.utilities.task_types) says which tool satisfies a
// requirement; this file maps each tool name to what the route editor does when the user starts it. The mapping is
// total over ROUTE_REQUIREMENT_TOOLS (guideTools.test.ts checks it), so a tool the backend can name always has an entry.

// 'guide' steps only instruct the organiser (there is no tool to start).
export type WizardStepKind = 'route' | 'point' | 'observation' | 'takeoff_gate' | 'landing_gate' | 'polygon' | 'guide';

// What routeEditorWizardTransitions.ts turns into editor state.
export interface WizardStep {
  // The tool's name.
  key: string;
  label: string;
  help: string;
  kind: WizardStepKind;
  pointType?: RoutePoint['type'];
  featureType?: NonNullable<RoutePoint['featureType']>;
  polygonType?: Polygon['type'];
  placement?: 'route_insert' | 'free_map';
}

export interface ToolAction {
  // The button of a step with one tool.
  buttonLabel: string;
  // The button of a step with several tools ("at least one of"): the kind of feature the tool places.
  shortLabel: string;
  // What a click does while the tool is active; the banner over the map shows it when the step has no better prompt.
  prompt: string;
  // The editor state the tool starts. null: there is no placing tool (a leg is made curved in the point editor).
  step: Omit<WizardStep, 'key' | 'label' | 'help'> | null;
  // The tool ends itself when its one element is placed (the mode returns to select).
  singleShot?: boolean;
}

export const TOOL_ACTIONS: Record<RouteRequirementTool, ToolAction> = {
  route_waypoint: {
    buttonLabel: 'Place waypoints',
    shortLabel: 'Route waypoint',
    prompt: 'Click the map to place the next route waypoint.',
    step: { kind: 'route', pointType: 'tp', featureType: 'route_waypoint' },
  },
  // Inserted on the leg that is clicked (legInsertType in MapCanvas), not appended to the route.
  hidden_gate: {
    buttonLabel: 'Place hidden gates',
    shortLabel: 'Hidden gate',
    prompt: 'Click a leg of the route to place a hidden gate.',
    step: { kind: 'point', pointType: 'secret', featureType: 'route_waypoint', placement: 'route_insert' },
  },
  // A standalone timed point on the free map: that is what the registry counts as a known time gate.
  known_time_gate: {
    buttonLabel: 'Place timed points',
    shortLabel: 'Known time gate',
    prompt: 'Click the map to place a known time gate.',
    step: { kind: 'point', pointType: 'timed_turnpoint', featureType: 'known_time_gate', placement: 'free_map' },
  },
  catalogue_turnpoint: {
    buttonLabel: 'Place turn points',
    shortLabel: 'Catalogue turn point',
    prompt: 'Click the map to place a catalogue turn point.',
    step: { kind: 'point', pointType: 'catalogue_turnpoint', featureType: 'catalogue_turnpoint', placement: 'free_map' },
  },
  circle_start: {
    buttonLabel: 'Place start',
    shortLabel: 'Circle start',
    prompt: 'Click the map to place the circle start (SP).',
    step: { kind: 'point', pointType: 'circle_start', featureType: 'circle_start_marker', placement: 'free_map' },
  },
  circle_center: {
    buttonLabel: 'Place centre',
    shortLabel: 'Circle centre',
    prompt: 'Click the map to place the circle centre (CM).',
    step: { kind: 'point', pointType: 'circle_center', featureType: 'circle_center_marker', placement: 'free_map' },
  },
  circle_entry: {
    buttonLabel: 'Place entry',
    shortLabel: 'Circle entry',
    prompt: 'Click the map to place the circle entry (X).',
    step: { kind: 'point', pointType: 'circle_entry', featureType: 'circle_entry_marker', placement: 'free_map' },
  },
  circle_exit: {
    buttonLabel: 'Place exit',
    shortLabel: 'Circle exit',
    prompt: 'Click the map to place the circle exit (WP).',
    step: { kind: 'point', pointType: 'circle_exit', featureType: 'circle_exit_marker', placement: 'free_map' },
  },
  photo: {
    buttonLabel: 'Place photos',
    shortLabel: 'Photo',
    prompt: 'Click the map, close to the route, where the photo was taken.',
    step: { kind: 'observation' },
  },
  landing_area: {
    buttonLabel: 'Draw area',
    shortLabel: 'Landing area',
    prompt: 'Click the map to draw the landing area. Click the first point to close it.',
    step: { kind: 'polygon', polygonType: 'duration_landing_area' },
    singleShot: true,
  },
  takeoff_gate: {
    buttonLabel: 'Place gate',
    shortLabel: 'Take-off gate',
    prompt: 'Click the two ends of the take-off line.',
    step: { kind: 'takeoff_gate' },
    singleShot: true,
  },
  landing_gate: {
    buttonLabel: 'Place gate',
    shortLabel: 'Landing gate',
    prompt: 'Click the two ends of the landing line.',
    step: { kind: 'landing_gate' },
    singleShot: true,
  },
  // Click a backbone waypoint to make it an unknown-leg point; the extension waypoints follow by themselves.
  unknown_leg_point: {
    buttonLabel: 'Choose point',
    shortLabel: 'Unknown-leg point',
    prompt: 'Click the route waypoint that should be an unknown-leg point.',
    step: { kind: 'point', pointType: 'ul', featureType: 'route_waypoint', placement: 'route_insert' },
  },
  // Started through the unknown-leg flow (beginDummyBranchStep): pick the amber point, then click for each waypoint.
  extension_waypoint: {
    buttonLabel: 'Place extensions',
    shortLabel: 'Extension waypoint',
    prompt: 'Click an amber unknown-leg point, then click the map for each extension waypoint.',
    step: { kind: 'point', pointType: 'dummy', featureType: 'dummy_branch_waypoint', placement: 'free_map' },
  },
  // No placing tool: a leg is made curved in the point editor (or with the curve option while placing waypoints).
  curved_leg: {
    buttonLabel: 'How',
    shortLabel: 'Curved leg',
    prompt: 'Select a route waypoint and choose Make Curved, or tick Add Curved Leg while placing waypoints.',
    step: null,
  },
};

export const getToolAction = (tool: RouteRequirementTool): ToolAction => TOOL_ACTIONS[tool];

// The editor state to start for [tool], or null for a tool without a placing tool (curved_leg).
export const getToolWizardStep = (tool: RouteRequirementTool, label: string, help: string): WizardStep | null => {
  const { step } = TOOL_ACTIONS[tool];
  return step ? { key: tool, label, help, ...step } : null;
};

const BACKBONE_TYPES = new Set<RoutePoint['type']>(['sp', 'tp', 'fp', 'secret', 'anrtp', 'ul', 'unknown_leg', 'dummy']);

export interface RouteContent {
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
}

// How many of what the tool places the route holds now, counted from the editor's own state: what the guide shows
// until the backend has answered for the current route content. For the extension waypoints it is the number of
// unknown-leg points that still have none, as in the registry (a prohibition).
export const countForTool = (tool: RouteRequirementTool, content: RouteContent): number => {
  const { routePoints, standalonePoints } = content;
  switch (tool) {
    case 'route_waypoint':
      return routePoints.filter((point) => point.featureType !== 'dummy_branch_waypoint' && BACKBONE_TYPES.has(point.type)).length;
    case 'hidden_gate':
      return routePoints.filter((point) => point.type === 'secret').length;
    case 'known_time_gate':
      return standalonePoints.filter((point) => point.type === 'timed_turnpoint').length;
    case 'catalogue_turnpoint':
    case 'circle_start':
    case 'circle_center':
    case 'circle_entry':
    case 'circle_exit': {
      const pointType = TOOL_ACTIONS[tool].step?.pointType;
      return standalonePoints.filter((point) => point.type === pointType).length;
    }
    case 'photo':
      return content.observationMarkers.length;
    case 'landing_area':
      return content.polygons.filter((polygon) => polygon.type === 'duration_landing_area').length;
    case 'takeoff_gate':
      return content.gates.filter((gate) => gate.type === 'takeoff').length;
    case 'landing_gate':
      return content.gates.filter((gate) => gate.type === 'landing').length;
    case 'unknown_leg_point':
      return routePoints.filter((point) => point.type === 'ul').length;
    case 'extension_waypoint':
      return routePoints.filter((point) => (
        point.type === 'ul'
        && !standalonePoints.some((other) => other.featureType === 'dummy_branch_waypoint' && other.triggerPointId === point.id)
      )).length;
    case 'curved_leg':
      // Legs, not segments: a hidden gate splits a curve into two curved segments, which is still one curved leg
      return routeLegs(routePoints).filter((leg) => leg.controls.length > 0).length;
    default:
      return 0;
  }
};
