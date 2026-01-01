import React from 'react';
import { Contest, MyParticipatingContest, NavigationTask } from '../types';

interface PastContestItemProps {
    contest: Contest;
    myContests: MyParticipatingContest[];
    showPastContestants?: boolean;
}

const PastContestItem: React.FC<PastContestItemProps> = ({ contest, myContests, showPastContestants }) => {
    // myTeamIds is still relevant if myContests are passed and used for any internal logic
    const myTeamIds = myContests.flatMap(mc => mc.team ? [mc.team.id] : []);
    
    return (
        <div className={`card bg-base-100 shadow-xl`}> {/* No border for registered past contests */}
            <div className="card-body">
                <div className='flex items-start justify-between'>
                    <div className='flex items-start'>
                        <img src={contest.logo} alt={`${contest.name} logo`} className="h-16 w-16 mr-4" />
                        <div>
                            <h2 className="card-title">
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
                    {/* Removed Register/Withdraw buttons */}
                </div>
                
                <div className="divider">Navigation Tasks</div>

                <div className="space-y-2">
                    {contest.navigationtask_set.map(task => {
                        // In PastContestItem, we don't need to filter myFutureContestantsForThisTask
                        // as we only care about past contestants.
                        // However, we still need correspondingMyTask to access task.past_contestants which is in myContests
                        const correspondingMyTask = myContests
                            .find(mc => mc.contest.id === contest.id)
                            ?.contest.navigationtask_set.find(nt => nt.pk === task.pk);

                        return (
                            <div key={task.pk} className="p-2 rounded-lg bg-base-200 mb-2">
                                <div className="flex justify-between items-center">
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
                                            Available: {new Date(task.start_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })} to {new Date(task.finish_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
                                        </p>
                                    </div>
                                    {/* Removed future contestant display and Schedule/Delete buttons */}
                                </div>
                                {showPastContestants && correspondingMyTask && correspondingMyTask.past_contestants && correspondingMyTask.past_contestants.length > 0 && (
                                    <div className="mt-4 border-t border-base-300 pt-2">
                                        <h5 className="font-semibold text-md mb-2">Past Flights:</h5>
                                        {correspondingMyTask.past_contestants.map(pc => (
                                            <div key={pc.id} className="flex justify-between items-center text-sm">
                                                <span>Take-off: {new Date(pc.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</span>
                                                <span className="text-gray-500">Contestant #{pc.contestant_number}</span>
                                            </div>
                                        ))}
                                    </div>
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
