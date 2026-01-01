import React, { useState, useEffect, useMemo } from 'react';
import { Contest, MyParticipatingContest, PaginatedContests, NavigationTask } from './types';
import * as api from './api';
import UpcomingFlights from './components/UpcomingFlights';
import ContestItem from './components/ContestItem';
import Select from 'react-select';
import ScheduleFlightForm from './components/ScheduleFlightForm';
import ContestRegistrationForm from './components/ContestRegistrationForm';
import { Link } from "react-router-dom"; // Import Link


// Mock data for development
declare global {
    interface Document {
        configuration: {
            CONTESTS_LIST_URL: string;
            MY_PARTICIPATING_CONTESTS_URL: string;
            MY_PARTICIPATED_CONTESTS_URL: string;
            contestSignUpUrl: (contestId: number) => string;
            loginUrl: string;
        }
    }
}
const CONTESTS_LIST_URL = document.configuration?.CONTESTS_LIST_URL || '/api/v1/contests/?is_public=true&is_featured=true';
const MY_PARTICIPATING_CONTESTS_URL = document.configuration?.MY_PARTICIPATING_CONTESTS_URL || '/api/v1/myparticipatingcontests/';


const ScheduleFlightContainer = () => {
    const [contests, setContests] = useState<Contest[]>([]);
    const [myContests, setMyContests] = useState<MyParticipatingContest[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [nextContestsUrl, setNextContestsUrl] = useState<string | null>(CONTESTS_LIST_URL);
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
    const [selectedTask, setSelectedTask] = useState<{ contest: Contest, navigationTask: NavigationTask } | null>(null);
    const [selectedContestForRegistration, setSelectedContestForRegistration] = useState<Contest | null>(null);

    const loadContests = () => {
        if (!nextContestsUrl) return;
        setLoading(true);
        api.fetchContests(nextContestsUrl)
            .then(data => {
                const futureContests = data.results.filter(c => new Date(c.finish_time) > new Date());
                setContests(prev => [...prev, ...futureContests]);
                setNextContestsUrl(data.next);
            })
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        setLoading(true);
        Promise.all([
            api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL),
        ])
        .then(([myContestsData]) => {
            setMyContests(myContestsData);
            loadContests(); // initial load
        })
        .catch(err => {
            // Check for 401 Unauthorized specifically for fetchMyParticipatingContests
            if (err.status === 401) {
                console.log("User not authenticated, redirecting to login in 5 seconds.");
                setError("You are not authenticated. Redirecting to login page in 5 seconds..."); // Provide user feedback
                const loginPageUrl = document.configuration?.loginUrl || '/login';
                setTimeout(() => {
                    window.location.href = loginPageUrl;
                }, 5000); // 5000ms = 5 seconds
                setLoading(false); // Stop loading animation
            } else {
                setError(err.message);
                setLoading(false);
            }
        });
    }, []);

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number) => {
        try {
            setLoading(true);
            await api.cancelFlight(contestId, navigationTaskId, futureContestantId);
            // Refresh data
            const [myContestsData, contestsData] = await Promise.all([
                api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL),
                api.fetchContests(CONTESTS_LIST_URL)
            ]);
            setMyContests(myContestsData);
            const futureContests = contestsData.results.filter(c => new Date(c.finish_time) > new Date());
            setContests(futureContests);
            setNextContestsUrl(contestsData.next);
            setLoading(false);
        } catch (error) {
            setError((error as Error).message);
            setLoading(false);
        }
    };


    const handleScheduleFlight = async () => {
        try {
            setLoading(true);
            // Refresh data
            const [myContestsData, contestsData] = await Promise.all([
                api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL),
                api.fetchContests(CONTESTS_LIST_URL)
            ]);
            setMyContests(myContestsData);
            const futureContests = contestsData.results.filter(c => new Date(c.finish_time) > new Date());
            setContests(futureContests);
            setNextContestsUrl(contestsData.next);
            setLoading(false);
        } catch (error) {
            setError((error as Error).message);
            setLoading(false);
        }
    };

    const handleRegisterClick = (contest: Contest) => {
        setSelectedContestForRegistration(contest);
    };

    const handleWithdrawClick = async (contestId: number) => {
        try {
            setLoading(true);
            await api.withdraw(contestId);
            // Refresh data
            const [myContestsData, contestsData] = await Promise.all([
                api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL),
                api.fetchContests(CONTESTS_LIST_URL)
            ]);
            setMyContests(myContestsData);
            const futureContests = contestsData.results.filter(c => new Date(c.finish_time) > new Date());
            setContests(futureContests);
            setNextContestsUrl(contestsData.next);
            setLoading(false);
        } catch (error) {
            setError((error as Error).message);
            setLoading(false);
        }
    };

    const filteredAndSortedContests = useMemo(() => {
        return contests
            .filter(contest => {
                const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
                const countryMatch = selectedCountries.length === 0 || selectedCountries.includes(contest.country);
                return nameMatch && countryMatch;
            })
            .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
    }, [contests, nameFilter, selectedCountries]);

    const countryOptions = useMemo(() => {
        const uniqueCountries = Array.from(new Set(contests.map(c => c.country))).sort();
        return uniqueCountries.map(country => ({ value: country, label: country }));
    }, [contests]);

    const handleScheduleClick = (contest: Contest, navigationTask: NavigationTask) => {
        setSelectedTask({ contest, navigationTask });
    };
    
    const onFormClose = () => {
        setSelectedTask(null);
        handleScheduleFlight();
    }

    const onRegisterFormClose = () => {
        setSelectedContestForRegistration(null);
        setLoading(true);
        Promise.all([
            api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL),
            api.fetchContests(CONTESTS_LIST_URL)
        ])
        .then(([myContestsData, contestsData]) => {
            setMyContests(myContestsData);
            const futureContests = contestsData.results.filter(c => new Date(c.finish_time) > new Date());
            setContests(futureContests);
            setNextContestsUrl(contestsData.next);
        })
        .catch(err => setError(err.message))
        .finally(() => setLoading(false));
    };


    if (selectedTask) {
        return <ScheduleFlightForm 
            contest={selectedTask.contest} 
            navigationTaskId={selectedTask.navigationTask.pk} 
            myContests={myContests}
            onClose={onFormClose} 
            />
    }

    if (selectedContestForRegistration) {
        return <ContestRegistrationForm
            contest={selectedContestForRegistration}
            myContests={myContests}
            onClose={onRegisterFormClose}
        />;
    }

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-4xl font-bold mb-4">
                Schedule a Flight
                <Link to="/past-flights" className="btn btn-sm btn-link ml-4">View Past Flights</Link>
            </h1>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                    <h2 className="text-2xl font-bold mb-4">My Upcoming Flights</h2>
                    <UpcomingFlights myContests={myContests} onCancel={handleCancelFlight} />
                </div>

                <div className="md:col-span-2">
                    <h2 className="text-2xl font-bold mb-4">Available Contests</h2>
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
                            <ContestItem
                                key={contest.id}
                                contest={contest}
                                isRegistered={myContests.some(mc => mc.contest.id === contest.id)}
                                onScheduleClick={(task) => handleScheduleClick(contest, task)}
                                onRegisterClick={handleRegisterClick}
                                onWithdrawClick={handleWithdrawClick}
                                myContests={myContests}
                            />
                        ))}
                    </div>
                    {loading && <div className="loading loading-lg"></div>}
                    {nextContestsUrl && !loading && (
                        <button className="btn btn-primary mt-4" onClick={loadContests}>
                            Load More
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};


export default ScheduleFlightContainer;