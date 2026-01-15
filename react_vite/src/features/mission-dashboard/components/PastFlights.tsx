import React, { useState, useEffect, useMemo } from 'react';
import { Contest, NavigationTask } from '../types';
import * as api from '../api';
import { fetchNavigationTask } from '../../competition-map/api';
import PastContestItem from './PastContestItem';
import Select from 'react-select';
import { reverse } from '../../../urls';

const PastFlights = () => {
    const [contests, setContests] = useState<Contest[]>([]);
    const [myContestantIds, setMyContestantIds] = useState<Set<number>>(new Set());
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);

    useEffect(() => {
        setLoading(true);
        api.fetchMyPreviousFlights()
            .then(async (myContestants: any[]) => {
                if (myContestants.length === 0) {
                    setContests([]);
                    setLoading(false);
                    return;
                }

                setMyContestantIds(new Set(myContestants.map(c => c.id)));

                // 1. Get unique contest IDs and fetch contests
                const contestIds = [...new Set(myContestants.map(c => c.contest_id).filter(id => id != null))];
                const fetchedContests = contestIds.length > 0 ? await api.fetchContests({ pks: contestIds }) : [];
                const contestsDataMap = new Map<number, Contest>(fetchedContests.map(c => [c.id, c]));

                // 2. Get unique nav tasks and fetch them
                const uniqueNavTaskKeys = new Set(myContestants
                    .filter(c => c.contest_id != null && c.navigation_task != null)
                    .map(c => `${c.contest_id}-${c.navigation_task}`)
                );
                const navTaskPromises = [...uniqueNavTaskKeys].map(key => {
                    const [contestId, taskId] = key.split('-').map(Number);
                    return fetchNavigationTask(contestId, taskId);
                });
                
                const settledNavTasks = await Promise.allSettled(navTaskPromises);
                const resolvedNavTasks = settledNavTasks
                    .filter(result => result.status === 'fulfilled')
                    .map(result => (result as PromiseFulfilledResult<NavigationTask>).value);
                
                // 3. Grouping logic
                const groupedContests = new Map<number, Contest & { navigationtask_set: (NavigationTask)[] }>();

                resolvedNavTasks.forEach((navTask: any) => {
                    const contest = contestsDataMap.get(navTask.contest);

                    if (!contest) {
                        console.error("Missing contest for navTask", navTask);
                        return;
                    }

                    let groupedContest = groupedContests.get(contest.id);
                    if (!groupedContest) {
                        groupedContest = { ...contest, navigationtask_set: [] };
                        groupedContests.set(contest.id, groupedContest);
                    }
                    groupedContest.navigationtask_set.push(navTask);
                });
                
                const pastContests = Array.from(groupedContests.values())
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

    const filteredAndSortedContests = useMemo(() => {
        return contests
            .filter(contest => {
                const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
                const countryMatch = selectedCountries.length === 0 || selectedCountries.includes(contest.country);
                return nameMatch && countryMatch;
            });
    }, [contests, nameFilter, selectedCountries]);

    const countryOptions = useMemo(() => {
        const uniqueCountries = Array.from(new Set(contests.map(c => c.country))).sort();
        return uniqueCountries.map(country => ({ value: country, label: country }));
    }, [contests]);

    return (
        <div>
            {error && <div className="alert alert-error">{error}</div>}

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
            <div className="space-y-2 sm:space-y-4">
                {filteredAndSortedContests.map(contest => (
                    <PastContestItem
                        key={contest.id}
                        contest={contest}
                        myContestantIds={myContestantIds}
                        showPastContestants={true}
                    />
                ))}
            </div>
            {loading && <div className="loading loading-lg"></div>}
            {!loading && filteredAndSortedContests.length === 0 && (
                <p className="text-center mt-2 sm:mt-4">No past flights found.</p>
            )}
        </div>
    );
};

export default PastFlights;