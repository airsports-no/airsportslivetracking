import React, { useState } from 'react';
import { Contest } from '../../mission-dashboard/types';
import { createContest, createNavigationTask } from '../api';
import { contestLocalTimeToIso, nextStep, NavigationTaskCreationEntry, NavigationTaskCreationStep } from '../navigationTaskFlow';
import { NavigationTaskDetailsFormValues } from '../schemas/navigationTaskSchema';
import { ContestCreationFormValues } from '../schemas/contestCreationSchema';
import { TaskParameters } from './TaskParametersStep';
import { TaskTemplateChoice } from '../types';
import TaskTemplateStep from './TaskTemplateStep';
import RouteSelectionStep from './RouteSelectionStep';
import ContestCreationStep from './ContestCreationStep';
import TaskParametersStep from './TaskParametersStep';
import TaskDetailsStep from './TaskDetailsStep';

interface NavigationTaskCreationFlowProps {
    entry: NavigationTaskCreationEntry;
    // Pre-known contest, when entry.kind === 'contest' (avoids an extra fetch for data the
    // caller already has - e.g. ContestManagementPage already loaded it).
    initialContest?: Contest;
    onCreated: (contestId: number, navigationTaskId: number) => void;
    onCancel: () => void;
}

// Replaces both NewNavigationTaskWizard (entry: contest) and RouteToTaskWizard (entry: route) -
// see the wizard->SPA migration plan. One component parameterized by entry so the two nearly-
// identical wizards don't become two nearly-identical React flows.
const NavigationTaskCreationFlow: React.FC<NavigationTaskCreationFlowProps> = ({ entry, initialContest, onCreated, onCancel }) => {
    const [step, setStep] = useState<NavigationTaskCreationStep>('template');
    const [template, setTemplate] = useState<TaskTemplateChoice | null>(null);
    const [editableRouteId, setEditableRouteId] = useState<number | null>(entry.kind === 'route' ? entry.editableRouteId : null);
    const [contest, setContest] = useState<Contest | null>(initialContest ?? null);
    const [parameters, setParameters] = useState<TaskParameters>({});
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [warnings, setWarnings] = useState<string[]>([]);

    const advance = () => setStep(current => {
        const next = nextStep(current, entry, template?.task_type ?? null);
        return next === 'submit' ? current : next;
    });

    const handleNewContestSubmit = async (values: ContestCreationFormValues) => {
        setSubmitting(true);
        setError(null);
        try {
            const created = await createContest({
                ...values,
                start_time: contestLocalTimeToIso(values.start_time, values.time_zone),
                finish_time: contestLocalTimeToIso(values.finish_time, values.time_zone),
            });
            setContest(created);
            advance();
        } catch (err) {
            // The contest may or may not have been created - a retry here only ever tries to
            // create a *new* one, matching this step's own idempotency (unlike the old wizard's
            // done(), which rolled the whole thing back on any later failure). If contest
            // creation itself is what failed, nothing was created and retrying is safe.
            setError((err as Error).message);
        } finally {
            setSubmitting(false);
        }
    };

    const handleDetailsSubmit = async (values: NavigationTaskDetailsFormValues) => {
        if (!template || !editableRouteId || !contest) return;
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
            onCreated(contest.id, response.id);
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
                        editableRouteId={entry.kind === 'route' ? entry.editableRouteId : undefined}
                        value={template}
                        onChange={value => {
                            setTemplate(value);
                            advance();
                        }}
                    />
                )}

                {step === 'contest' && (
                    <ContestCreationStep
                        submitting={submitting}
                        onExistingContestChosen={value => {
                            setContest(value);
                            advance();
                        }}
                        onNewContestSubmit={handleNewContestSubmit}
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
                    <>
                        <TaskParametersStep taskType={template.task_type} value={parameters} onChange={setParameters} />
                        <div className="card-actions justify-end mt-4">
                            <button type="button" className="btn btn-primary" onClick={advance}>
                                Next
                            </button>
                        </div>
                    </>
                )}

                {step === 'details' && template && (
                    <TaskDetailsStep
                        taskType={template.task_type}
                        onSubmit={handleDetailsSubmit}
                        submitting={submitting}
                        submitLabel="Create navigation task"
                    />
                )}

                <div className="card-actions justify-start mt-4">
                    <button type="button" className="btn btn-ghost" onClick={onCancel}>
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    );
};

export default NavigationTaskCreationFlow;
