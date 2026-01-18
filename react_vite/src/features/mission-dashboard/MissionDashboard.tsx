import React, { useState, useEffect, useMemo, useLayoutEffect } from 'react';
import Select from 'react-select';
import { LatLngBounds } from 'leaflet';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { useMissionDashboardStore } from './store';
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
    const {
        contests,
        ongoingNavigations,
        myFutureFlights,
        myContestTeams,
        myEditorContests,
        myPreviousFlights,
        fetchContests: fetchContestsFromStore,
        fetchOngoingNavigation: fetchOngoingNavigationFromStore,
        fetchMyFutureFlights: fetchMyFutureFlightsFromStore,
        fetchMyPreviousFlights: fetchMyPreviousFlightsFromStore,
        fetchMyContestTeams: fetchMyContestTeamsFromStore,
        fetchMyEditorContests: fetchMyEditorContestsFromStore,
        cancelFlight: cancelFlightFromStore,
    } = useMissionDashboardStore();

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState('allContests');
    const [nameFilter, setNameFilter] = useState('');
    const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
    const [mapBounds, setMapBounds] = useState<LatLngBounds | null>(null);
    const [hasUserInteractedWithMap, setHasUserInteractedWithMap] = useState(false);
    const [oldestContestDate, setOldestContestDate] = useState<Date | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
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
        // This effect sets up local UI state that doesn't depend on fetched data
        const today = new Date();
        const oneYearAgo = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
        const sliderMinDate = new Date(2021, 1, 15);

        setOldestContestDate(oneYearAgo);
        setDateRange([oneYearAgo.getTime(), today.getTime()]);
        setSliderRange([sliderMinDate.getTime(), today.getTime()]);
    }, []); // Empty dependency array ensures this runs only once on mount

    useLayoutEffect(() => {
        document.querySelector('main')?.scrollTo(0, 0);
    }, [loading, activeTab]);

    useEffect(() => {
        const fetchDashboardData = async () => {
            const state = useMissionDashboardStore.getState();
            // Only show the main page loader if the main contest list is not yet loaded.
            if (state.contests.length === 0) {
                setLoading(true);
            }

            const fetchPromises = [];

            // These actions are now cached in the store, so it's safe to call them.
            // They will only fetch if the data is not already present.
            fetchPromises.push(fetchOngoingNavigationFromStore());
            if (document.configuration.isAuthenticated) {
                fetchPromises.push(fetchMyFutureFlightsFromStore());
                fetchPromises.push(fetchMyPreviousFlightsFromStore());
                fetchPromises.push(fetchMyContestTeamsFromStore());
                fetchPromises.push(fetchMyEditorContestsFromStore());
            }

            // Conditionally fetch the main contest list only if it's empty.
            if (state.contests.length === 0) {
                const oneYearAgo = new Date(new Date().getFullYear() - 1, new Date().getMonth(), new Date().getDate());
                fetchPromises.push(fetchContestsFromStore({ startTimeGte: oneYearAgo.toISOString().split('T')[0] }));
            }

            try {
                await Promise.allSettled(fetchPromises);

                // Check for missing contests referenced by user data
                if (document.configuration.isAuthenticated) {
                    const updatedState = useMissionDashboardStore.getState();
                    const loadedContestIds = new Set(updatedState.contests.map(c => c.id));
                    const requiredContestIds = new Set<number>();

                    updatedState.myFutureFlights.forEach((f: any) => {
                        if (f.contest_id) requiredContestIds.add(f.contest_id);
                    });
                    updatedState.myContestTeams.forEach((t: any) => {
                        if (t.contest) requiredContestIds.add(t.contest);
                    });
                    updatedState.myPreviousFlights.forEach((f: any) => {
                        if (f.contest_id) requiredContestIds.add(f.contest_id);
                        else if (f.contest && typeof f.contest === 'number') requiredContestIds.add(f.contest);
                    });

                    const missingContestIds = Array.from(requiredContestIds).filter(id => !loadedContestIds.has(id));

                    if (missingContestIds.length > 0) {
                        await fetchContestsFromStore({ pks: missingContestIds });
                    }
                }
            } catch (err) {
                setError((err as Error).message);
            } finally {
                setLoading(false);
            }
        };

        fetchDashboardData();
    // The dependency array includes the fetch actions to adhere to linting rules,
    // but since they are stable from Zustand, this effect will run only once.
    }, [fetchContestsFromStore, fetchOngoingNavigationFromStore, fetchMyFutureFlightsFromStore, fetchMyContestTeamsFromStore, fetchMyEditorContestsFromStore, fetchMyPreviousFlightsFromStore]);

    const handleSliderChange = (newRange: [number, number]) => {
        setDateRange(newRange);
    };

    const handleSliderAfterChange = async (newRange: [number, number]) => {
        const newStartDate = new Date(newRange[0]);
        if (oldestContestDate && newStartDate < oldestContestDate) {
            setLoadingMore(true);
            try {
                await fetchContestsFromStore({
                    startTimeGte: newStartDate.toISOString().split('T')[0],
                    finishTimeLte: oldestContestDate.toISOString().split('T')[0]
                });
                setOldestContestDate(newStartDate);
            } catch (err) {
                setError((err as Error).message);
            } finally {
                setLoadingMore(false);
            }
        }
    };
			
    useEffect(() => {
        const interval = setInterval(() => {
            fetchOngoingNavigationFromStore();
        }, 2 * 60 * 1000); // Every 2 minutes

        return () => clearInterval(interval); // Cleanup on unmount
    }, [fetchOngoingNavigationFromStore]);

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number) => {
        try {
            await cancelFlightFromStore(contestId, navigationTaskId, futureContestantId);
        } catch (error) {
            setError((error as Error).message);
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
