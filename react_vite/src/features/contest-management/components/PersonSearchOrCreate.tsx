import React from 'react';
import { useFormContext } from 'react-hook-form';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { Copilot } from '../../mission-dashboard/types';
import { copilotForMode, pilotForMode } from '../teamRegistrationFlow';
import { TeamRegistrationFormValues } from '../schemas/teamRegistrationSchema';

interface PersonSearchOrCreateProps {
    field: 'pilot' | 'copilot';
    label: string;
    allowSkip: boolean;
    persons: Copilot[];
}

// Replaces RegisterTeamWizard's member1search/member1create (or member2search/member2create)
// step pair: search existing persons or fill in fields to create a new one. Picking a different
// person after typing "create" fields, or vice versa, resets the other mode's fields via
// pilotForMode/copilotForMode - editing after an "existing" match effectively starts a fresh
// selection rather than silently keeping stale data around.
const PersonSearchOrCreate: React.FC<PersonSearchOrCreateProps> = ({ field, label, allowSkip, persons }) => {
    const {
        register,
        setValue,
        watch,
        formState: { errors },
    } = useFormContext<TeamRegistrationFormValues>();
    const selection = watch(field) as { mode: string; person?: number };
    const mode = selection.mode;
    const fieldErrors = (errors[field] as any) || {};

    const setMode = (nextMode: 'existing' | 'create' | 'skip') => {
        const next = field === 'pilot' ? pilotForMode(nextMode as 'existing' | 'create') : copilotForMode(nextMode as any);
        setValue(field, next as any);
    };

    return (
        <div className="border border-base-300 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
                <span className="font-semibold">{label}</span>
                <div role="tablist" className="tabs tabs-boxed tabs-xs">
                    <button type="button" role="tab" className={`tab ${mode === 'existing' ? 'tab-active' : ''}`} onClick={() => setMode('existing')}>
                        Existing
                    </button>
                    <button type="button" role="tab" className={`tab ${mode === 'create' ? 'tab-active' : ''}`} onClick={() => setMode('create')}>
                        New
                    </button>
                    {allowSkip && (
                        <button type="button" role="tab" className={`tab ${mode === 'skip' ? 'tab-active' : ''}`} onClick={() => setMode('skip')}>
                            Skip
                        </button>
                    )}
                </div>
            </div>

            {mode === 'existing' && (
                <label className="form-control w-full">
                    <Select
                        options={persons.map(p => ({ value: p.id, label: `${p.first_name} ${p.last_name} (${p.email})` }))}
                        value={
                            selection.person
                                ? {
                                      value: selection.person,
                                      label: (() => {
                                          const p = persons.find(item => item.id === selection.person);
                                          return p ? `${p.first_name} ${p.last_name} (${p.email})` : String(selection.person);
                                      })(),
                                  }
                                : null
                        }
                        onChange={selected => setValue(`${field}.person` as any, selected ? selected.value : undefined)}
                        placeholder={`Search for ${label.toLowerCase()}`}
                        classNamePrefix="my-react-select"
                        styles={selectStyles}
                    />
                    {fieldErrors.person && <span className="text-error text-sm">{fieldErrors.person.message}</span>}
                    <span className="text-xs text-gray-500 mt-1">Details for an existing person will not be changed.</span>
                </label>
            )}

            {mode === 'create' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <label className="form-control w-full">
                        <input className="input input-bordered input-sm w-full" placeholder="First name" {...register(`${field}.first_name` as any)} />
                        {fieldErrors.first_name && <span className="text-error text-sm">{fieldErrors.first_name.message}</span>}
                    </label>
                    <label className="form-control w-full">
                        <input className="input input-bordered input-sm w-full" placeholder="Last name" {...register(`${field}.last_name` as any)} />
                        {fieldErrors.last_name && <span className="text-error text-sm">{fieldErrors.last_name.message}</span>}
                    </label>
                    <label className="form-control w-full">
                        <input className="input input-bordered input-sm w-full" placeholder="Email" {...register(`${field}.email` as any)} />
                        {fieldErrors.email && <span className="text-error text-sm">{fieldErrors.email.message}</span>}
                    </label>
                    <label className="form-control w-full">
                        <input className="input input-bordered input-sm w-full" placeholder="Phone" {...register(`${field}.phone` as any)} />
                    </label>
                </div>
            )}

            {mode === 'skip' && <p className="text-sm text-gray-500">No co-pilot for this team.</p>}
        </div>
    );
};

export default PersonSearchOrCreate;
