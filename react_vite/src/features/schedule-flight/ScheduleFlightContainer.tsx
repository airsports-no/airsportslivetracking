import React, { useState, useEffect, useMemo } from 'react';
import { Contest, MyParticipatingContest, PaginatedContests } from './types';
import * as api from './api';
import UpcomingFlights from './components/UpcomingFlights';
import ContestItem from './components/ContestItem';
import Select from 'react-select';
import ScheduleFlightForm from './components/ScheduleFlightForm';

// Mock data for development
declare global {
    interface Document {
        configuration: {
            CONTESTS_LIST_URL: string;
            MY_PARTICIPATING_CONTESTS_URL: string;
            contestSignUpUrl: (contestId: number) => string;
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
    const [selectedTask, setSelectedTask] = useState<{ contest: Contest, taskId: number } | null>(null);

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
            setError(err.message);
            setLoading(false);
        });
    }, []);

    const handleCancelFlight = async (contestId: number, navigationTaskId: number) => {
        try {
            await api.cancelFlight(contestId, navigationTaskId);
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

    const handleScheduleClick = (contest: Contest, taskId: number) => {
        setSelectedTask({ contest, taskId });
    };
    
    const onFormClose = () => {
        setSelectedTask(null);
        handleScheduleFlight();
    }

    if (selectedTask) {
        return <ScheduleFlightForm 
            contest={selectedTask.contest} 
            navigationTaskId={selectedTask.taskId} 
            myContests={myContests}
            onClose={onFormClose} 
            />
    }

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-4xl font-bold mb-4">Schedule a Flight</h1>

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
                                onScheduleClick={(taskId) => handleScheduleClick(contest, taskId)}
                                onCancel={handleCancelFlight}
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