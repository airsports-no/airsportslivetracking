import React, { useState, useEffect, useMemo } from 'react';
import Select from 'react-select';
import { LatLngBounds } from 'leaflet';
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
    const location = useLocation();

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const tab = params.get('tab');
        if (tab && ['allContests', 'upcoming', 'past', 'editorContests'].includes(tab)) {
            setActiveTab(tab);
        }
    }, [location.search]);

    useEffect(() => {
        const loadInitialData = async () => {
            setLoading(true);
            try {
                const oneYearAgo = new Date();
                oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);

                const [contestsData, ongoingData, myFutureFlightsData, myContestTeamsData] = await Promise.all([
                    fetchContests({ startTimeGte: oneYearAgo.toISOString().split('T')[0] }),
                    fetchOngoingNavigation(),
                    fetchMyFutureFlights(),
                    fetchMyContestTeams(),
                ]);

                setContests(contestsData);
                if (contestsData.length > 0) {
                    const oldest = new Date(contestsData.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())[0].start_time);
                    setOldestContestDate(oldest);
                } else {
                    setOldestContestDate(oneYearAgo);
                }

                setOngoingNavigations(ongoingData);
                setMyFutureFlights(myFutureFlightsData);
                setMyContestTeams(myContestTeamsData);
            } catch (err) {
                setError((err as Error).message);
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        loadInitialData();
    }, []);

    const handleFetchMore = async () => {
        if (!oldestContestDate) return;
        setLoadingMore(true);
    
        const oneYearBeforeOldest = new Date(oldestContestDate);
        oneYearBeforeOldest.setFullYear(oneYearBeforeOldest.getFullYear() - 1);
    
        try {
            const moreContests = await fetchContests({
                startTimeGte: oneYearBeforeOldest.toISOString().split('T')[0],
                finishTimeLte: oldestContestDate.toISOString().split('T')[0]
            });
    
            const existingContestIds = new Set(contests.map(c => c.id));
            const newContests = moreContests.filter(c => !existingContestIds.has(c.id));
    
            setContests([...contests, ...newContests]);
            setOldestContestDate(oneYearBeforeOldest);
        } catch (err) {
            setError((err as Error).message);
            console.error(err);
        } finally {
            setLoadingMore(false);
        }
    };

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

    const editorContests = useMemo(() => {
        if (!contests) return [];
        return contests.filter(contest => contest.is_editor);
    }, [contests]);

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
                return nameMatch && countryMatch;
            });
    }, [contests, nameFilter, selectedCountries]);

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

    return (
        <div className="container mx-auto p-4" data-theme="aviation">
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
                                        <Link to={live.tracking_link} className="btn btn-primary">Watch Tracking</Link>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div className="tabs tabs-boxed mb-4">
                <a className={`tab ${activeTab === 'allContests' ? 'tab-active' : ''}`} onClick={() => setActiveTab('allContests')}>All Contests</a> 
                <a className={`tab ${activeTab === 'upcoming' ? 'tab-active' : ''}`} onClick={() => setActiveTab('upcoming')}>My Upcoming Flights</a>
                <a className={`tab ${activeTab === 'past' ? 'tab-active' : ''}`} onClick={() => setActiveTab('past')}>My Past Flights</a>
                <a className={`tab ${activeTab === 'editorContests' ? 'tab-active' : ''}`} onClick={() => setActiveTab('editorContests')}>My Contests</a>
            </div>

            {loading && <Loading />}

            {activeTab === 'allContests' && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">
                        All Contests
                        <span className="ml-2 text-gray-500 text-lg">({listFilteredContests.length})</span>
                    </h2>
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
                    <div className="text-center mt-4 mb-4">
                        <p className="mb-2">Showing contests since {oldestContestDate?.toLocaleDateString()}</p>
                        <button onClick={handleFetchMore} className="btn btn-secondary" disabled={loadingMore}>
                            {loadingMore ? 'Loading...' : 'Fetch More'}
                        </button>
                    </div>
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

            {activeTab === 'past' && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">My Past Flights</h2>
                    <PastFlights />
                </div>
            )}

            {activeTab === 'editorContests' && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">
                        My Contests
                        <Link to={reverse("contest_create")} className="btn btn-primary btn-sm ml-4">Create New Contest</Link>
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {editorContests.map(contest => {
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
                        {editorContests.length === 0 && !loading && (
                            <p className="text-center mt-2 sm:mt-4 col-span-full">You are not an editor for any contests.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default MissionDashboard;
