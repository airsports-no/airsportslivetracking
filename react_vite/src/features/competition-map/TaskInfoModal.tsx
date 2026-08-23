import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { fetchNavigationTask } from './api';
import type { NavigationTask } from './types';
import { Loading } from '../route-editor/components/basicComponents';

interface Props {
    isOpen: boolean;
    onClose: () => void;
}

const renderBulletSection = (title: string, items: string[]) => {
    if (!items || items.length === 0) {
        return null;
    }
    return (
        <div>
            <h3 className="text-xl font-bold my-2">{title}</h3>
            <ul className="list-disc pl-6 space-y-2">
                {items.map((item, index) => (
                    <li key={`${title}-${index}`}>{item}</li>
                ))}
            </ul>
        </div>
    );
};

const TaskInfoModal: React.FC<Props> = ({ isOpen, onClose }) => {
    const { contestId, navigationTaskId } = useParams();
    const [navTask, setNavTask] = useState<NavigationTask | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (isOpen && !navTask && contestId && navigationTaskId) {
            setLoading(true);
            fetchNavigationTask(Number(contestId), Number(navigationTaskId))
                .then(setNavTask)
                .catch(console.error)
                .finally(() => setLoading(false));
        }
    }, [isOpen, navTask, contestId, navigationTaskId]);

    const renderRules = () => {
        if (!navTask) return null;
        const info = navTask.task_information;
        if (!info) {
            return <div className="alert alert-warning">No task information is available for this task.</div>;
        }

        return (
            <div className="space-y-4">
                <div className="rounded-lg border border-base-300 bg-base-200 p-4">
                    <div className="text-sm uppercase tracking-wide text-base-content/70">Task family</div>
                    <div className="text-lg font-semibold">{info.family_display_name}</div>
                    <div className="text-sm uppercase tracking-wide text-base-content/70 mt-3">Task subtype</div>
                    <div className="text-lg font-semibold">{info.subtype_display_name}</div>
                </div>
                <div>
                    <h3 className="text-xl font-bold my-2">Objective</h3>
                    <p>{info.objective}</p>
                </div>
                {renderBulletSection('Task summary', info.summary)}
                {renderBulletSection('Scoring', info.scoring)}
                {renderBulletSection('Penalties', info.penalties)}
                {renderBulletSection('Current task-specific values', info.overrides)}
            </div>
        );
    };

    if (!isOpen) {
        return null;
    }

    return (
        <dialog className="modal modal-open z-[6000]" onClick={onClose}>
            <div className="modal-box w-11/12 max-w-4xl top-[16px] relative max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <form method="dialog">
                    <button className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={onClose}>✕</button>
                </form>

                {loading ? (
                    <div className="text-center p-10">
                        <Loading />
                    </div>
                ) : navTask ? (
                    <div className="prose lg:prose-xl max-w-none">
                        <h1 className="text-4xl font-extrabold text-primary mb-2">{navTask.name}</h1>
                        <h2 className="text-xl font-bold text-secondary mb-2">{navTask.contest.name}</h2>
                        <p className="text-base-content/70 !mt-0">
                            {navTask.task_information?.family_display_name} · {navTask.task_information?.subtype_display_name}
                        </p>
                        <div className="divider"></div>
                        {renderRules()}
                    </div>
                ) : (
                    <div className="alert alert-error">Could not load navigation task information.</div>
                )}
                 <div className="modal-action mt-6">
                    <button className="btn" onClick={onClose}>Close</button>
                </div>
            </div>
        </dialog>
    );
}

export default TaskInfoModal;
