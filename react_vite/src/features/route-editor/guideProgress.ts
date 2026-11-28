import type { RouteRequirementTool } from './api';
import { getToolAction } from './guideTools';
import type { WizardChecklist, WizardStepState } from './taskRequirements';

// What happens when a step of the guide ends. Pure, so it is testable without the map.

export const findStep = (steps: WizardStepState[], tool: RouteRequirementTool | null): WizardStepState | undefined => (
  tool ? steps.find((step) => step.tools.includes(tool)) : undefined
);

// A required step that is not met yet. Optional steps are never offered by themselves.
export const isUnmetRequired = (step: WizardStepState): boolean => step.required && !step.met;

export const allRequiredMet = (checklist: Pick<WizardChecklist, 'steps' | 'generic' | 'confirmed'>): boolean => (
  checklist.steps.every((step) => !step.required || step.met)
  && (!checklist.confirmed || checklist.generic.every((requirement) => requirement.satisfied))
);

// The first unmet required step, starting after [afterKey] and wrapping round, never [afterKey] itself.
export const nextUnmetRequiredStep = (steps: WizardStepState[], afterKey: RouteRequirementTool | null = null): WizardStepState | null => {
  const current = steps.findIndex((step) => step.key === afterKey);
  const ordered = current < 0
    ? steps
    : [...steps.slice(current + 1), ...steps.slice(0, current)];
  return ordered.find(isUnmetRequired) ?? null;
};

export type StepEnd =
  // Start this tool's step.
  | { kind: 'start'; tool: RouteRequirementTool }
  // Every required step is met: stop and say so.
  | { kind: 'all_done' }
  // Nothing else to start (the step that ended is itself still unmet): just stop.
  | { kind: 'stop' };

// What follows when the user presses "Done, next step" on the step with [activeTool].
export const resolveStepEnd = (checklist: Pick<WizardChecklist, 'steps' | 'generic' | 'confirmed'>, activeTool: RouteRequirementTool | null): StepEnd => {
  const active = findStep(checklist.steps, activeTool);
  const next = nextUnmetRequiredStep(checklist.steps, active?.key ?? null);
  if (next) return { kind: 'start', tool: next.key };
  return allRequiredMet(checklist) ? { kind: 'all_done' } : { kind: 'stop' };
};

// A step with a fixed count ends by itself when the last one is placed; a single-shot tool (a polygon, a gate) when the
// editor has returned to select mode.
export const stepEndsByItself = (step: WizardStepState): boolean => (
  step.fixedCount !== null && step.count >= step.fixedCount
);

// The end of the active step, when it has come by itself: null while the step goes on.
export const autoAdvance = (
  checklist: Pick<WizardChecklist, 'steps' | 'generic' | 'confirmed'>,
  activeTool: RouteRequirementTool | null,
  mode: string,
): StepEnd | null => {
  const active = findStep(checklist.steps, activeTool);
  if (!active || !activeTool) return null;
  const singleShotDone = getToolAction(activeTool).singleShot === true && mode === 'view';
  if (!stepEndsByItself(active) && !singleShotDone) return null;
  return resolveStepEnd(checklist, activeTool);
};

// A step with a fixed count has nothing to press: it ends by itself, so the button only stops it. An open-ended step
// is ended by the user.
export const doneButtonLabel = (step: WizardStepState): string => (step.fixedCount !== null ? 'Stop' : 'Done, next step');

// A new route (no id in the URL) opens with the choice of task; an existing route opens as it is. The choice is made once
// per editor session: the chosen task is saved in the route's settings, and the route then has an id.
export const shouldOfferTaskChoice = (routeIdInUrl: string | null | undefined): boolean => !routeIdInUrl;
