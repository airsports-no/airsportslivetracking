import React from 'react';
import { Contest } from '../types';

interface ContestCardProps {
    contest: Contest;
    status: 'live' | 'upcoming' | 'past';
    isRegistered?: boolean;
    hasScheduledFlight?: boolean;
}

const ContestCard: React.FC<ContestCardProps> = ({ contest, status, isRegistered, hasScheduledFlight }) => {
    return (
        <div className="card bg-base-200 shadow-xl image-full h-[280px] overflow-hidden">
            {contest.header_image && (
                <figure><img src={contest.header_image} alt={contest.name} /></figure>
            )}
            <div className="card-body">
                <h2 className="card-title">
                    {contest.name}
                    {contest.country_flag_url && (
                        <img src={contest.country_flag_url} alt={`${contest.country} flag`} className="ml-2 w-6 h-4 inline-block" />
                    )}
                </h2>
                {contest.navigationtask_set && contest.navigationtask_set.length > 0 && (
                    <p className="text-sm text-gray-400">{contest.navigationtask_set.length} tasks</p>
                )}
                <div className="card-actions justify-end">
                    {hasScheduledFlight && <div className="badge badge-info">Scheduled</div>}
                    {isRegistered && <div className="badge badge-success">Registered</div>}
                    {status === 'live' && <div className="badge badge-error">LIVE</div>}
                    <button className="btn btn-primary">View</button>
                </div>
            </div>
        </div>
    );
};

export default ContestCard;
