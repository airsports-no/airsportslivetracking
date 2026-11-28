import React from 'react';
import { CheckCircle2, Circle, Wand2, X } from 'lucide-react';
import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../../types';
import { countWizardStepMatches, getVisibleTaskTemplates, TaskTemplate, TASK_TEMPLATES } from '../taskTemplates';
import { TaskCompatibilityResult, RouteRequirementResult } from '../api';
import { buildWizardChecklist, CompatibilityStatus } from '../taskRequirements';

interface TaskWizardPanelProps {
  selectedTaskTemplateId: string | null;
  setSelectedTaskTemplateId: (id: string | null) => void;
  visibleTaskTypeGroups?: string[];
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
  // The backend's verdict on the current route content; it decides which steps are required and
  // whether they are satisfied. While it is pending or failed the panel shows local counts only.
  taskCompatibility: TaskCompatibilityResult | null;
  compatibilityStatus: CompatibilityStatus;
  startWizardStep: (stepKey: string) => void;
  stopWizardAction: () => void;
  currentWizardActionLabel: string | null;
  onClose: () => void;
}

const describeLimits = (requirement: RouteRequirementResult): string => {
  if (requirement.maximum === 0) return `${requirement.found} found, none allowed`;
  if (requirement.maximum != null && requirement.maximum === requirement.minimum) {
    return `${requirement.found} / exactly ${requirement.minimum}`;
  }
  return `${requirement.found} / ${requirement.minimum} required${requirement.maximum != null ? ` · max ${requirement.maximum}` : ''}`;
};

const TaskWizardPanel: React.FC<TaskWizardPanelProps> = ({
  selectedTaskTemplateId,
  setSelectedTaskTemplateId,
  visibleTaskTypeGroups,
  routePoints,
  standalonePoints,
  gates,
  observationMarkers,
  polygons,
  taskCompatibility,
  compatibilityStatus,
  startWizardStep,
  stopWizardAction,
  currentWizardActionLabel,
  onClose,
}) => {
  const selectedTemplate = TASK_TEMPLATES.find((template) => template.id === selectedTaskTemplateId) ?? null;
  const visibleTemplates = getVisibleTaskTemplates(
    visibleTaskTypeGroups ?? (document.configuration.showCimaTaskTypes ? ['legacy', 'cima'] : ['legacy'])
  );

  const grouped = visibleTemplates.reduce<Record<string, TaskTemplate[]>>((acc, template) => {
    acc[template.group] = acc[template.group] || [];
    acc[template.group].push(template);
    return acc;
  }, {});

  return (
    <div className="bg-base-100">
      <div className="flex justify-between items-center pb-2 mb-3 border-b border-base-200">
        <h2 className="text-base font-bold flex items-center gap-2"><Wand2 size={16} /> Task Route Guide</h2>
        <button onClick={onClose} className="btn btn-ghost btn-xs btn-square">
          <X size={16} />
        </button>
      </div>

      <div className="space-y-4">
        {!selectedTemplate && Object.entries(grouped).map(([group, templates]) => (
          <div key={group} className="space-y-2">
            <h3 className="text-xs font-bold uppercase text-gray-500">{group}</h3>
            <div className="space-y-2">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => setSelectedTaskTemplateId(template.id)}
                  className="w-full text-left p-3 rounded-lg border border-base-300 hover:border-primary hover:bg-base-200 transition"
                >
                  <div className="font-semibold text-sm">{template.label}</div>
                  <div className="text-xs text-gray-500 mt-1">{template.description}</div>
                </button>
              ))}
            </div>
          </div>
        ))}

        {selectedTemplate && (
          <div className="space-y-4">
            <div>
              <button
                onClick={() => setSelectedTaskTemplateId(null)}
                className="btn btn-ghost btn-xs mb-2"
              >
                ← Back to task list
              </button>
              <h3 className="text-sm font-bold">{selectedTemplate.label}</h3>
              <p className="text-xs text-gray-500 mt-1">{selectedTemplate.description}</p>
              {currentWizardActionLabel && !selectedTemplate.guideOnly && (
                <div className="mt-2 text-xs text-primary font-medium bg-primary/10 border border-primary/20 rounded p-2 space-y-2">
                  <div>Active step: {currentWizardActionLabel}</div>
                  <div className="text-[11px] text-base-content/70">
                    Click on the map to place points. Use “Stop active step” when you are done adding this kind of point.
                  </div>
                  <button onClick={stopWizardAction} className="btn btn-outline btn-xs">
                    Stop active step
                  </button>
                </div>
              )}
              {selectedTemplate.guideOnly && (
                <div className="mt-2 text-xs text-gray-500 bg-base-200 border border-base-300 rounded p-2 space-y-1">
                  <div className="font-medium text-base-content/80">Guide only</div>
                  <div>{selectedTemplate.guideSummary || 'Build a normal precision-style route and use the point editor / existing route tools to add the required primitives.'}</div>
                </div>
              )}
            </div>

            {(() => {
              const checklist = buildWizardChecklist(
                selectedTemplate,
                taskCompatibility,
                compatibilityStatus,
                (step) => countWizardStepMatches(step, routePoints, standalonePoints, gates, observationMarkers, polygons),
              );
              const unconfirmedNote = compatibilityStatus === 'failed'
                ? 'Could not check this route against the task requirements; showing local counts only.'
                : 'Checking the route against the task requirements...';
              return (
                <>
                  {!checklist.confirmed && (
                    <p className="text-[11px] text-gray-400">{unconfirmedNote}</p>
                  )}
                  <div className="space-y-2">
                    {checklist.steps.map((state, index) => {
                      const { step } = state;
                      const maxCountReached = state.maximum != null && state.count >= state.maximum;
                      const actionLabel = step.kind === 'route' ? 'Start' : maxCountReached ? 'Done' : 'Add';
                      const complete = state.satisfied === true;
                      return (
                        <div key={step.key} className="p-3 rounded-lg border border-base-300 bg-base-50">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                {complete ? (
                                  <CheckCircle2 size={16} className="text-success" />
                                ) : (
                                  <Circle size={16} className="text-gray-400" />
                                )}
                                <span className="font-medium text-sm">{index + 1}. {step.label}</span>
                                {checklist.structureKnown && !state.required && (
                                  <span className="badge badge-ghost badge-xs">Optional</span>
                                )}
                              </div>
                              <p className="text-xs text-gray-500 mt-1 ml-6">{step.help}</p>
                              <p className="text-[11px] text-gray-400 mt-1 ml-6">
                                {checklist.confirmed && state.primary
                                  ? describeLimits(state.primary)
                                  : `${state.count} placed`}
                              </p>
                              {state.message && (
                                <p className="text-[11px] text-warning mt-1 ml-6">{state.message}</p>
                              )}
                            </div>
                            {!selectedTemplate.guideOnly && step.kind !== 'guide' && (
                              <button
                                onClick={() => startWizardStep(step.key)}
                                className="btn btn-primary btn-xs"
                                disabled={maxCountReached}
                                title={maxCountReached ? 'The maximum number is already placed.' : undefined}
                              >
                                {actionLabel}
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {checklist.generic.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase text-gray-500">Other requirements</h4>
                      {checklist.generic.map((requirement) => {
                        const ok = checklist.confirmed && requirement.satisfied;
                        return (
                          <div key={requirement.key} className="p-3 rounded-lg border border-base-300 bg-base-50">
                            <div className="flex items-center gap-2">
                              {ok ? <CheckCircle2 size={16} className="text-success" /> : <Circle size={16} className="text-gray-400" />}
                              <span className="font-medium text-sm">{requirement.label}</span>
                            </div>
                            {checklist.confirmed && (
                              <p className="text-[11px] text-gray-400 mt-1 ml-6">{describeLimits(requirement)}</p>
                            )}
                            {checklist.confirmed && !requirement.satisfied && (
                              <p className="text-[11px] text-warning mt-1 ml-6">{requirement.message}</p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
};

export default TaskWizardPanel;
