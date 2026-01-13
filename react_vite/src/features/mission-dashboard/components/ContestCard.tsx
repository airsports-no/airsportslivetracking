import React from 'react';
import { Contest } from '../types';

interface ContestCardProps {
    contest: Contest;
    status: 'live' | 'upcoming' | 'past';
    isRegistered?: boolean;
}

const ContestCard: React.FC<ContestCardProps> = ({ contest, status, isRegistered }) => {
    return (
        <div className="card bg-base-200 shadow-xl image-full h-[280px] overflow-hidden">
            {contest.header_image && (
                <figure><img src={contest.header_image} alt={contest.name} /></figure>
            )}
            <div className="card-body">
                <h2 className="card-title">{contest.name}</h2>
                <p>{contest.location}</p>
                <div className="card-actions justify-end">
                    {isRegistered && <div className="badge badge-success">Registered</div>}
                    {status === 'live' && <div className="badge badge-error">LIVE</div>}
                    <button className="btn btn-primary">View</button>
                </div>
            </div>
        </div>
    );
};

export default ContestCard;
