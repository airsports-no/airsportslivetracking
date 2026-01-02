import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import { Contest, MyParticipatingContest, Club, Aircraft, Copilot, RegisterTeamPayload, ScheduleFlightPayload } from '../types';
import * as api from '../api';

interface ScheduleFlightFormProps {
    contest: Contest;
    navigationTaskId: number;
    myContests: MyParticipatingContest[];
    onClose: () => void;
}

const ScheduleFlightForm: React.FC<ScheduleFlightFormProps> = ({ contest, navigationTaskId, myContests, onClose }) => {
    const existingRegistration = myContests.find(mc => mc.contest.id === contest.id);

    // Form state
    const [copilot, setCopilot] = useState<number | null>(existingRegistration?.team.crew.member2?.id || null);
    const [aircraft, setAircraft] = useState<string>(existingRegistration?.team.aeroplane.registration || '');
    const [airspeed, setAirspeed] = useState<number>(existingRegistration?.air_speed || 65);
    const [club, setClub] = useState<string>(existingRegistration?.team.club?.name || '');
    
    const [startTime, setStartTime] = useState<string>(new Date().toISOString().slice(0, 16));
    const [windSpeed, setWindSpeed] = useState<number>(0);
    const [windDirection, setWindDirection] = useState<number>(0);
    const [adaptiveStart, setAdaptiveStart] = useState<boolean>(false);

    // Autocomplete state
    const [clubs, setClubs] = useState<Club[]>([]);
    const [aircrafts, setAircrafts] = useState<Aircraft[]>([]);
    const [pilots, setPilots] = useState<Copilot[]>([]);

    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([
            api.fetchClubs(),
            api.fetchAircrafts(),
            api.fetchPilots()
        ]).then(([clubsData, aircraftsData, pilotsData]) => {
            setClubs(clubsData);
            setAircrafts(aircraftsData);
            setPilots(pilotsData);
        }).catch(err => setError(err.message));
    }, []);
    
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            let contestTeamId: number | undefined = existingRegistration?.id;

            const currentRegistrationDetails = {
                club_name: club,
                aircraft_registration: aircraft,
                airspeed: airspeed,
                copilot_id: copilot,
            };

            // Check if registration details have changed if an existing registration exists
            let registrationDetailsChanged = false;
            if (existingRegistration) {
                const existingRegistrationDetails = {
                    club_name: existingRegistration.team.club?.name || '',
                    aircraft_registration: existingRegistration.team.aeroplane.registration || '',
                    airspeed: existingRegistration.air_speed,
                    copilot_id: existingRegistration.team.crew.member2?.id || null,
                };

                // Perform a deep comparison. For simplicity, convert to JSON and compare strings.
                registrationDetailsChanged = JSON.stringify(currentRegistrationDetails) !== JSON.stringify(existingRegistrationDetails);
            }
            
            // Logic for handling registration
            if (existingRegistration && registrationDetailsChanged) {
                // withdraw existing and register new
                await api.withdraw(contest.id);
                const registrationPayload: RegisterTeamPayload = {
                    contestId: contest.id,
                    ...currentRegistrationDetails,
                };
                const registrationResponse = await api.registerForContest(registrationPayload);
                contestTeamId = registrationResponse.id;

            } else if (!existingRegistration) {
                // No existing registration, just register new
                const registrationPayload: RegisterTeamPayload = {
                    contestId: contest.id,
                    ...currentRegistrationDetails,
                };
                const registrationResponse = await api.registerForContest(registrationPayload);
                contestTeamId = registrationResponse.id;
            }
            // Else: existingRegistration exists and registrationDetailsChanged is false,
            // so contestTeamId already holds existingRegistration.id and no action is needed.


            if(contestTeamId) {
                // Step 2: Schedule the flight.
                const schedulePayload: ScheduleFlightPayload = {
                    contest_team: contestTeamId,
                    starting_point_time: new Date(startTime + ':00Z').toISOString(),
                    adaptive_start: adaptiveStart,
                    wind_speed: windSpeed,
                    wind_direction: windDirection,
                };

                await api.scheduleFlight(contest.id, navigationTaskId, schedulePayload);
                onClose(); // Close form on success
            } else {
                setError("Failed to obtain contest team ID for scheduling flight.");
            }
            
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    };


    return (
        <div className="card bg-base-100 shadow-xl max-w-2xl mx-auto">
            <div className="card-body">
                <h2 className="card-title">Schedule flight for {contest.name}</h2>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <>
                        <div className="divider">Team Registration</div>
                        {/* Copilot */}
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
                        {/* Aircraft */}
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
                        {/* Airspeed */}
                         <label className="form-control w-full">
                            <div className="label"><span className="label-text">Airspeed (knots)</span></div>
                            <input type="number" required value={airspeed} onChange={e => setAirspeed(parseInt(e.target.value))} className="input input-bordered w-full" />
                        </label>
                        {/* Club */}
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
                    {/* Start Time */}
                    <label className="form-control w-full">
                        <div className="label"><span className="label-text">Start Time</span></div>
                        <input type="datetime-local" required value={startTime} onChange={e => setStartTime(e.target.value)} className="input input-bordered w-full" />
                    </label>
                    {/* Wind */}
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
                    {/* Adaptive Start */}
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
