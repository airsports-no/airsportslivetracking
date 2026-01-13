import React from 'react';
import { Contest, MyParticipatingContest, NavigationTask, ContestantResult } from '../types';
import TaskScoreDisplay from './TaskScoreDisplay';

interface PastContestItemProps {
    contest: Contest;
    showPastContestants?: boolean;
}

const PastContestItem: React.FC<PastContestItemProps> = ({ contest, showPastContestants }) => {
    const currentUserEmail = document.configuration.currentUserEmail;

    return (
        <div className={`card bg-base-100 shadow-xl`}>
            <div className="card-body p-2 sm:p-4">
                <div className='flex items-start justify-between gap-2 sm:gap-4'>
                    <div className='flex items-start flex-grow'>
                        <img src={contest.logo} alt={`${contest.name} logo`} className="h-12 w-12 sm:h-16 sm:w-16 mr-2 sm:mr-4" />
                        <div>
                            <h2 className="card-title text-lg sm:text-xl">
                                {contest.name}
                                {contest.country_flag_url && (
                                    <img src={contest.country_flag_url} alt={`${contest.country} flag`} className="w-6 h-4 ml-2 inline-block" />
                                )}
                            </h2>
                            <p>{new Date(contest.start_time).toLocaleDateString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric' })} - {new Date(contest.finish_time).toLocaleDateString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric' })}</p>
                            <p>{contest.location}</p>
                            {contest.contest_website && (
                                <p>
                                    <a href={contest.contest_website} target="_blank" rel="noopener noreferrer" className="link link-primary">
                                        Contest Website
                                    </a>
                                </p>
                            )}
                        </div>
                    </div>
                </div>
                
                <div className="divider">Navigation Tasks</div>

                <div className="space-y-2">
                    {contest.navigationtask_set.map(task => {
                        return (
                            <div key={task.pk} className="p-1 sm:p-2 rounded-lg bg-base-200 mb-1 sm:mb-2">
                                <div className="flex justify-between items-center">
                                    <div>
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
                                </div>
                                {task.contestant_set && task.contestant_set.length > 0 && (
                                    <TaskScoreDisplay task={task} currentUserEmail={currentUserEmail} />
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};
export default PastContestItem;
