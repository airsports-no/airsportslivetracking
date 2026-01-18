import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Contest, NavigationTask, ContestResults, MyContestTeam } from './types';
import { Contestant } from '../competition-map/types';
import { Loading } from '../route-editor/components/basicComponents';
import TaskCard from './components/TaskCard';
import Leaderboard from './components/Leaderboard';
import { OngoingNavigation } from './types';
import ContestRegistrationForm from './components/ContestRegistrationForm';
import ScheduleFlightForm from './components/ScheduleFlightForm';
import TaskScoreDisplay from './components/TaskScoreDisplay';
import UpcomingFlights from './components/UpcomingFlights';
import PublicityIcon from './components/PublicityIcon';
import { HelpCircle } from 'lucide-react'; // Import HelpCircle
import { reverse, generatePath } from '../../urls';
import { useMissionDashboardStore } from './store';
import { fetchNavigationTask } from '../competition-map/api';
import { formatDateInterval } from '../../utils';
const ContestDashboard = () => {
    const { contestId } = useParams<{ contestId: string }>();
    const {
        contestsById,
        myFutureFlights,
        myPreviousFlights,
        myContestTeams,
        ongoingNavigations,
        results,
        fetchContest,
        fetchMyFutureFlights,
        fetchMyPreviousFlights,
        fetchOngoingNavigation,
        fetchContestResults,
        fetchMyContestTeams,
        withdraw,
        cancelFlight,
    } = useMissionDashboardStore();

    const contest = contestsById[Number(contestId)];
    const contestResults = results[Number(contestId)];

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [showRegistrationForm, setShowRegistrationForm] = useState(false);
    const [showScheduleForm, setShowScheduleForm] = useState<NavigationTask | null>(null);
    const [viewingScoresForTask, setViewingScoresForTask] = useState<NavigationTask | null>(null);
    const [loadingTaskScores, setLoadingTaskScores] = useState(false);


    const canManageThisContest = contest?.is_editor || document.configuration.is_superuser;

    const hasFutureFlightsScheduled = useMemo(() => {
        if (!contest || !myFutureFlights) return false;
        const now = new Date();
        return contest.navigationtask_set.some(task => {
            const isTaskScheduledForMe = myFutureFlights.some(flight => flight.navigation_task === task.pk);
            return isTaskScheduledForMe && new Date(task.finish_time) > now;
        });
    }, [contest, myFutureFlights]);

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
            const promises = [
                fetchContest(Number(contestId)),
                fetchOngoingNavigation(),
                fetchContestResults(Number(contestId)),
            ];
            if (document.configuration.isAuthenticated) {
                promises.push(fetchMyFutureFlights());
                promises.push(fetchMyPreviousFlights());
                promises.push(fetchMyContestTeams());
            }

            Promise.all(promises).catch(err => {
                setError((err as Error).message)
            })
            .finally(() => setLoading(false));
        }
    }

    useEffect(() => {
        refreshData();
    }, [contestId]);
    
    const handleWithdrawClick = async (contestId: number) => {
        try {
            await withdraw(contestId);
            await fetchContest(contestId, true);
        } catch (error) {
            setError((error as Error).message);
        }
    };

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContantId: number) => {
        try {
            await cancelFlight(contestId, navigationTaskId, futureContantId);
        } catch (error) {
            setError((error as Error).message);
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
    const canSchedule = document.configuration.isAuthenticated && (!userContestTeam || !!userContestTeam?.is_user_pilot);

    const tasksForThisContest = new Set(contest.navigationtask_set.map(t => t.pk));
    const upcomingFlightsForThisContest = myFutureFlights.filter(f => tasksForThisContest.has(f.navigation_task));

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            {/* Modals for forms */}
            {showRegistrationForm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-center">
                    <ContestRegistrationForm
                        contest={contest}
                        myFutureParticipations={myFutureFlights}
                        myContestTeams={myContestTeams}
                        onClose={async () => {
                            setShowRegistrationForm(false);
                            await fetchMyContestTeams(true);
                            await fetchContest(contest.id, true);
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
                        onClose={async () => {
                            setShowScheduleForm(null);
                            await fetchMyContestTeams(true);
                            await fetchMyFutureFlights(true);
                            await fetchContest(contest.id, true);
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
                            <h1 className="text-4xl font-bold flex items-center gap-2">
                                {contest.name}
                                <PublicityIcon isPublic={contest.is_public} isFeatured={contest.is_featured} size={24} />
                            </h1>
                            <p className="text-lg text-gray-400">{formatDateInterval(contest.start_time, contest.finish_time)}</p>
                            <p className="flex items-center gap-2">
                                {contest.latitude?.toFixed(2)}, {contest.longitude?.toFixed(2)}
                                {contest.country_flag_url && (
                                    <img src={contest.country_flag_url} alt={`${contest.country} flag`} className="w-6 h-4 inline-block" />
                                )}
                            </p>
                            {contest.time_zone && <p className="text-sm text-gray-500">Time Zone: {contest.time_zone}</p>}
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
                                    <div className="tooltip tooltip-bottom" data-tip={hasFutureFlightsScheduled ? "Cannot withdraw, you have scheduled flights in the future." : ""}>
                                        <button
                                            className="btn btn-warning"
                                            onClick={() => handleWithdrawClick(contest.id)}
                                            disabled={hasFutureFlightsScheduled}
                                        >
                                            Withdraw
                                        </button>
                                    </div>
                                );
                            } else if (userContestTeam) {
                                return (
                                    <button className="btn btn-info" disabled>Registered</button>
                                );
                            } else if (document.configuration.isAuthenticated) {
                                return (
                                    <button className="btn btn-success" onClick={() => setShowRegistrationForm(true)}>Register</button>
                                );
                            } else {
                                return (
                                    <div className="text-sm text-gray-500 p-2 border border-gray-300 rounded-md">
                                        Please <a href={`${reverse('login')}?next=/`} className="link link-primary">log in</a> to participate in the contest.
                                    </div>
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
                    <Leaderboard results={contestResults || null} />
                </div>

                {/* Task Suite */}
                <div>
                    <p className="text-sm text-gray-500 mb-4">All times are in contest time zone: {contest.time_zone}</p>
                    {upcomingFlightsForThisContest.length > 0 && (
                        <div className="mb-8">
                            <h2 className="text-2xl font-bold mb-4">My Upcoming Flights</h2>
                            <UpcomingFlights myFutureFlights={upcomingFlightsForThisContest} contests={contest ? [contest] : []} onCancel={handleCancelFlight} />
                        </div>
                    )}
                    <h2 className="text-2xl font-bold mb-1 flex items-center gap-2">
                        Task Suite
                        <div className="dropdown dropdown-hover dropdown-left">
                            <label tabIndex={0} className="m-1"><HelpCircle size={20} className="cursor-pointer" /></label>
                            <div tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-200 rounded-box w-64">
                                <p className="font-bold">Open:</p>
                                <p className="mb-2">The task's finish time has not passed, and you currently do not have a flight scheduled for it. It is ready for flight plan registration.</p>
                                <p className="font-bold">Scheduled:</p>
                                <p className="mb-2">You have successfully registered a flight plan.</p>
                                <p className="font-bold">Live:</p>
                                <p className="mb-2">The task is actively being tracked.</p>
                                <p className="font-bold">Finalized:</p>
                                <p>The task's finish time has passed and results are available.</p>
                            </div>
                        </div>
                    </h2>
                    <div className="space-y-4">
                        {contest.navigationtask_set
                            .filter(task => {
                                if (contest.is_editor || document.configuration.is_superuser) {
                                    return true; // Editor OR Superuser sees all tasks
                                } else {
                                    return task.is_featured && task.is_public; // Non-editor/non-superuser sees only public and featured tasks
                                }
                            })
                            .map(task => {
                                const futureContestant = myFutureFlights.find(f => f.navigation_task === task.pk);
                                const canCancelThisFlight = futureContestant && userContestTeam && futureContestant.team.id === userContestTeam.team && userContestTeam.is_user_pilot;

                                return (
                                    <TaskCard
                                        key={task.pk}
                                        name={task.name}
                                        status={getTaskStatus(task)}
                                        contestId={contest.id}
                                        taskId={task.pk}
                                        start_time={task.start_time}
                                        finish_time={task.finish_time}
                                        tracking_link={task.tracking_link}
                                        onScheduleClick={() => setShowScheduleForm(task)}
                                        onViewScoresClick={() => handleViewScoresClick(task)}
                                        canSchedule={canSchedule}
                                        is_public={task.is_public}
                                        is_featured={task.is_featured}
                                        timeZone={contest.time_zone}
                                        route={task.route}
                                        flown_contestants_count={task.flown_contestants_count}
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
