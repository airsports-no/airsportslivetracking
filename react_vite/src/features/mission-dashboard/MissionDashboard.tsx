import React, { useState, useEffect, useMemo, useLayoutEffect, useRef } from 'react';
import Select from 'react-select';
import { selectStyles } from '../../utils/selectStyles';
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
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { reverse } from '../../urls';

// Define NavigationTask interface based on likely API response structure
interface NavigationTask {
    pk: number;
    name: string;
    status?: 'Open' | 'Scheduled' | 'Live' | 'Finalized';
    start_time: string; // ISO string
    finish_time: string; // ISO string
    allow_self_management: boolean;
    flown_contestants_count: number;
}

const ITEMS_PER_PAGE = 30;

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
    const [showOnlyWithOpenTasks, setShowOnlyWithOpenTasks] = useState(false);
    const [showOnlyWithFlownContestants, setShowOnlyWithFlownContestants] = useState(false);
    const [dateRange, setDateRange] = useState<[number, number] | null>(null);
    const [sliderRange, setSliderRange] = useState<[number, number] | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [myContestsPage, setMyContestsPage] = useState(1);
    const location = useLocation();
    const navigate = useNavigate();
    const isMounted = useRef(true);

    useEffect(() => {
        isMounted.current = true;
        return () => {
            isMounted.current = false;
        };
    }, []);

    const updateURL = (updates: Record<string, string | string[] | boolean | number | null>) => {
        if (!isMounted.current) return;
        // Safety: If we are already navigating away from the dashboard, don't update its URL
        if (location.pathname !== '/' && location.pathname !== '') return;

        const params = new URLSearchParams(location.search);
        Object.entries(updates).forEach(([key, value]) => {
            if (value === null || value === '' || value === false || (Array.isArray(value) && value.length === 0)) {
                params.delete(key);
            } else {
                params.set(key, Array.isArray(value) ? value.join(',') : String(value));
            }
        });
        // Use replace: true so that filter changes don't clutter the history
        navigate({ search: params.toString() }, { replace: true });
    };

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        
        const name = params.get('name');
        if (name !== null && name !== nameFilter) setNameFilter(name);

        const countries = params.get('countries');
        if (countries !== null) {
            const countryList = countries.split(',');
            if (JSON.stringify(countryList) !== JSON.stringify(selectedCountries)) {
                setSelectedCountries(countryList);
            }
        } else if (selectedCountries.length > 0) {
            setSelectedCountries([]);
        }

        const openTasks = params.get('openTasks');
        if (openTasks !== null) {
            const isOpen = openTasks === 'true';
            if (isOpen !== showOnlyWithOpenTasks) setShowOnlyWithOpenTasks(isOpen);
        } else if (showOnlyWithOpenTasks) {
            setShowOnlyWithOpenTasks(false);
        }

        const withFlown = params.get('withFlown');
        if (withFlown !== null) {
            const isWithFlown = withFlown === 'true';
            if (isWithFlown !== showOnlyWithFlownContestants) setShowOnlyWithFlownContestants(isWithFlown);
        } else if (showOnlyWithFlownContestants) {
            setShowOnlyWithFlownContestants(false);
        }

        const page = params.get('page');
        if (page !== null) {
            const p = parseInt(page, 10);
            if (!isNaN(p) && p !== currentPage) setCurrentPage(p);
        } else if (currentPage !== 1) {
            setCurrentPage(1);
        }

        const myPage = params.get('myPage');
        if (myPage !== null) {
            const p = parseInt(myPage, 10);
            if (!isNaN(p) && p !== myContestsPage) setMyContestsPage(p);
        } else if (myContestsPage !== 1) {
            setMyContestsPage(1);
        }

        const tab = params.get('tab');
        if (tab && ['allContests', 'upcoming', 'past', 'editorContests'].includes(tab)) {
            let shouldSetActiveTab = true;
            if (!document.configuration.isAuthenticated) {
                if (['upcoming', 'past', 'editorContests'].includes(tab)) {
                    shouldSetActiveTab = false;
                }
            } else {
                if (tab === 'editorContests' && !document.configuration.isOrganizer) {
                    shouldSetActiveTab = false;
                }
            }

            if (shouldSetActiveTab) {
                if (tab !== activeTab) setActiveTab(tab);
            } else {
                if (activeTab !== 'allContests') setActiveTab('allContests');
            }
        }
    }, [location.search]);

    useEffect(() => {
        const today = new Date();
        const oneYearAgo = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
        const twoYearsFromNow = new Date(today.getFullYear() + 2, today.getMonth(), today.getDate());
        const sliderMinDate = new Date(2021, 1, 15);

        let maxTime = today.getTime();
        if (contests && contests.length > 0) {
            const validContests = contests.filter(c => new Date(c.finish_time).getTime() <= twoYearsFromNow.getTime());
            if (validContests.length > 0) {
                const latestFinishTime = Math.max(...validContests.map(c => new Date(c.finish_time).getTime()));
                maxTime = Math.max(maxTime, latestFinishTime);
            }
        }

        setOldestContestDate(prev => prev || oneYearAgo);
        setSliderRange(prev => {
            const min = prev ? prev[0] : sliderMinDate.getTime();
            return [min, maxTime];
        });
        setDateRange(prev => {
            if (!prev) return [oneYearAgo.getTime(), maxTime];
            return [prev[0], maxTime];
        });
    }, [contests]);

    useLayoutEffect(() => {
        document.querySelector('main')?.scrollTo(0, 0);
    }, [loading, activeTab, currentPage]);

    useEffect(() => {
        const fetchDashboardData = async () => {
            const state = useMissionDashboardStore.getState();
            if (state.contests.length === 0) {
                setLoading(true);
            }

            const fetchPromises = [];

            fetchPromises.push(fetchOngoingNavigationFromStore(true));
            if (document.configuration.isAuthenticated) {
                fetchPromises.push(fetchMyFutureFlightsFromStore(true));
                fetchPromises.push(fetchMyPreviousFlightsFromStore(true));
                fetchPromises.push(fetchMyContestTeamsFromStore(true));
                fetchPromises.push(fetchMyEditorContestsFromStore(true));
            }

            const now = new Date();
            const oneYearAgo = new Date(now.getFullYear() - 1, now.getMonth(), 1);
            const finishTimeGte = oneYearAgo.toISOString().split('T')[0];

            if (document.configuration.is_superuser) {
                fetchPromises.push(fetchContestsFromStore({ 
                    finishTimeGte, 
                    excludeTeams: true,
                    excludeTasks: true
                }, true));
            } else {
                fetchPromises.push(fetchContestsFromStore({ 
                    finishTimeGte, 
                    excludeTeams: true, 
                    excludeTasks: true,
                    publicOnly: true
                }, true));

                if (document.configuration.isAuthenticated) {
                    fetchPromises.push(fetchContestsFromStore({ 
                        finishTimeGte, 
                        excludeTeams: true,
                        excludeTasks: true,
                        sharedOnly: true
                    }, false));
                }
            }

            try {
                await Promise.allSettled(fetchPromises);

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
    }, [fetchContestsFromStore, fetchOngoingNavigationFromStore, fetchMyFutureFlightsFromStore, fetchMyContestTeamsFromStore, fetchMyEditorContestsFromStore, fetchMyPreviousFlightsFromStore]);

    const handleSliderChange = (newRange: [number, number]) => {
        setDateRange(newRange);
        setCurrentPage(1);
        updateURL({ page: 1 });
    };

    const handleSliderAfterChange = async (newRange: [number, number]) => {
        const newStartDate = new Date(newRange[0]);
        if (oldestContestDate && newStartDate < oldestContestDate) {
            setLoadingMore(true);
            try {
                await fetchContestsFromStore({
                    finishTimeGte: newStartDate.toISOString().split('T')[0],
                    startTimeLte: oldestContestDate.toISOString().split('T')[0],
                    excludeTasks: true
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
            fetchOngoingNavigationFromStore(true);
        }, 2 * 60 * 1000);

        return () => clearInterval(interval);
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

        return contests
            .filter(contest => {
                const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
                const countryMatch = selectedCountries.length === 0 || (contest.country && selectedCountries.includes(contest.country));

                const contestStartDate = new Date(contest.start_time).getTime();
                const contestEndDate = new Date(contest.finish_time).getTime();
                const dateMatch = !dateRange || (contestEndDate >= dateRange[0] && contestStartDate <= dateRange[1]);
                
                const openTasksFilterMatch = !showOnlyWithOpenTasks || !!contest.has_open_tasks;
                const flownContestantsFilterMatch = !showOnlyWithFlownContestants || !!contest.has_flown_contestants;

                return nameMatch && countryMatch && dateMatch && openTasksFilterMatch && flownContestantsFilterMatch;
            });
    }, [contests, nameFilter, selectedCountries, showOnlyWithOpenTasks, showOnlyWithFlownContestants, dateRange]);

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

    const totalPages = Math.ceil(listFilteredContests.length / ITEMS_PER_PAGE);
    
    const paginatedContests = useMemo(() => {
        const start = (currentPage - 1) * ITEMS_PER_PAGE;
        return listFilteredContests.slice(start, start + ITEMS_PER_PAGE);
    }, [listFilteredContests, currentPage]);

    const handlePageChange = (page: number) => {
        setCurrentPage(page);
        updateURL({ page });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const filteredMyEditorContests = useMemo(() => {
        if (!myEditorContests) return [];
        return myEditorContests.filter(contest => {
            const nameMatch = nameFilter === '' || contest.name.toLowerCase().includes(nameFilter.toLowerCase());
            return nameMatch;
        });
    }, [myEditorContests, nameFilter]);

    const totalMyPages = Math.ceil(filteredMyEditorContests.length / ITEMS_PER_PAGE);

    const paginatedMyEditorContests = useMemo(() => {
        const start = (myContestsPage - 1) * ITEMS_PER_PAGE;
        return filteredMyEditorContests.slice(start, start + ITEMS_PER_PAGE);
    }, [filteredMyEditorContests, myContestsPage]);

    const handleMyPageChange = (page: number) => {
        setMyContestsPage(page);
        updateURL({ myPage: page });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <div className="container mx-auto p-4">
            <div className="flex justify-between items-center mb-4">
                <h1 className="text-4xl font-bold">Mission Dashboard</h1>
                {document.configuration.isOrganizer && (
                    <a href={reverse("contest_create")} className="btn btn-primary">Create New Contest</a>
                )}
            </div>

            {error && <div className="alert alert-error">{error}</div>}
            
            <div className="mb-8 hidden lg:block z-30">
                <h2 className="text-2xl font-bold mb-4">Contest Map</h2>
                <ContestMap 
                    contests={textFilteredContests} 
                    onBoundsChanged={(bounds) => {
                        setMapBounds(bounds);
                        if (bounds) {
                            setCurrentPage(1);
                            updateURL({ page: 1 });
                        }
                    }} 
                    minZoom={2}
                    onInteraction={() => {
                        setHasUserInteractedWithMap(true);
                        setCurrentPage(1);
                        updateURL({ page: 1 });
                    }} 
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
                    <a className={`tab ${activeTab === 'allContests' ? 'tab-active' : ''}`} onClick={() => updateURL({ tab: 'allContests' })}>All Contests</a> 
                    <>
                        <a className={`tab ${activeTab === 'upcoming' ? 'tab-active' : ''}`} onClick={() => updateURL({ tab: 'upcoming' })}>My Upcoming Flights</a>
                        <a className={`tab ${activeTab === 'past' ? 'tab-active' : ''}`} onClick={() => updateURL({ tab: 'past' })}>My Past Flights</a>
                        {document.configuration.isOrganizer && (
                            <a className={`tab ${activeTab === 'editorContests' ? 'tab-active' : ''}`} onClick={() => updateURL({ tab: 'editorContests' })}>My Contests</a>
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
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
                        <input
                            type="text"
                            placeholder="Filter by name"
                            className="input input-bordered input-sm w-full max-w-[180px]"
                            value={nameFilter}
                            onChange={(e) => {
                                setNameFilter(e.target.value);
                                setCurrentPage(1);
                                updateURL({ name: e.target.value, page: 1 });
                            }}
                        />
                        <Select
                            isMulti
                            options={countryOptions}
                            value={countryOptions.filter(option => selectedCountries.includes(option.value))}
                            onChange={(selectedOptions) => {
                                const countries = selectedOptions ? selectedOptions.map(option => option.value) : [];
                                setSelectedCountries(countries);
                                setCurrentPage(1);
                                updateURL({ countries, page: 1 });
                            }}
                            className="w-full max-w-[200px] text-sm"
                            placeholder="Country..."
                            classNamePrefix="my-react-select"
                            styles={selectStyles}
                        />
                        <div className="form-control">
                            <label className="label cursor-pointer flex gap-2 py-0">
                                <span className="label-text text-sm">Open tasks</span>
                                <input
                                    type="checkbox"
                                    className="checkbox checkbox-sm"
                                    checked={showOnlyWithOpenTasks}
                                    onChange={(e) => {
                                        const openTasks = e.target.checked;
                                        setShowOnlyWithOpenTasks(openTasks);
                                        setCurrentPage(1);
                                        updateURL({ openTasks, page: 1 });
                                    }}
                                />
                            </label>
                        </div>
                        <div className="form-control">
                            <label className="label cursor-pointer flex gap-2 py-0">
                                <span className="label-text text-sm">Flown</span>
                                <input
                                    type="checkbox"
                                    className="checkbox checkbox-sm"
                                    checked={showOnlyWithFlownContestants}
                                    onChange={(e) => {
                                        const withFlown = e.target.checked;
                                        setShowOnlyWithFlownContestants(withFlown);
                                        setCurrentPage(1);
                                        updateURL({ withFlown, page: 1 });
                                    }}
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
                        {paginatedContests.map(contest => {
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
                                    hasOpenTasksForScheduling={contest.has_open_tasks}
                                    viewLink={viewLink}
                                    manageLink={manageLink}
                                />
                            );
                        })}
                        {paginatedContests.length === 0 && !loading && (
                            <p className="text-center mt-2 sm:mt-4 col-span-full">No contests match your filters.</p>
                        )}
                    </div>

                    {/* Pagination UI */}
                    {totalPages > 1 && (
                        <div className="flex justify-center mt-8">
                            <div className="join shadow-lg">
                                <button 
                                    className={`join-item btn ${currentPage === 1 ? 'btn-disabled' : ''}`}
                                    onClick={() => handlePageChange(currentPage - 1)}
                                >
                                    «
                                </button>
                                {[...Array(totalPages)].map((_, i) => {
                                    const page = i + 1;
                                    // Logic to show only a few pages around current page
                                    if (page === 1 || page === totalPages || (page >= currentPage - 2 && page <= currentPage + 2)) {
                                        return (
                                            <button 
                                                key={page}
                                                className={`join-item btn ${currentPage === page ? 'btn-active btn-primary' : ''}`}
                                                onClick={() => handlePageChange(page)}
                                            >
                                                {page}
                                            </button>
                                        );
                                    } else if (page === currentPage - 3 || page === currentPage + 3) {
                                        return <button key={page} className="join-item btn btn-disabled">...</button>;
                                    }
                                    return null;
                                })}
                                <button 
                                    className={`join-item btn ${currentPage === totalPages ? 'btn-disabled' : ''}`}
                                    onClick={() => handlePageChange(currentPage + 1)}
                                >
                                    »
                                </button>
                            </div>
                        </div>
                    )}
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
                    <div className="flex space-x-2 sm:space-x-4 mb-4">
                        <input
                            type="text"
                            placeholder="Filter by name"
                            className="input input-bordered input-sm w-full max-w-[180px]"
                            value={nameFilter}
                            onChange={(e) => {
                                setNameFilter(e.target.value);
                                setMyContestsPage(1);
                                updateURL({ name: e.target.value, myPage: 1 });
                            }}
                        />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {paginatedMyEditorContests.map(contest => {
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
                        {paginatedMyEditorContests.length === 0 && !loading && (
                            <p className="text-center mt-2 sm:mt-4 col-span-full">No contests match your filters.</p>
                        )}
                    </div>

                    {/* My Contests Pagination UI */}
                    {totalMyPages > 1 && (
                        <div className="flex justify-center mt-8">
                            <div className="join shadow-lg">
                                <button 
                                    className={`join-item btn ${myContestsPage === 1 ? 'btn-disabled' : ''}`}
                                    onClick={() => handleMyPageChange(myContestsPage - 1)}
                                >
                                    «
                                </button>
                                {[...Array(totalMyPages)].map((_, i) => {
                                    const page = i + 1;
                                    if (page === 1 || page === totalMyPages || (page >= myContestsPage - 2 && page <= myContestsPage + 2)) {
                                        return (
                                            <button 
                                                key={page}
                                                className={`join-item btn ${myContestsPage === page ? 'btn-active btn-primary' : ''}`}
                                                onClick={() => handleMyPageChange(page)}
                                            >
                                                {page}
                                            </button>
                                        );
                                    } else if (page === myContestsPage - 3 || page === myContestsPage + 3) {
                                        return <button key={page} className="join-item btn btn-disabled">...</button>;
                                    }
                                    return null;
                                })}
                                <button 
                                    className={`join-item btn ${myContestsPage === totalMyPages ? 'btn-disabled' : ''}`}
                                    onClick={() => handleMyPageChange(myContestsPage + 1)}
                                >
                                    »
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default MissionDashboard;
