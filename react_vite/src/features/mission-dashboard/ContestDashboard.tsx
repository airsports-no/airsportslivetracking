import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Contest, NavigationTask, ContestResults, MyContestTeam } from './types';
import { Contestant } from '../competition-map/types';
import * as api from './api';
import { fetchNavigationTask } from '../competition-map/api';
import { Loading } from '../route-editor/components/basicComponents';
import TaskCard from './components/TaskCard';
import Leaderboard from './components/Leaderboard';
import { OngoingNavigation } from './types';
import ContestRegistrationForm from './components/ContestRegistrationForm';
import ScheduleFlightForm from './components/ScheduleFlightForm';
import TaskScoreDisplay from './components/TaskScoreDisplay';
import { reverse, generatePath } from '../../urls';

const ContestDashboard = () => {
    const { contestId } = useParams<{ contestId: string }>();
    const [contest, setContest] = useState<Contest | null>(null);
    const [results, setResults] = useState<ContestResults | null>(null);
    const [myFutureFlights, setMyFutureFlights] = useState<Contestant[]>([]);
    const [myPreviousFlights, setMyPreviousFlights] = useState<Contestant[]>([]); // New state
    const [myContestTeams, setMyContestTeams] = useState<MyContestTeam[]>([]);
    const [ongoingNavigations, setOngoingNavigations] = useState<OngoingNavigation[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [showRegistrationForm, setShowRegistrationForm] = useState(false);
    const [showScheduleForm, setShowScheduleForm] = useState<NavigationTask | null>(null);
    const [viewingScoresForTask, setViewingScoresForTask] = useState<NavigationTask | null>(null);
    const [loadingTaskScores, setLoadingTaskScores] = useState(false);


    const canManageThisContest = contest?.is_editor || document.configuration.is_superuser;

    const myContestantIds = useMemo(() => {
        const allMyContestantIds = [
            ...myFutureFlights.map(f => f.id),
            ...myPreviousFlights.map(f => f.id)
        ];
        return new Set(allMyContestantIds);
    }, [myFutureFlights, myPreviousFlights]); // Updated dependency array

    const refreshData = () => {
        if (contestId) {
            setLoading(true);
            Promise.all([
                api.fetchContest(Number(contestId)),
                api.fetchMyFutureFlights(),
                api.fetchMyPreviousFlights(),
                api.fetchOngoingNavigation(),
                api.fetchContestResults(Number(contestId)),
                api.fetchMyContestTeams(),
            ]).then(([contestData, myFutureFlightsData, myPreviousFlightsData, ongoingData, resultsData, myContestTeamsData]) => {
                setContest(contestData);
                setMyFutureFlights(myFutureFlightsData);
                setMyPreviousFlights(myPreviousFlightsData); // Set new state
                setOngoingNavigations(ongoingData);
                setResults(resultsData);
                setMyContestTeams(myContestTeamsData);
            }).catch(err => {
                setError((err as Error).message)
                console.error(err);
            })
            .finally(() => setLoading(false));
        }
    }

    useEffect(() => {
        refreshData();
    }, [contestId]);
    
    const handleWithdrawClick = async (contestId: number) => {
        try {
            await api.withdraw(contestId);
            refreshData();
        } catch (error) {
            setError((error as Error).message);
                       console.error(error);
        }
    };

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number) => {
        try {
            await api.cancelFlight(contestId, navigationTaskId, futureContestantId);
            refreshData();
        } catch (error) {
            setError((error as Error).message);
            console.error(error);
        }
    };

    const handleViewScoresClick = async (task: NavigationTask) => {
        setLoadingTaskScores(true);
        setViewingScoresForTask(task); // Show modal immediately with partial data
        try {
            const fullTaskData = await fetchNavigationTask(contest.id, task.pk);
            setViewingScoresForTask(fullTaskData);
        } catch (err) {
            setError('Failed to load task scores.');
            console.error(err);
            setViewingScoresForTask(null);
        } finally {
            setLoadingTaskScores(false);
        }
    };

    const getTaskStatus = (task: NavigationTask): 'Open' | 'Scheduled' | 'Live' | 'Finalized' => {
        if (ongoingNavigations.some(nav => nav.pk === task.pk)) {
            return 'Live';
        }
        if (new Date(task.finish_time) < new Date()) {
            return 'Finalized';
        }

        const isTaskScheduled = myFutureFlights.some(flight => flight.navigation_task === task.pk);
        if (isTaskScheduled) {
            return 'Scheduled';
        }
        
        return 'Open';
    };

    if (loading) return <div className="w-screen h-screen flex items-center justify-center"><Loading /></div>;
    if (error) return <div className="alert alert-error">{error}</div>;
    if (!contest) return <div className="alert alert-warning">Contest not found.</div>;

    const userContestTeam = myContestTeams.find(team => team.contest === contest?.id);
    const canSchedule = !userContestTeam || !!userContestTeam?.is_user_pilot;

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            {/* Modals for forms */}
            {showRegistrationForm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-center">
                    <ContestRegistrationForm
                        contest={contest}
                        myFutureParticipations={myFutureFlights}
                        myContestTeams={myContestTeams}
                        onClose={() => {
                            setShowRegistrationForm(false);
                            refreshData();
                        }}
                    />
                </div>
            )}
            {showScheduleForm && (
                 <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-center">
                    <ScheduleFlightForm
                        contest={contest}
                        navigationTaskId={showScheduleForm.pk}
                        myContestTeams={myContestTeams}
                        onClose={() => {
                            setShowScheduleForm(null);
                            refreshData();
                        }}
                    />
                </div>
            )}
            {viewingScoresForTask && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-center">
                    <div className="card bg-base-100 shadow-xl max-w-4xl w-full">
                        <div className="card-body">
                            {loadingTaskScores ? (
                                <Loading />
                            ) : (
                                <TaskScoreDisplay task={viewingScoresForTask} myContestantIds={myContestantIds} />
                            )}
                            <div className="card-actions justify-end">
                                <button onClick={() => setViewingScoresForTask(null)} className="btn">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Contest Header */}
            <div className="mb-8">
                {(contest.header_image || contest.logo) && (
                    <img
                        src={contest.header_image || contest.logo}
                        alt={contest.name}
                        className="w-full h-64 object-cover rounded-lg mb-4"
                    />
                )}
                <div className="flex items-center justify-between">
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
                     <div className="flex flex-col items-stretch gap-2">
                        {canManageThisContest && (
                            <a href={reverse('contest_details', contest.id)} className="btn btn-primary btn-sm">
                                Manage Contest
                            </a>
                        )}
                        {(() => {
                            if (userContestTeam?.is_user_pilot) {
                                return (
                                    <button className="btn btn-warning" onClick={() => handleWithdrawClick(contest.id)}>Withdraw</button>
                                );
                            } else if (userContestTeam) {
                                return (
                                    <button className="btn btn-info" disabled>Registered</button>
                                );
                            } else {
                                return (
                                    <button className="btn btn-success" onClick={() => setShowRegistrationForm(true)}>Register</button>
                                );
                            }
                        })()}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Leaderboard */}
                <div className="lg:col-span-2">
                    <div className="flex justify-between items-center">
                        <h2 className="text-2xl font-bold mb-4">Leaderboard</h2>
                        <Link to={generatePath('CONTEST_RESULTS_TABLE', { contestId: contestId })} className="btn btn-primary">View Full Results</Link>
                    </div>
                    <Leaderboard results={results} />
                </div>

                {/* Task Suite */}
                <div>
                    <h2 className="text-2xl font-bold mb-4">Task Suite</h2>
                    <div className="space-y-4">
                        {contest.navigationtask_set.map(task => {
                            const futureContestant = myFutureFlights.find(f => f.navigation_task === task.pk);
                            const canCancelThisFlight = futureContestant && userContestTeam && futureContestant.team.id === userContestTeam.team && userContestTeam.is_user_pilot;

                            return (
                                <TaskCard
                                    key={task.pk}
                                    name={task.name}
                                    status={getTaskStatus(task)}
                                    contestId={contest.id}
                                    taskId={task.pk}
                                    tracking_link={task.tracking_link}
                                    onScheduleClick={() => setShowScheduleForm(task)}
                                    futureContestant={futureContestant}
                                    onCancelClick={canCancelThisFlight ? () => futureContestant && handleCancelFlight(contest.id, task.pk, futureContestant.id) : undefined}
                                    onViewScoresClick={() => handleViewScoresClick(task)}
                                    canSchedule={canSchedule}
                                />
                            );
                        })}
                    </div>
                </div>
            </div>
            <Link to="/" className="btn btn-secondary mt-4">Back to Dashboard</Link>
        </div>
    );
};
export default ContestDashboard;
