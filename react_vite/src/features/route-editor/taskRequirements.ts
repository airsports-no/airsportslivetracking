import type { RouteRequirementResult, RouteRequirementTool, TaskCompatibilityResult, TaskCompatibilitySubtype, TaskTypeRouteEditorFlags } from './api';
import type { TaskTemplate } from './taskTemplates';

// The guide's steps (label, help text, which tool satisfies them, whether they are optional) come from the backend's
// route requirements (display.utilities.task_types, evaluated by display.services.route_compatibility), so the
// checklist and the backend verdict cannot differ. Until the backend has answered for the route, the subtype
// catalogue (the same requirements for an empty route) gives the steps and the editor's own counts the numbers.
// What each tool does in the editor is in guideTools.ts.

// An optional requirement (no minimum, no maximum) is always satisfied: it only describes a step of the guide, so it is
// not part of the checklist, which shows what the route must meet.
export const isOptionalRequirement = (requirement: RouteRequirementResult): boolean => (
  requirement.minimum === 0 && requirement.maximum === null
);

export const NO_ROUTE_EDITOR_FLAGS: TaskTypeRouteEditorFlags = {
  three_point_backbone: false,
  standalone_timed_turnpoints: false,
  circle_markers: false,
  curve_required: false,
  extension_waypoints: false,
};

// The special behaviour of the task type [subtypeKey] (the selected template's subtype), from the backend's registry.
// All false for a task type without a subtype (the legacy templates), an unknown one, or before the backend answered.
export const getRouteEditorFlags = (
  subtypes: TaskCompatibilitySubtype[] | null | undefined,
  subtypeKey: string | null | undefined,
): TaskTypeRouteEditorFlags => (
  subtypes?.find((subtype) => subtype.key === subtypeKey)?.flags ?? NO_ROUTE_EDITOR_FLAGS
);

// Which requirement carries the counts shown on a step when several share it.
const COUNT_REQUIREMENT_KEYS = ['route_waypoints', 'route_waypoint'];

// The order of the route waypoints is part of the route step, not a step of its own.
const SHARED_STEP_PROHIBITIONS = new Set(['route_waypoint_order']);

export type CompatibilityStatus = 'pending' | 'ready' | 'failed';

export interface WizardStepState {
  // The step's primary tool: its identity. Requirements sharing a tool are one step.
  key: RouteRequirementTool;
  // Every tool that satisfies the step: the primary tool, then the others of an "at least one of" requirement.
  tools: RouteRequirementTool[];
  label: string;
  help: string;
  // The backend requirements the step stands for; empty for an optional step.
  requirements: RouteRequirementResult[];
  // The step must be met by the route (an optional step is always met).
  required: boolean;
  // What the organiser sees as the count: the backend's found when confirmed, else the local count.
  count: number;
  // The backend requirement carrying minimum/maximum for display (null for optional steps).
  primary: RouteRequirementResult | null;
  // true: backend confirmed it is met; false: backend says it is not; null: not (yet) known or optional.
  satisfied: boolean | null;
  // Met as far as is known: the backend's verdict when confirmed, otherwise judged from the local count. An optional
  // step is always met.
  met: boolean;
  // The backend message explaining what is wrong, only when the backend said unsatisfied.
  message: string | null;
  // Upper limit from the backend's requirement (when known), to stop placing more markers.
  maximum: number | null;
  // Minimum equals maximum (and is above 0): the step ends by itself when the last one is placed.
  fixedCount: number | null;
}

export interface WizardChecklist {
  steps: WizardStepState[];
  // Backend requirements that no step shows, rendered as generic rows.
  generic: RouteRequirementResult[];
  // True only when the backend answered for the current route content.
  confirmed: boolean;
  // True when there are requirements at all (from the backend's answer or the catalogue).
  structureKnown: boolean;
}

const toolsOf = (requirement: RouteRequirementResult): RouteRequirementTool[] => (
  requirement.tool ? [requirement.tool, ...(requirement.other_tools ?? [])] : []
);

// 2.A4 (navigation over a known circuit): the circuit's known time gates are the timed turn points of its route, which
// the scoring flies as gates. A free-standing known time gate (what the registry's known_time_gate tool places) is not
// part of the route, so it scores nothing there: the guide offers the hidden gate and photo tools only, and says so.
const KNOWN_CIRCUIT_KEY = 'known_circuit';
export const KNOWN_CIRCUIT_TIME_GATE_HELP = (
  'The turn points of the circuit are its known time gates: they are timed and scored without adding anything here.'
);

const withoutFreeStandingTimeGates = (step: { tools: RouteRequirementTool[]; help: string }) => {
  if (!step.tools.includes('known_time_gate')) return step;
  return {
    tools: step.tools.filter((tool) => tool !== 'known_time_gate'),
    help: [KNOWN_CIRCUIT_TIME_GATE_HELP, step.help].filter(Boolean).join(' '),
  };
};

export const getRequirementsForTemplate = (
  template: TaskTemplate,
  compatibility: TaskCompatibilityResult | null,
): RouteRequirementResult[] | null => {
  if (!compatibility) return null;
  const subtype = compatibility.subtypes.find((item) => item.key === template.backendKey);
  return subtype ? subtype.requirements ?? [] : null;
};

// [localCount] counts what one tool places in the editor's own state (guideTools.countForTool).
export const buildWizardChecklist = (
  template: TaskTemplate,
  compatibility: TaskCompatibilityResult | null,
  catalogue: TaskCompatibilitySubtype[] | null,
  status: CompatibilityStatus,
  localCount: (tool: RouteRequirementTool) => number,
): WizardChecklist => {
  const fromBackend = getRequirementsForTemplate(template, compatibility);
  const catalogued = catalogue?.find((item) => item.key === template.backendKey)?.requirements ?? null;
  const requirements = fromBackend ?? catalogued;
  const confirmed = status === 'ready' && fromBackend !== null;

  // One step per tool, in the order of the requirements; a requirement without a tool is a generic row.
  const grouped = new Map<RouteRequirementTool, RouteRequirementResult[]>();
  const generic: RouteRequirementResult[] = [];
  const withoutTool: RouteRequirementResult[] = [];
  for (const requirement of requirements ?? []) {
    if (requirement.tool) {
      grouped.set(requirement.tool, [...(grouped.get(requirement.tool) ?? []), requirement]);
    } else {
      withoutTool.push(requirement);
    }
  }
  const sharedByStep = new Map<RouteRequirementTool, RouteRequirementResult[]>();
  for (const requirement of withoutTool) {
    if (requirement.maximum !== null && SHARED_STEP_PROHIBITIONS.has(requirement.key) && grouped.has('route_waypoint')) {
      sharedByStep.set('route_waypoint', [...(sharedByStep.get('route_waypoint') ?? []), requirement]);
    } else if (!isOptionalRequirement(requirement)) {
      generic.push(requirement);
    }
  }

  const steps: WizardStepState[] = [];
  for (const [tool, own] of grouped) {
    const required = own.filter((item) => !isOptionalRequirement(item));
    const checked = [...required, ...(sharedByStep.get(tool) ?? [])];
    const primary = checked.find((item) => COUNT_REQUIREMENT_KEYS.includes(item.key)) ?? checked[0] ?? null;
    const source = primary ?? own[0];
    const firstUnsatisfied = checked.find((item) => !item.satisfied) ?? null;
    const allTools = [...new Set(own.flatMap(toolsOf))];
    const stepHelp = source.help || own.find((item) => item.help)?.help || '';
    const { tools, help } = template.backendKey === KNOWN_CIRCUIT_KEY
      ? withoutFreeStandingTimeGates({ tools: allTools, help: stepHelp })
      : { tools: allTools, help: stepHelp };
    const local = tools.reduce((sum, item) => sum + localCount(item), 0);
    const counted = primary && primary.maximum !== 0 ? primary : null;
    const satisfied = confirmed && checked.length > 0 ? firstUnsatisfied === null : null;
    // Judged from the local count while the backend has not answered for this route content. A prohibition counts
    // the violations, so it is met at zero.
    const metLocally = primary === null
      ? true
      : local >= primary.minimum && (primary.maximum === null || local <= primary.maximum);
    steps.push({
      key: tool,
      tools,
      label: source.label,
      help,
      requirements: checked,
      required: checked.length > 0,
      count: confirmed && counted ? counted.found : local,
      primary,
      satisfied,
      met: satisfied !== null ? satisfied : metLocally,
      message: confirmed && firstUnsatisfied ? firstUnsatisfied.message : null,
      maximum: counted ? counted.maximum : null,
      fixedCount: counted && counted.maximum !== null && counted.maximum > 0 && counted.minimum === counted.maximum
        ? counted.maximum
        : null,
    });
  }

  return { steps, generic, confirmed, structureKnown: requirements !== null };
};
