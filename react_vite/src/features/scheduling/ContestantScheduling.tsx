import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchContestTeams, fetchNavigationTask, scheduleContestants, updateContestant, fetchTeam } from './api';
import SchedulingForm from './SchedulingForm';
import Timeline from './Timeline';
import ContestantTimetable from './ContestantTimetable';
import { Loading } from '../route-editor/components/basicComponents';
import { useToast } from '../competition-map/hooks/useToast';

const ContestantScheduling = () => {
    const { contestId, navigationTaskId } = useParams();
    const [contestTeams, setContestTeams] = useState([]);
    const [navigationTask, setNavigationTask] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const { showToast, ToastContainer, toasts, removeToast } = useToast();

    const loadData = async () => {
        setLoading(true);
        try {
            if (contestId && navigationTaskId) {
                const teams = await fetchContestTeams(Number(contestId));
                
                // Fetch full team details for each contest team
                const teamsWithDetails = await Promise.all(teams.map(async (ct: any) => {
                    if (ct.team && typeof ct.team === 'number') {
                        try {
                            const teamData = await fetchTeam(ct.team);
                            return { ...ct, team: teamData };
                        } catch (e) {
                            console.error(`Failed to fetch team details for team ${ct.team}`, e);
                            return ct;
                        }
                    }
                    return ct;
                }));

                const task = await fetchNavigationTask(Number(contestId), Number(navigationTaskId));
                setContestTeams(teamsWithDetails as any);
                setNavigationTask(task);
            }
        } catch (error: any) {
            showToast(error.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [contestId, navigationTaskId]);

    const handleSchedule = async (formData: any) => {
        try {
            if (contestId && navigationTaskId) {
                const result = await scheduleContestants(Number(contestId), Number(navigationTaskId), formData);
                if (result.status === 'success') {
                    showToast('Scheduling successful', 'success');
                    loadData(); // Reload to get new contestants
                }
                if (result.messages && result.messages.length > 0) {
                    result.messages.forEach((msg: string) => showToast(msg, 'warning'));
                }
            }
        } catch (error: any) {
            showToast(error.message, 'error');
        }
    };

    const handleContestantUpdate = async (contestantId: number, updates: any) => {
        try {
            if (contestId && navigationTaskId) {
                await updateContestant(Number(contestId), Number(navigationTaskId), contestantId, updates);
                loadData(); 
            }
        } catch (error: any) {
            showToast(error.message, 'error');
        }
    }

    if (loading) return <Loading />;

    const timeZone = navigationTask?.time_zone || 'UTC';
    const formatTime = (date: string) => new Date(date).toLocaleString([], {
        timeZone,
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
            <ToastContainer toasts={toasts} removeToast={removeToast} />
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h1 className="text-3xl font-bold">Schedule Contestants: {navigationTask?.name}</h1>
                    <p className="text-sm opacity-70">
                        Window: {formatTime(navigationTask?.start_time)} - {formatTime(navigationTask?.finish_time)} ({timeZone})
                    </p>
                </div>
                <Link to={`/competition-map/${contestId}/${navigationTaskId}`} className="btn btn-secondary btn-sm">
                    Back to Map
                </Link>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-1">
                    <div className="card bg-base-100 shadow-xl">
                        <div className="card-body">
                            <h2 className="card-title">Configuration</h2>
                            <SchedulingForm 
                                contestTeams={contestTeams} 
                                navigationTask={navigationTask} 
                                onSubmit={handleSchedule} 
                            />
                        </div>
                    </div>
                </div>
                <div className="lg:col-span-2">
                     <div className="card bg-base-100 shadow-xl">
                        <div className="card-body">
                            <h2 className="card-title">Timeline</h2>
                            <p className="text-sm text-gray-500 mb-2">Drag bars to reschedule. Locked if tracking started.</p>
                            <Timeline 
                                navigationTask={navigationTask} 
                                onUpdate={handleContestantUpdate}
                            />
                        </div>
                    </div>
                    <ContestantTimetable navigationTask={navigationTask} />
                </div>
            </div>
        </div>
    );
};

export default ContestantScheduling;
