import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchNavigationTask } from './api';
import type { NavigationTask } from './types';
import { Loading } from '../route-editor/components/basicComponents';
import AboutAirsportChallenge from './components/rules/AboutAirsportChallenge';
import AboutAirsports from './components/rules/AboutAirsports';
import AboutANR from './components/rules/AboutANR';
import AboutPilotPokerRun from './components/rules/AboutPilotPokerRun';
import AboutPrecisionFlying from './components/rules/AboutPrecisionFlying';
import { ArrowLeft } from 'lucide-react';

const TaskInfoPage: React.FC = () => {
    const { contestId, navigationTaskId } = useParams();
    const [navTask, setNavTask] = useState<NavigationTask | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (contestId && navigationTaskId) {
            setLoading(true);
            fetchNavigationTask(Number(contestId), Number(navigationTaskId))
                .then(setNavTask)
                .catch(console.error)
                .finally(() => setLoading(false));
        }
    }, [contestId, navigationTaskId]);

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

    return (
        <div className="container mx-auto p-4 max-w-4xl">
            <div className="mb-6">
                <Link to={`/competition-map/${contestId}/${navigationTaskId}`} className="btn btn-ghost">
                    <ArrowLeft size={16} className="mr-2" />
                    Back to Map
                </Link>
            </div>

            {loading ? (
                <div className="text-center p-10">
                    <Loading />
                </div>
            ) : navTask ? (
                <div className="prose lg:prose-xl bg-base-100 p-6 rounded-lg shadow">
                    <h1>{navTask.name}</h1>
                    <div className="divider"></div>
                    {renderRules()}
                </div>
            ) : (
                <div className="alert alert-error">Could not load navigation task information.</div>
            )}
        </div>
    );
}

export default TaskInfoPage;
