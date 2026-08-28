import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { Contestant } from '../../competition-map/types';
import PublicityIcon from './PublicityIcon';
import { Route } from '../types';
import TaskStatistics from './TaskStatistics';
import { formatDateInterval } from '../../../utils';

interface TaskCardProps {
    name: string;
    status: 'Open' | 'Scheduled' | 'Live' | 'Finalized';
    contestId: number;
    taskId: number;
    start_time: string;
    finish_time: string;
    onScheduleClick: () => void;
    tracking_link: string;
    onViewScoresClick: () => void;
    contestName?: string;
    canSchedule?: boolean;
    is_public: boolean;
    is_featured: boolean;
    timeZone?: string;
    route: Route;
    flown_contestants_count: number;
    isRegisteredButNotPilot?: boolean;
    allow_self_management?: boolean;
}

const TaskCard: React.FC<TaskCardProps> = ({ name, status, contestId, taskId, start_time, finish_time, onScheduleClick, tracking_link, onViewScoresClick, contestName, canSchedule, is_public, is_featured, timeZone, route, flown_contestants_count, isRegisteredButNotPilot, allow_self_management }) => {
    const getStatusBadge = () => {
        switch (status) {
            case 'Open':
                return <div className="badge badge-outline">Open</div>;
            case 'Scheduled':
                return <div className="badge badge-info">Scheduled</div>;
            case 'Live':
                return <div className="badge badge-error gap-1">🔴 Live</div>;
            case 'Finalized':
                return <div className="badge badge-success">Finalized</div>;
            default:
                return null;
        }
    };

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h3 className="card-title flex flex-wrap items-center gap-2">
                    <span className="flex-1">{name}</span>
                    {getStatusBadge()}
                    <PublicityIcon isPublic={is_public} isFeatured={is_featured} />
                    <a href={tracking_link} target="_blank" rel="noopener noreferrer" className="btn btn-xs btn-outline btn-info gap-1">
                        <MapPin size={14} />
                        Live Map
                    </a>
                </h3>
                
                <TaskStatistics route={route} flown_contestants_count={flown_contestants_count} />
                <p className="text-sm text-gray-500">{formatDateInterval(start_time, finish_time)}</p>

                {contestName && <p>{contestName}</p>}
                {(status === 'Open' || status === 'Scheduled') && canSchedule && allow_self_management && (
                    <div className="card-actions justify-end items-center gap-2">
                        <button onClick={onScheduleClick} className="btn btn-primary">Register Flight Plan</button>
                    </div>
                )}
                {isRegisteredButNotPilot && allow_self_management && (
                    <div role="alert" className="alert alert-warning text-sm mt-2">
                        <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                        <span>You cannot schedule flight because you are not the team pilot.</span>
                    </div>
                )}
                {status === 'Live' && (
                    <div className="card-actions justify-end items-center">
                        {canSchedule && allow_self_management && <button onClick={onScheduleClick} className="btn btn-ghost btn-xs px-0 justify-start">Register another flight plan</button>}
                        <a href={tracking_link} target="_blank" rel="noopener noreferrer" className="btn btn-primary">Watch Tracking</a>
                    </div>
                )}
                {status === 'Finalized' && (
                     <div className="card-actions justify-end items-center">
                        <button onClick={onViewScoresClick} className="btn btn-secondary">View Scores</button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default TaskCard;
