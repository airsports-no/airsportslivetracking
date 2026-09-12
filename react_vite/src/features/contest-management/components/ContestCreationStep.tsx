import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { useMissionDashboardStore } from '../../mission-dashboard/store';
import { Contest } from '../../mission-dashboard/types';
import { contestCreationDefaults, contestCreationSchema, ContestCreationFormValues } from '../schemas/contestCreationSchema';

interface ContestCreationStepProps {
    onExistingContestChosen: (contest: Contest) => void;
    onNewContestSubmit: (values: ContestCreationFormValues) => void;
    submitting: boolean;
}

const TIME_ZONES: string[] =
    typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [contestCreationDefaults.time_zone];

// Replaces RouteToTaskWizard's contest_selection/contest_creation steps: pick an existing contest
// you can edit, or fill in the minimum needed to create a new one inline. Unlike that wizard,
// assigning an event token to the new contest is not offered here - there's no existing API to
// list a user's available token grants before a contest exists (the wizard populated that
// dropdown directly from the ORM); assign one afterwards via the classic contest page instead.
const ContestCreationStep: React.FC<ContestCreationStepProps> = ({ onExistingContestChosen, onNewContestSubmit, submitting }) => {
    const [mode, setMode] = useState<'existing' | 'new'>('existing');
    const { myEditorContests, managedClubs, fetchMyEditorContests, fetchManagedClubs } = useMissionDashboardStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([fetchMyEditorContests(), fetchManagedClubs()])
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    }, []);

    const {
        register,
        handleSubmit,
        setValue,
        watch,
        formState: { errors },
    } = useForm<ContestCreationFormValues>({
        resolver: zodResolver(contestCreationSchema),
        defaultValues: contestCreationDefaults,
    });
    const timeZone = watch('time_zone');
    const organizingClub = watch('organizing_club');

    if (loading) return <span className="loading loading-spinner"></span>;
    if (error) return <div className="alert alert-error">{error}</div>;

    return (
        <div>
            <div role="tablist" className="tabs tabs-boxed mb-4">
                <button
                    type="button"
                    role="tab"
                    className={`tab ${mode === 'existing' ? 'tab-active' : ''}`}
                    onClick={() => setMode('existing')}
                >
                    Existing contest
                </button>
                <button type="button" role="tab" className={`tab ${mode === 'new' ? 'tab-active' : ''}`} onClick={() => setMode('new')}>
                    New contest
                </button>
            </div>

            {mode === 'existing' && (
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Contest</span></div>
                    <Select
                        options={myEditorContests.map(contest => ({ value: contest.id, label: contest.name, contest }))}
                        onChange={selected => selected && onExistingContestChosen(selected.contest)}
                        placeholder="Choose a contest"
                        classNamePrefix="my-react-select"
                        styles={selectStyles}
                    />
                </label>
            )}

            {mode === 'new' && (
                <form onSubmit={handleSubmit(onNewContestSubmit)} className="space-y-4">
                    <label className="form-control w-full">
                        <div className="label"><span className="label-text">Contest name</span></div>
                        <input className="input input-bordered w-full" {...register('name')} />
                        {errors.name && <span className="text-error text-sm">{errors.name.message}</span>}
                    </label>

                    <label className="form-control w-full">
                        <div className="label"><span className="label-text">Timezone</span></div>
                        <Select
                            options={TIME_ZONES.map(tz => ({ value: tz, label: tz }))}
                            value={{ value: timeZone, label: timeZone }}
                            onChange={selected => selected && setValue('time_zone', selected.value)}
                            classNamePrefix="my-react-select"
                            styles={selectStyles}
                        />
                    </label>

                    <label className="form-control w-full">
                        <div className="label"><span className="label-text">Location (latitude,longitude)</span></div>
                        <input className="input input-bordered w-full" placeholder="60.0,11.0" {...register('location')} />
                        {errors.location && <span className="text-error text-sm">{errors.location.message}</span>}
                    </label>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Start time</span></div>
                            <input type="datetime-local" className="input input-bordered w-full" {...register('start_time')} />
                            {errors.start_time && <span className="text-error text-sm">{errors.start_time.message}</span>}
                        </label>
                        <label className="form-control w-full">
                            <div className="label"><span className="label-text">Finish time</span></div>
                            <input type="datetime-local" className="input input-bordered w-full" {...register('finish_time')} />
                            {errors.finish_time && <span className="text-error text-sm">{errors.finish_time.message}</span>}
                        </label>
                    </div>

                    <label className="form-control w-full">
                        <div className="label"><span className="label-text">Organizing club (optional)</span></div>
                        <Select
                            isClearable
                            options={managedClubs.map(club => ({ value: club.id, label: club.name }))}
                            value={
                                organizingClub
                                    ? { value: organizingClub, label: managedClubs.find(club => club.id === organizingClub)?.name ?? '' }
                                    : null
                            }
                            onChange={selected => setValue('organizing_club', selected ? selected.value : null)}
                            placeholder="No organizing club"
                            classNamePrefix="my-react-select"
                            styles={selectStyles}
                        />
                    </label>

                    <div className="card-actions justify-end">
                        <button type="submit" className="btn btn-primary" disabled={submitting}>
                            {submitting && <span className="loading loading-spinner"></span>}
                            Create contest and continue
                        </button>
                    </div>
                </form>
            )}
        </div>
    );
};

export default ContestCreationStep;
