import React from 'react';
import { Contest } from '../types';
import { Link } from 'react-router-dom';
import PublicityIcon from './PublicityIcon';

interface ContestCardProps {
    contest: Contest;
    status: 'live' | 'upcoming' | 'past';
    isRegistered?: boolean;
    hasScheduledFlight?: boolean;
    isEditorContest?: boolean;
    hasOpenTasksForScheduling?: boolean; // New prop
    viewLink: string;
    manageLink?: string;
}

const ContestCard: React.FC<ContestCardProps> = ({ contest, status, isRegistered, hasScheduledFlight, isEditorContest, hasOpenTasksForScheduling, viewLink, manageLink }) => {
    return (
        <div className="card bg-base-200 shadow-xl image-full h-[280px] overflow-hidden">
            {contest.header_image && (
                <figure><img src={contest.header_image} alt={contest.name} /></figure>
            )}
            <div className="card-body">
                <h2 className="card-title flex items-center gap-2">
                    <PublicityIcon isPublic={contest.is_public} isFeatured={contest.is_featured} />
                    {contest.name}
                    {contest.country_flag_url && (
                        <img src={contest.country_flag_url} alt={`${contest.country} flag`} className="ml-2 w-6 h-4 inline-block" />
                    )}
                </h2>
                {contest.navigationtask_set && contest.navigationtask_set.length > 0 && (
                    <p className="text-sm text-gray-400">{contest.navigationtask_set.length} tasks</p>
                )}
            </div>
            <div className="absolute bottom-0 left-0 right-0 p-4 flex justify-between items-end">
                <div className="flex flex-wrap gap-2">
                    {status === 'live' && <div className="badge badge-error">LIVE</div>}
                    {hasScheduledFlight && <div className="badge badge-info">Scheduled</div>}
                    {isRegistered && <div className="badge badge-success">Registered</div>}
                    {hasOpenTasksForScheduling && <div className="badge badge-accent">Tasks Open</div>}
                </div>
                <div className="flex gap-2">
                    <Link to={viewLink} className="btn btn-primary">View</Link>
                    {isEditorContest && manageLink && (
                        <a href={manageLink} className="btn btn-secondary">Manage</a>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ContestCard;
