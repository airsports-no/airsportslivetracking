import React from 'react';
import { Contest } from '../types';
import { Link } from 'react-router-dom';
import PublicityIcon from './PublicityIcon';
import { formatDateInterval } from '../../../utils';

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
        <div className={`card bg-base-300 shadow-xl ${contest.header_image ? 'image-full' : ''} h-[270px] overflow-hidden`}>
            {contest.header_image && (
                <figure><img src={contest.header_image} alt={contest.name} className="w-full h-full object-cover" /></figure>
            )}
            <div className="card-body p-4 flex flex-col h-full">
                <div className="flex-1 overflow-hidden">
                    <h2 className="card-title text-base flex items-center gap-2 line-clamp-2 leading-tight mb-1">
                        <PublicityIcon isPublic={contest.is_public} isFeatured={contest.is_featured} />
                        <span className="break-words">{contest.name}</span>
                        {contest.country_flag_url && (
                            <img src={contest.country_flag_url} alt={`${contest.country} flag`} className="ml-1 w-5 h-3 inline-block shrink-0" />
                        )}
                    </h2>
                    <p className={`text-xs ${contest.header_image ? 'text-white' : 'text-base-content'} opacity-90`}>
                        {formatDateInterval(contest.start_time, contest.finish_time)}
                    </p>
                    {contest.navigation_task_count > 0 && (
                        <p className={`text-xs ${contest.header_image ? 'text-white' : 'text-base-content'} opacity-90 font-semibold mt-1`}>
                            {contest.navigation_task_count} tasks
                        </p>
                    )}
                </div>
                
                <div className="mt-auto pt-2 flex items-end justify-between gap-2">
                    <div className="flex flex-col gap-1 mb-1">
                        {status === 'live' && <div className="badge badge-error badge-xs">LIVE</div>}
                        {hasScheduledFlight && <div className="badge badge-info badge-xs">Scheduled</div>}
                        {isRegistered && <div className="badge badge-success badge-xs">Registered</div>}
                        {hasOpenTasksForScheduling && <div className="badge badge-accent badge-xs">Tasks Open</div>}
                    </div>
                    <div className="flex gap-2 shrink-0">
                        <Link to={viewLink} className="btn btn-primary btn-sm">View</Link>
                        {isEditorContest && manageLink && (
                            <a href={manageLink} className="btn btn-secondary btn-sm">Manage</a>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ContestCard;
