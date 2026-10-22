import { createStandaloneWizardPoint } from './routeEditorMapClickHelpers';
import { LatLng, RoutePoint } from '../../types';

export type DummyBranchPhase = 'idle' | 'awaiting_trigger' | 'placing';

export const UNKNOWN_LEG_TRIGGER_TYPE = 'ul';

export const isUnknownLegTrigger = (point?: RoutePoint | null) => point?.type === UNKNOWN_LEG_TRIGGER_TYPE;

export function getDummyBranchPhase(
  stepActive: boolean,
  triggerId: string | null,
  routePoints: RoutePoint[],
): DummyBranchPhase {
  if (!stepActive) {
    return 'idle';
  }

  if (!triggerId) {
    return 'awaiting_trigger';
  }

  const trigger = routePoints.find((point) => point.id === triggerId);
  return isUnknownLegTrigger(trigger) ? 'placing' : 'awaiting_trigger';
}

export function getWizardBannerText(
  phase: DummyBranchPhase,
  triggerName?: string | null,
): { title: string; instruction: string } {
  if (phase === 'placing') {
    return {
      title: `Placing dummy waypoints for ${triggerName || 'selected trigger'}`,
      instruction: 'Click the map for each dummy waypoint on this branch.',
    };
  }

  if (phase === 'awaiting_trigger') {
    return {
      title: 'Select an unknown-leg trigger',
      instruction: 'Click an unknown-leg trigger on the map (amber) to start placing dummy waypoints.',
    };
  }

  return {
    title: 'No active unknown-leg step',
    instruction: 'Start the unknown-leg wizard step to select a trigger and place dummy waypoints.',
  };
}

export function buildDummyBranchWaypoint(
  latlng: LatLng,
  trigger: RoutePoint,
  existingBranchPoints: RoutePoint[],
): RoutePoint {
  const nextCount = existingBranchPoints.length + 1;
  const point = createStandaloneWizardPoint(
    latlng,
    'dummy',
    'dummy_branch_waypoint',
    `${trigger.name}-D${nextCount}`,
    nextCount,
  );

  return {
    ...point,
    triggerPointId: trigger.id,
    branchSequence: existingBranchPoints.length,
    isTiming: false,
    isPassing: true,
  };
}

const withName = (point: RoutePoint, name: string): RoutePoint => (point.name === name ? point : { ...point, name });

/**
 * Names the points of an unknown-legs (2.A5) route in the order the map shows them, so that the numbers on the
 * generated map follow the route including its dummy legs: SP, then TP 1, TP 2, ... through the turnpoints and each
 * unknown-leg trigger's dummy waypoints (right after the trigger, in branch order), then FP. The triggers themselves
 * are never shown and are named Unknown leg 1, 2, ...; secret points keep their names. Points whose name is already
 * right are returned as they are, so an already named route comes back unchanged (same arrays).
 */
export function nameUnknownLegsRoutePoints(
  routePoints: RoutePoint[],
  standalonePoints: RoutePoint[],
): { routePoints: RoutePoint[]; standalonePoints: RoutePoint[] } {
  const dummiesByTrigger = new Map<string, RoutePoint[]>();
  standalonePoints.forEach((point) => {
    if (point.featureType === 'dummy_branch_waypoint' && point.triggerPointId) {
      dummiesByTrigger.set(point.triggerPointId, [...(dummiesByTrigger.get(point.triggerPointId) || []), point]);
    }
  });
  const dummyNames = new Map<string, string>();
  let turnpointCounter = 0;
  let unknownLegCounter = 0;

  const namedRoutePoints = routePoints.map((point, index) => {
    if (index === 0) return withName(point, 'SP');
    if (index === routePoints.length - 1) return withName(point, 'FP');
    if (point.type === 'secret') return point;
    if (isUnknownLegTrigger(point)) {
      unknownLegCounter += 1;
      [...(dummiesByTrigger.get(point.id) || [])]
        .sort((a, b) => (a.branchSequence ?? 0) - (b.branchSequence ?? 0))
        .forEach((dummy) => {
          turnpointCounter += 1;
          dummyNames.set(dummy.id, `TP ${turnpointCounter}`);
        });
      return withName(point, `Unknown leg ${unknownLegCounter}`);
    }
    turnpointCounter += 1;
    return withName(point, `TP ${turnpointCounter}`);
  });
  const namedStandalonePoints = standalonePoints.map((point) => {
    const name = dummyNames.get(point.id);
    return name ? withName(point, name) : point;
  });

  const unchanged = (before: RoutePoint[], after: RoutePoint[]) => after.every((point, index) => point === before[index]);
  return {
    routePoints: unchanged(routePoints, namedRoutePoints) ? routePoints : namedRoutePoints,
    standalonePoints: unchanged(standalonePoints, namedStandalonePoints) ? standalonePoints : namedStandalonePoints,
  };
}

// The point a dummy-branch waypoint's leg starts from: the waypoint before it on its branch, or the unknown-leg trigger
// for the first one. A curved dummy leg is drawn from there.
export function previousOnDummyBranch(
  point: RoutePoint,
  routePoints: RoutePoint[],
  standalonePoints: RoutePoint[],
): RoutePoint | undefined {
  if (point.featureType !== 'dummy_branch_waypoint' || !point.triggerPointId) return undefined;
  const branch = standalonePoints
    .filter((item) => item.featureType === 'dummy_branch_waypoint' && item.triggerPointId === point.triggerPointId)
    .sort((left, right) => (left.branchSequence ?? 0) - (right.branchSequence ?? 0));
  const position = branch.findIndex((item) => item.id === point.id);
  if (position > 0) return branch[position - 1];
  return routePoints.find((item) => item.id === point.triggerPointId);
}

// The waypoint after [point] on its dummy branch, or the first one when [point] is the trigger: the leg starting at
// [point], whose curve handle moves along when [point] is dragged
export function nextOnDummyBranch(point: RoutePoint, standalonePoints: RoutePoint[]): RoutePoint | undefined {
  const triggerId = point.featureType === 'dummy_branch_waypoint' ? point.triggerPointId : point.id;
  if (!triggerId) return undefined;
  const branch = standalonePoints
    .filter((item) => item.featureType === 'dummy_branch_waypoint' && item.triggerPointId === triggerId)
    .sort((left, right) => (left.branchSequence ?? 0) - (right.branchSequence ?? 0));
  if (point.featureType !== 'dummy_branch_waypoint') return branch[0];
  const position = branch.findIndex((item) => item.id === point.id);
  return position >= 0 ? branch[position + 1] : undefined;
}
