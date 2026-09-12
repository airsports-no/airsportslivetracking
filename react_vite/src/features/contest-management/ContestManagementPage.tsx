import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Loading } from '../route-editor/components/basicComponents';
import { useMissionDashboardStore } from '../mission-dashboard/store';
import { canManageContest } from '../mission-dashboard/permissions';
import { reverse, generatePath } from '../../urls';
import NavigationTaskCreationFlow from './components/NavigationTaskCreationFlow';
import TeamRegistrationFlow from './components/TeamRegistrationFlow';
import ImportTeamsPanel from './components/ImportTeamsPanel';
import TeamList from './components/TeamList';
import * as contestManagementApi from './api';
import { ContestTeamListItem } from './types';

const ContestManagementPage = () => {
    const { contestId } = useParams<{ contestId: string }>();
    const navigate = useNavigate();
    const { contestsById, fetchContest } = useMissionDashboardStore();
    const contest = contestsById[Number(contestId)];

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showCreateTask, setShowCreateTask] = useState(false);
    const [teams, setTeams] = useState<ContestTeamListItem[]>([]);
    const [teamsLoading, setTeamsLoading] = useState(true);
    const [editingContestTeam, setEditingContestTeam] = useState<ContestTeamListItem | 'new' | null>(null);
    const [showImportTeams, setShowImportTeams] = useState(false);

    useEffect(() => {
        if (!contestId) return;
        setLoading(true);
        fetchContest(Number(contestId))
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    }, [contestId]);

    const refreshTeams = () => {
        if (!contestId) return;
        setTeamsLoading(true);
        contestManagementApi
            .fetchContestTeams(Number(contestId))
            .then(setTeams)
            .catch(err => setError((err as Error).message))
            .finally(() => setTeamsLoading(false));
    };

    useEffect(() => {
        refreshTeams();
    }, [contestId]);

    if (loading) return <div className="w-screen h-screen flex items-center justify-center"><Loading /></div>;
    if (error) return <div className="alert alert-error">{error}</div>;
    if (!contest) return <div className="alert alert-warning">Contest not found.</div>;

    if (!canManageContest(contest)) {
        return (
            <div className="container mx-auto p-4" data-theme="aviation">
                <div className="alert alert-warning">You do not have permission to manage this contest.</div>
                <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contest.id })} className="btn btn-sm mt-4">
                    Back to contest
                </Link>
            </div>
        );
    }

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            {showCreateTask && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-start overflow-y-auto p-4">
                    <NavigationTaskCreationFlow
                        entry={{ kind: 'contest', contestId: contest.id }}
                        initialContest={contest}
                        onCancel={() => setShowCreateTask(false)}
                        onCreated={(createdContestId, navigationTaskId) => {
                            setShowCreateTask(false);
                            fetchContest(createdContestId, true);
                            navigate(generatePath('COMPETITION_MAP_DETAIL', { contestId: createdContestId, navigationTaskId }));
                        }}
                    />
                </div>
            )}
            {editingContestTeam && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-start overflow-y-auto p-4">
                    <TeamRegistrationFlow
                        contestId={contest.id}
                        editingContestTeam={editingContestTeam === 'new' ? undefined : editingContestTeam}
                        onCancel={() => setEditingContestTeam(null)}
                        onSaved={() => {
                            setEditingContestTeam(null);
                            refreshTeams();
                        }}
                    />
                </div>
            )}
            {showImportTeams && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-start overflow-y-auto p-4">
                    <ImportTeamsPanel
                        contestId={contest.id}
                        onCancel={() => setShowImportTeams(false)}
                        onImported={() => {
                            setShowImportTeams(false);
                            refreshTeams();
                        }}
                    />
                </div>
            )}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
                <div>
                    <h1 className="text-3xl font-bold">{contest.name}</h1>
                    <p className="text-sm text-gray-500">Manage navigation tasks and registered teams</p>
                </div>
                <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contest.id })} className="btn btn-sm">
                    View contest
                </Link>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="card bg-base-100 shadow">
                    <div className="card-body">
                        <div className="flex items-center justify-between">
                            <h2 className="card-title">Navigation tasks</h2>
                            <button className="btn btn-primary btn-sm" onClick={() => setShowCreateTask(true)}>
                                Add navigation task
                            </button>
                        </div>
                        {contest.navigationtask_set.length === 0 ? (
                            <p className="text-sm text-gray-500">No navigation tasks yet.</p>
                        ) : (
                            <ul className="menu bg-base-100 rounded-box">
                                {contest.navigationtask_set.map(task => (
                                    <li key={task.pk}>
                                        <Link to={generatePath('COMPETITION_MAP_DETAIL', { contestId: contest.id, navigationTaskId: task.pk })}>
                                            {task.name}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>

                <div className="card bg-base-100 shadow">
                    <div className="card-body">
                        <div className="flex items-center justify-between">
                            <h2 className="card-title">Registered teams</h2>
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

            <div className="mt-6 text-sm text-gray-500">
                Looking for permissions, tokens, publicity, or deleting the contest?{' '}
                <a href={reverse('contest_details', contest.id)} className="link link-primary">
                    Use the classic contest page
                </a>
                .
            </div>
        </div>
    );
};

export default ContestManagementPage;
