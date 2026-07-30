import React from 'react';
import { CheckCircle2, Circle, Wand2, X } from 'lucide-react';
import { TaskTemplate, TASK_TEMPLATES, countWizardStepMatches } from '../taskTemplates';
import { Gate, ObservationMarker, Polygon, RoutePoint } from '../../../types';

interface TaskWizardPanelProps {
  selectedTaskTemplateId: string | null;
  setSelectedTaskTemplateId: (id: string | null) => void;
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
  startWizardStep: (stepKey: string) => void;
  currentWizardActionLabel: string | null;
  onClose: () => void;
}

const TaskWizardPanel: React.FC<TaskWizardPanelProps> = ({
  selectedTaskTemplateId,
  setSelectedTaskTemplateId,
  routePoints,
  standalonePoints,
  gates,
  observationMarkers,
  polygons,
  startWizardStep,
  currentWizardActionLabel,
  onClose,
}) => {
  const selectedTemplate = TASK_TEMPLATES.find((template) => template.id === selectedTaskTemplateId) ?? null;

  const grouped = TASK_TEMPLATES.reduce<Record<string, TaskTemplate[]>>((acc, template) => {
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
                <div className="mt-2 text-xs text-primary font-medium bg-primary/10 border border-primary/20 rounded p-2">
                  Active step: {currentWizardActionLabel}
                </div>
              )}
              {selectedTemplate.guideOnly && (
                <div className="mt-2 text-xs text-gray-500 bg-base-200 border border-base-300 rounded p-2 space-y-1">
                  <div className="font-medium text-base-content/80">Guide only</div>
                  <div>{selectedTemplate.guideSummary || 'Build a normal precision-style route and use the point editor / existing route tools to add the required primitives.'}</div>
                </div>
              )}
            </div>

            <div className="space-y-2">
              {selectedTemplate.steps.map((step, index) => {
                const count = countWizardStepMatches(step, routePoints, standalonePoints, gates, observationMarkers, polygons);
                const complete = count >= step.minCount;
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
                        </div>
                        <p className="text-xs text-gray-500 mt-1 ml-6">{step.help}</p>
                        <p className="text-[11px] text-gray-400 mt-1 ml-6">
                          {count} / {step.minCount} required
                        </p>
                      </div>
                      {!selectedTemplate.guideOnly && (
                        <button
                          onClick={() => startWizardStep(step.key)}
                          className="btn btn-primary btn-xs"
                        >
                          {step.kind === 'route' ? 'Start' : 'Add'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TaskWizardPanel;
