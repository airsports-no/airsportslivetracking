import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import { Contest, MyParticipatingContest, Club, Aircraft, Copilot, RegisterTeamPayload, ScheduleFlightPayload, MyContestTeam, Team } from '../types';
import * as api from '../api';
import { useMissionDashboardStore } from '../store';

const formatInTimeZone = (date: Date, timeZone: string) => {
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: timeZone || 'UTC',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false
    }).formatToParts(date);
    const p = (type: string) => parts.find(it => it.type === type)?.value;
    return `${p('year')}-${p('month')}-${p('day')}T${p('hour')}:${p('minute')}`;
};

const getContestTimeWithOffset = (dateStr: string, timeZone: string): string => {
    const d = new Date(dateStr + ':00Z');
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: timeZone || 'UTC',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    }).formatToParts(d);
    const p = (type: string) => parseInt(parts.find(it => it.type === type)!.value);
    const localInTZ = Date.UTC(p('year'), p('month') - 1, p('day'), p('hour'), p('minute'), p('second'));
    const diffMinutes = (localInTZ - d.getTime()) / 60000;
    const absDiff = Math.abs(diffMinutes);
    const hours = Math.floor(absDiff / 60);
    const minutes = absDiff % 60;
    const sign = diffMinutes >= 0 ? '+' : '-';
    const offset = `${sign}${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
    return `${dateStr}:00${offset}`;
};

interface ScheduleFlightFormProps {
    contest: Contest;
    navigationTaskId: number;
    myContestTeams: MyContestTeam[];
    onClose: () => void;
}

const ScheduleFlightForm: React.FC<ScheduleFlightFormProps> = ({ contest, navigationTaskId, myContestTeams, onClose }) => {
    const { clubs, aircrafts, pilots, fetchClubs, fetchAircrafts, fetchPilots, withdraw } = useMissionDashboardStore();
    const [prefillRegistration, setPrefillRegistration] = useState<MyParticipatingContest | null>(null);
    const [loadingPrefillData, setLoadingPrefillData] = useState<boolean>(false);

    // Form state
    const [copilot, setCopilot] = useState<number | null>(null);
    const [aircraft, setAircraft] = useState<string>('');
    const [airspeed, setAirspeed] = useState<number>(65);
    const [club, setClub] = useState<string>('');
    
    const [startTime, setStartTime] = useState<string>(() => {
        const future = new Date(new Date().getTime() + 60 * 60 * 1000);
        return formatInTimeZone(future, contest.time_zone);
    });
    const [windSpeed, setWindSpeed] = useState<number>(0);
    const [windDirection, setWindDirection] = useState<number>(0);
    const [adaptiveStart, setAdaptiveStart] = useState<boolean>(false);

    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPrefillData = async () => {
            setLoadingPrefillData(true);
            setError(null);
            let registrationToPrefill: MyParticipatingContest | null = null;

            const existingContestTeamRegistration = myContestTeams.find(mct => mct.contest === contest.id);
            if (existingContestTeamRegistration) {
                try {
                    const teamData = await api.fetchTeam(existingContestTeamRegistration.team);
                    registrationToPrefill = {
                        id: existingContestTeamRegistration.id,
                        air_speed: existingContestTeamRegistration.air_speed,
                        tracking_service: existingContestTeamRegistration.tracking_service,
                        tracking_device: existingContestTeamRegistration.tracking_device,
                        tracker_device_id: existingContestTeamRegistration.tracker_device_id,
                        contest: contest,
                        team: teamData,
                        can_edit: true, // Assuming default
                    };
                } catch (err) {
                    setError(`Failed to load team data for prefill: ${(err as Error).message}`);
                }
            }
            setPrefillRegistration(registrationToPrefill);
            setLoadingPrefillData(false);
        };

        fetchPrefillData();
    }, [contest, myContestTeams]);

    useEffect(() => {
        if (prefillRegistration) {
            setCopilot(prefillRegistration.team.crew.member2?.id || null);
            setAircraft(prefillRegistration.team.aeroplane.registration || '');
            setAirspeed(prefillRegistration.air_speed || 65);
            setClub(prefillRegistration.team.club?.name || '');
        } else {
            setCopilot(null);
            setAircraft('');
            setAirspeed(65);
            setClub('');
        }
    }, [prefillRegistration]);

    useEffect(() => {
        const promise = Promise.all([
            fetchClubs(),
            fetchAircrafts(),
            fetchPilots()
        ]);
        promise.catch(err => {
            setError(err.message);
            console.error("Fetching autocomplete data:", err);
        });
    }, [fetchClubs, fetchAircrafts, fetchPilots]);
    
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            let contestTeamId: number | undefined = prefillRegistration?.id;

            const currentRegistrationDetails = {
                club_name: club,
                aircraft_registration: aircraft,
                airspeed: airspeed,
                copilot_id: copilot,
            };

            let registrationDetailsChanged = false;
            if (prefillRegistration) {
                const existingRegistrationDetails = {
                    club_name: prefillRegistration.team.club?.name || '',
                    aircraft_registration: prefillRegistration.team.aeroplane.registration || '',
                    airspeed: prefillRegistration.air_speed,
                    copilot_id: prefillRegistration.team.crew.member2?.id || null,
                };
                registrationDetailsChanged = JSON.stringify(currentRegistrationDetails) !== JSON.stringify(existingRegistrationDetails);
            }
            
            if (prefillRegistration && registrationDetailsChanged) {
                await withdraw(contest.id);
                const registrationPayload: RegisterTeamPayload = {
                    contestId: contest.id,
                    ...currentRegistrationDetails,
                };
                const registrationResponse = await api.registerForContest(registrationPayload);
                contestTeamId = registrationResponse.id;
            } else if (!prefillRegistration) {
                const registrationPayload: RegisterTeamPayload = {
                    contestId: contest.id,
                    ...currentRegistrationDetails,
                };
                const registrationResponse = await api.registerForContest(registrationPayload);
                contestTeamId = registrationResponse.id;
            }

            if(contestTeamId) {
                const schedulePayload: ScheduleFlightPayload = {
                    contest_team: contestTeamId,
                    starting_point_time: getContestTimeWithOffset(startTime, contest.time_zone),
                    adaptive_start: adaptiveStart,
                    wind_speed: windSpeed,
                    wind_direction: windDirection,
                };
                await api.scheduleFlight(contest.id, navigationTaskId, schedulePayload);
                onClose();
            } else {
                setError("Failed to obtain contest team ID for scheduling flight.");
                console.error("Failed to obtain contest team ID for scheduling flight:");
            }
            
        } catch (err) {
            setError((err as Error).message);
            console.error("Scheduling flight failed:", err);
        } finally {
            setLoading(false);
        }
    };

    if (loadingPrefillData) return <div className="w-full text-center py-4"><span className="loading loading-spinner"></span> Loading registration data...</div>;

    return (
        <div className="card bg-base-100 shadow-xl max-w-2xl mx-auto">
            <div className="card-body">
                <h2 className="card-title">Schedule flight for {contest.name}</h2>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <>
                        <div className="divider">Team Registration</div>
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Co-pilot (optional)</span></div>
                            <Select
                                options={pilots.map(p => ({ value: p.id, label: `${p.first_name} ${p.last_name} (${p.email})` }))}
                                value={copilot ? { value: copilot, label: pilots.find(p => p.id === copilot)?.first_name + ' ' + pilots.find(p => p.id === copilot)?.last_name + ' (' + pilots.find(p => p.id === copilot)?.email + ')' } : null}
                                onChange={selectedOption => setCopilot(selectedOption ? selectedOption.value : null)}
                                isClearable
                                placeholder="Select a co-pilot"
                                classNamePrefix="my-react-select"
                            />
                        </label>
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Aircraft Registration</span></div>
                            <Select
                                options={aircrafts.map(a => ({ value: a.registration, label: a.registration }))}
                                value={aircraft ? { value: aircraft, label: aircraft } : null}
                                onChange={selectedOption => setAircraft(selectedOption ? selectedOption.value : '')}
                                isClearable
                                placeholder="Select or type aircraft registration"
                                classNamePrefix="my-react-select"
                            />
                        </label>
                         <label className="form-control w-full">
                            <div className="label"><span className="label-text">Airspeed (knots)</span></div>
                            <input type="number" required value={airspeed} onChange={e => setAirspeed(parseInt(e.target.value))} className="input input-bordered w-full" />
                        </label>
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Club</span></div>
                            <Select
                                options={clubs.map(c => ({ value: c.name, label: c.name }))}
                                value={club ? { value: club, label: club } : null}
                                onChange={selectedOption => setClub(selectedOption ? selectedOption.value : '')}
                                isClearable
                                placeholder="Select or type club"
                                classNamePrefix="my-react-select"
                            />
                        </label>
                    </>
                    
                    <div className="divider">Flight Details</div>
                    <label className="form-control w-full">
                        <div className="label"><span className="label-text">Starting Point Time</span></div>
                        <input type="datetime-local" required value={startTime} onChange={e => setStartTime(e.target.value)} className="input input-bordered w-full" />
                    </label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Wind Speed (knots)</span></div>
                            <input type="number" value={windSpeed} onChange={e => setWindSpeed(parseInt(e.target.value))} className="input input-bordered w-full" />
                        </label>
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Wind Direction</span></div>
                            <input type="number" value={windDirection} onChange={e => setWindDirection(parseInt(e.target.value))} className="input input-bordered w-full" />
                        </label>
                    </div>
                    <div className="form-control">
                        <label className="label cursor-pointer">
                            <span className="label-text inline-flex items-center">
                                Adaptive Start
                                <div className="tooltip tooltip-right" data-tip="If adaptive start is selected, your start time will be set to the nearest whole minute you cross the 10 NM long line going through the starting gate anywhere between one hour before and one hour after the selected starting point time (FAQ).">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current shrink-0 w-4 h-4 ml-2"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                </div>
                            </span> 
                            <input type="checkbox" checked={adaptiveStart} onChange={e => setAdaptiveStart(e.target.checked)} className="checkbox checkbox-primary" />
                        </label>
                    </div>

                    {error && <div className="alert alert-error mt-4">{error}</div>}

                    <div className="card-actions justify-end">
                        <button type="button" onClick={onClose} className="btn btn-ghost">Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={loading}>
                            {loading && <span className="loading loading-spinner"></span>}
                            Schedule
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ScheduleFlightForm;
