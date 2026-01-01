import React from 'react';
import { MyParticipatingContest } from '../types';

interface UpcomingFlightsProps {
    myContests: MyParticipatingContest[];
    onCancel: (contestId: number, navigationTaskId: number, futureContestantId: number) => void;
}

const UpcomingFlights: React.FC<UpcomingFlightsProps> = ({ myContests, onCancel }) => {
    
    const upcomingFlights = myContests.flatMap(mc => 
        mc.contest.navigationtask_set.flatMap(nt => 
            nt.future_contestants.map(fc => ({...fc, navigationTask: nt, contest: mc.contest}))
        )
    ).filter(flight => new Date(flight.finished_by_time) > new Date());


    if (upcomingFlights.length === 0) {
        return <div className="card bg-base-100 shadow-xl"><div className="card-body"><p>No upcoming flights scheduled.</p></div></div>;
    }

    return (
        <div className="space-y-4">
            {upcomingFlights.map(flight => (
                <div key={flight.id} className="card bg-base-100 shadow-xl">
                    <div className="card-body">
                        <h3 className="card-title">
                            {flight.navigationTask.name}
                            <a href={flight.navigationTask.tracking_link} target="_blank" rel="noopener noreferrer" className="ml-2">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                            </a>
                        </h3>
                        <p>{flight.contest.name}</p>
                        <p>Take-off: {new Date(flight.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</p>
                        <div className="card-actions justify-end">
                            <button 
                                className="btn btn-error btn-sm"
                                onClick={() => onCancel(flight.contest.id, flight.navigationTask.pk, flight.id)}
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default UpcomingFlights;
