import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { useMissionDashboardStore } from '../../mission-dashboard/store';
import { Contest } from '../../mission-dashboard/types';
import { contestSettingsSchema, ContestSettingsFormValues } from '../schemas/contestSettingsSchema';
import { contestLocalTimeToIso } from '../navigationTaskFlow';
import { updateContest, shareContest } from '../../mission-dashboard/api';

interface Props {
    contest: Contest;
    onSaved: () => void;
}

const TIME_ZONES: string[] = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];

// Local-time-input -> ISO string, mirroring the timezone offset the backend actually stores the
// value at, so re-opening this form later shows the same wall-clock time it was saved with.
const isoToLocalInput = (iso: string, timeZone: string): string => {
    const date = new Date(iso);
    const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
    }).formatToParts(date);
    const get = (type: string) => parts.find(p => p.type === type)?.value ?? '00';
    return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
};

const ContestSettingsForm: React.FC<Props> = ({ contest, onSaved }) => {
    const { managedClubs, fetchManagedClubs } = useMissionDashboardStore();
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [sharing, setSharing] = useState(false);

    useEffect(() => {
        fetchManagedClubs().catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const {
        register,
        handleSubmit,
        setValue,
        watch,
        formState: { errors },
    } = useForm<ContestSettingsFormValues>({
        resolver: zodResolver(contestSettingsSchema),
        defaultValues: {
            name: contest.name,
            time_zone: contest.time_zone,
            location: contest.location,
            start_time: isoToLocalInput(contest.start_time, contest.time_zone),
            finish_time: isoToLocalInput(contest.finish_time, contest.time_zone),
            organizing_club: contest.organizing_club ?? null,
            contest_website: contest.contest_website ?? '',
            summary_score_sorting_direction: (contest.summary_score_sorting_direction as 'asc' | 'desc') ?? 'desc',
            autosum_scores: contest.autosum_scores ?? false,
        },
    });
    const timeZone = watch('time_zone');
    const organizingClub = watch('organizing_club');
    const sortingDirection = watch('summary_score_sorting_direction');

    const onSubmit = async (values: ContestSettingsFormValues) => {
        setSubmitting(true);
        setError(null);
        try {
            await updateContest(contest.id, {
                ...values,
                start_time: contestLocalTimeToIso(values.start_time, values.time_zone),
                finish_time: contestLocalTimeToIso(values.finish_time, values.time_zone),
            } as Partial<Contest>);
            onSaved();
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setSubmitting(false);
        }
    };

    const handlePublicityChange = async (visibility: 'public' | 'private' | 'unlisted') => {
        setSharing(true);
        setError(null);
        try {
            await shareContest(contest.id, visibility);
            onSaved();
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setSharing(false);
        }
    };

    return (
        <div className="space-y-4">
            {error && <div className="alert alert-error">{error}</div>}

            <div>
                <div className="label"><span className="label-text">Publicity</span></div>
                <div className="join">
                    {/* Mirrors Contest.share_string: public+featured = public, public+unfeatured = unlisted, else private. */}
                    {(() => {
                        const currentVisibility = contest.is_public
                            ? contest.is_featured
                                ? 'public'
                                : 'unlisted'
                            : 'private';
                        return (['public', 'unlisted', 'private'] as const).map(visibility => (
                            <button
                                key={visibility}
                                type="button"
                                disabled={sharing}
                                className={`btn btn-sm join-item ${visibility === currentVisibility ? 'btn-active' : ''}`}
                                onClick={() => handlePublicityChange(visibility)}
                            >
                                {visibility}
                            </button>
                        ));
                    })()}
                </div>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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

                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Contest website (optional)</span></div>
                    <input className="input input-bordered w-full" placeholder="https://..." {...register('contest_website')} />
                    {errors.contest_website && <span className="text-error text-sm">{errors.contest_website.message}</span>}
                </label>

                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Summary score sorting</span></div>
                    <select className="select select-bordered w-full" value={sortingDirection} onChange={e => setValue('summary_score_sorting_direction', e.target.value as 'asc' | 'desc')}>
                        <option value="desc">Highest score first</option>
                        <option value="asc">Lowest score first</option>
                    </select>
                </label>

                <label className="label cursor-pointer justify-start gap-3">
                    <input type="checkbox" className="checkbox" {...register('autosum_scores')} />
                    <span className="label-text">Automatically sum scores across tasks</span>
                </label>

                <div className="card-actions justify-end">
                    <button type="submit" className="btn btn-primary" disabled={submitting}>
                        {submitting && <span className="loading loading-spinner"></span>}
                        Save settings
                    </button>
                </div>
            </form>
        </div>
    );
};

export default ContestSettingsForm;
