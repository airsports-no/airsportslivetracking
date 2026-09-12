import React, { useState } from 'react';
import { Contest } from '../../mission-dashboard/types';
import { createNavigationTask } from '../api';
import { contestLocalTimeToIso, nextStep, NavigationTaskCreationStep } from '../navigationTaskFlow';
import { NavigationTaskDetailsFormValues } from '../schemas/navigationTaskSchema';
import { TaskParameters } from './TaskParametersStep';
import { TaskTemplateChoice } from '../types';
import TaskTemplateStep from './TaskTemplateStep';
import RouteSelectionStep from './RouteSelectionStep';
import TaskParametersStep from './TaskParametersStep';
import TaskDetailsStep from './TaskDetailsStep';

interface NavigationTaskCreationFlowProps {
    contest: Contest;
    onCreated: (navigationTaskId: number) => void;
    onCancel: () => void;
}

// Replaces NewNavigationTaskWizard (see the wizard->SPA migration plan) - a task template picker,
// a route picker filtered to that template's compatibility, per-family parameters, then the task
// details form. Kept as one component parameterized by an `entry` so a follow-up slice can drive
// it from an EditableRoute instead of a Contest without duplicating this step machinery.
const NavigationTaskCreationFlow: React.FC<NavigationTaskCreationFlowProps> = ({ contest, onCreated, onCancel }) => {
    const entry = { kind: 'contest' as const, contestId: contest.id };
    const [step, setStep] = useState<NavigationTaskCreationStep>('template');
    const [template, setTemplate] = useState<TaskTemplateChoice | null>(null);
    const [editableRouteId, setEditableRouteId] = useState<number | null>(null);
    const [parameters, setParameters] = useState<TaskParameters>({});
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [warnings, setWarnings] = useState<string[]>([]);

    const advance = () => setStep(current => {
        const next = nextStep(current, entry, template?.task_type ?? null);
        return next === 'submit' ? current : next;
    });

    const handleDetailsSubmit = async (values: NavigationTaskDetailsFormValues) => {
        if (!template || !editableRouteId) return;
        setSubmitting(true);
        setError(null);
        try {
            const response = await createNavigationTask(contest.id, {
                ...values,
                start_time: contestLocalTimeToIso(values.start_time, contest.time_zone),
                finish_time: contestLocalTimeToIso(values.finish_time, contest.time_zone),
                editable_route: editableRouteId,
                task_subtype: template.task_subtype,
                ...parameters,
            });
            setWarnings(response.warnings ?? []);
            onCreated(response.id);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="card bg-base-100 shadow-xl max-w-2xl mx-auto">
            <div className="card-body">
                <h2 className="card-title">Add a navigation task</h2>
                <div className="text-sm breadcrumbs mb-4">
                    <ul>
                        <li className={step === 'template' ? 'font-bold' : ''}>Task type</li>
                        <li className={step === 'route' ? 'font-bold' : ''}>Route</li>
                        {template && ['parameters'].includes(step) && <li className="font-bold">Parameters</li>}
                        <li className={step === 'details' ? 'font-bold' : ''}>Details</li>
                    </ul>
                </div>

                {warnings.length > 0 && (
                    <div className="alert alert-warning mb-4">
                        <ul>
                            {warnings.map((warning, index) => (
                                <li key={index}>{warning}</li>
                            ))}
                        </ul>
                    </div>
                )}
                {error && <div className="alert alert-error mb-4">{error}</div>}

                {step === 'template' && (
                    <TaskTemplateStep
                        value={template}
                        onChange={value => {
                            setTemplate(value);
                            advance();
                        }}
                    />
                )}

                {step === 'route' && template && (
                    <RouteSelectionStep
                        subtypeKey={template.subtype_key}
                        value={editableRouteId}
                        onChange={value => {
                            setEditableRouteId(value);
                            advance();
                        }}
                    />
                )}

                {step === 'parameters' && template && (
                    <TaskParametersStep taskType={template.task_type} value={parameters} onChange={setParameters} />
                )}

                {step === 'details' && template && (
                    <TaskDetailsStep
                        taskType={template.task_type}
                        onSubmit={handleDetailsSubmit}
                        submitting={submitting}
                        submitLabel="Create navigation task"
                    />
                )}

                <div className="card-actions justify-between mt-4">
                    <button type="button" className="btn btn-ghost" onClick={onCancel}>
                        Cancel
                    </button>
                    {step === 'parameters' && (
                        <button type="button" className="btn btn-primary" onClick={advance}>
                            Next
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default NavigationTaskCreationFlow;
