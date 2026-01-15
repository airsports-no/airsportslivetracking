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
import { Link } from 'react-router-dom';
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

    const refreshData = async () => {
        try {
            setLoading(true);
            const [contestsData, ongoingData, myFutureFlightsData, myContestTeamsData] = await Promise.all([
                fetchContests(),
                fetchOngoingNavigation(),
                fetchMyFutureFlights(),
                fetchMyContestTeams(),
            ]);
            setContests(contestsData);
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

    useEffect(() => {
        refreshData();
    }, []);

    const handleCancelFlight = async (contestId: number, navigationTaskId: number, futureContestantId: number) => {
        try {
            await cancelFlight(contestId, navigationTaskId, futureContestantId);
            refreshData(); // Refresh data to reflect the cancellation
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
            
            <div className="mb-8 hidden lg:block">
                <h2 className="text-2xl font-bold mb-4">Contest Map</h2>
                <ContestMap 
                    contests={textFilteredContests} 
                    onBoundsChanged={setMapBounds} 
                    minZoom={1}
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
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {listFilteredContests.map(contest => (
                            <Link to={`/mission-dashboard/${contest.id}`} key={contest.id}>
                                <ContestCard
                                    contest={contest}
                                    status={getContestStatus(contest)}
                                    isRegistered={registeredContestIds.has(contest.id)}
                                    hasScheduledFlight={scheduledFlightContestIds.has(contest.id)}
                                />
                            </Link>
                        ))}
                        {listFilteredContests.length === 0 && !loading && (
                            <p className="text-center mt-2 sm:mt-4 col-span-full">No contests match your filters.</p>
                        )}
                    </div>
                </div>
            )}

            {activeTab === 'upcoming' && (
                <div>
                    <h2 className="text-2xl font-bold mb-4">My Upcoming Flights</h2>
                    <UpcomingFlights myFutureFlights={myFutureFlights} contests={contests} onCancel={handleCancelFlight} />
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
                    <h2 className="text-2xl font-bold mb-4">My Contests</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {editorContests.map(contest => (
                            <Link to={reverse('contest_details', contest.id)} key={contest.id}>
                                <ContestCard
                                    contest={contest}
                                    status={getContestStatus(contest)}
                                    isRegistered={registeredContestIds.has(contest.id)}
                                    hasScheduledFlight={scheduledFlightContestIds.has(contest.id)}
                                    isEditorContest={true}
                                />
                            </Link>
                        ))}
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
