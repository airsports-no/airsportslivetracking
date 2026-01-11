import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Contest, MyParticipatingContest } from '../schedule-flight/types';
import { fetchContest, fetchMyParticipatingContests } from '../schedule-flight/api';
import { Loading } from '../route-editor/components/basicComponents';
import TaskCard from './components/TaskCard';
import Leaderboard from './components/Leaderboard';
import { OngoingNavigation } from './types';
import { fetchOngoingNavigation } from './api';

const ContestDashboard = () => {
    const { contestId } = useParams<{ contestId: string }>();
    const [contest, setContest] = useState<Contest | null>(null);
    const [myContests, setMyContests] = useState<MyParticipatingContest[]>([]);
    const [ongoingNavigations, setOngoingNavigations] = useState<OngoingNavigation[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (contestId) {
            Promise.all([
                fetchContest(Number(contestId)),
                fetchMyParticipatingContests(),
                fetchOngoingNavigation()
            ]).then(([contestData, myContestsData, ongoingData]) => {
                setContest(contestData);
                setMyContests(myContestsData);
                setOngoingNavigations(ongoingData);
            }).catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
        }
    }, [contestId]);

    const getTaskStatus = (task: import('../schedule-flight/types').NavigationTask): 'Open' | 'Scheduled' | 'Live' | 'Finalized' => {
        if (ongoingNavigations.some(nav => nav.pk === task.pk)) {
            return 'Live';
        }
        if (new Date(task.finish_time) < new Date()) {
            return 'Finalized';
        }

        const myContest = myContests.find(mc => mc.contest.id === contest?.id);
        if (myContest) {
            const myTask = myContest.contest.navigationtask_set.find(nt => nt.pk === task.pk);
            if (myTask && myTask.future_contestants && myTask.future_contestants.length > 0) {
                return 'Scheduled';
            }
        }
        
        return 'Open';
    };

    if (loading) return <div className="w-screen h-screen flex items-center justify-center"><Loading /></div>;
    if (error) return <div className="alert alert-error">{error}</div>;
    if (!contest) return <div className="alert alert-warning">Contest not found.</div>;

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            {/* Contest Header */}
            <div className="mb-8">
                {contest.header_image && (
                    <img src={contest.header_image} alt={contest.name} className="w-full h-64 object-cover rounded-lg mb-4" />
                )}
                <div className="flex items-center">
                    {contest.logo && (
                        <img src={contest.logo} alt={`${contest.name} logo`} className="h-24 w-24 mr-4" />
                    )}
                    <div>
                        <h1 className="text-4xl font-bold">{contest.name}</h1>
                        <p>{contest.location}</p>
                        {contest.contest_website && (
                            <a href={contest.contest_website} target="_blank" rel="noopener noreferrer" className="link link-primary">
                                Contest Website
                            </a>
                        )}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Leaderboard */}
                <div className="lg:col-span-2">
                    <h2 className="text-2xl font-bold mb-4">Leaderboard</h2>
                    <Leaderboard contest={contest} />
                </div>

                {/* Task Suite */}
                <div>
                    <h2 className="text-2xl font-bold mb-4">Task Suite</h2>
                    <div className="space-y-4">
                        {contest.navigationtask_set.map(task => (
                            <TaskCard
                                key={task.pk}
                                name={task.name}
                                status={getTaskStatus(task)}
                                contestId={contest.id}
                                taskId={task.pk}
                            />
                        ))}
                    </div>
                </div>
            </div>
            <Link to="/mission-dashboard" className="btn btn-secondary mt-4">Back to Dashboard</Link>
        </div>
    );
};

export default ContestDashboard;
