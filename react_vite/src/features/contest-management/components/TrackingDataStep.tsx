import React from 'react';
import { useFormContext } from 'react-hook-form';
import { TeamRegistrationFormValues, TRACKING_DEVICE_CHOICES, TRACKING_SERVICE_CHOICES } from '../schemas/teamRegistrationSchema';

// The four TrackingDataForm fields (RegisterTeamWizard's last step) - reused for both a new
// registration and editing an existing one (today's inline "edit tracking device" affordance on
// contestteam_list.html reopens this same form with contest_team set).
const TrackingDataStep: React.FC = () => {
    const {
        register,
        watch,
        formState: { errors },
    } = useFormContext<TeamRegistrationFormValues>();
    const trackingDevice = watch('tracking_device');

    return (
        <div className="border border-base-300 rounded-lg p-4">
            <span className="font-semibold">Team contest information</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2">
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Airspeed (knots)</span></div>
                    <input type="number" className="input input-bordered input-sm w-full" {...register('air_speed', { valueAsNumber: true })} />
                    {errors.air_speed && <span className="text-error text-sm">{errors.air_speed.message}</span>}
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Tracking service</span></div>
                    <select className="select select-bordered select-sm w-full" {...register('tracking_service')}>
                        {TRACKING_SERVICE_CHOICES.map(choice => (
                            <option key={choice.value} value={choice.value}>
                                {choice.label}
                            </option>
                        ))}
                    </select>
                </label>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Tracking device</span></div>
                    <select className="select select-bordered select-sm w-full" {...register('tracking_device')}>
                        {TRACKING_DEVICE_CHOICES.map(choice => (
                            <option key={choice.value} value={choice.value}>
                                {choice.label}
                            </option>
                        ))}
                    </select>
                </label>
            </div>
            {trackingDevice === 'device' && (
                <label className="form-control w-full mt-2">
                    <div className="label"><span className="label-text">Tracker device ID</span></div>
                    <input className="input input-bordered input-sm w-full" {...register('tracker_device_id')} />
                </label>
            )}
        </div>
    );
};

export default TrackingDataStep;
