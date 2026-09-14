import React, { useState } from 'react';
import { useFormContext } from 'react-hook-form';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { Copilot } from '../../mission-dashboard/types';
import { copilotForMode, pilotForMode } from '../teamRegistrationFlow';
import { TeamRegistrationFormValues } from '../schemas/teamRegistrationSchema';
import ImageUploadField from './ImageUploadField';
import { removePersonPictureBackground } from '../api';

interface PersonSearchOrCreateProps {
    field: 'pilot' | 'copilot';
    label: string;
    allowSkip: boolean;
    persons: Copilot[];
    contestId: number;
}

// Replaces RegisterTeamWizard's member1search/member1create (or member2search/member2create)
// step pair: search existing persons or fill in fields to create a new one. Picking a different
// person after typing "create" fields, or vice versa, resets the other mode's fields via
// pilotForMode/copilotForMode - editing after an "existing" match effectively starts a fresh
// selection rather than silently keeping stale data around.
const PersonSearchOrCreate: React.FC<PersonSearchOrCreateProps> = ({ field, label, allowSkip, persons, contestId }) => {
    const {
        register,
        setValue,
        watch,
        formState: { errors },
    } = useFormContext<TeamRegistrationFormValues>();
    const selection = watch(field) as { mode: string; person?: number; picture?: File };
    const mode = selection.mode;
    const fieldErrors = (errors[field] as any) || {};
    const selectedExistingPerson = mode === 'existing' ? persons.find(p => p.id === selection.person) : undefined;

    // Overrides the selected person's displayed picture with the freshly-processed one, without
    // waiting for the parent's `persons` list (a store-wide fetch) to refresh - keyed by person id
    // so switching the selection doesn't show a stale override for a different person.
    const [backgroundRemoved, setBackgroundRemoved] = useState<{ personId: number; pictureUrl: string } | null>(null);
    const [removingBackground, setRemovingBackground] = useState(false);
    const [backgroundError, setBackgroundError] = useState<string | null>(null);
    const displayedPictureUrl =
        backgroundRemoved && backgroundRemoved.personId === selectedExistingPerson?.id
            ? backgroundRemoved.pictureUrl
            : selectedExistingPerson?.picture;

    const setMode = (nextMode: 'existing' | 'create' | 'skip') => {
        const next = field === 'pilot' ? pilotForMode(nextMode as 'existing' | 'create') : copilotForMode(nextMode as any);
        setValue(field, next as any);
    };

    const handleRemoveBackground = async () => {
        if (!selectedExistingPerson) return;
        setRemovingBackground(true);
        setBackgroundError(null);
        try {
            const pictureUrl = await removePersonPictureBackground(contestId, selectedExistingPerson.id);
            setBackgroundRemoved({ personId: selectedExistingPerson.id, pictureUrl });
        } catch (err) {
            setBackgroundError((err as Error).message);
        } finally {
            setRemovingBackground(false);
        }
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
                <div className="flex items-start gap-2">
                    {displayedPictureUrl && (
                        <div className="flex flex-col items-center gap-1 flex-shrink-0">
                            <img
                                src={displayedPictureUrl}
                                alt=""
                                className="w-8 h-8 rounded-full object-cover border border-base-300 mt-1"
                            />
                            <button
                                type="button"
                                className="btn btn-2xs btn-ghost px-1"
                                disabled={removingBackground}
                                onClick={handleRemoveBackground}
                                title="Remove the background from this photo"
                            >
                                {removingBackground ? <span className="loading loading-spinner loading-xs"></span> : 'Remove bg'}
                            </button>
                        </div>
                    )}
                    <label className="form-control w-full min-w-0">
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
                        {backgroundError && <span className="text-error text-sm">{backgroundError}</span>}
                        <span className="text-xs text-gray-500 mt-1">Details for an existing person will not be changed.</span>
                    </label>
                </div>
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
                    <div className="sm:col-span-2">
                        <ImageUploadField
                            label="Photo"
                            value={selection.picture}
                            onChange={file => setValue(`${field}.picture` as any, file ?? undefined)}
                        />
                    </div>
                </div>
            )}

            {mode === 'skip' && <p className="text-sm text-gray-500">No co-pilot for this team.</p>}
        </div>
    );
};

export default PersonSearchOrCreate;
