import React, { useState, useEffect, useMemo } from 'react';
import { fetchContests } from '../schedule-flight/api';
import { fetchOngoingNavigation } from './api';
import { Contest } from '../schedule-flight/types';
import { OngoingNavigation } from './types';
import ContestCard from './components/ContestCard';
import TaskCard from './components/TaskCard';
import { Loading } from '../route-editor/components/basicComponents';
import { Link } from 'react-router-dom';

const MissionDashboard = () => {
    const [contests, setContests] = useState<Contest[]>([]);
    const [ongoingNavigations, setOngoingNavigations] = useState<OngoingNavigation[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);
                const [contestsData, ongoingData] = await Promise.all([
                    fetchContests(),
                    fetchOngoingNavigation(),
                ]);
                setContests(contestsData.results);
                setOngoingNavigations(ongoingData);
            } catch (err) {
                setError((err as Error).message);
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, []);

    const liveContestsPks = useMemo(() => {
        return ongoingNavigations.map(nav => nav.contest.id);
    }, [ongoingNavigations]);

    const getContestStatus = (contest: Contest): 'live' | 'upcoming' | 'past' => {
        const now = new Date();
        const startTime = new Date(contest.start_time);
        const finishTime = new Date(contest.finish_time);

        if (liveContestsPks.includes(contest.id)) {
            return 'live';
        }
        if (now > finishTime) {
            return 'past';
        }
        return 'upcoming';
    };

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            <h1 className="text-4xl font-bold mb-4">Mission Dashboard</h1>

            {error && <div className="alert alert-error">{error}</div>}
            {loading && <Loading />}

            {/* Live Now Section */}
            {ongoingNavigations.length > 0 && (
                <div className="mb-8">
                    <h2 className="text-2xl font-bold mb-4 text-error">🔴 Live Now</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {ongoingNavigations.map(live => (
                            <div key={live.pk} className="card bg-base-200 shadow-xl">
                                <div className="card-body">
                                    <h3 className="card-title">{live.contest.name}</h3>
                                    <p>{live.name}</p>
                                    <p>{live.active_contestants.length} active contestants</p>
                                    <div className="card-actions justify-end">
                                        <Link to={live.tracking_link} className="btn btn-primary">Watch Tracking</Link>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* All Contests Section */}
            <div>
                <h2 className="text-2xl font-bold mb-4">All Contests</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {contests.map(contest => (
                        <Link to={`/mission-dashboard/${contest.id}`} key={contest.id}>
                            <ContestCard
                                contest={contest}
                                status={getContestStatus(contest)}
                            />
                        </Link>
                    ))}
                </div>
            </div>

            {/* Task Suite Placeholder */}
            <div className="mt-8">
                <h2 className="text-2xl font-bold mb-4">Task Suite</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <TaskCard name="Task 1" status="Open" />
                    <TaskCard name="Task 2" status="Scheduled" takeOffTime="14:00" />
                    <TaskCard name="Task 3" status="Live" />
                    <TaskCard name="Task 4" status="Finalized" />
                </div>
            </div>
        </div>
    );
};

export default MissionDashboard;
