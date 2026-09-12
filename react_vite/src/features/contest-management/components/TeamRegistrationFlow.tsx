import React, { useEffect, useState } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMissionDashboardStore } from '../../mission-dashboard/store';
import * as api from '../api';
import { ContestTeamListItem } from '../types';
import { buildRegisterPayload } from '../teamRegistrationFlow';
import {
    teamRegistrationDefaults,
    teamRegistrationSchema,
    TeamRegistrationFormInput,
    TeamRegistrationFormValues,
} from '../schemas/teamRegistrationSchema';
import PersonSearchOrCreate from './PersonSearchOrCreate';
import AeroplaneSearchOrCreate from './AeroplaneSearchOrCreate';
import ClubSearchOrCreate from './ClubSearchOrCreate';
import TrackingDataStep from './TrackingDataStep';

interface TeamRegistrationFlowProps {
    contestId: number;
    editingContestTeam?: ContestTeamListItem;
    onSaved: (contestTeam: ContestTeamListItem) => void;
    onCancel: () => void;
}

function defaultsForEdit(contestTeam: ContestTeamListItem): TeamRegistrationFormValues {
    const { team } = contestTeam;
    return {
        pilot: { mode: 'existing', person: team.crew.member1.id },
        copilot: team.crew.member2 ? { mode: 'existing', person: team.crew.member2.id } : { mode: 'skip' },
        aeroplane: { registration: team.aeroplane.registration, type: team.aeroplane.type, colour: team.aeroplane.colour },
        club: { name: team.club?.name ?? '', country: team.club?.country ?? '' },
        air_speed: contestTeam.air_speed,
        tracking_service: contestTeam.tracking_service,
        tracking_device: contestTeam.tracking_device,
        tracker_device_id: contestTeam.tracker_device_id ?? '',
    };
}

// Admin team registration/edit form - replaces RegisterTeamWizard. One form rather than a
// multi-step wizard: pilot/copilot mode toggles (PersonSearchOrCreate) and aeroplane/club
// creatable selects are all visible at once, matching this feature directory's other flows'
// react-hook-form + zod convention.
const TeamRegistrationFlow: React.FC<TeamRegistrationFlowProps> = ({ contestId, editingContestTeam, onSaved, onCancel }) => {
    const { clubs, aircrafts, pilots, fetchClubs, fetchAircrafts, fetchPilots } = useMissionDashboardStore();
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([fetchClubs(), fetchAircrafts(), fetchPilots()])
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    }, []);

    const methods = useForm<TeamRegistrationFormInput, unknown, TeamRegistrationFormValues>({
        resolver: zodResolver(teamRegistrationSchema),
        defaultValues: editingContestTeam ? defaultsForEdit(editingContestTeam) : teamRegistrationDefaults,
    });

    const onSubmit = async (values: TeamRegistrationFormValues) => {
        setSubmitting(true);
        setError(null);
        try {
            const payload = buildRegisterPayload(values, editingContestTeam?.id);
            const contestTeam = await api.registerTeam(contestId, payload);
            onSaved(contestTeam);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <span className="loading loading-spinner"></span>;

    return (
        <div className="card bg-base-100 shadow-xl max-w-3xl w-full mx-auto">
            <div className="card-body">
                <h2 className="card-title">{editingContestTeam ? 'Edit team registration' : 'Register a team'}</h2>
                <FormProvider {...methods}>
                    <form onSubmit={methods.handleSubmit(onSubmit)} className="space-y-4">
                        <PersonSearchOrCreate field="pilot" label="Pilot" allowSkip={false} persons={pilots} />
                        <PersonSearchOrCreate field="copilot" label="Co-pilot" allowSkip persons={pilots} />
                        <AeroplaneSearchOrCreate aircrafts={aircrafts} />
                        <ClubSearchOrCreate clubs={clubs} />
                        <TrackingDataStep />

                        {error && <div className="alert alert-error">{error}</div>}

                        <div className="card-actions justify-end">
                            <button type="button" className="btn btn-ghost" onClick={onCancel}>
                                Cancel
                            </button>
                            <button type="submit" className="btn btn-primary" disabled={submitting}>
                                {submitting && <span className="loading loading-spinner"></span>}
                                {editingContestTeam ? 'Save changes' : 'Register team'}
                            </button>
                        </div>
                    </form>
                </FormProvider>
            </div>
        </div>
    );
};

export default TeamRegistrationFlow;
