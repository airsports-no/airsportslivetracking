import { Mode, RoutePoint } from '../../types';
import { TaskTemplate, WizardStep } from './taskTemplates';

export type WizardTransition = {
  mode: Mode | null;
  currentWizardActionLabel: string | null;
  wizardRouteInsertType: string | null;
  wizardRouteInsertFeatureType: string | undefined;
  wizardPolygonType: string | null;
  clearSelectionType: boolean;
  preserveSelectedPoint: boolean;
  nextSelectionType: 'wizard' | 'point' | 'standalone_point' | null;
  resetTempPolygonPoints: boolean;
  routeInsertPrompt: string | null;
  selectExistingRouteType?: RoutePoint['type'] | null;
  selectExistingRouteFeatureType?: RoutePoint['featureType'] | undefined;
};

const DEFAULT_TRANSITION: WizardTransition = {
  mode: null,
  currentWizardActionLabel: null,
  wizardRouteInsertType: null,
  wizardRouteInsertFeatureType: undefined,
  wizardPolygonType: null,
  clearSelectionType: false,
  preserveSelectedPoint: false,
  nextSelectionType: null,
  resetTempPolygonPoints: false,
  routeInsertPrompt: null,
  selectExistingRouteType: null,
  selectExistingRouteFeatureType: undefined,
};

export function getWizardTransition(step: WizardStep | undefined, routeInsertLabel: (step: WizardStep) => string): WizardTransition {
  if (!step) {
    return DEFAULT_TRANSITION;
  }

  if (step.kind === 'route') {
    return {
      ...DEFAULT_TRANSITION,
      mode: 'add_point',
      currentWizardActionLabel: step.help,
    };
  }

  if (step.kind === 'point') {
    if (step.placement === 'route_insert') {
      if (step.pointType === 'ul') {
        return {
          ...DEFAULT_TRANSITION,
          mode: 'view',
          currentWizardActionLabel: step.help,
          clearSelectionType: false,
          nextSelectionType: 'point',
          routeInsertPrompt: routeInsertLabel(step),
          selectExistingRouteType: step.pointType ?? null,
          selectExistingRouteFeatureType: step.featureType,
        };
      }
      return {
        ...DEFAULT_TRANSITION,
        mode: 'add_point',
        currentWizardActionLabel: step.help,
        wizardRouteInsertType: step.pointType ?? null,
        wizardRouteInsertFeatureType: step.featureType,
        routeInsertPrompt: routeInsertLabel(step),
      };
    }

    if (step.featureType === 'catalogue_turnpoint') {
      return {
        ...DEFAULT_TRANSITION,
        mode: 'add_catalogue_turnpoint',
        currentWizardActionLabel: step.help,
        clearSelectionType: true,
        nextSelectionType: 'wizard',
      };
    }

    if (step.placement === 'free_map') {
      return {
        ...DEFAULT_TRANSITION,
        mode: 'add_point',
        currentWizardActionLabel: step.help,
        wizardRouteInsertType: step.pointType ?? null,
        wizardRouteInsertFeatureType: step.featureType,
        clearSelectionType: step.featureType !== 'dummy_branch_waypoint',
        preserveSelectedPoint: step.featureType === 'dummy_branch_waypoint',
        nextSelectionType: step.featureType === 'dummy_branch_waypoint' ? 'point' : 'wizard',
      };
    }

    return DEFAULT_TRANSITION;
  }

  if (step.kind === 'observation') {
    return {
      ...DEFAULT_TRANSITION,
      mode: 'add_observation',
      currentWizardActionLabel: step.help,
    };
  }

  if (step.kind === 'takeoff_gate') {
    return {
      ...DEFAULT_TRANSITION,
      mode: 'add_takeoff',
      currentWizardActionLabel: step.help,
    };
  }

  if (step.kind === 'landing_gate') {
    return {
      ...DEFAULT_TRANSITION,
      mode: 'add_landing',
      currentWizardActionLabel: step.help,
    };
  }

  if (step.kind === 'polygon') {
    return {
      ...DEFAULT_TRANSITION,
      mode: 'add_polygon',
      currentWizardActionLabel: step.help,
      wizardPolygonType: step.polygonType ?? null,
      resetTempPolygonPoints: true,
    };
  }

  return DEFAULT_TRANSITION;
}

export function getWizardStep(template: TaskTemplate | undefined, stepKey: string): WizardStep | undefined {
  return template?.steps.find((item) => item.key === stepKey);
}
