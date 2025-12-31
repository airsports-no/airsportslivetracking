import React from 'react';
import { Contest, MyParticipatingContest } from '../types';

interface ContestItemProps {
    contest: Contest;
    isRegistered: boolean;
    onScheduleClick: (taskId: number) => void;
    onCancel: (contestId: number, navigationTaskId: number) => void;
    myContests: MyParticipatingContest[];
}

const ContestItem: React.FC<ContestItemProps> = ({ contest, isRegistered, onScheduleClick, onCancel, myContests }) => {
    const myTeamIds = myContests.flatMap(mc => mc.team ? [mc.team.id] : []);
    
    return (
        <div className={`card bg-base-100 shadow-xl ${isRegistered ? 'border-2 border-primary' : ''}`}>
            <div className="card-body">
                <div className='flex items-start'>
                    <img src={contest.logo} alt={`${contest.name} logo`} className="h-16 w-16 mr-4" />
                    <div>
                        <h2 className="card-title">
                            {contest.name}
                            {isRegistered && <div className="badge badge-secondary">Registered</div>}
                        </h2>
                        <p>{new Date(contest.start_time).toLocaleDateString()} - {new Date(contest.finish_time).toLocaleDateString()}</p>
                        <p>{contest.location}</p>
                    </div>
                </div>
                
                <div className="divider">Navigation Tasks</div>

                <div className="space-y-2">
                    {contest.navigationtask_set.map(task => {
                        const correspondingMyTask = myContests
                            .find(mc => mc.contest.id === contest.id)
                            ?.contest.navigationtask_set.find(nt => nt.pk === task.pk);

                        const myFutureContestantsForThisTask = correspondingMyTask ?
                            correspondingMyTask.future_contestants.filter(fc => myTeamIds.includes(fc.team)) :
                            [];

                        return (
                            <div key={task.pk} className="flex justify-between items-center p-2 rounded-lg bg-base-200">
                                <div>
                                    <h4 className="font-bold">
                                        {task.name}
                                        <a href={task.tracking_link} target="_blank" rel="noopener noreferrer" className="ml-2">
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                            </svg>
                                        </a>
                                    </h4>
                                    <p className='text-sm'>
                                        Available: {new Date(task.start_time).toLocaleString()} to {new Date(task.finish_time).toLocaleString()}
                                    </p>
                                </div>
                                {myFutureContestantsForThisTask.length > 0 ? (
                                    <div className="text-right">
                                        {myFutureContestantsForThisTask.map(fc => (
                                            <div key={fc.id} className="flex items-center justify-end space-x-2">
                                                <p className="text-sm font-semibold">
                                                    Scheduled: {new Date(fc.takeoff_time).toLocaleString()}
                                                </p>
                                                <button
                                                    className="btn btn-error btn-sm"
                                                    onClick={() => onCancel(contest.id, task.pk)}
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <button
                                        className="btn btn-primary btn-sm"
                                        onClick={() => onScheduleClick(task.pk)}
                                    >
                                        Schedule
                                    </button>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};
export default ContestItem;