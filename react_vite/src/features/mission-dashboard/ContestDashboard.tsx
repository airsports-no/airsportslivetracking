import React, { useState, useEffect, useMemo, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useParams, Link, useNavigate } from 'react-router-dom';
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
import { canManageContest } from './permissions';
import { fetchNavigationTask } from '../competition-map/api';
import { formatDateInterval } from '../../utils';
import NavigationTaskCreationFlow from '../contest-management/components/NavigationTaskCreationFlow';
import TeamRegistrationFlow from '../contest-management/components/TeamRegistrationFlow';
import ImportTeamsPanel from '../contest-management/components/ImportTeamsPanel';
import TeamList from '../contest-management/components/TeamList';
import ContestSettingsForm from '../contest-management/components/ContestSettingsForm';
import ContestTokenPanel from './components/ContestTokenPanel';
import ContestPermissionsPanel from '../contest-management/components/ContestPermissionsPanel';
import * as contestManagementApi from '../contest-management/api';
import {
    assignContestToken,
    replaceContestToken,
    deleteContest,
    fetchContestPermissions,
    addContestPermission,
    changeContestPermission,
    removeContestPermission,
    ContestPermissionGrant,
} from './api';
import { ContestTeamListItem } from '../contest-management/types';

const ContestDashboard = () => {
    const { contestId } = useParams<{ contestId: string }>();
    const navigate = useNavigate();
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
        fetchContestResults,
        fetchMyContestTeams,
        fetchOngoingNavigation,
        withdraw,
        cancelFlight,
    } = useMissionDashboardStore();

    const contest = contestsById[Number(contestId)];
    const contestResults = results[Number(contestId)];

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [toastMessage, setToastMessage] = useState<string[] | null>(null);

    useEffect(() => {
        if (toastMessage) {
            const timer = setTimeout(() => setToastMessage(null), 5000);
            return () => clearTimeout(timer);
        }
    }, [toastMessage]);

    const [showRegistrationForm, setShowRegistrationForm] = useState(false);
    const [showScheduleForm, setShowScheduleForm] = useState<NavigationTask | null>(null);
    const [viewingScoresForTask, setViewingScoresForTask] = useState<NavigationTask | null>(null);
    const [loadingTaskScores, setLoadingTaskScores] = useState(false);

    // Owner-only management tools (task creation, team management) - rendered inline below
    // instead of on a separate page, so there's a single contest view for every visitor.
    const [showCreateTask, setShowCreateTask] = useState(false);
    const [teams, setTeams] = useState<ContestTeamListItem[]>([]);
    const [teamsLoading, setTeamsLoading] = useState(true);
    const [teamsError, setTeamsError] = useState<string | null>(null);
    const [editingContestTeam, setEditingContestTeam] = useState<ContestTeamListItem | 'new' | null>(null);
    const [showImportTeams, setShowImportTeams] = useState(false);
    const [permissionGrants, setPermissionGrants] = useState<ContestPermissionGrant[]>([]);
    const [permissionsLoading, setPermissionsLoading] = useState(false);
    const [permissionsError, setPermissionsError] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const latestTeamsContestId = useRef(contestId);

    const canManageThisContest = canManageContest(contest);

    const refreshTeams = () => {
        if (!contestId) return;
        const requestedContestId = contestId;
        setTeamsLoading(true);
        setTeamsError(null);
        contestManagementApi
            .fetchContestTeams(Number(requestedContestId))
            .then(result => {
                if (requestedContestId === latestTeamsContestId.current) setTeams(result);
            })
            .catch(err => {
                if (requestedContestId === latestTeamsContestId.current) setTeamsError((err as Error).message);
            })
            .finally(() => {
                if (requestedContestId === latestTeamsContestId.current) setTeamsLoading(false);
            });
    };

    const refreshPermissions = () => {
        if (!contestId) return;
        const requestedContestId = contestId;
        // Clear the previous contest's rows immediately - otherwise they stay rendered (and
        // actionable) under the new contest's heading until this fetch resolves.
        setPermissionGrants([]);
        setPermissionsLoading(true);
        setPermissionsError(null);
        fetchContestPermissions(Number(requestedContestId))
            .then(result => {
                if (requestedContestId === latestTeamsContestId.current) setPermissionGrants(result);
            })
            .catch(err => {
                if (requestedContestId === latestTeamsContestId.current) setPermissionsError((err as Error).message);
            })
            .finally(() => {
                if (requestedContestId === latestTeamsContestId.current) setPermissionsLoading(false);
            });
    };

    useEffect(() => {
        latestTeamsContestId.current = contestId;
        if (canManageThisContest) {
            refreshTeams();
            refreshPermissions();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [contestId, canManageThisContest]);

    const handleDeleteContest = async () => {
        if (!window.confirm(`Delete contest "${contest.name}"? This cannot be undone.`)) return;
        setDeleting(true);
        setDeleteError(null);
        try {
            await deleteContest(contest.id);
            navigate('/');
        } catch (err) {
            setDeleteError((err as Error).message);
            setDeleting(false);
        }
    };


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
                fetchContestResults(Number(contestId)),
                fetchOngoingNavigation(true),
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

    useLayoutEffect(() => {
        document.querySelector('main')?.scrollTo(0, 0);
    }, [contestId, loading]);

    useEffect(() => {
        refreshData();
        
        const interval = setInterval(() => {
            if (contestId) {
                // Swallow errors here (unlike refreshData's Promise.all above, which surfaces
                // them via setError): a background poll tick failing - e.g. a transient mobile
                // network blip (Sentry JAVASCRIPT-REACT-2/3/4, all WebKit's generic "Load
                // failed" fetch-abort error) - shouldn't show an error banner over data that's
                // already on screen, and the next tick two minutes later will just retry.
                // Without a .catch() here these were uncaught promise rejections.
                Promise.all([
                    fetchContest(Number(contestId), true),
                    fetchContestResults(Number(contestId), true),
                    fetchOngoingNavigation(true),
                ]).catch(() => {});
            }
        }, 2 * 60 * 1000); // Refresh every 2 minutes

        return () => clearInterval(interval);
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
    const isRegisteredButNotPilot = !!userContestTeam && !userContestTeam.is_user_pilot;

    const tasksForThisContest = new Set(contest.navigationtask_set.map(t => t.pk));
    const upcomingFlightsForThisContest = myFutureFlights.filter(f => tasksForThisContest.has(f.navigation_task));

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            {toastMessage && (
                <div className="toast toast-top toast-end z-[2000]">
                    {toastMessage.map((msg, idx) => (
                         <div key={idx} className="alert alert-warning">
                            <span>{msg}</span>
                        </div>
                    ))}
                </div>
            )}
            {/* Modals for forms */}
            {showCreateTask && createPortal(
                <div className="fixed inset-0 bg-black/50 z-[9999] flex justify-center items-start overflow-y-auto p-4">
                    <NavigationTaskCreationFlow
                        entry={{ kind: 'contest', contestId: contest.id }}
                        initialContest={contest}
                        onCancel={() => setShowCreateTask(false)}
                        onCreated={createdContestId => {
                            setShowCreateTask(false);
                            fetchContest(createdContestId, true);
                        }}
                    />
                </div>,
                document.body
            )}
            {editingContestTeam && createPortal(
                <div className="fixed inset-0 bg-black/50 z-[9999] flex justify-center items-start overflow-y-auto p-4">
                    <TeamRegistrationFlow
                        contestId={contest.id}
                        editingContestTeam={editingContestTeam === 'new' ? undefined : editingContestTeam}
                        onCancel={() => setEditingContestTeam(null)}
                        onSaved={() => {
                            setEditingContestTeam(null);
                            refreshTeams();
                        }}
                    />
                </div>,
                document.body
            )}
            {showImportTeams && createPortal(
                <div className="fixed inset-0 bg-black/50 z-[9999] flex justify-center items-start overflow-y-auto p-4">
                    <ImportTeamsPanel
                        contestId={contest.id}
                        onCancel={() => setShowImportTeams(false)}
                        onImported={() => {
                            setShowImportTeams(false);
                            refreshTeams();
                        }}
                    />
                </div>,
                document.body
            )}
            {showRegistrationForm && (
                <div className="fixed inset-0 bg-black/50 z-[1000] flex justify-center items-start overflow-y-auto p-4">
                    <ContestRegistrationForm
                        contest={contest}
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
                 <div className="fixed inset-0 bg-black/50 z-[1000] flex justify-center items-start overflow-y-auto p-4">
                    <ScheduleFlightForm
                        contest={contest}
                        navigationTaskId={showScheduleForm.pk}
                        myContestTeams={myContestTeams}
                        onClose={async (warnings?: string[]) => {
                            if (warnings && warnings.length > 0) {
                                setToastMessage(warnings);
                            }
                            setShowScheduleForm(null);
                            await fetchMyContestTeams(true);
                            await fetchMyFutureFlights(true);
                            await fetchContest(contest.id, true);
                        }}
                    />
                </div>
            )}
            {viewingScoresForTask && (
                <div className="fixed inset-0 bg-black/50 z-[1000] flex justify-center items-start overflow-y-auto p-4">
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
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex flex-col md:flex-row md:items-center">
                        {contest.logo && (
                            <img src={contest.logo} alt={`${contest.name} logo`} className="hidden md:block h-24 w-24 mr-4" />
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
                     <div className="flex flex-col items-stretch gap-2 w-full md:w-auto">
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

            {canManageThisContest && (
                <div className="mb-8">
                    <h2 className="text-2xl font-bold mb-4">Manage this contest</h2>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="card bg-base-100 shadow">
                            <div className="card-body">
                                <div className="flex items-center justify-between">
                                    <h3 className="card-title">Navigation tasks</h3>
                                    <button className="btn btn-primary btn-sm" onClick={() => setShowCreateTask(true)}>
                                        Add navigation task
                                    </button>
                                </div>
                                <p className="text-sm text-gray-500">
                                    {contest.navigationtask_set.length === 0
                                        ? 'No navigation tasks yet.'
                                        : 'Manage each task (contestants, flight orders, scorecard) from its card in the Task Suite below.'}
                                </p>
                            </div>
                        </div>

                        <div className="card bg-base-100 shadow">
                            <div className="card-body">
                                <div className="flex items-center justify-between">
                                    <h3 className="card-title">Registered teams</h3>
                                    <div className="flex gap-2">
                                        <button className="btn btn-sm" onClick={() => setShowImportTeams(true)}>
                                            Import teams
                                        </button>
                                        <button className="btn btn-primary btn-sm" onClick={() => setEditingContestTeam('new')}>
                                            Register team
                                        </button>
                                    </div>
                                </div>
                                {teamsLoading ? (
                                    <Loading />
                                ) : teamsError ? (
                                    <div className="alert alert-error">
                                        <span>Failed to load teams: {teamsError}</span>
                                        <button type="button" className="btn btn-sm" onClick={refreshTeams}>
                                            Retry
                                        </button>
                                    </div>
                                ) : (
                                    <TeamList
                                        contestId={contest.id}
                                        teams={teams}
                                        onEdit={contestTeam => setEditingContestTeam(contestTeam)}
                                        onRemoved={contestTeamId => setTeams(prev => prev.filter(item => item.id !== contestTeamId))}
                                    />
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                        <div className="card bg-base-100 shadow">
                            <div className="card-body">
                                <h3 className="card-title">Contest settings</h3>
                                <ContestSettingsForm contest={contest} onSaved={() => fetchContest(contest.id, true)} />
                            </div>
                        </div>

                        <div className="space-y-4">
                            {contest.current_token_assignment && !contest.current_token_assignment.is_active_now && (
                                <div className="alert alert-warning shadow-sm">
                                    <div>
                                        <div className="font-bold">Archive Mode</div>
                                        <div className="text-sm">
                                            This contest token ({contest.current_token_assignment.token_type_name}) expired on{' '}
                                            {contest.current_token_assignment.expires_at &&
                                                new Date(contest.current_token_assignment.expires_at).toLocaleString()}
                                            . Historical results remain readable, but creating new tasks or launching new
                                            live sessions requires a new token or annual pass.
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="card bg-base-200 shadow-sm border border-base-300">
                                <div className="card-body p-5">
                                    <h3 className="card-title text-lg">Access &amp; limits</h3>
                                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                                        <span className="badge badge-info">{contest.access_status?.tier_label}</span>
                                        <span className="text-xs opacity-70">Source: {contest.access_status?.source_type}</span>
                                    </div>
                                    <div className="bg-base-100 rounded-lg p-3 text-sm">
                                        <div className="opacity-70">Competing pilots</div>
                                        <div className="font-semibold">
                                            {contest.access_status?.contestants_used} /{' '}
                                            {contest.access_status?.contestant_limit == null ? 'Unlimited' : contest.access_status.contestant_limit}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {!!contest.club_access_grants?.length && (
                                <div className="card bg-base-200 shadow-sm border border-base-300">
                                    <div className="card-body p-5">
                                        <h3 className="card-title text-lg">Club access</h3>
                                        <div className="space-y-2">
                                            {contest.club_access_grants.map((grant, index) => (
                                                <div key={index} className="rounded-lg bg-base-100 p-3 text-sm">
                                                    <div className="font-semibold">{grant.tier_label}</div>
                                                    <div className="opacity-70">
                                                        Competing pilots: {grant.contestant_limit == null ? 'Unlimited' : grant.contestant_limit}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}

                            <ContestTokenPanel
                                grants={contest.available_token_grants}
                                currentTokenGrantId={contest.access_status?.token_grant_id}
                                onAssign={async tokenGrantId => {
                                    await assignContestToken(contest.id, tokenGrantId);
                                    fetchContest(contest.id, true);
                                }}
                                onReplace={async tokenGrantId => {
                                    await replaceContestToken(contest.id, tokenGrantId);
                                    fetchContest(contest.id, true);
                                }}
                            />

                            {!!contest.club_manager_memberships?.length && (
                                <div className="card bg-base-200 shadow-sm border border-base-300">
                                    <div className="card-body p-5">
                                        <h3 className="card-title text-lg">Club managers</h3>
                                        <div className="space-y-2">
                                            {contest.club_manager_memberships.map(membership => (
                                                <div key={membership.email} className="rounded-lg bg-base-100 p-3 text-sm flex justify-between gap-2">
                                                    <span>{membership.email}</span>
                                                    <span className="badge badge-ghost badge-sm">{membership.role}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                        <div>
                            {permissionsError && <div className="alert alert-error mb-2">{permissionsError}</div>}
                            <ContestPermissionsPanel
                                grants={permissionGrants}
                                currentUserId={document.configuration.userId ?? -1}
                                loading={permissionsLoading}
                                onAdd={async (identifier, level) => {
                                    await addContestPermission(contest.id, identifier, level);
                                    refreshPermissions();
                                }}
                                onChange={async (userId, level) => {
                                    await changeContestPermission(contest.id, userId, level);
                                    refreshPermissions();
                                }}
                                onRemove={async userId => {
                                    await removeContestPermission(contest.id, userId);
                                    refreshPermissions();
                                }}
                            />
                        </div>

                        <div className="card bg-error/10 border border-error/30 shadow-sm">
                            <div className="card-body p-5">
                                <h3 className="card-title text-lg text-error">Danger zone</h3>
                                <p className="text-sm opacity-80">
                                    Deleting a contest permanently removes it, its navigation tasks, and all results.
                                </p>
                                {deleteError && <div className="alert alert-error text-sm py-2">{deleteError}</div>}
                                <div className="card-actions justify-end">
                                    <button className="btn btn-error btn-sm" disabled={deleting} onClick={handleDeleteContest}>
                                        {deleting && <span className="loading loading-spinner"></span>}
                                        Delete contest
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Task Suite */}
                <div className="lg:col-span-2 order-1 lg:order-2">
                    {upcomingFlightsForThisContest.length > 0 && (
                        <div className="mb-8">
                            <h2 className="text-2xl font-bold mb-4">My Upcoming Flights</h2>
                            <UpcomingFlights myFutureFlights={upcomingFlightsForThisContest} contests={contest ? [contest] : []} onCancel={handleCancelFlight} />
                        </div>
                    )}
                    <div className="flex flex-wrap justify-between items-center mb-4 gap-2">
                        <h2 className="text-2xl font-bold flex items-center gap-2">
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
                        <p className="text-sm text-gray-500">Times in {contest.time_zone}</p>
                    </div>
                    <div className="space-y-4">
                        {contest.navigationtask_set
                            .filter(task => {
                                if (canManageContest(contest)) {
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
                                        allow_self_management={task.allow_self_management}
                                        isRegisteredButNotPilot={isRegisteredButNotPilot}
                                        is_public={task.is_public}
                                        is_featured={task.is_featured}
                                        timeZone={contest.time_zone}
                                        route={task.route}
                                        flown_contestants_count={task.flown_contestants_count}
                                        canManage={canManageThisContest}
                                    />
                                );
                            })}
                    </div>
                </div>

                {/* Leaderboard */}
                <div className="order-2 lg:order-1">
                    <div className="flex justify-between items-center">
                        <h2 className="text-2xl font-bold mb-4">Leaderboard</h2>
                        <Link to={generatePath('CONTEST_RESULTS_TABLE', { contestId: contestId })} className="btn btn-primary">View Full Results</Link>
                    </div>
                    <Leaderboard results={contestResults || null} />
                </div>
            </div>
            <Link to="/" className="btn btn-secondary mt-4">Back to Dashboard</Link>
        </div>
    );
};
export default ContestDashboard;
