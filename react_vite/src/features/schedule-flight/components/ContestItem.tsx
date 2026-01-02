import React, { useState } from 'react';
import { Contest, MyParticipatingContest, NavigationTask } from '../types';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface ContestItemProps {
    contest: Contest;
    isRegistered: boolean;
    onScheduleClick: (task: NavigationTask) => void;
    onCancel: (contestId: number, navigationTaskId: number, futureContestantId: number) => void;
    myContests: MyParticipatingContest[];
    onRegisterClick: (contest: Contest) => void;
    onWithdrawClick: (contestId: number) => void;
}

const ContestItem: React.FC<ContestItemProps> = ({ contest, isRegistered, onScheduleClick, onCancel, myContests, onRegisterClick, onWithdrawClick }) => {
    const [areNavigationTasksVisible, setAreNavigationTasksVisible] = useState(false);
    const myTeamIds = myContests.flatMap(mc => mc.team ? [mc.team.id] : []);

    return (
        <div className={`card bg-base-100 shadow-xl ${isRegistered ? 'border-2 border-primary' : ''}`}>
            <div className="card-body p-2 sm:p-4">
                <div className='flex flex-col gap-4'>
                    <div className='flex items-center w-full'>
                        <img src={contest.logo} alt={`${contest.name} logo`} className="h-12 w-12 sm:h-16 sm:w-16 mr-2 sm:mr-4" />
                        <div className='flex-grow'>
                            <h2 className="card-title text-lg sm:text-xl">
                                {contest.name}
                                {contest.country_flag_url && (
                                    <img src={contest.country_flag_url} alt={`${contest.country} flag`} className="w-6 h-4 ml-2 inline-block" />
                                )}
                            </h2>
                        </div>
                    </div>

                    <div className="flex justify-between items-center">
                        <div>
                            <p>{new Date(contest.start_time).toLocaleDateString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric' })} - {new Date(contest.finish_time).toLocaleDateString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric' })}</p>
                            {contest.contest_website && (
                                <p>
                                    <a href={contest.contest_website} target="_blank" rel="noopener noreferrer" className="link link-primary">
                                        Contest Website
                                    </a>
                                </p>
                            )}
                        </div>

                        <div className="flex flex-col items-stretch gap-2">
                            {isRegistered ? (
                                <button className="btn btn-warning" onClick={() => onWithdrawClick(contest.id)}>Withdraw</button>
                            ) : (
                                <button className="btn btn-success" onClick={() => onRegisterClick(contest)}>Register</button>
                            )}
                        </div>
                    </div>
                </div>

                {contest.navigationtask_set.length > 0 && (
                    <>
                        <div className="divider">Navigation Tasks</div>
                        <div
                            className="flex cursor-pointer items-center"
                            onClick={() => setAreNavigationTasksVisible(!areNavigationTasksVisible)}
                        >
                            {areNavigationTasksVisible ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
                            <p className="pl-2">
                                {areNavigationTasksVisible ? 'Hide' : 'Show'} {contest.navigationtask_set.length} navigation tasks
                            </p>
                        </div>
                    </>
                )}

                {areNavigationTasksVisible && (
                    <div className="space-y-2 mt-2">
                        {contest.navigationtask_set.map(task => {
                            const correspondingMyTask = myContests
                                .find(mc => mc.contest.id === contest.id)
                                ?.contest.navigationtask_set.find(nt => nt.pk === task.pk);

                            const myFutureContestantsForThisTask = correspondingMyTask ?
                                correspondingMyTask.future_contestants.filter(fc => myTeamIds.includes(fc.team)) :
                                [];

                            return (
                                <div key={task.pk} className="p-1 sm:p-2 rounded-lg bg-base-200 mb-1 sm:mb-2">
                                    <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-2">
                                        <div className='flex-grow'>
                                            <h4 className="font-bold text-base sm:text-lg">
                                                {task.name}
                                                <a href={task.tracking_link} target="_blank" rel="noopener noreferrer" className="ml-2">
                                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                    </svg>
                                                </a>
                                            </h4>
                                            <p className='text-sm'>
                                                Available: {new Date(task.start_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })} to {new Date(task.finish_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
                                            </p>
                                        </div>
                                        {myFutureContestantsForThisTask.length > 0 ? (
                                            <div className="flex flex-col items-stretch sm:items-end gap-1">
                                                {myFutureContestantsForThisTask.map(fc => (
                                                    <div key={fc.id} className="flex items-center justify-end space-x-1 sm:space-x-2">
                                                        <p className="text-sm font-semibold">
                                                            Scheduled: {new Date(fc.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
                                                        </p>
                                                        <button
                                                            className="btn btn-error btn-sm"
                                                            onClick={() => onCancel(contest.id, task.pk, fc.id)} // Pass fc.id
                                                        >
                                                            Delete
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            task.allow_self_management && (
                                                <button
                                                    className="btn btn-primary btn-sm"
                                                    onClick={() => onScheduleClick(task)}
                                                >
                                                    Schedule
                                                </button>
                                            )
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
export default ContestItem;