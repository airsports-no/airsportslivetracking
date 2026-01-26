import React from 'react';
import { AlertTriangle, HelpCircle } from 'lucide-react';

interface ContestantTimetableProps {
    navigationTask: any;
}

const ContestantTimetable: React.FC<ContestantTimetableProps> = ({ navigationTask }) => {
    if (!navigationTask || !navigationTask.contestant_set || navigationTask.contestant_set.length === 0) {
        return null;
    }

    const timeZone = navigationTask.time_zone || 'UTC';

    const sortedContestants = [...navigationTask.contestant_set].sort((a, b) => 
        new Date(a.takeoff_time).getTime() - new Date(b.takeoff_time).getTime()
    );

    const formatTime = (dateStr: string) => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleTimeString([], {
            timeZone,
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    };

    const getStartTime = (contestant: any) => {
        // Try to get from gate_times if available
        if (contestant.gate_times && navigationTask.route?.waypoints?.length > 0) {
            const startGateName = navigationTask.route.waypoints[0].name;
            if (contestant.gate_times[startGateName]) {
                return contestant.gate_times[startGateName];
            }
        }
        // Fallback to calculation if gate_times or route info is missing
        const takeoff = new Date(contestant.takeoff_time);
        const minutes = contestant.minutes_to_starting_point || 0;
        return new Date(takeoff.getTime() + minutes * 60000).toISOString();
    };

    let lastDate = '';

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString([], {
            timeZone,
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric'
        });
    };

    return (
        <div className="card bg-base-100 shadow-xl mt-8">
            <div className="card-body">
                <h2 className="card-title flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <span>Timetable</span>
                        <div className="dropdown dropdown-hover dropdown-right">
                            <label tabIndex={0} className="cursor-pointer text-base-content/50 hover:text-base-content"><HelpCircle size={18} /></label>
                            <div tabIndex={0} className="dropdown-content z-[1] card card-compact w-96 p-2 shadow bg-base-100 text-base-content font-normal text-sm">
                                <div className="card-body">
                                    <p>This tracker is shared by multiple contestants, causing simultaneous active flights in different tasks. To prevent data contamination, when a contestant crosses the start line, any earlier overlapping flights are automatically terminated.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <span className="hidden print:block text-xl font-bold">{navigationTask.name}</span>
                </h2>
                <div className="overflow-x-auto w-full">
                    <table className="table table-sm w-full table-zebra">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Contestant</th>
                                <th>Aircraft</th>
                                <th>Planning</th>
                                <th>Take-off</th>
                                <th>Start Point</th>
                                <th>Landing</th>
                                <th>Airspeed</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sortedContestants.map((c, index) => {
                                const startTime = getStartTime(c);
                                const landingTime = c.landing_time_after_final_gate || c.finished_by_time;
                                
                                const planningMinutes = navigationTask.planning_time ?? 45;
                                const planningTime = new Date(new Date(c.takeoff_time).getTime() - planningMinutes * 60000).toISOString();

                                const currentDate = formatDate(c.takeoff_time);
                                const showDateHeader = currentDate !== lastDate;
                                lastDate = currentDate;

                                return (
                                    <React.Fragment key={c.id}>
                                        {showDateHeader && (
                                            <tr className="bg-base-300 font-bold">
                                                <td colSpan={8} className="text-center py-2">
                                                    {currentDate}
                                                </td>
                                            </tr>
                                        )}
                                        <tr>
                                            <td>
                                                <div className="flex items-center gap-1">
                                                    {c.contestant_number}
                                                    {c.overlap_warnings && c.overlap_warnings.length > 0 && (
                                                        <div className="tooltip tooltip-right text-warning" data-tip="Overlapping contestants detected on this tracker.">
                                                            <AlertTriangle size={14} />
                                                        </div>
                                                    )}
                                                </div>
                                            </td>
                                            <td>
                                                {c.team.crew.member1.first_name} {c.team.crew.member1.last_name}
                                            </td>
                                            <td>{c.team.aeroplane.registration}</td>
                                            {c.adaptive_start ? (
                                                <>
                                                    <td className="text-center opacity-30">-</td>
                                                    <td className="font-mono">{formatTime(c.tracker_start_time)}</td>
                                                    <td className="font-bold text-primary italic">Adaptive</td>
                                                    <td className="font-mono">{formatTime(c.finished_by_time)}</td>
                                                </>
                                            ) : (
                                                <>
                                                    <td className="font-mono">{formatTime(planningTime)}</td>
                                                    <td className="font-mono">{formatTime(c.takeoff_time)}</td>
                                                    <td className="font-mono">{formatTime(startTime)}</td>
                                                    <td className="font-mono">{formatTime(landingTime)}</td>
                                                </>
                                            )}
                                            <td>{c.air_speed} kt</td>
                                        </tr>
                                    </React.Fragment>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default ContestantTimetable;
