import { Mode } from '../../types';
import { TaskTemplate, WizardStep } from './taskTemplates';

export type WizardTransition = {
  mode: Mode | null;
  currentWizardActionLabel: string | null;
  wizardRouteInsertType: string | null;
  wizardRouteInsertFeatureType: string | undefined;
  wizardPolygonType: string | null;
  clearSelectionType: boolean;
  nextSelectionType: 'wizard' | 'point' | 'standalone_point' | null;
  resetTempPolygonPoints: boolean;
  routeInsertPrompt: string | null;
};

const DEFAULT_TRANSITION: WizardTransition = {
  mode: null,
  currentWizardActionLabel: null,
  wizardRouteInsertType: null,
  wizardRouteInsertFeatureType: undefined,
  wizardPolygonType: null,
  clearSelectionType: false,
  nextSelectionType: null,
  resetTempPolygonPoints: false,
  routeInsertPrompt: null,
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
        clearSelectionType: true,
        nextSelectionType: 'wizard',
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
