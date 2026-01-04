import React, { useState, useEffect, useMemo } from 'react';
import { Contest, MyParticipatingContest, PaginatedContests, NavigationTask } from './types';
import * as api from './api';
import UpcomingFlights from './components/UpcomingFlights';
import ContestItem from './components/ContestItem';
import Select from 'react-select';
import ScheduleFlightForm from './components/ScheduleFlightForm';
import ContestRegistrationForm from './components/ContestRegistrationForm';
import { Link, useSearchParams } from "react-router-dom";


// Mock data for development
declare global {
    interface Document {
        configuration: {
            CONTESTS_LIST_URL: string;
            MY_PARTICIPATING_CONTESTS_URL: string;
            MY_PARTICIPATED_CONTESTS_URL: string;
            contestSignUpUrl: (contestId: number) => string;
            loginUrl: string;
            editNavigationTaskUrl: (navigationTaskId: number) => string;
        }
    }
}
const CONTESTS_LIST_URL = document.configuration?.CONTESTS_LIST_URL || '/api/v1/contests/?is_public=true&is_featured=true';
const MY_PARTICIPATING_CONTESTS_URL = document.configuration?.MY_PARTICIPATING_CONTESTS_URL || '/api/v1/myparticipatingcontests/';


const ScheduleFlightContainer = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const contestIdParam = searchParams.get('contestId');
    const navigationTaskIdParam = searchParams.get('navigationTaskId');

    const [contests, setContests] = useState<Contest[]>([]);
    const [myContests, setMyContests] = useState<MyParticipatingContest[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [nextCursor, setNextCursor] = useState<string | null>(null);
    const [hasMore, setHasMore] = useState(true);
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
    const [selectedTask, setSelectedTask] = useState<{ contest: Contest, navigationTask: NavigationTask } | null>(null);
    const [selectedContestForRegistration, setSelectedContestForRegistration] = useState<Contest | null>(null);
    const [initialSelectedTask, setInitialSelectedTask] = useState<{ contest: Contest, navigationTask: NavigationTask } | null>(null);

    const loadContests = (loadMore = false) => {
        let url = CONTESTS_LIST_URL;
        if (loadMore && nextCursor) {
            url += `&cursor=${nextCursor}`;
        } else if (loadMore && !nextCursor) {
            setHasMore(false);
            return Promise.resolve();
        }

        return api.fetchContests(url)
            .then(data => {
                const futureContests = data.results.filter(c => new Date(c.finish_time) > new Date());
                if (loadMore) {
                    setContests(prev => [...prev, ...futureContests]);
                } else {
                    setContests(futureContests);
                }
                setNextCursor(data.next);
                if (!data.next) {
                    setHasMore(false);
                } else {
                    setHasMore(true);
                }
            });
    };

    useEffect(() => {
        const loadInitialData = async () => {
            setLoading(true);
            try {
                const myContestsData = await api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL);
                setMyContests(myContestsData);
                await loadContests();
            } catch (err: any) {
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
            } finally {
                setLoading(false);
            }
        };

        loadInitialData();
    }, []);

    useEffect(() => {
        const handleDeepLink = async () => {
            if (contestIdParam && navigationTaskIdParam) {
                setLoading(true);
                try {
                    const contestId = Number(contestIdParam);
                    const navigationTaskId = Number(navigationTaskIdParam);
                    const contest = await api.fetchContest(contestId);
                    const navigationTask = contest.navigationtask_set.find(
                        (nt) => nt.pk === navigationTaskId
                    );
                    if (contest && navigationTask) {
                        setInitialSelectedTask({ contest, navigationTask });
                    } else {
                        setError("Deep link: Contest or Navigation Task not found.");
                    }
                } catch (err) {
                    setError((err as Error).message);
                } finally {
                    setLoading(false);
                }
            } else {
                setInitialSelectedTask(null);
            }
        };

        handleDeepLink();
    }, [contestIdParam, navigationTaskIdParam]);

    const refreshData = () => {
        setLoading(true);
        api.fetchMyParticipatingContests(MY_PARTICIPATING_CONTESTS_URL)
            .then(data => {
                setMyContests(data);
                return loadContests();
            })
            .catch(err => {
                setError(err.message);
            })
            .finally(() => {
                setLoading(false);
            });
    }

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number) => {
        try {
            await api.cancelFlight(contestId, navigationTaskId, futureContestantId);
            refreshData();
        } catch (error) {
            setError((error as Error).message);
        }
    };


    const handleScheduleFlight = async () => {
        refreshData();
    };

    const handleRegisterClick = (contest: Contest) => {
        setSelectedContestForRegistration(contest);
    };

    const handleWithdrawClick = async (contestId: number) => {
        try {
            await api.withdraw(contestId);
            refreshData();
        } catch (error) {
            setError((error as Error).message);
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

    const hasUpcomingFlights = useMemo(() => {
        return myContests.some(mc =>
            mc.contest.navigationtask_set.some(nt => nt.future_contestants && nt.future_contestants.length > 0)
        );
    }, [myContests]);

    const countryOptions = useMemo(() => {
        const uniqueCountries = Array.from(new Set(contests.map(c => c.country))).sort();
        return uniqueCountries.map(country => ({ value: country, label: country }));
    }, [contests]);

    const handleScheduleClick = (contest: Contest, navigationTask: NavigationTask) => {
        setSelectedTask({ contest, navigationTask });
    };

    const onFormClose = () => {
        setSelectedTask(null);
        setSearchParams({});
        refreshData();
    }

    const onRegisterFormClose = () => {
        setSelectedContestForRegistration(null);
        refreshData();
    };


    if (selectedTask || initialSelectedTask) {
        const taskToDisplay = selectedTask || initialSelectedTask;
        if (!taskToDisplay) return null; // Should not happen

        return <ScheduleFlightForm
            contest={taskToDisplay.contest}
            navigationTaskId={taskToDisplay.navigationTask.pk}
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
        <div className="container mx-auto p-2 sm:p-4">
            <div className="flex flex-row justify-between items-start gap-2 mb-2 sm:mb-4">
                <h1 className="text-2xl sm:text-4xl font-bold">
                    Schedule Flights
                </h1>
                <Link to="/past-flights" className="btn btn-primary">Past Flights</Link>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 sm:gap-4">
                <div className={!hasUpcomingFlights ? "hidden md:block" : ""}>
                    <h2 className="text-xl sm:text-2xl font-bold mb-2 sm:mb-4">My Upcoming Flights</h2>
                    <UpcomingFlights myContests={myContests} onCancel={handleCancelFlight} />
                </div>

                <div className="md:col-span-2">
                    <h2 className="text-xl sm:text-2xl font-bold mb-2 sm:mb-4">Available Contests</h2>
                    <div className="flex flex-col sm:flex-row gap-4 mb-4">
                        <input
                            type="text"
                            placeholder="Filter by name"
                            className="input input-bordered w-full sm:w-auto sm:max-w-xs"
                            value={nameFilter}
                            onChange={(e) => setNameFilter(e.target.value)}
                        />
                        <Select
                            isMulti
                            options={countryOptions}
                            value={countryOptions.filter(option => selectedCountries.includes(option.value))}
                            onChange={(selectedOptions) => setSelectedCountries(selectedOptions ? selectedOptions.map(option => option.value) : [])}
                            className="my-react-select-container"
                            classNamePrefix="my-react-select"
                            placeholder="Filter by country"
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
                                onCancel={handleCancelFlight}
                                myContests={myContests}
                            />
                        ))}
                    </div>
                    {loading && <div className="loading loading-lg"></div>}
                    {hasMore && !loading && (
                        <button className="btn btn-primary mt-4" onClick={() => {
                            setLoading(true);
                            loadContests(true).finally(() => setLoading(false));
                        }}>
                            Load More
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};


export default ScheduleFlightContainer;