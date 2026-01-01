import React, { useState, useEffect, useMemo } from 'react';
import { Contest, MyParticipatingContest } from './types';
import * as api from './api';
import PastContestItem from './components/PastContestItem'; // Changed import
import Select from 'react-select';

const MY_PARTICIPATED_CONTESTS_URL = document.configuration.MY_PARTICIPATED_CONTESTS_URL;

const PastFlightsPage = () => {
    const [contests, setContests] = useState<Contest[]>([]);
    const [myContests, setMyContests] = useState<MyParticipatingContest[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);

    useEffect(() => {
        setLoading(true);
        api.fetchMyParticipatedContests(MY_PARTICIPATED_CONTESTS_URL)
        .then(myContestsData => {
            setMyContests(myContestsData);
            
            // Filter myContestsData to get only contests that have past flights
            const pastContestsWithPastFlights = myContestsData
                .filter(mc => 
                    mc.contest.navigationtask_set.some(nt => nt.past_contestants && nt.past_contestants.length > 0)
                )
                .map(mc => {
                    const filteredNavigationTasks = mc.contest.navigationtask_set.filter(
                        nt => nt.past_contestants && nt.past_contestants.length > 0
                    );
                    return {
                        ...mc.contest,
                        registered: true,
                        navigationtask_set: filteredNavigationTasks
                    };
                })
                .sort((a, b) => new Date(b.finish_time).getTime() - new Date(a.finish_time).getTime()); // Sort by finish time, newest first

            setContests(pastContestsWithPastFlights);
        })
        .catch(err => {
            if (err.status === 401) {
                console.log("User not authenticated, redirecting to login in 5 seconds.");
                setError("You are not authenticated. Redirecting to login page in 5 seconds...");
                const loginPageUrl = document.configuration?.loginUrl || '/login';
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
            })
            .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()); // Keep original sorting or adapt as needed
    }, [contests, nameFilter, selectedCountries]);

    const countryOptions = useMemo(() => {
        const uniqueCountries = Array.from(new Set(contests.map(c => c.country))).sort();
        return uniqueCountries.map(country => ({ value: country, label: country }));
    }, [contests]);

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-4xl font-bold mb-4">Past Flights</h1>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-3"> {/* Use full width for past flights */}
                    <div className="flex space-x-4 mb-4">
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
                            className="w-full max-w-xs"
                            placeholder="Filter by country"
                            classNamePrefix="react-select"
                        />
                    </div>
                    <div className="space-y-4">
                        {filteredAndSortedContests.map(contest => (
                            <PastContestItem // Changed component here
                                key={contest.id}
                                contest={contest}
                                myContests={myContests}
                                showPastContestants={true}
                            />
                        ))}
                    </div>
                    {loading && <div className="loading loading-lg"></div>}
                    {!loading && filteredAndSortedContests.length === 0 && (
                        <p className="text-center mt-4">No past flights found.</p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default PastFlightsPage;
