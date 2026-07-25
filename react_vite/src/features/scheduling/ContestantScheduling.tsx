import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchContestTeams, fetchNavigationTask, fetchScheduleCapacityPreview, scheduleContestants, updateContestant, fetchTeam, fetchContestant, deleteContestant } from './api';
import SchedulingForm from './SchedulingForm';
import Timeline from './Timeline';
import ContestantTimetable from './ContestantTimetable';
import { Loading } from '../route-editor/components/basicComponents';
import { useToast } from '../competition-map/hooks/useToast';
import './print.css';
import { reverse } from '../../urls';

const ContestantScheduling = () => {
    const { contestId, navigationTaskId } = useParams();
    const [contestTeams, setContestTeams] = useState([]);
    const [navigationTask, setNavigationTask] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [scheduling, setScheduling] = useState(false);
    const [firstTakeoffTime, setFirstTakeoffTime] = useState<any>(null);
    const [capacityPreview, setCapacityPreview] = useState<any>(null);
    const [isInfoCollapsed, setIsInfoCollapsed] = useState(false);
    const { showToast, ToastContainer, toasts, removeToast } = useToast();

    const loadData = async (silent = false) => {
        if (!silent) setLoading(true);
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
            if (!silent) setLoading(false);
        }
    };

    useEffect(() => {
        setFirstTakeoffTime(null);
        loadData(false);
    }, [contestId, navigationTaskId]);

    useEffect(() => {
        const visitCountStr = localStorage.getItem('scheduling_info_visits');
        let visitCount = visitCountStr ? parseInt(visitCountStr, 10) : 0;
        visitCount++;
        localStorage.setItem('scheduling_info_visits', visitCount.toString());
        
        if (visitCount > 3) {
            setIsInfoCollapsed(true);
        }
    }, []);

    const refreshCapacityPreview = useCallback(async (selectedContestTeamIds: number[], firstTakeoffIso?: string | null) => {
        if (!contestId || !navigationTaskId) return;
        try {
            const preview = await fetchScheduleCapacityPreview(
                Number(contestId),
                Number(navigationTaskId),
                selectedContestTeamIds,
                firstTakeoffIso || undefined,
            );
            setCapacityPreview(preview);
        } catch (error: any) {
            console.error("Failed to fetch capacity preview", error);
        }
    }, [contestId, navigationTaskId]);

    useEffect(() => {
        if (!navigationTask || !firstTakeoffTime) return;
        const selectedContestTeamIds = contestTeams
            .filter((ct: any) => navigationTask?.contestant_set?.some((c: any) => c.team?.id === ct.team?.id))
            .map((ct: any) => ct.id);
        const firstTakeoffIso = firstTakeoffTime instanceof Date ? firstTakeoffTime.toISOString() : undefined;
        refreshCapacityPreview(selectedContestTeamIds, firstTakeoffIso);
    }, [navigationTask, contestTeams, firstTakeoffTime]);

    const handleSchedule = async (formData: any) => {
        setScheduling(true);
        try {
            if (contestId && navigationTaskId) {
                const result = await scheduleContestants(Number(contestId), Number(navigationTaskId), formData);
                if (result.status === 'success') {
                    showToast('Scheduling successful', 'success');
                    loadData(true); // Reload to get new contestants
                }
                if (result.messages && result.messages.length > 0) {
                    result.messages.forEach((msg: string) => showToast(msg, 'warning'));
                }
            }
        } catch (error: any) {
            showToast(error.message, 'error');
        } finally {
            setScheduling(false);
        }
    };

    const handleContestantUpdate = async (contestantId: number, updates: any) => {
        try {
            if (contestId && navigationTaskId) {
                const updatedContestant = await updateContestant(Number(contestId), Number(navigationTaskId), contestantId, updates);
                
                if (updatedContestant.overlap_warnings && updatedContestant.overlap_warnings.length > 0) {
                    updatedContestant.overlap_warnings.forEach((msg: string) => showToast(msg, 'warning'));
                }

                setNavigationTask((prev: any) => {
                    if (!prev) return prev;
                    const newContestantSet = prev.contestant_set.map((c: any) => {
                        if (c.id === updatedContestant.id) {
                            // Preserve the nested team object if the response only returns an ID
                            const team = (typeof updatedContestant.team === 'object' && updatedContestant.team !== null) 
                                ? updatedContestant.team 
                                : c.team;
                            return { ...updatedContestant, team };
                        }
                        return c;
                    });
                    return { ...prev, contestant_set: newContestantSet };
                });
            }
        } catch (error: any) {
            showToast(error.message, 'error');
            // Revert to server data for this contestant only
            if (contestId && navigationTaskId) {
                try {
                    const serverContestant = await fetchContestant(Number(contestId), Number(navigationTaskId), contestantId);
                    setNavigationTask((prev: any) => {
                        if (!prev) return prev;
                        const newContestantSet = prev.contestant_set.map((c: any) => {
                            if (c.id === serverContestant.id) {
                                // Preserve the nested team object if the response only returns an ID
                                const team = (typeof serverContestant.team === 'object' && serverContestant.team !== null) 
                                    ? serverContestant.team 
                                    : c.team;
                                return { ...serverContestant, team };
                            }
                            return c;
                        });
                        return { ...prev, contestant_set: newContestantSet };
                    });
                } catch (fetchError: any) {
                    console.error("Failed to revert contestant data:", fetchError);
                    loadData(true); // Fallback to full reload if single fetch fails
                }
            }
        }
    }

    const handleContestantDelete = async (contestantId: number) => {
        try {
            if (contestId && navigationTaskId) {
                await deleteContestant(Number(contestId), Number(navigationTaskId), contestantId);
                setNavigationTask((prev: any) => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        contestant_set: prev.contestant_set.filter((c: any) => c.id !== contestantId)
                    };
                });
                showToast('Contestant deleted', 'success');
            }
        } catch (error: any) {
            showToast(error.message, 'error');
            loadData(true); // Reload to restore state if delete failed
        }
    };

    const handleToggleLock = async (contestantId: number, currentLockState: boolean) => {
        await handleContestantUpdate(contestantId, { schedule_locked: !currentLockState });
    };

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
                    <h1 className="text-3xl font-bold">
                        <span className="print:hidden">Schedule Contestants: </span>
                        {navigationTask?.name}
                    </h1>
                    <p className="text-sm opacity-70 print:hidden">
                        Window: {formatTime(navigationTask?.start_time)} - {formatTime(navigationTask?.finish_time)} ({timeZone})
                    </p>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => window.print()} className="btn btn-primary btn-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 mr-1">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.055 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z" />
                        </svg>
                        Print Schedule
                    </button>
                    <a href={reverse('navigationtask_detail', navigationTaskId )} className="btn btn-secondary btn-sm">
                        Back to navigation task
                    </a>
                </div>
            </div>

            <div className="alert alert-info shadow-sm mb-6 text-sm">
                <div className="w-full">
                    <div className="flex items-start gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current flex-shrink-0 w-6 h-6"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        <div className="w-full">
                            <div className="flex justify-between items-center cursor-pointer" onClick={() => setIsInfoCollapsed(!isInfoCollapsed)}>
                                <h3 className="font-bold">Scheduling flights</h3>
                                <button className="btn btn-ghost btn-xs btn-circle">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={`w-4 h-4 transition-transform ${isInfoCollapsed ? 'rotate-180' : ''}`}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
                                    </svg>
                                </button>
                            </div>
                            {!isInfoCollapsed && (
                                <ul className="list-disc list-inside space-y-1 mt-2">
                                    <li>The scheduler manages all flights ending after the <strong>First Takeoff Time</strong>. Flights before this time are untouched.</li>
                                    <li><strong>Locked Flights (🔒 / 📡):</strong> 
                                        <ul className="list-disc list-inside ml-4 mt-1">
                                            <li><strong>Manual Lock (🔒):</strong> Double-click a flight in the timeline to lock/unlock. These are never moved or deleted by the scheduler.</li>
                                            <li><strong>Tracking Started (📡):</strong> Flights where the calculator has started are automatically locked. They cannot be moved, but they can be deleted if necessary.</li>
                                        </ul>
                                    </li>
                                    <li><strong>Unlocked Flights:</strong> Flights in the scheduling window will be overwritten. If a team is not selected, their unlocked future flight will be removed.</li>
                                    <li><strong>Manual Adjustment:</strong> After the automatic scheduling process, you can click and drag a contestant along the timeline to change its scheduling manually.</li>
                                    <li><strong>Initial Scheduling:</strong> Determine the first takeoff time, select all teams that will be flying, and press "Run Scheduler". This will populate all contestants.</li>
                                    <li><strong>Updates During Competition:</strong> If changes are needed (e.g. delays or roster changes):
                                        <ul className="list-disc list-inside ml-4 mt-1">
                                            <li>Lock all contestants that have already flown or whose time should not change.</li>
                                            <li>Update the <strong>Next Takeoff Time</strong> to the desired time for the first <em>new</em> flight to be scheduled.</li>
                                            <li>Select/deselect any teams as required for the remaining flights.</li>
                                            <li>Run scheduler again.</li>
                                        </ul>
                                    </li>
                                </ul>
                            )}
                        </div>
                    </div>
                </div>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-1">
                    <div className="card bg-base-100 shadow-xl">
                        <div className="card-body">
                            <h2 className="card-title">Configuration</h2>
                            <SchedulingForm 
                                contestTeams={contestTeams} 
                                navigationTask={navigationTask}
                                capacityPreview={capacityPreview}
                                firstTakeoffTime={firstTakeoffTime}
                                setFirstTakeoffTime={setFirstTakeoffTime}
                                onSubmit={handleSchedule}
                                onCapacityPreviewChange={refreshCapacityPreview}
                                isLoading={scheduling}
                            />
                        </div>
                    </div>
                </div>
                <div className="lg:col-span-2">
                    <div id="timeline-container">
                        <div className="card bg-base-100 shadow-xl h-[700px]">
                            <div className="card-body flex flex-col h-full">
                                <h2 className="card-title">Timeline</h2>
                                <p className="text-sm text-gray-500 mb-2">Drag bars to reschedule. Locked if tracking started. Select and delete key to remove.</p>
                                <div className="flex-grow">
                                    <Timeline 
                                        navigationTask={navigationTask} 
                                        firstTakeoffTime={firstTakeoffTime}
                                        onUpdate={handleContestantUpdate}
                                        onToggleLock={handleToggleLock}
                                        onDelete={handleContestantDelete}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                    <div id="timetable-container" className="mt-8">
                        <ContestantTimetable navigationTask={navigationTask} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ContestantScheduling;
