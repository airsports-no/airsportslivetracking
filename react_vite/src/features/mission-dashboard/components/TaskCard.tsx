import React from 'react';
import { Link } from 'react-router-dom';

interface TaskCardProps {
    name: string;
    status: 'Open' | 'Scheduled' | 'Live' | 'Finalized';
    takeOffTime?: string;
    contestId: number;
    taskId: number;
    onScheduleClick: () => void;
    onCancelClick?: () => void;
    futureContestantId?: number;
    tracking_link: string;
}

const TaskCard: React.FC<TaskCardProps> = ({ name, status, takeOffTime, contestId, taskId, onScheduleClick, onCancelClick, futureContestantId, tracking_link }) => {
    return (
        <div className="card bg-base-200 shadow-xl">
            <div className="card-body">
                <h2 className="card-title">
                    <Link to={tracking_link}>{name}</Link>
                </h2>
                <div className="flex justify-between items-center mt-4">
                    <div>
                        {status === 'Open' && <button onClick={onScheduleClick} className="btn btn-primary">Register Flight Plan</button>}
                        {status === 'Scheduled' && (
                            <div>
                                <p>Take-off: {takeOffTime}</p>
                                {futureContestantId && onCancelClick && (
                                     <button onClick={onCancelClick} className="btn btn-error mt-2">Cancel Flight</button>
                                )}
                            </div>
                        )}
                        {status === 'Live' && (
                            <div>
                                <p className="text-error">🔴 LIVE</p>
                                <button className="btn btn-primary mt-2">Watch Tracking</button>
                            </div>
                        )}
                        {status === 'Finalized' && (
                             <div>
                                <p>Results Ready</p>
                                <button className="btn btn-secondary mt-2">View Scorecard</button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TaskCard;
