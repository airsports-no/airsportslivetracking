import React from 'react';
import { Contest } from '../../schedule-flight/types';

interface ContestCardProps {
    contest: Contest;
    status: 'live' | 'upcoming' | 'past';
}

const ContestCard: React.FC<ContestCardProps> = ({ contest, status }) => {
    return (
        <div className="card bg-base-200 shadow-xl image-full">
            {contest.header_image && (
                <figure><img src={contest.header_image} alt={contest.name} /></figure>
            )}
            <div className="card-body">
                <h2 className="card-title">{contest.name}</h2>
                <p>{contest.location}</p>
                <div className="card-actions justify-end">
                    {status === 'live' && <div className="badge badge-error">LIVE</div>}
                    <button className="btn btn-primary">View</button>
                </div>
            </div>
        </div>
    );
};

export default ContestCard;
