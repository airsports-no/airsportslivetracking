import React, { useState, useEffect, useMemo } from 'react';
import { Contest, NavigationTask } from '../types';
import * as api from '../api';
import { fetchNavigationTask } from '../../competition-map/api';
import Select from 'react-select';
import { reverse } from '../../../urls';
import { Contestant } from '../../competition-map/types';
import { Loading } from '../../route-editor/components/basicComponents';
import ContestCard from '../components/ContestCard';
import TaskScoreDisplay from '../components/TaskScoreDisplay';

const PastFlights = () => {
    const [myPreviousFlights, setMyPreviousFlights] = useState<Contestant[]>([]);
    const [contests, setContests] = useState<Contest[]>([]);
    const [myContestantIds, setMyContestantIds] = useState<Set<number>>(new Set());
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
    
    const [selectedContest, setSelectedContest] = useState<Contest | null>(null);
    const [modalContent, setModalContent] = useState<NavigationTask[] | null>(null);
    const [loadingModal, setLoadingModal] = useState<boolean>(false);

    useEffect(() => {
        setLoading(true);
        api.fetchMyPreviousFlights()
            .then(async (myContestants: Contestant[]) => {
                if (myContestants.length === 0) {
                    setContests([]);
                    setLoading(false);
                    return;
                }
                setMyPreviousFlights(myContestants);
                setMyContestantIds(new Set(myContestants.map(c => c.id)));

                const contestIds = [...new Set(myContestants.map(c => c.contest_id).filter(id => id != null))];
                const fetchedContests = contestIds.length > 0 ? await api.fetchContests({ pks: contestIds }) : [];
                
                const pastContests = fetchedContests
                    .sort((a, b) => new Date(b.finish_time).getTime() - new Date(a.finish_time).getTime());

                setContests(pastContests);
            })
            .catch(err => {
                if (err.status === 401) {
                    console.log("User not authenticated, redirecting to login in 5 seconds.");
                    setError("You are not authenticated. Redirecting to login page in 5 seconds...");
                    const loginPageUrl = reverse('login');
                    setTimeout(() => {
                        window.location.href = loginPageUrl;
                    }, 5000);
                } else {
                    setError(`Error fetching past flights: ${err.message}`);
                }
            })
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        if (!selectedContest) {
            setModalContent(null);
            return;
        }

        const fetchTasksForContest = async () => {
            setLoadingModal(true);
            
            const relevantFlights = myPreviousFlights.filter(f => f.contest_id === selectedContest.id);
            const uniqueNavTaskIds = [...new Set(relevantFlights.map(f => f.navigation_task))];

            const navTaskPromises = uniqueNavTaskIds.map(taskId => 
                fetchNavigationTask(selectedContest.id, taskId)
            );
            
            const settledNavTasks = await Promise.allSettled(navTaskPromises);
            const resolvedNavTasks = settledNavTasks
                .filter(result => result.status === 'fulfilled')
                .map(result => (result as PromiseFulfilledResult<NavigationTask>).value);
            
            setModalContent(resolvedNavTasks);
            setLoadingModal(false);
        };

        fetchTasksForContest();

    }, [selectedContest, myPreviousFlights]);

    const filteredAndSortedContests = useMemo(() => {
        return contests
            .filter(contest => {
                const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
                const countryMatch = selectedCountries.length === 0 || (contest.country && selectedCountries.includes(contest.country));
                return nameMatch && countryMatch;
            });
    }, [contests, nameFilter, selectedCountries]);

    const countryOptions = useMemo(() => {
        if (!contests) return [];
        const uniqueCountries = Array.from(new Set(contests.map(c => c.country).filter(Boolean))).sort();
        return uniqueCountries.map(country => ({ value: country!, label: country! }));
    }, [contests]);

    return (
        <div>
            {error && <div className="alert alert-error">{error}</div>}

            {selectedContest && (
                <div className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex justify-center items-center">
                    <div className="card bg-base-100 shadow-xl max-w-4xl w-full">
                        <div className="card-body">
                            <h2 className="card-title">Results for {selectedContest.name}</h2>
                            {loadingModal ? (
                                <Loading />
                            ) : (
                                <div className="max-h-96 overflow-y-auto space-y-4 p-4">
                                    {modalContent && modalContent.map(task => (
                                        <div key={task.pk} className="p-2 rounded-lg bg-base-200">
                                            <h4 className="font-bold text-lg">{task.name}</h4>
                                            <TaskScoreDisplay task={task} myContestantIds={myContestantIds} />
                                        </div>
                                    ))}
                                    {(!modalContent || modalContent.length === 0) && <p>No tasks found for this contest.</p>}
                                </div>
                            )}
                            <div className="card-actions justify-end">
                                <button onClick={() => setSelectedContest(null)} className="btn">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="flex space-x-2 sm:space-x-4 mb-2 sm:mb-4">
                <input
                    type="text"
                    placeholder="Filter by name"
                    className="input input-bordered w-full max-w-xs"
                    value={nameFilter}
                    onChange={(e) => setNameFilter(e.target.value)}
                />
                <Select
                    isMulti
                    options={countryOptions}
                    value={countryOptions.filter(option => selectedCountries.includes(option.value))}
                    onChange={(selectedOptions) => setSelectedCountries(selectedOptions ? selectedOptions.map(option => option.value) : [])}
                    className="w-full max-w-xs dark:bg-black"
                    placeholder="Filter by country"
                    classNamePrefix="my-react-select"
                />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAndSortedContests.map(contest => (
                    <div key={contest.id} onClick={() => setSelectedContest(contest)} className="cursor-pointer">
                        <ContestCard
                            contest={contest}
                            status={'past'}
                        />
                    </div>
                ))}
            </div>
            {loading && <Loading />}
            {!loading && filteredAndSortedContests.length === 0 && (
                <p className="text-center mt-2 sm:mt-4">No past flights found.</p>
            )}
        </div>
    );
};

export default PastFlights;
