import React from 'react';
import { useFormContext } from 'react-hook-form';
import CreatableSelect from 'react-select/creatable';
import { selectStyles } from '../../../utils/selectStyles';
import { Club } from '../../mission-dashboard/types';
import { TeamRegistrationFormValues } from '../schemas/teamRegistrationSchema';
import ImageUploadField from './ImageUploadField';

interface ClubSearchOrCreateProps {
    clubs: Club[];
}

// Same non-mutation-on-reuse notice as AeroplaneSearchOrCreate, for Club.country/logo.
const ClubSearchOrCreate: React.FC<ClubSearchOrCreateProps> = ({ clubs }) => {
    const {
        register,
        setValue,
        watch,
        formState: { errors },
    } = useFormContext<TeamRegistrationFormValues>();
    const name = watch('club.name');
    const logo = watch('club.logo');
    const existing = clubs.find(c => c.name === name);

    return (
        <div className="border border-base-300 rounded-lg p-4">
            <span className="font-semibold">Club</span>
            <div className="flex items-start gap-2 mt-2">
                {existing?.logo && (
                    <img src={existing.logo} alt="" className="w-8 h-8 rounded object-cover border border-base-300 flex-shrink-0 mt-1" />
                )}
                <label className="form-control w-full min-w-0">
                    <CreatableSelect
                        options={clubs.map(c => ({ value: c.name, label: c.name }))}
                        value={name ? { value: name, label: name } : null}
                        onChange={selected => setValue('club.name', selected ? selected.value : '')}
                        isClearable
                        placeholder="Select or type a club name"
                        classNamePrefix="my-react-select"
                        styles={selectStyles}
                    />
                    {errors.club?.name && <span className="text-error text-sm">{errors.club.name.message}</span>}
                </label>
            </div>
            {existing ? (
                <p className="text-xs text-gray-500 mt-2">
                    "{existing.name}" already exists ({existing.country}) - its details will not be changed.
                </p>
            ) : (
                <div className="space-y-2 mt-2">
                    <input className="input input-bordered input-sm w-full" placeholder="Country code (e.g. NO)" {...register('club.country')} />
                    <ImageUploadField label="Logo" value={logo} onChange={file => setValue('club.logo', file ?? undefined)} />
                </div>
            )}
        </div>
    );
};

export default ClubSearchOrCreate;
