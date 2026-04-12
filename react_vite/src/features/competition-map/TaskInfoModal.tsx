import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { fetchNavigationTask } from './api';
import type { NavigationTask } from './types';
import { Loading } from '../route-editor/components/basicComponents';
import AboutAirsportChallenge from './components/rules/AboutAirsportChallenge';
import AboutAirsports from './components/rules/AboutAirsports';
import AboutANR from './components/rules/AboutANR';
import AboutPilotPokerRun from './components/rules/AboutPilotPokerRun';
import AboutPrecisionFlying from './components/rules/AboutPrecisionFlying';

interface Props {
    isOpen: boolean;
    onClose: () => void;
}

const TaskInfoModal: React.FC<Props> = ({ isOpen, onClose }) => {
    const { contestId, navigationTaskId } = useParams();
    const [navTask, setNavTask] = useState<NavigationTask | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Only fetch data when the modal is opened for the first time
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
        const { scorecard, route } = navTask;

        if (scorecard.task_type.includes("airsportchallenge")) {
            return <AboutAirsportChallenge scorecard={scorecard} route={route} />;
        }
        if (scorecard.task_type.includes("airsports")) {
            return <AboutAirsports scorecard={scorecard} route={route} />;
        }
        if (scorecard.task_type.includes("anr_corridor")) {
            return <AboutANR scorecard={scorecard} route={route} />;
        }
        if (scorecard.task_type.includes("poker")) {
            return <AboutPilotPokerRun />;
        }
        if (scorecard.task_type.includes("precision")) {
            return <AboutPrecisionFlying scorecard={scorecard} route={route} />;
        }
        
        return <div className="alert alert-warning">No specific rules found for this task type.</div>;
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
                        <h2 className="text-xl font-bold text-secondary mb-6">{navTask.contest.name}</h2>
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
