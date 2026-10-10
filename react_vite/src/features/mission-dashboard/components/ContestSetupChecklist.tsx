import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Circle } from 'lucide-react';
import { Contest } from '../types';
import { generatePath } from '../../../urls';
import routes from '../../../routes.json';

interface ContestSetupChecklistProps {
    contest: Contest;
    teamCount: number;
    onAddTask: () => void;
    onAddTeam: () => void;
    onOpenSettings: () => void;
}

const storageKey = (contestId: number) => `aslt-setup-checklist-dismissed:${contestId}`;

const readDismissed = (contestId: number): boolean => {
    try {
        return window.localStorage.getItem(storageKey(contestId)) === '1';
    } catch {
        return false;
    }
};

interface Step {
    key: string;
    title: string;
    detail: string;
    done: boolean;
    action: React.ReactNode;
}

/**
 * "What to do next" guide for contest editors. Every step is derived from data the contest
 * dashboard already has, so there is no extra state to keep in sync.
 */
const ContestSetupChecklist: React.FC<ContestSetupChecklistProps> = ({ contest, teamCount, onAddTask, onAddTeam, onOpenSettings }) => {
    const [dismissed, setDismissed] = useState(() => readDismissed(contest.id));
    const tasks = contest.navigationtask_set ?? [];
    const selfManagedTasks = tasks.filter(t => t.allow_self_management);
    const hiddenSelfManaged = selfManagedTasks.filter(t => !(t.is_public && t.is_featured));
    const firstTask = tasks[0];

    const steps: Step[] = [
        {
            key: 'contest',
            title: 'Create the contest',
            detail: 'Done. A contest is the event that holds your tasks and teams.',
            done: true,
            action: null,
        },
        {
            key: 'task',
            title: 'Draw a route, then add a navigation task',
            detail: 'Draw or import a route in the route editor, then create a task from it. The task is the flight pilots will fly.',
            done: tasks.length > 0,
            action: (
                <div className="flex gap-2">
                    <Link to={`/${routes.ROUTE_EDITOR_LIST}`} className="btn btn-xs btn-outline">Route editor</Link>
                    <button className="btn btn-xs btn-primary" onClick={onAddTask}>Add navigation task</button>
                </div>
            ),
        },
        {
            key: 'teams',
            title: 'Add teams',
            detail: 'Register pilots yourself, import a list, or let pilots register on their own.',
            done: teamCount > 0,
            action: <button className="btn btn-xs btn-primary" onClick={onAddTeam}>Add team</button>,
        },
        {
            key: 'schedule',
            title: 'Schedule start times',
            detail: 'Give each team a start time on the task, or turn on self-management so pilots book their own.',
            done: tasks.some(t => t.flown_contestants_count > 0 || (t.future_contestants?.length ?? 0) > 0),
            action: firstTask ? (
                <Link
                    to={generatePath('CONTESTANT_SCHEDULING', { contestId: contest.id, navigationTaskId: firstTask.pk })}
                    className="btn btn-xs btn-primary"
                >
                    Open scheduling
                </Link>
            ) : null,
        },
        {
            key: 'visibility',
            title: 'Decide who can see the contest',
            detail: 'New contests are private. Make it public (or unlisted) when you are ready to share it.',
            done: contest.is_public,
            action: <button className="btn btn-xs btn-primary" onClick={onOpenSettings}>Contest settings</button>,
        },
    ];

    if (selfManagedTasks.length > 0) {
        steps.push({
            key: 'self-management',
            title: 'Let pilots find self-registration tasks',
            detail:
                'Pilots only see tasks that are public and featured. Open the task and set its visibility to Public' +
                (hiddenSelfManaged.length > 0
                    ? ` (${hiddenSelfManaged.map(t => t.name).join(', ')} not yet).`
                    : '.'),
            done: hiddenSelfManaged.length === 0 && contest.is_public,
            action: null,
        });
    }

    const allDone = steps.every(s => s.done);
    if (dismissed || allDone) {
        return null;
    }

    const dismiss = () => {
        setDismissed(true);
        try {
            window.localStorage.setItem(storageKey(contest.id), '1');
        } catch {
            // Storage unavailable; the checklist just comes back on the next visit.
        }
    };
    const doneCount = steps.filter(s => s.done).length;

    return (
        <div className="card bg-base-100 shadow border border-info/30 mb-8">
            <div className="card-body">
                <div className="flex items-center justify-between gap-2">
                    <h3 className="card-title">Set up your contest <span className="text-sm font-normal opacity-60">{doneCount} of {steps.length}</span></h3>
                    <button className="btn btn-ghost btn-xs" onClick={dismiss}>Hide</button>
                </div>
                <ul className="space-y-3">
                    {steps.map(step => (
                        <li key={step.key} className="flex items-start gap-3">
                            {step.done ? (
                                <Check size={18} className="text-success mt-0.5 shrink-0" aria-label="Done" />
                            ) : (
                                <Circle size={18} className="opacity-40 mt-0.5 shrink-0" aria-label="To do" />
                            )}
                            <div className="flex-1">
                                <div className={step.done ? 'line-through opacity-60' : 'font-semibold'}>{step.title}</div>
                                {!step.done && <div className="text-sm opacity-80">{step.detail}</div>}
                            </div>
                            {!step.done && step.action}
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
};

export default ContestSetupChecklist;
