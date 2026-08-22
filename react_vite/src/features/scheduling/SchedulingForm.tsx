import React, { useState } from 'react';

interface SchedulingFormProps {
    contestTeams: any[];
    navigationTask: any;
    capacityPreview?: any;
    firstTakeoffTime: Date;
    setFirstTakeoffTime: (time: Date) => void;
    onSubmit: (data: any) => void;
    onCapacityPreviewChange?: (selectedTeamIds: number[], firstTakeoffIso?: string) => void;
    isLoading?: boolean;
}

const HelpIcon: React.FC<{ text: string }> = ({ text }) => (
    <div className="tooltip tooltip-right ml-1 cursor-help z-50" data-tip={text}>
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current text-info shrink-0 w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
    </div>
);

const SchedulingForm: React.FC<SchedulingFormProps> = ({ 
    contestTeams,
    navigationTask,
    capacityPreview,
    firstTakeoffTime,
    setFirstTakeoffTime,
    onSubmit,
    onCapacityPreviewChange,
    isLoading = false
}) => {
    const [selectedTeamIds, setSelectedTeamIds] = React.useState<number[]>([]);
    const [startInterval, setStartInterval] = React.useState(5);
    const [finishInterval, setFinishInterval] = React.useState(2);
    const [aircraftSwitchTime, setAircraftSwitchTime] = React.useState(30);
    const [trackerSwitchTime, setTrackerSwitchTime] = React.useState(15);
    const [crewSwitchTime, setCrewSwitchTime] = React.useState(15);
    const [trackerLeadTime, setTrackerLeadTime] = React.useState(15);
    const [optimise, setOptimise] = React.useState(true);
    const [nextTakeoffTime, setNextTakeoffTime] = useState<Date | null>(null);

    const timeZone = navigationTask?.time_zone || 'UTC';

    const formatInTimeZone = (date: Date | null, tz: string) => {
        if (!date) return '';
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: tz,
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hour12: false
        }).formatToParts(date);
        const getPart = (type: string) => parts.find(p => p.type === type)?.value;
        return `${getPart('year')}-${getPart('month')}-${getPart('day')}T${getPart('hour')}:${getPart('minute')}`;
    };

    const sortedContestTeams = React.useMemo(() => {
        return [...contestTeams].sort((a, b) => {
            const nameA = `${a.team?.crew?.member1?.first_name || ''} ${a.team?.crew?.member1?.last_name || ''}`.toLowerCase();
            const nameB = `${b.team?.crew?.member1?.first_name || ''} ${b.team?.crew?.member1?.last_name || ''}`.toLowerCase();
            return nameA.localeCompare(nameB);
        });
    }, [contestTeams]);

    const existingReservedPilotIds = React.useMemo(() => {
        const ownerPersonId = navigationTask?.contest?.created_by?.person?.id ?? null;
        const ids = new Set<number>();
        for (const contestant of navigationTask?.contestant_set || []) {
            const pilotId = contestant?.team?.crew?.member1?.id;
            if (!pilotId || pilotId === ownerPersonId) continue;
            ids.add(pilotId);
        }
        return ids;
    }, [navigationTask]);

    const selectedNewPilotCount = React.useMemo(() => {
        const ownerPersonId = navigationTask?.contest?.created_by?.person?.id ?? null;
        const selectedPilotIds = new Set<number>();
        for (const ct of contestTeams) {
            if (!selectedTeamIds.includes(ct.id)) continue;
            const pilotId = ct?.team?.crew?.member1?.id;
            if (!pilotId || pilotId === ownerPersonId) continue;
            if (!existingReservedPilotIds.has(pilotId)) {
                selectedPilotIds.add(pilotId);
            }
        }
        return selectedPilotIds.size;
    }, [contestTeams, selectedTeamIds, existingReservedPilotIds, navigationTask]);

    const reservedNow = capacityPreview?.reserved_before_count ?? existingReservedPilotIds.size;
    const reservedAfterSelection = reservedNow + selectedNewPilotCount;
    const capacityLimit = capacityPreview?.contestant_limit ?? navigationTask?.contest?.access_status?.contestant_limit ?? null;
    const wouldExceed = capacityLimit !== null && reservedAfterSelection > capacityLimit;

    // Initialize firstTakeoffTime if not set
    React.useEffect(() => {
        if (navigationTask?.start_time && !firstTakeoffTime) {
            const startTime = new Date(navigationTask.start_time);
            const scheduleStartTime = navigationTask.schedule_start_time ? new Date(navigationTask.schedule_start_time) : null;
            const planningTime = navigationTask.planning_time;
            const defaultTime = scheduleStartTime || new Date(startTime.getTime() + planningTime * 60000);
            
            setFirstTakeoffTime(defaultTime);
        }
    }, [navigationTask, firstTakeoffTime, setFirstTakeoffTime]);

    // Update nextTakeoffTime when firstTakeoffTime changes or if unset
    React.useEffect(() => {
        if (firstTakeoffTime && navigationTask) {
            const planningTime = navigationTask.planning_time;
            const minNextTime = new Date(firstTakeoffTime.getTime()); 
            const now=new Date()
            const targetNext = new Date(now.getTime() + planningTime * 60000);
            
            if (!nextTakeoffTime || nextTakeoffTime < firstTakeoffTime) {
                 setNextTakeoffTime(targetNext);
            }
        }
    }, [firstTakeoffTime, navigationTask]);

    // Pre-check teams that already have a contestant in this task
    React.useEffect(() => {
        if (navigationTask?.contestant_set && contestTeams.length > 0) {
            const existingTeamIds = navigationTask.contestant_set.map((c: any) => c.team?.id).filter(Boolean);
            const initialSelectedIds = contestTeams
                .filter(ct => existingTeamIds.includes(ct.team?.id))
                .map(ct => ct.id);
            setSelectedTeamIds(initialSelectedIds);
        }
    }, [navigationTask?.contestant_set, contestTeams]);

    React.useEffect(() => {
        if (onCapacityPreviewChange) {
            const firstTakeoffIso = firstTakeoffTime instanceof Date ? firstTakeoffTime.toISOString() : undefined;
            onCapacityPreviewChange(selectedTeamIds, firstTakeoffIso);
        }
    }, [selectedTeamIds, firstTakeoffTime, onCapacityPreviewChange]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit({
            contest_teams: selectedTeamIds,
            first_takeoff_time: firstTakeoffTime,
            next_takeoff_time: nextTakeoffTime,
            minutes_between_contestants_at_start: startInterval,
            minutes_between_contestants_at_finish: finishInterval,
            minutes_for_aircraft_switch: aircraftSwitchTime,
            minutes_for_tracker_switch: trackerSwitchTime,
            minutes_for_crew_switch: crewSwitchTime,
            tracker_lead_time_minutes: trackerLeadTime,
            optimise: optimise
        });
    };

    const handleCheckboxChange = (teamId: number) => {
        setSelectedTeamIds(prev => {
            if (prev.includes(teamId)) {
                return prev.filter(id => id !== teamId);
            } else {
                return [...prev, teamId];
            }
        });
    };

    const handleSelectAll = () => {
        setSelectedTeamIds(contestTeams.map(ct => ct.id));
    };

    const handleDeselectAll = () => {
        setSelectedTeamIds([]);
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4 max-h-[calc(100vh-200px)] overflow-y-auto px-1">
            <div className="form-control w-full">
                <label className="label">
                    <span className="label-text font-bold">Contest Teams</span>
                    <span className="label-text-alt">
                        <button type="button" className="btn btn-xs btn-ghost" onClick={handleSelectAll}>Select All</button>
                        <button type="button" className="btn btn-xs btn-ghost" onClick={handleDeselectAll}>None</button>
                    </span>
                </label>
                {capacityLimit !== null && (
                    <div className={`alert ${wouldExceed ? 'alert-warning' : 'alert-info'} mb-3 text-sm`}>
                        <div>
                            <div className="font-bold">Pilot capacity status</div>
                            {wouldExceed ? (
                                <div>
                                    Reserved now: {reservedNow} / {capacityLimit}. If all selected teams are scheduled, the task would require {reservedAfterSelection} / {capacityLimit} guest pilot slots. Deselect teams that introduce new pilots, remove unstarted contestants, reuse an already-counted pilot, or apply a larger token or club pass. The contest owner is exempt.
                                </div>
                            ) : (
                                <div>
                                    Reserved now: {reservedNow} / {capacityLimit}. New pilot reservations from the current team selection: {selectedNewPilotCount}. The contest owner is exempt.
                                </div>
                            )}
                        </div>
                    </div>
                )}
                <div className="h-64 overflow-y-auto overflow-x-hidden border border-base-300 rounded-lg p-2 bg-base-100">
                    {sortedContestTeams.map(ct => {
                        const label = !ct.team?.crew?.member1 
                            ? `Team ${ct.id} (Loading...)`
                            : `${ct.team.crew.member1.first_name} ${ct.team.crew.member1.last_name} (${ct.team.aeroplane?.registration})`;
                        
                        return (
                            <label key={ct.id} className="flex items-start cursor-pointer justify-start gap-3 hover:bg-base-200 rounded-sm p-1 text-left">
                                <input 
                                    type="checkbox" 
                                    className="checkbox checkbox-sm checkbox-primary mt-0.5"
                                    checked={selectedTeamIds.includes(ct.id)}
                                    onChange={() => handleCheckboxChange(ct.id)}
                                />
                                <span className="label-text text-sm break-words whitespace-normal flex-1">{label}</span>
                            </label>
                        );
                    })}
                    {sortedContestTeams.length === 0 && <div className="text-center text-gray-500 py-4">No teams found.</div>}
                </div>
            </div>

            <div className="form-control w-full">
                <label className="label justify-start gap-1 flex-wrap">
                    <span className="label-text">First Takeoff Time</span>
                    <HelpIcon text="Defines the start of the scheduling window. Flights before this time are preserved." />
                    <span className="label-text-alt ml-auto">{timeZone}</span>
                </label>
                <input 
                    type="datetime-local" 
                    className="input input-bordered w-full" 
                    value={formatInTimeZone(firstTakeoffTime, navigationTask?.time_zone)}
                    onChange={e => {
                        const val = e.target.value;
                        if (val) {
                            setFirstTakeoffTime(new Date(val));
                        }
                    }}
                    required
                />
            </div>

            <div className="form-control w-full">
                <label className="label justify-start gap-1 flex-wrap">
                    <span className="label-text">Next Takeoff Time</span>
                    <HelpIcon text="The scheduled start time for the first new contestant." />
                    <span className="label-text-alt ml-auto">{timeZone}</span>
                </label>
                <input 
                    type="datetime-local" 
                    className="input input-bordered w-full" 
                    value={formatInTimeZone(nextTakeoffTime, navigationTask?.time_zone)}
                    onChange={e => {
                        const val = e.target.value;
                        if (val) {
                            setNextTakeoffTime(new Date(val));
                        }
                    }}
                    required
                />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="form-control w-full">
                    <label className="label justify-start gap-1 flex-wrap">
                        <span className="label-text">Start Interval (min)</span>
                        <HelpIcon text="The minimum time between takeoffs." />
                    </label>
                    <input type="number" className="input input-bordered w-full" value={startInterval} onChange={e => setStartInterval(Number(e.target.value))} />
                </div>
                <div className="form-control w-full">
                    <label className="label justify-start gap-1 flex-wrap">
                        <span className="label-text">Finish Interval (min)</span>
                        <HelpIcon text="It is the minimum time between arriving aircraft." />
                    </label>
                    <input type="number" className="input input-bordered w-full" value={finishInterval} onChange={e => setFinishInterval(Number(e.target.value))} />
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="form-control w-full">
                    <label className="label justify-start gap-1 flex-wrap">
                        <span className="label-text">Aircraft Switch (min)</span>
                        <HelpIcon text="The time required to switch from one crew to another for a single aircraft." />
                    </label>
                    <input type="number" className="input input-bordered w-full" value={aircraftSwitchTime} onChange={e => setAircraftSwitchTime(Number(e.target.value))} />
                </div>
                <div className="form-control w-full">
                    <label className="label justify-start gap-1 flex-wrap">
                        <span className="label-text">Tracker Switch (min)</span>
                        <HelpIcon text="The time required to move a physical tracker from one crew to another, this is not relevant where using app tracking." />
                    </label>
                    <input type="number" className="input input-bordered w-full" value={trackerSwitchTime} onChange={e => setTrackerSwitchTime(Number(e.target.value))} />
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="form-control w-full">
                    <label className="label justify-start gap-1 flex-wrap">
                        <span className="label-text">Crew Switch (min)</span>
                        <HelpIcon text="The time required for a single crew member to switch to another crew." />
                    </label>
                    <input type="number" className="input input-bordered w-full" value={crewSwitchTime} onChange={e => setCrewSwitchTime(Number(e.target.value))} />
                </div>
                <div className="form-control w-full">
                    <label className="label justify-start gap-1 flex-wrap">
                        <span className="label-text">Tracker Lead Time (min)</span>
                        <HelpIcon text="How many minutes before take off time that we start tracking the crew." />
                    </label>
                    <input type="number" className="input input-bordered w-full" value={trackerLeadTime} onChange={e => setTrackerLeadTime(Number(e.target.value))} />
                </div>
            </div>

            <div className="form-control">
                <label className="label cursor-pointer justify-start gap-2 flex-wrap">
                    <span className="label-text">Optimise Schedule</span>
                    <HelpIcon text="Runs an additional linear programming optimizer on top of the algorithmic optimization." />
                    <input type="checkbox" className="checkbox ml-auto" checked={optimise} onChange={e => setOptimise(e.target.checked)} />
                </label>
            </div>

            <button type="submit" className="btn btn-primary w-full" disabled={isLoading || wouldExceed}>
                {isLoading ? <span className="loading loading-spinner"></span> : 'Run Scheduler'}
            </button>
        </form>
    );
};

export default SchedulingForm;
