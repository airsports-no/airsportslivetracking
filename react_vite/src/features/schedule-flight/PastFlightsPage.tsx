import React, { useState, useEffect, useMemo } from 'react';
import { Contest, NavigationTask } from './types';
import * as api from './api';
import PastContestItem from './components/PastContestItem';
import Select from 'react-select';
import { reverse } from '../../urls';


const MY_PARTICIPATED_CONTESTS_URL_REVERSE_NAME = 'userprofile-my-participated-contests';
const ACCOUNT_LOGIN_URL_REVERSE_NAME = 'login';

const PastFlightsPage = () => {
    const [contests, setContests] = useState<Contest[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);

    useEffect(() => {
        setLoading(true);
        api.fetchMyParticipatedContests(reverse(MY_PARTICIPATED_CONTESTS_URL_REVERSE_NAME))
            .then(myTasksData => {
                const contestsMap = new Map<number, Contest>();
                myTasksData.forEach(task => {
                    if (task.contestant_set && task.contestant_set.length > 0) {
                        const contest = task.contest;
                        if (!contestsMap.has(contest.id)) {
                            contestsMap.set(contest.id, { ...contest, navigationtask_set: [] });
                        }
                        contestsMap.get(contest.id)!.navigationtask_set.push(task);
                    }
                });

                const pastContests = Array.from(contestsMap.values())
                    .sort((a, b) => new Date(b.finish_time).getTime() - new Date(a.finish_time).getTime());

                setContests(pastContests);
            })
            .catch(err => {
                if (err.status === 401) {
                    console.log("User not authenticated, redirecting to login in 5 seconds.");
                    setError("You are not authenticated. Redirecting to login page in 5 seconds...");
                    const loginPageUrl = reverse(ACCOUNT_LOGIN_URL_REVERSE_NAME);
                    setTimeout(() => {
                        window.location.href = loginPageUrl;
                    }, 5000);
                } else {
                    setError(err.message);
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
        <div className="container mx-auto p-2 sm:p-4">
            <h1 className="text-2xl sm:text-4xl font-bold mb-2 sm:mb-4">Past Flights</h1>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="grid grid-cols-1 md:col-span-3 gap-2 sm:gap-4">
                <div className="md:col-span-3">
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
                                showPastContestants={true}
                            />
                        ))}
                    </div>
                    {loading && <div className="loading loading-lg"></div>}
                    {!loading && filteredAndSortedContests.length === 0 && (
                        <p className="text-center mt-2 sm:mt-4">No past flights found.</p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default PastFlightsPage;
