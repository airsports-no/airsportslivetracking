import React, { useState, useEffect, useMemo } from 'react';
import Select from 'react-select';
import { LatLngBounds } from 'leaflet';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { fetchContests, fetchOngoingNavigation, fetchMyFutureFlights, cancelFlight, fetchMyContestTeams } from './api';
import { Contest, OngoingNavigation, MyContestTeam } from './types';
import { Contestant } from '../competition-map/types';
import ContestCard from './components/ContestCard';
import UpcomingFlights from './components/UpcomingFlights';
import PastFlights from './components/PastFlights';
import ContestMap from './components/ContestMap';
import { Loading } from '../route-editor/components/basicComponents';
import { Link, useLocation } from 'react-router-dom';
import { reverse } from '../../urls';

// Define NavigationTask interface based on likely API response structure
// This is a minimal definition for the current task's needs.
interface NavigationTask {
    pk: number;
    name: string;
    status: 'Open' | 'Scheduled' | 'Live' | 'Finalized';
    start_time: string; // ISO string
    finish_time: string; // ISO string
    allow_self_management: boolean;
    // Add other fields from API if available and relevant for other tasks
}

const MissionDashboard = () => {
    const [contests, setContests] = useState<Contest[]>([]);
    const [ongoingNavigations, setOngoingNavigations] = useState<OngoingNavigation[]>([]);
    const [myFutureFlights, setMyFutureFlights] = useState<Contestant[]>([]);
    const [myContestTeams, setMyContestTeams] = useState<MyContestTeam[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState('allContests');
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
    const [mapBounds, setMapBounds] = useState<LatLngBounds | null>(null);
    const [hasUserInteractedWithMap, setHasUserInteractedWithMap] = useState(false);
    const [oldestContestDate, setOldestContestDate] = useState<Date | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [myEditorContests, setMyEditorContests] = useState<Contest[]>([]); // New state
    const [showOnlyWithOpenTasks, setShowOnlyWithOpenTasks] = useState(false); // New state for filtering
    const [dateRange, setDateRange] = useState<[number, number] | null>(null);
    const [sliderRange, setSliderRange] = useState<[number, number] | null>(null);
    const location = useLocation();

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const tab = params.get('tab');
        if (tab && ['allContests', 'upcoming', 'past', 'editorContests'].includes(tab)) {
            let shouldSetActiveTab = true;
            if (!document.configuration.isAuthenticated) {
                if (['upcoming', 'past', 'editorContests'].includes(tab)) {
                    shouldSetActiveTab = false;
                }
            } else { // Authenticated
                if (tab === 'editorContests' && !document.configuration.isOrganizer) {
                    shouldSetActiveTab = false;
                }
            }

            if (shouldSetActiveTab) {
                setActiveTab(tab);
            } else {
                setActiveTab('allContests');
            }
        }
    }, [location.search]);

    useEffect(() => {
        const loadInitialData = async () => {
            setLoading(true);
            const today = new Date();
            const oneYearAgo = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
            const sliderMinDate = new Date(2020, 0, 1);

            setOldestContestDate(oneYearAgo);
            setDateRange([oneYearAgo.getTime(), today.getTime()]);
            setSliderRange([sliderMinDate.getTime(), today.getTime()]);

            const fetchPromises = [];
            const allContestsFetchPromise = fetchContests(
                { startTimeGte: oneYearAgo.toISOString().split('T')[0] },
                (pageResults) => {
                    setContests(prev => [...prev, ...pageResults]);
                }
            ).catch(err => {
                setError((err as Error).message);
                console.error("Failed to fetch all contests:", err);
            });
            fetchPromises.push(allContestsFetchPromise);

            const ongoingNavPromise = fetchOngoingNavigation()
                .then(ongoingData => setOngoingNavigations(ongoingData))
                .catch(err => console.error("Failed to fetch ongoing navigations:", err));
            fetchPromises.push(ongoingNavPromise);

            if (document.configuration.isAuthenticated) {
                const myFutureFlightsPromise = fetchMyFutureFlights()
                    .then(myFutureFlightsData => setMyFutureFlights(myFutureFlightsData))
                    .catch(err => console.error("Failed to fetch my future flights:", err));
                fetchPromises.push(myFutureFlightsPromise);

                const myContestTeamsPromise = fetchMyContestTeams()
                    .then(myContestTeamsData => setMyContestTeams(myContestTeamsData))
                    .catch(err => console.error("Failed to fetch my contest teams:", err));
                fetchPromises.push(myContestTeamsPromise);

                const myEditorContestsPromise = fetchContests({ isEditor: true })
                    .then(myEditorContestsData => setMyEditorContests(myEditorContestsData))
                    .catch(err => console.error("Failed to fetch my editor contests:", err));
                fetchPromises.push(myEditorContestsPromise);
            }

            await Promise.allSettled(fetchPromises);
            setLoading(false);
        };
        loadInitialData();
    }, []);

    const handleSliderChange = (newRange: [number, number]) => {
        setDateRange(newRange);
    };

    const handleSliderAfterChange = async (newRange: [number, number]) => {
        const newStartDate = new Date(newRange[0]);
        if (oldestContestDate && newStartDate < oldestContestDate) {
            setLoadingMore(true);
            try {
                const moreContests = await fetchContests({
                    startTimeGte: newStartDate.toISOString().split('T')[0],
                    finishTimeLte: oldestContestDate.toISOString().split('T')[0]
                });

                const existingContestIds = new Set(contests.map(c => c.id));
                const newUniqueContests = moreContests.filter(c => !existingContestIds.has(c.id));

                setContests(prev => [...prev, ...newUniqueContests]);
                setOldestContestDate(newStartDate);
            } catch (err) {
                setError((err as Error).message);
                console.error(err);
            } finally {
                setLoadingMore(false);
            }
        }
    };
			
    useEffect(() => {
        const interval = setInterval(() => {
            fetchOngoingNavigation()
                .then(ongoingData => setOngoingNavigations(ongoingData))
                .catch(err => {
                    console.error("Failed to refresh ongoing navigations:", err);
                });
        }, 2 * 60 * 1000); // Every 2 minutes

        return () => clearInterval(interval); // Cleanup on unmount
    }, []);

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number) => {
        try {
            await cancelFlight(contestId, navigationTaskId, futureContestantId);
            // Re-fetch future flights after cancellation
            const myFutureFlightsData = await fetchMyFutureFlights();
            setMyFutureFlights(myFutureFlightsData);
        } catch (error) {
            setError((error as Error).message);
            console.error(error);
        }
    };

    const liveContestsPks = useMemo(() => {
        return ongoingNavigations.map(nav => nav.contest.id);
    }, [ongoingNavigations]);

    const getContestStatus = (contest: Contest): 'live' | 'upcoming' | 'past' => {
        const now = new Date();
        const finishTime = new Date(contest.finish_time);

        if (liveContestsPks.includes(contest.id)) {
            return 'live';
        }
        if (now > finishTime) {
            return 'past';
        }
        return 'upcoming';
    };

    const registeredContestIds = useMemo(() => {
        const futureFlightContestIds = myFutureFlights.map(flight => flight.contest_id);
        const contestTeamIds = myContestTeams.map(team => team.contest);
        return new Set([...futureFlightContestIds, ...contestTeamIds]);
    }, [myFutureFlights, myContestTeams]);

    const scheduledFlightContestIds = useMemo(() => {
        if (!myFutureFlights) return new Set();

        return new Set(myFutureFlights.map(flight => flight.contest_id));
    }, [myFutureFlights]);

    const countryOptions = useMemo(() => {
        if (!contests) return [];
        const uniqueCountries = Array.from(new Set(contests.map(c => c.country).filter(Boolean))).sort();
        return uniqueCountries.map(country => ({ value: country!, label: country! }));
    }, [contests]);

    const textFilteredContests = useMemo(() => {
        if (!contests) return [];
        const now = new Date();

        return contests
            .filter(contest => {
                const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
                const countryMatch = selectedCountries.length === 0 || (contest.country && selectedCountries.includes(contest.country));

                const contestDate = new Date(contest.start_time).getTime();
                const dateMatch = !dateRange || (contestDate >= dateRange[0] && contestDate <= dateRange[1]);
                
                // Determine if contest has any navigation tasks open for scheduling
                const hasOpenTasks = contest.navigationtask_set?.some((task: NavigationTask) => 
                    task.allow_self_management === true &&
                    new Date(task.start_time) <= now &&
                    new Date(task.finish_time) >= now
                );
                // Temporarily attach this property to the contest object for filtering and passing to ContestCard
                (contest as any).hasOpenTasksForScheduling = hasOpenTasks; 

                const openTasksFilterMatch = !showOnlyWithOpenTasks || hasOpenTasks;

                return nameMatch && countryMatch && dateMatch && openTasksFilterMatch;
            });
    }, [contests, nameFilter, selectedCountries, showOnlyWithOpenTasks, dateRange]);

    const listFilteredContests = useMemo(() => {
        if (!textFilteredContests) return [];
        if (!hasUserInteractedWithMap) {
            return textFilteredContests;
        }
        return textFilteredContests.filter(contest => {
            const boundsMatch = !mapBounds || (contest.latitude != null && contest.longitude != null && mapBounds.contains([contest.latitude, contest.longitude]));
            return boundsMatch;
        })
    }, [textFilteredContests, mapBounds, hasUserInteractedWithMap]);

    const filteredMyEditorContests = useMemo(() => { // NEW useMemo for My Contests filtering
        if (!myEditorContests) return [];
        return myEditorContests.filter(contest => {
            const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
            return nameMatch;
        });
    }, [myEditorContests, nameFilter]);

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-4xl font-bold mb-4">Mission Dashboard</h1>

            {error && <div className="alert alert-error">{error}</div>}
            
            <div className="mb-8 hidden lg:block z-30">
                <h2 className="text-2xl font-bold mb-4">Contest Map</h2>
                <ContestMap 
                    contests={textFilteredContests} 
                    onBoundsChanged={setMapBounds} 
                    minZoom={2}
                    onInteraction={() => setHasUserInteractedWithMap(true)} 
                />
            </div>

            {/* Live Now Section */}
            {ongoingNavigations.length > 0 && (
                <div className="mb-8">
                    <h2 className="text-2xl font-bold mb-4 text-error">🔴 Live Now</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {ongoingNavigations.map(live => (
                            <div key={live.pk} className="card bg-base-200 shadow-xl">
                                <div className="card-body">
                                    <h3 className="card-title">{live.contest.name}</h3>
                                    <p>{live.name}</p>
                                    <p>{live.active_contestants.length} active contestants</p>
                                    <div className="card-actions justify-end">
                                        <a href={live.tracking_link} className="btn btn-primary">Watch Tracking</a>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {document.configuration.isAuthenticated && (
                <div className="tabs tabs-boxed mb-4">
                    <a className={`tab ${activeTab === 'allContests' ? 'tab-active' : ''}`} onClick={() => setActiveTab('allContests')}>All Contests</a> 
                    <>
                        <a className={`tab ${activeTab === 'upcoming' ? 'tab-active' : ''}`} onClick={() => setActiveTab('upcoming')}>My Upcoming Flights</a>
                        <a className={`tab ${activeTab === 'past' ? 'tab-active' : ''}`} onClick={() => setActiveTab('past')}>My Past Flights</a>
                        {document.configuration.isOrganizer && (
                            <a className={`tab ${activeTab === 'editorContests' ? 'tab-active' : ''}`} onClick={() => setActiveTab('editorContests')}>My Contests</a>
                        )}
                    </>
                </div>
            )}

            {loading && <Loading />}

            {activeTab === 'allContests' && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">
                        All Contests
                        <span className="ml-2 text-gray-500 text-lg">
                            ({listFilteredContests.length})
                        </span>
                    </h2>
                    <div className="flex flex-wrap items-center gap-2 sm:gap-4 mb-2 sm:mb-4">
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
                        <div className="form-control">
                            <label className="label cursor-pointer flex gap-2">
                                <span className="label-text">Tasks open for scheduling</span>
                                <input
                                    type="checkbox"
                                    className="checkbox"
                                    checked={showOnlyWithOpenTasks}
                                    onChange={(e) => setShowOnlyWithOpenTasks(e.target.checked)}
                                />
                            </label>
                        </div>
                    </div>
                    {sliderRange && dateRange && (
                        <div className="flex flex-col gap-2 sm:gap-4 mb-2 sm:mb-4">
                            <div className="flex items-center gap-4">
                                <span>{new Date(dateRange[0]).toLocaleDateString()}</span>
                                <Slider
                                    range
                                    min={sliderRange[0]}
                                    max={sliderRange[1]}
                                    value={dateRange}
                                    onChange={(value) => handleSliderChange(value as [number, number])}
                                    onAfterChange={(value) => handleSliderAfterChange(value as [number, number])}
                                    className="w-full"
                                />
                                <span>{new Date(dateRange[1]).toLocaleDateString()}</span>
                                {loadingMore && <Loading />}
                            </div>
                        </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {listFilteredContests.map(contest => {
                            const canManageThisContest = contest.is_editor || document.configuration.is_superuser;
                            const viewLink = `/mission-dashboard/${contest.id}`;
                            const manageLink = canManageThisContest ? reverse('contest_details', contest.id) : undefined;

                            return (
                                <ContestCard
                                    key={contest.id}
                                    contest={contest}
                                    status={getContestStatus(contest)}
                                    isRegistered={registeredContestIds.has(contest.id)}
                                    hasScheduledFlight={scheduledFlightContestIds.has(contest.id)}
                                    isEditorContest={canManageThisContest}
                                    hasOpenTasksForScheduling={(contest as any).hasOpenTasksForScheduling} // Pass new prop
                                    viewLink={viewLink}
                                    manageLink={manageLink}
                                />
                            );
                        })}
                        {listFilteredContests.length === 0 && !loading && (
                            <p className="text-center mt-2 sm:mt-4 col-span-full">No contests match your filters.</p>
                        )}
                    </div>
                </div>
            )}

            {activeTab === 'upcoming' && document.configuration.isAuthenticated && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">My Upcoming Flights</h2>
                    <UpcomingFlights
                        myFutureFlights={myFutureFlights}
                        contests={contests}
                        onCancel={handleCancelFlight}
                    />
                </div>
            )}

            {activeTab === 'past' && document.configuration.isAuthenticated && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">My Past Flights</h2>
                    <PastFlights />
                </div>
            )}

            {activeTab === 'editorContests' && document.configuration.isAuthenticated && document.configuration.isOrganizer && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">
                        My Contests
                        <span className="ml-2 text-gray-500 text-lg">({filteredMyEditorContests.length})</span>
                        <a href={reverse("contest_create")} className="btn btn-primary btn-sm ml-4">Create New Contest</a>
                    </h2>
                    <div className="flex space-x-2 sm:space-x-4 mb-2 sm:mb-4">
                        <input
                            type="text"
                            placeholder="Filter by name"
                            className="input input-bordered w-full max-w-xs"
                            value={nameFilter}
                            onChange={(e) => setNameFilter(e.target.value)}
                        />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredMyEditorContests.map(contest => {
                            const viewLink = `/mission-dashboard/${contest.id}`;
                            const manageLink = reverse('contest_details', contest.id);
                            return (
                                <ContestCard
                                    key={contest.id}
                                    contest={contest}
                                    status={getContestStatus(contest)}
                                    isRegistered={registeredContestIds.has(contest.id)}
                                    hasScheduledFlight={scheduledFlightContestIds.has(contest.id)}
                                    isEditorContest={true}
                                    viewLink={viewLink}
                                    manageLink={manageLink}
                                />
                            );
                        })}
                        {filteredMyEditorContests.length === 0 && !loading && (
                            <p className="text-center mt-2 sm:mt-4 col-span-full">No contests match your filters.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default MissionDashboard;
