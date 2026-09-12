import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { fetchScorecardChoices } from '../api';
import {
    NavigationTaskDetailsFormValues,
    NavigationTaskDetailsInput,
    navigationTaskDetailsDefaults,
    navigationTaskDetailsSchema,
} from '../schemas/navigationTaskSchema';

interface TaskDetailsStepProps {
    taskType: string;
    onSubmit: (values: NavigationTaskDetailsFormValues) => void;
    submitting: boolean;
    submitLabel: string;
}

const TaskDetailsStep: React.FC<TaskDetailsStepProps> = ({ taskType, onSubmit, submitting, submitLabel }) => {
    const {
        register,
        handleSubmit,
        setValue,
        watch,
        formState: { errors },
    } = useForm<NavigationTaskDetailsInput, unknown, NavigationTaskDetailsFormValues>({
        resolver: zodResolver(navigationTaskDetailsSchema),
        defaultValues: navigationTaskDetailsDefaults,
    });

    const [scorecardOptions, setScorecardOptions] = useState<{ value: string; label: string }[]>([]);
    const originalScorecard = watch('original_scorecard');

    useEffect(() => {
        fetchScorecardChoices(taskType).then(scorecards => {
            const options = scorecards.map(scorecard => ({ value: scorecard.shortcut_name, label: scorecard.name }));
            setScorecardOptions(options);
            if (!originalScorecard && options.length > 0) {
                setValue('original_scorecard', options[0].value);
            }
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [taskType]);

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <label className="form-control w-full">
                <div className="label"><span className="label-text">Name</span></div>
                <input className="input input-bordered w-full" {...register('name')} />
                {errors.name && <span className="text-error text-sm">{errors.name.message}</span>}
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
                <div className="label"><span className="label-text">Scorecard</span></div>
                <Select
                    options={scorecardOptions}
                    value={scorecardOptions.find(option => option.value === originalScorecard) ?? null}
                    onChange={selected => selected && setValue('original_scorecard', selected.value)}
                    placeholder="Choose a scorecard"
                    classNamePrefix="my-react-select"
                    styles={selectStyles}
                />
                {errors.original_scorecard && <span className="text-error text-sm">{errors.original_scorecard.message}</span>}
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Minutes to starting point</span></div>
                    <input type="number" className="input input-bordered w-full" {...register('minutes_to_starting_point')} />
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Planning time (minutes)</span></div>
                    <input type="number" className="input input-bordered w-full" {...register('planning_time')} />
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Minutes to landing</span></div>
                    <input type="number" className="input input-bordered w-full" {...register('minutes_to_landing')} />
                </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Wind speed (0-40)</span></div>
                    <input type="number" className="input input-bordered w-full" {...register('wind_speed')} />
                    {errors.wind_speed && <span className="text-error text-sm">{errors.wind_speed.message}</span>}
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Wind direction (0-360)</span></div>
                    <input type="number" className="input input-bordered w-full" {...register('wind_direction')} />
                    {errors.wind_direction && <span className="text-error text-sm">{errors.wind_direction.message}</span>}
                </label>
            </div>

            <label className="form-control w-full">
                <div className="label"><span className="label-text">Calculation delay (minutes)</span></div>
                <input type="number" className="input input-bordered w-full" {...register('calculation_delay_minutes')} />
                {errors.calculation_delay_minutes && (
                    <span className="text-error text-sm">{errors.calculation_delay_minutes.message}</span>
                )}
            </label>

            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('display_background_map')} />
                <span className="label-text">Display background map</span>
            </label>
            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('display_secrets')} />
                <span className="label-text">Display secrets</span>
            </label>
            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('allow_self_management')} />
                <span className="label-text">Allow self-management</span>
            </label>

            <div className="card-actions justify-end">
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting && <span className="loading loading-spinner"></span>}
                    {submitLabel}
                </button>
            </div>
        </form>
    );
};

export default TaskDetailsStep;
