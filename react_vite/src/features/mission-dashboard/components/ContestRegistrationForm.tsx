import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import CreatableSelect from 'react-select/creatable';
import { Contest, MyParticipatingContest, Club, Aircraft, Copilot, RegisterTeamPayload, MyContestTeam } from '../types';
import * as api from '../api';
import { useMissionDashboardStore } from '../store';

interface ContestRegistrationFormProps {
    contest: Contest;
    myContestTeams: MyContestTeam[];
    onClose: () => void;
}

const ContestRegistrationForm: React.FC<ContestRegistrationFormProps> = ({ contest, myContestTeams, onClose }) => {
    const { clubs, aircrafts, pilots, fetchClubs, fetchAircrafts, fetchPilots, withdraw } = useMissionDashboardStore();
    const existingRegistration = myContestTeams.find(mc => mc.contest === contest.id);

    // Form state for registration
    const [copilot, setCopilot] = useState<number | null>(null);
    const [aircraft, setAircraft] = useState<string>('');
    const [airspeed, setAirspeed] = useState<number>(65);
    const [club, setClub] = useState<string>('');
    
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const promise = Promise.all([
            fetchClubs(),
            fetchAircrafts(),
            fetchPilots()
        ]);
        promise.catch(err => setError(err.message));
    }, [fetchClubs, fetchAircrafts, fetchPilots]);
    
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            const currentRegistrationDetails = {
                club_name: club,
                aircraft_registration: aircraft,
                airspeed: airspeed,
                copilot_id: copilot,
            };

            // Check if registration details have changed if an existing registration exists
            let registrationDetailsChanged = false;
            if (existingRegistration) {
                // This logic needs to be adapted as we don't have the full team details here.
                // For simplicity, we'll assume if there is an existing registration, we withdraw and re-register.
                registrationDetailsChanged = true;
            }
            
            // Logic for handling registration
            if (existingRegistration && registrationDetailsChanged) {
                // withdraw existing and register new
                await withdraw(contest.id);
                const registrationPayload: RegisterTeamPayload = {
                    contestId: contest.id,
                    ...currentRegistrationDetails,
                };
                await api.registerForContest(registrationPayload);

            } else if (!existingRegistration) {
                // No existing registration, just register new
                const registrationPayload: RegisterTeamPayload = {
                    contestId: contest.id,
                    ...currentRegistrationDetails,
                };
                await api.registerForContest(registrationPayload);
            }
            // Else: existingRegistration exists and registrationDetailsChanged is false,
            // so no action is needed as registration details haven't changed.
            onClose(); // Close form on success
            
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    };


    return (
        <div className="card bg-base-100 shadow-xl max-w-2xl mx-auto">
            <div className="card-body">
                <h2 className="card-title">Register for {contest.name}</h2>
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
                            <CreatableSelect
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
                            <CreatableSelect
                                options={clubs.map(c => ({ value: c.name, label: c.name }))}
                                value={club ? { value: club, label: club } : null}
                                onChange={selectedOption => setClub(selectedOption ? selectedOption.value : '')}
                                isClearable
                                placeholder="Select or type club"
                                classNamePrefix="my-react-select"
                            />
                        </label>
                    </>
                    
                    {error && <div className="alert alert-error mt-4">{error}</div>}

                    <div className="card-actions justify-end">
                        <button type="button" onClick={onClose} className="btn btn-ghost">Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={loading}>
                            {loading && <span className="loading loading-spinner"></span>}
                            Register
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ContestRegistrationForm;