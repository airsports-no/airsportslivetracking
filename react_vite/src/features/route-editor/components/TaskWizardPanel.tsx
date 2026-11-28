import React from 'react';
import { CheckCircle2, Circle, CircleDot, Wand2, X } from 'lucide-react';
import { getVisibleTaskTemplates, groupTemplates, getTaskTemplateById } from '../taskTemplates';
import type { RouteRequirementResult, RouteRequirementTool } from '../api';
import { type CompatibilityStatus, type WizardChecklist, type WizardStepState } from '../taskRequirements';
import { allRequiredMet, doneButtonLabel, findStep } from '../guideProgress';
import { getToolAction } from '../guideTools';

interface TaskWizardPanelProps {
  selectedTaskTemplateId: string | null;
  // Choosing a task (also from the list in this panel) starts the guide on it.
  onChooseTask: (id: string) => void;
  onBackToTaskList: () => void;
  visibleTaskTypeGroups?: string[];
  // The steps of the selected task, with the backend's verdict when it has answered for the route, otherwise the
  // catalogue's requirements and the editor's own counts. null while there is nothing to show yet.
  checklist: WizardChecklist | null;
  compatibilityStatus: CompatibilityStatus;
  // The tool of the step that is active, if any.
  activeTool: RouteRequirementTool | null;
  startWizardStep: (tool: RouteRequirementTool) => void;
  // Ends the active step and starts the next unmet required one.
  onDone: () => void;
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
  onChooseTask,
  onBackToTaskList,
  visibleTaskTypeGroups,
  checklist,
  compatibilityStatus,
  activeTool,
  startWizardStep,
  onDone,
  onClose,
}) => {
  const selectedTemplate = getTaskTemplateById(selectedTaskTemplateId) ?? null;
  const visibleTemplates = getVisibleTaskTemplates(
    visibleTaskTypeGroups ?? (document.configuration.showCimaTaskTypes ? ['legacy', 'cima'] : ['legacy'])
  );
  const grouped = groupTemplates(visibleTemplates);
  const activeStep = checklist ? findStep(checklist.steps, activeTool) : undefined;

  const renderButtons = (state: WizardStepState) => {
    if (activeStep?.key === state.key) {
      return (
        <button onClick={onDone} className="btn btn-warning btn-xs">
          {doneButtonLabel(state)}
        </button>
      );
    }
    // A step that is met and cannot take more has nothing to start. Otherwise: the main button while it is unmet or
    // optional, a quiet one to add more when it is met.
    const full = state.met && state.maximum !== null && state.count >= state.maximum;
    if (full) return null;
    const quiet = state.required && state.met;
    const several = state.tools.length > 1;
    return (
      <div className="flex flex-wrap justify-end gap-1">
        {state.tools.map((tool) => {
          const action = getToolAction(tool);
          const label = quiet ? `Add more${several ? `: ${action.shortLabel}` : ''}` : several ? action.shortLabel : action.buttonLabel;
          return (
            <button
              key={tool}
              onClick={() => startWizardStep(tool)}
              className={`btn btn-xs ${quiet ? 'btn-ghost' : 'btn-primary'}`}
            >
              {action.step === null && tool === state.key ? action.buttonLabel : label}
            </button>
          );
        })}
      </div>
    );
  };

  const renderStep = (state: WizardStepState, index: number | null) => {
    const active = activeStep?.key === state.key;
    const complete = state.required && state.met;
    return (
      <div
        key={state.key}
        data-step={state.key}
        data-active={active ? 'true' : undefined}
        className={`p-3 rounded-lg border bg-base-50 ${active ? 'border-primary ring-1 ring-primary bg-primary/5' : 'border-base-300'}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {active ? (
                <CircleDot size={16} className="text-primary" />
              ) : complete ? (
                <CheckCircle2 size={16} className="text-success" />
              ) : (
                <Circle size={16} className="text-gray-400" />
              )}
              <span className="font-medium text-sm">{index !== null ? `${index + 1}. ` : ''}{state.label}</span>
              {active && <span className="badge badge-primary badge-xs">Current step</span>}
              {!state.required && <span className="badge badge-ghost badge-xs">Optional</span>}
            </div>
            {state.help && <p className="text-xs text-gray-500 mt-1 ml-6">{state.help}</p>}
            <p className="text-[11px] text-gray-400 mt-1 ml-6">
              {checklist?.confirmed && state.primary
                ? describeLimits(state.primary)
                : state.primary?.maximum === 0 ? '' : `${state.count} placed`}
            </p>
            {state.message && (
              <p className="text-[11px] text-warning mt-1 ml-6">{state.message}</p>
            )}
          </div>
          <div className="shrink-0">{renderButtons(state)}</div>
        </div>
      </div>
    );
  };

  const renderChecklist = (list: WizardChecklist) => {
    const required = list.steps.filter((step) => step.required);
    const optional = list.steps.filter((step) => !step.required);
    const unconfirmedNote = compatibilityStatus === 'failed'
      ? 'Could not check this route against the task requirements; showing local counts only.'
      : 'Checking the route against the task requirements...';
    const done = required.length > 0 && allRequiredMet(list);
    return (
      <>
        {!list.confirmed && <p className="text-[11px] text-gray-400">{unconfirmedNote}</p>}
        {done && !activeStep && (
          <div role="status" className="rounded-lg border border-success/40 bg-success/10 p-2 text-xs font-medium text-success">
            All required steps are done.{optional.length > 0 ? ' The optional steps are below.' : ''}
          </div>
        )}
        <div className="space-y-2">
          {required.map((state, index) => renderStep(state, index))}
        </div>
        {optional.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase text-gray-500">Optional steps</h4>
            {optional.map((state) => renderStep(state, null))}
          </div>
        )}
        {list.generic.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase text-gray-500">Other requirements</h4>
            {list.generic.map((requirement) => {
              const ok = list.confirmed && requirement.satisfied;
              return (
                <div key={requirement.key} className="p-3 rounded-lg border border-base-300 bg-base-50">
                  <div className="flex items-center gap-2">
                    {ok ? <CheckCircle2 size={16} className="text-success" /> : <Circle size={16} className="text-gray-400" />}
                    <span className="font-medium text-sm">{requirement.label}</span>
                  </div>
                  {list.confirmed && (
                    <p className="text-[11px] text-gray-400 mt-1 ml-6">{describeLimits(requirement)}</p>
                  )}
                  {list.confirmed && !requirement.satisfied && (
                    <p className="text-[11px] text-warning mt-1 ml-6">{requirement.message}</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </>
    );
  };

  return (
    <div className="bg-base-100">
      <div className="flex justify-between items-center pb-2 mb-3 border-b border-base-200">
        <h2 className="text-base font-bold flex items-center gap-2"><Wand2 size={16} /> Task Route Guide</h2>
        <button onClick={onClose} className="btn btn-ghost btn-xs btn-square" aria-label="Close the guide" title="Close the guide">
          <X size={16} />
        </button>
      </div>

      <div className="space-y-4">
        {!selectedTemplate && grouped.map(([group, templates]) => (
          <div key={group} className="space-y-2">
            <h3 className="text-xs font-bold uppercase text-gray-500">{group}</h3>
            <div className="space-y-2">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => onChooseTask(template.id)}
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
              <button onClick={onBackToTaskList} className="btn btn-ghost btn-xs mb-2">
                ← Back to task list
              </button>
              <h3 className="text-sm font-bold">{selectedTemplate.label}</h3>
              <p className="text-xs text-gray-500 mt-1">{selectedTemplate.description}</p>
            </div>
            {checklist ? renderChecklist(checklist) : (
              <p className="text-[11px] text-gray-400">Loading the steps for this task...</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TaskWizardPanel;
