import React from 'react';
import { useFormContext } from 'react-hook-form';
import CreatableSelect from 'react-select/creatable';
import { selectStyles } from '../../../utils/selectStyles';
import { Aircraft } from '../../mission-dashboard/types';
import { TeamRegistrationFormValues } from '../schemas/teamRegistrationSchema';

interface AeroplaneSearchOrCreateProps {
    aircrafts: Aircraft[];
}

// Type/colour are only ever applied by the backend when the registration doesn't match an
// existing Aeroplane (see get_or_create_aeroplane) - RegisterTeamWizard used to overwrite an
// existing, possibly shared aeroplane's fields on every registration that reused it. The notice
// below makes that non-mutation visible rather than silently ignoring the type/colour inputs.
const AeroplaneSearchOrCreate: React.FC<AeroplaneSearchOrCreateProps> = ({ aircrafts }) => {
    const {
        register,
        setValue,
        watch,
        formState: { errors },
    } = useFormContext<TeamRegistrationFormValues>();
    const registration = watch('aeroplane.registration');
    const existing = aircrafts.find(a => a.registration === registration);

    return (
        <div className="border border-base-300 rounded-lg p-4">
            <span className="font-semibold">Aeroplane</span>
            <label className="form-control w-full mt-2">
                <CreatableSelect
                    options={aircrafts.map(a => ({ value: a.registration, label: a.registration }))}
                    value={registration ? { value: registration, label: registration } : null}
                    onChange={selected => setValue('aeroplane.registration', selected ? selected.value : '')}
                    isClearable
                    placeholder="Select or type a registration"
                    classNamePrefix="my-react-select"
                    styles={selectStyles}
                />
                {errors.aeroplane?.registration && <span className="text-error text-sm">{errors.aeroplane.registration.message}</span>}
            </label>
            {existing ? (
                <p className="text-xs text-gray-500 mt-2">
                    "{existing.registration}" already exists ({existing.type}, {existing.colour}) - its details will not be changed.
                </p>
            ) : (
                <div className="grid grid-cols-2 gap-2 mt-2">
                    <input className="input input-bordered input-sm w-full" placeholder="Type (e.g. Cessna 172)" {...register('aeroplane.type')} />
                    <input className="input input-bordered input-sm w-full" placeholder="Colour" {...register('aeroplane.colour')} />
                </div>
            )}
        </div>
    );
};

export default AeroplaneSearchOrCreate;
