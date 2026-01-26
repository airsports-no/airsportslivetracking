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
}

const TaskCard: React.FC<TaskCardProps> = ({ name, status, contestId, taskId, start_time, finish_time, onScheduleClick, tracking_link, onViewScoresClick, contestName, canSchedule, is_public, is_featured, timeZone, route, flown_contestants_count }) => {
    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h3 className="card-title flex flex-wrap items-center gap-2">
                    <span className="flex-1">{name}</span>
                    <PublicityIcon isPublic={is_public} isFeatured={is_featured} />
                    <a href={tracking_link} target="_blank" rel="noopener noreferrer" className="btn btn-xs btn-outline btn-info gap-1">
                        <MapPin size={14} />
                        Live Map
                    </a>
                </h3>
                
                <TaskStatistics route={route} flown_contestants_count={flown_contestants_count} />
                <p className="text-sm text-gray-500">{formatDateInterval(start_time, finish_time)}</p>

                {contestName && <p>{contestName}</p>}
                {(status === 'Open' || status === 'Scheduled') && canSchedule && (
                    <div className="card-actions justify-end items-center gap-2">
                        {status === 'Scheduled' && <div className="badge badge-info">Scheduled</div>}
                        <button onClick={onScheduleClick} className="btn btn-primary">Register Flight Plan</button>
                    </div>
                )}
                {status === 'Live' && (
                    <div className="card-actions justify-between items-center">
                        <div className="flex flex-col gap-1">
                            <p className="text-error">🔴 LIVE</p>
                            {canSchedule && <button onClick={onScheduleClick} className="btn btn-ghost btn-xs px-0 justify-start">Register another flight plan</button>}
                        </div>
                        <a href={tracking_link} target="_blank" rel="noopener noreferrer" className="btn btn-primary">Watch Tracking</a>
                    </div>
                )}
                {status === 'Finalized' && (
                     <div className="card-actions justify-between items-center">
                        <p>Results Ready</p>
                        <button onClick={onViewScoresClick} className="btn btn-secondary">View Scores</button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default TaskCard;
