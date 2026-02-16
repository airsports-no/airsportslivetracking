import React from 'react';
import { Contestant } from '../../competition-map/types';
import { Contest } from '../types';
import UpcomingFlightCard from './UpcomingFlightCard';

interface UpcomingFlightsProps {
    myFutureFlights: Contestant[];
    contests: Contest[];
    onCancel: (contestId: number, navigationTaskId: number, futureContestantId: number) => void;
}

const UpcomingFlights: React.FC<UpcomingFlightsProps> = ({ myFutureFlights, contests, onCancel }) => {
    
    const upcomingFlights = myFutureFlights.filter(flight => new Date(flight.finished_by_time) > new Date());

    if (upcomingFlights.length === 0) {
        return <div className="card bg-base-100 shadow-xl"><div className="card-body"><p>No upcoming flights scheduled.</p></div></div>;
    }

    return (
        <div className="space-y-4">
            {upcomingFlights.map(flight => {
                const contest = contests.find(c => c.id === flight.contest_id);
                const navTask = contest?.navigationtask_set.find(t => t.pk === flight.navigation_task);

                if (!contest || !navTask) {
                    return null; 
                }

                return (
                   <UpcomingFlightCard
                        key={flight.id}
                        flight={flight}
                        contest={contest}
                        navTask={navTask}
                        onCancelClick={() => onCancel(flight.contest_id, flight.navigation_task, flight.id)}
                    />
                );
            })}
        </div>
    );
};

export default UpcomingFlights;
