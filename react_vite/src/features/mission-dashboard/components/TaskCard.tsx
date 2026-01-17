import React from 'react';
import { Link } from 'react-router-dom';
import { Globe } from 'lucide-react'; // Added Globe import
import { Contestant } from '../../competition-map/types';

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
}

const TaskCard: React.FC<TaskCardProps> = ({ name, status, contestId, taskId, onScheduleClick, onCancelClick, futureContestant, tracking_link, onViewScoresClick, contestName, canSchedule }) => {
    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h3 className="card-title">
                    {name}
                    <a href={tracking_link} target="_blank" rel="noopener noreferrer" className="ml-2">
                        <Globe size={20} />
                    </a>
                </h3>
                {contestName && <p>{contestName}</p>}
                {status === 'Open' && canSchedule && <div className="card-actions justify-end"><button onClick={onScheduleClick} className="btn btn-primary">Register Flight Plan</button></div>}
                {status === 'Scheduled' && futureContestant && (
                    <>
                        <p>Take-off: {new Date(futureContestant.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</p>
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
