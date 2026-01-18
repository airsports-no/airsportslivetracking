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
                <h3 className="card-title flex items-center gap-2">
                    {name}
                    <PublicityIcon isPublic={is_public} isFeatured={is_featured} />
                    <div className="tooltip inline-flex" data-tip="View Live Tracking Map">
                        <a href={tracking_link} target="_blank" rel="noopener noreferrer" className="ml-2">
                            <MapPin size={20} />
                        </a>
                    </div>
                </h3>
                
                <TaskStatistics route={route} flown_contestants_count={flown_contestants_count} />
                <p className="text-sm text-gray-500">{formatDateInterval(start_time, finish_time)}</p>

                {contestName && <p>{contestName}</p>}
                {status === 'Open' && canSchedule && <div className="card-actions justify-end"><button onClick={onScheduleClick} className="btn btn-primary">Register Flight Plan</button></div>}
                {status === 'Scheduled' && (
                    <div className="card-actions justify-end">
                        <div className="badge badge-info">Scheduled</div>
                    </div>
                )}
                {status === 'Live' && (
                    <div className="card-actions justify-between items-center">
                        <p className="text-error">🔴 LIVE</p>
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
