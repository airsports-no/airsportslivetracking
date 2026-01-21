import React from 'react';

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

    return (
        <div className="card bg-base-100 shadow-xl mt-8">
            <div className="card-body">
                <h2 className="card-title flex justify-between items-center">
                    <span>Timetable</span>
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
                                const landingTime = c.landing_time || c.finished_by_time;
                                
                                const planningMinutes = navigationTask.planning_time ?? 45;
                                const planningTime = new Date(new Date(c.takeoff_time).getTime() - planningMinutes * 60000).toISOString();

                                return (
                                    <tr key={c.id}>
                                        <td>{c.contestant_number}</td>
                                        <td>
                                            {c.team.crew.member1.first_name} {c.team.crew.member1.last_name}
                                        </td>
                                        <td>{c.team.aeroplane.registration}</td>
                                        <td className="font-mono">{c.adaptive_start ? 'Adaptive' : formatTime(planningTime)}</td>
                                        <td className="font-mono">{c.adaptive_start ? 'Adaptive' : formatTime(c.takeoff_time)}</td>
                                        <td className="font-mono">{c.adaptive_start ? 'Adaptive' : formatTime(startTime)}</td>
                                        <td className="font-mono">{c.adaptive_start ? 'Adaptive' : formatTime(landingTime)}</td>
                                        <td>{c.air_speed} kt</td>
                                    </tr>
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
