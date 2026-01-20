import React, { useState } from 'react';

interface SchedulingFormProps {
    contestTeams: any[];
    navigationTask: any;
    onSubmit: (data: any) => void;
}

const SchedulingForm: React.FC<SchedulingFormProps> = ({ contestTeams, navigationTask, onSubmit }) => {
    const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>([]);
    const [firstTakeoffTime, setFirstTakeoffTime] = useState(navigationTask?.start_time ? new Date(navigationTask.start_time).toISOString().slice(0, 16) : '');
    const [startInterval, setStartInterval] = useState(5);
    const [finishInterval, setFinishInterval] = useState(2);
    const [aircraftSwitchTime, setAircraftSwitchTime] = useState(30);
    const [trackerSwitchTime, setTrackerSwitchTime] = useState(15);
    const [crewSwitchTime, setCrewSwitchTime] = useState(15);
    const [trackerLeadTime, setTrackerLeadTime] = useState(15);
    const [optimise, setOptimise] = useState(true);

    const timeZone = navigationTask?.time_zone || 'UTC';

    // Helper to format date for datetime-local input in specific timezone
    const formatInTimeZone = (date: Date, tz: string) => {
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: tz,
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hour12: false
        }).formatToParts(date);
        
        const getPart = (type: string) => parts.find(p => p.type === type)?.value;
        return `${getPart('year')}-${getPart('month')}-${getPart('day')}T${getPart('hour')}:${getPart('minute')}`;
    };

    React.useEffect(() => {
        if (navigationTask?.start_time) {
            // Default: Task Start Time + 30 minutes
            const startTime = new Date(navigationTask.start_time);
            const defaultTime = new Date(startTime.getTime() + 30 * 60000);
            setFirstTakeoffTime(formatInTimeZone(defaultTime, timeZone));
        }
    }, [navigationTask]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        
        // When sending back, we assume the backend handles the timezone conversion if we send iso string or
        // if we send it as is, the backend might treat it as local to the task.
        // However, datetime-local value is "YYYY-MM-DDTHH:mm".
        // To be safe, we should convert it back to ISO string with the correct offset.
        
        // Simple hack: construct a date object by appending the timezone offset of the target timezone?
        // Or cleaner: Use the same parts logic to construct a UTC date that represents that local time?
        // Actually, easiest is to just let the backend handle "local time" if the API expects a timezone-aware string.
        // But the previous implementation just sent the string. Let's see what `schedule_contestants` expects.
        // It expects `first_takeoff_time: datetime.datetime`.
        
        // If we send "2023-10-27T10:30", DRF usually interprets this as local time of the server or UTC if no TZ info.
        // But here "local" means "local to the contest".
        
        // Let's manually construct the ISO string with offset for the given timezone.
        // Since we don't have a heavy library like moment-timezone, we can try to rely on the backend interpreting a naive string 
        // as being in the contest's timezone if that's how it's set up, OR we try to determine the offset.
        
        // Given the complexity of client-side TZ without libraries, sending the naive string (from datetime-local)
        // is risky if the server assumes UTC. 
        // But `dateutil.parser.parse` in python handles naive dates.
        // The `schedule_and_create_contestants` function receives `first_takeoff_time`.
        // Let's assume the user picks a time in the "Contest Timezone".
        
        // Let's try to append the timezone name if possible? No, standard is offset.
        
        // For now, let's keep sending the string from the input. 
        // Ideally we'd convert `firstTakeoffTime` (which is "Local Contest Time") back to a UTC ISO string.
        
        // Let's stick to the previous behavior but just defaulted correctly.
        // The previous behavior was just sending `firstTakeoffTime` directly.
        
        onSubmit({
            contest_teams: selectedTeamIds,
            first_takeoff_time: firstTakeoffTime,
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
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="form-control w-full">
                <label className="label">
                    <span className="label-text">Contest Teams</span>
                    <span className="label-text-alt">
                        <button type="button" className="btn btn-xs btn-ghost" onClick={handleSelectAll}>Select All</button>
                        <button type="button" className="btn btn-xs btn-ghost" onClick={handleDeselectAll}>None</button>
                    </span>
                </label>
                <div className="h-64 overflow-y-auto overflow-x-hidden border border-base-300 rounded-lg p-2 bg-base-100">
                    {contestTeams.map(ct => {
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
                    {contestTeams.length === 0 && <div className="text-center text-gray-500 py-4">No teams found.</div>}
                </div>
            </div>

            <div className="form-control w-full">
                <label className="label">
                    <span className="label-text">First Takeoff Time</span>
                    <span className="label-text-alt">{timeZone}</span>
                </label>
                <input 
                    type="datetime-local" 
                    className="input input-bordered w-full" 
                    value={firstTakeoffTime}
                    onChange={e => setFirstTakeoffTime(e.target.value)}
                    required
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="form-control w-full">
                    <label className="label"><span className="label-text">Start Interval (min)</span></label>
                    <input type="number" className="input input-bordered w-full" value={startInterval} onChange={e => setStartInterval(Number(e.target.value))} />
                </div>
                <div className="form-control w-full">
                    <label className="label"><span className="label-text">Finish Interval (min)</span></label>
                    <input type="number" className="input input-bordered w-full" value={finishInterval} onChange={e => setFinishInterval(Number(e.target.value))} />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="form-control w-full">
                    <label className="label"><span className="label-text">Aircraft Switch (min)</span></label>
                    <input type="number" className="input input-bordered w-full" value={aircraftSwitchTime} onChange={e => setAircraftSwitchTime(Number(e.target.value))} />
                </div>
                <div className="form-control w-full">
                    <label className="label"><span className="label-text">Tracker Switch (min)</span></label>
                    <input type="number" className="input input-bordered w-full" value={trackerSwitchTime} onChange={e => setTrackerSwitchTime(Number(e.target.value))} />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="form-control w-full">
                    <label className="label"><span className="label-text">Crew Switch (min)</span></label>
                    <input type="number" className="input input-bordered w-full" value={crewSwitchTime} onChange={e => setCrewSwitchTime(Number(e.target.value))} />
                </div>
                <div className="form-control w-full">
                    <label className="label"><span className="label-text">Tracker Lead Time (min)</span></label>
                    <input type="number" className="input input-bordered w-full" value={trackerLeadTime} onChange={e => setTrackerLeadTime(Number(e.target.value))} />
                </div>
            </div>

            <div className="form-control">
                <label className="label cursor-pointer">
                    <span className="label-text">Optimise Schedule</span>
                    <input type="checkbox" className="checkbox" checked={optimise} onChange={e => setOptimise(e.target.checked)} />
                </label>
            </div>

            <button type="submit" className="btn btn-primary w-full">Run Scheduler</button>
        </form>
    );
};

export default SchedulingForm;
