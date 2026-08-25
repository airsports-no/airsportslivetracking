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
