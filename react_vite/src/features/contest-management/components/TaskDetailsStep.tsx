import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { fetchScorecardChoices } from '../api';
import HelpIcon from '../../../components/common/HelpIcon';
import SimulatorPolicyChoice from '../../../components/common/SimulatorPolicyChoice';
import { SimulatorPolicy } from '../../../utils/simulatorPolicy';
import {
    NavigationTaskDetailsFormValues,
    NavigationTaskDetailsInput,
    navigationTaskDetailsDefaults,
    navigationTaskDetailsSchema,
} from '../schemas/navigationTaskSchema';

interface TaskDetailsStepProps {
    taskType: string;
    // A CIMA subtype is offered only its own scorecard, a legacy task only the legacy ones
    taskSubtype: string;
    onSubmit: (values: NavigationTaskDetailsFormValues) => void;
    submitting: boolean;
    submitLabel: string;
}

const TaskDetailsStep: React.FC<TaskDetailsStepProps> = ({ taskType, taskSubtype, onSubmit, submitting, submitLabel }) => {
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
    const [scorecardsLoading, setScorecardsLoading] = useState(true);
    const [scorecardsError, setScorecardsError] = useState<string | null>(null);
    const [retryCount, setRetryCount] = useState(0);
    const originalScorecard = watch('original_scorecard');

    // The simulator policy is chosen with radio buttons that set the value directly: register it so it is always part of the submission
    useEffect(() => {
        register('simulator_policy');
    }, [register]);

    useEffect(() => {
        let cancelled = false;
        setScorecardsLoading(true);
        setScorecardsError(null);
        fetchScorecardChoices(taskType, taskSubtype)
            .then(scorecards => {
                if (cancelled) return;
                const options = scorecards.map(scorecard => ({ value: scorecard.shortcut_name, label: scorecard.name }));
                setScorecardOptions(options);
                if (!options.some(option => option.value === originalScorecard) && options.length > 0) {
                    setValue('original_scorecard', options[0].value);
                }
            })
            .catch(err => {
                if (!cancelled) setScorecardsError((err as Error).message);
            })
            .finally(() => {
                if (!cancelled) setScorecardsLoading(false);
            });
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [taskType, taskSubtype, retryCount]);

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <label className="form-control w-full">
                <div className="label"><span className="label-text">Name</span></div>
                <input className="input input-bordered w-full" {...register('name')} />
                {errors.name && <span className="text-error text-sm">{errors.name.message}</span>}
            </label>

            <SimulatorPolicyChoice
                value={(watch('simulator_policy') ?? 'not_allowed') as SimulatorPolicy}
                onChange={(policy) => setValue('simulator_policy', policy, { shouldDirty: true })}
                suggestSelfManagement={!watch('allow_self_management')}
            />

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
                <div className="label"><span className="label-text inline-flex items-center">Scorecard<HelpIcon text="The scoring rules for this task (penalties per mistake, etc). A sensible default is preselected; you can change it later from the task page." /></span></div>
                {scorecardsError ? (
                    <div className="alert alert-error">
                        <span>Failed to load scorecards: {scorecardsError}</span>
                        <button type="button" className="btn btn-sm" onClick={() => setRetryCount(count => count + 1)}>
                            Retry
                        </button>
                    </div>
                ) : (
                    <Select
                        isLoading={scorecardsLoading}
                        options={scorecardOptions}
                        value={scorecardOptions.find(option => option.value === originalScorecard) ?? null}
                        onChange={selected => selected && setValue('original_scorecard', selected.value)}
                        placeholder="Choose a scorecard"
                        classNamePrefix="my-react-select"
                        styles={selectStyles}
                    />
                )}
                {errors.original_scorecard && <span className="text-error text-sm">{errors.original_scorecard.message}</span>}
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <label className="form-control w-full">
                    <div className="label"><span className="label-text inline-flex items-center">Minutes to starting point<HelpIcon text="Minutes from take-off until the pilot should be over the starting point. Used to calculate take-off times." /></span></div>
                    <input type="number" className="input input-bordered w-full" {...register('minutes_to_starting_point')} />
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text inline-flex items-center">Planning time (minutes)<HelpIcon text="How long each team has for planning. Only used for the planning time column in the starting table." /></span></div>
                    <input type="number" className="input input-bordered w-full" {...register('planning_time')} />
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text inline-flex items-center">Minutes to landing<HelpIcon text="Minutes from the finish point until the pilot should have landed." /></span></div>
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
                <div className="label"><span className="label-text inline-flex items-center">Calculation delay (minutes)<HelpIcon text="Delays positions and scores on the public tracking map by this many minutes. Use 0 for no delay." /></span></div>
                <input type="number" className="input input-bordered w-full" {...register('calculation_delay_minutes')} />
                {errors.calculation_delay_minutes && (
                    <span className="text-error text-sm">{errors.calculation_delay_minutes.message}</span>
                )}
            </label>

            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('display_background_map')} />
                <span className="label-text inline-flex items-center">Display background map<HelpIcon text="Show map tiles on the online tracking map. Untick for a blank map." /></span>
            </label>
            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('display_secrets')} />
                <span className="label-text inline-flex items-center">Display secrets<HelpIcon text="Show secret gates (and their annotations) on the tracking map. Untick to show only the gates that are not secret." /></span>
            </label>
            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('allow_self_management')} />
                <span className="label-text inline-flex items-center">Allow self-management<HelpIcon text="Lets pilots who are registered for the contest book their own start time. The task must also be public and featured for pilots to see it." /></span>
            </label>
            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('allow_observation_registration')} />
                <span className="label-text inline-flex items-center">Allow observation registration in the app<HelpIcon text="Lets crews register observation photos from the app while they are being tracked. Registered observations are scored, and photos that are never marked count as missed when the flight ends. Crews can mark, change or cancel observations until five minutes after the tracking window; after that nothing can be changed." /></span>
            </label>
            <label className="label cursor-pointer justify-start gap-3">
                <input type="checkbox" className="checkbox" {...register('show_live_score_in_app')} />
                <span className="label-text inline-flex items-center">Show live feedback to pilots in the app<HelpIcon text="Pilots see their score so far in the mobile app while they fly, and training mode shows how early or late they were at each gate. Switch it off when pilots should not see any of this until the results are published. A calculation delay holds it back as well." /></span>
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
