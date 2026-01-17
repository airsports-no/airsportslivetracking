import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { Contestant } from '../../competition-map/types';
import PublicityIcon from './PublicityIcon';
import { Route } from '../types';
import TaskStatistics from './TaskStatistics';

interface TaskCardProps {
    name: string;
    status: 'Open' | 'Scheduled' | 'Live' | 'Finalized';
    contestId: number;
    taskId: number;
    onScheduleClick: () => void;
    onCancelClick?: () => void;
    futureContestant?: Contestant;
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

const TaskCard: React.FC<TaskCardProps> = ({ name, status, contestId, taskId, onScheduleClick, onCancelClick, futureContestant, tracking_link, onViewScoresClick, contestName, canSchedule, is_public, is_featured, timeZone, route, flown_contestants_count }) => {
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

                {contestName && <p>{contestName}</p>}
                {status === 'Open' && canSchedule && <div className="card-actions justify-end"><button onClick={onScheduleClick} className="btn btn-primary">Register Flight Plan</button></div>}
                {status === 'Scheduled' && futureContestant && (
                    <>
                        <p>Take-off: {new Date(futureContestant.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: timeZone })}</p>
                        <div className="card-actions justify-end">
                            {onCancelClick && (
                                <button onClick={onCancelClick} className="btn btn-error btn-sm">Cancel</button>
                            )}
                        </div>
                    </>
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
