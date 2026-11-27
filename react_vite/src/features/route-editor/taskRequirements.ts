import type { RouteRequirementResult, TaskCompatibilityResult } from './api';
import type { TaskTemplate, WizardStep } from './taskTemplates';

// The wizard's guidance (titles, help text, which tool to use, optional steps) lives in
// taskTemplates.ts. Whether a step is required, its minimum/maximum and whether it is satisfied
// come from the backend's route requirements (display.utilities.task_types, evaluated by
// display.services.route_compatibility), so the checklist and the backend verdict cannot differ.
// This file is the one place that connects the two.

// Backend requirement key -> key of the wizard step that guides the organiser through it. Several
// requirements may share a step (the route step covers the path, the waypoint count and their
// order). A requirement is only mapped when the selected template actually has that step and the
// requirement is not a prohibition (maximum 0 on a feature); everything else is shown as a generic
// checklist row, so a new backend rule can never be invisible in the wizard.
// Every key a task type can declare is listed in routeRequirementKeys.json, which a Django test
// keeps in sync with the registry and taskRequirements.test.ts checks against this table.
export const REQUIREMENT_STEP_KEYS: Record<string, string> = {
  route_path: 'route_waypoint',
  route_waypoint: 'route_waypoint',
  route_waypoints: 'route_waypoint',
  route_waypoint_order: 'route_waypoint',
  curved_leg: 'curved_leg',
  known_time_gate: 'timed_turnpoint',
  catalogue_turnpoint: 'catalogue_turnpoint',
  unknown_leg: 'unknown_leg',
  unknown_leg_extension: 'dummy',
  circle_start_marker: 'circle_start',
  circle_center_marker: 'circle_center',
  circle_entry_marker: 'circle_entry',
  circle_exit_marker: 'circle_exit',
  duration_landing_area: 'duration_landing_area',
  landing_gate: 'landing_gate',
  hidden_gate: 'hidden_gate',
};

// Which requirement carries the counts shown on a step when several share it.
const COUNT_REQUIREMENT_KEYS = ['route_waypoints', 'route_waypoint'];

export type CompatibilityStatus = 'pending' | 'ready' | 'failed';

export interface WizardStepState {
  step: WizardStep;
  // The backend requirements this step stands for; empty for an optional step.
  requirements: RouteRequirementResult[];
  required: boolean;
  // What the organiser sees as the count: the backend's found when confirmed, else the local count.
  count: number;
  // The backend requirement carrying minimum/maximum for display (null for optional steps).
  primary: RouteRequirementResult | null;
  // true: backend confirmed it is met; false: backend says it is not; null: not (yet) known or optional.
  satisfied: boolean | null;
  // The backend message explaining what is wrong, only when the backend said unsatisfied.
  message: string | null;
  // Upper limit from the backend's requirement (when known), to stop placing more markers.
  maximum: number | null;
}

export interface WizardChecklist {
  steps: WizardStepState[];
  // Backend requirements that no step shows, rendered as generic rows.
  generic: RouteRequirementResult[];
  // True only when the backend answered for the current route content.
  confirmed: boolean;
  // True when there is no backend answer at all yet, so required-ness is unknown.
  structureKnown: boolean;
}

export const getRequirementsForTemplate = (
  template: TaskTemplate,
  compatibility: TaskCompatibilityResult | null,
): RouteRequirementResult[] | null => {
  if (!compatibility) return null;
  const subtype = compatibility.subtypes.find((item) => item.key === template.backendKey);
  return subtype ? subtype.requirements ?? [] : null;
};

// route_waypoint_order counts violations (maximum 0) but is part of the route step, like the
// unknown-leg extension rule is part of the extension step.
const SHARED_STEP_PROHIBITIONS = new Set(['route_waypoint_order', 'unknown_leg_extension']);

export const buildWizardChecklist = (
  template: TaskTemplate,
  compatibility: TaskCompatibilityResult | null,
  status: CompatibilityStatus,
  localCount: (step: WizardStep) => number,
): WizardChecklist => {
  const requirements = getRequirementsForTemplate(template, compatibility);
  const confirmed = status === 'ready' && requirements !== null;

  const stepKeys = new Set(template.steps.map((step) => step.key));
  const byStep = new Map<string, RouteRequirementResult[]>();
  const generic: RouteRequirementResult[] = [];
  for (const requirement of requirements ?? []) {
    const stepKey = REQUIREMENT_STEP_KEYS[requirement.key];
    const belongsToStep = stepKey
      && stepKeys.has(stepKey)
      && (requirement.maximum !== 0 || SHARED_STEP_PROHIBITIONS.has(requirement.key));
    if (belongsToStep) {
      byStep.set(stepKey, [...(byStep.get(stepKey) ?? []), requirement]);
    } else {
      generic.push(requirement);
    }
  }

  const steps = template.steps.map((step): WizardStepState => {
    const own = byStep.get(step.key) ?? [];
    const primary = own.find((item) => COUNT_REQUIREMENT_KEYS.includes(item.key)) ?? own[0] ?? null;
    const firstUnsatisfied = own.find((item) => !item.satisfied) ?? null;
    let satisfied: boolean | null = null;
    if (confirmed && own.length > 0) satisfied = firstUnsatisfied === null;
    const counted = primary && !(primary.maximum === 0) ? primary : null;
    return {
      step,
      requirements: own,
      required: own.length > 0,
      count: confirmed && counted ? counted.found : localCount(step),
      primary,
      satisfied,
      message: confirmed && firstUnsatisfied ? firstUnsatisfied.message : null,
      maximum: counted ? counted.maximum : null,
    };
  });

  return { steps, generic, confirmed, structureKnown: requirements !== null };
};
