import React, { useEffect, useRef } from 'react';
import AsyncSelect from 'react-select/async';
import { selectStyles } from '../../utils/selectStyles';
import { reverse } from '../../urls';
import { PersonOption, PersonSearchResult, personOptionFromSearchResult } from './personOption';

interface PersonPickerProps {
    /** person: anyone in the system (pilots, co-pilots). user: accounts only (permissions). */
    kind: 'person' | 'user';
    value: PersonOption | null;
    onChange: (option: PersonOption | null) => void;
    /** kind="person" only: leave yourself out of the results (default true) */
    excludeSelf?: boolean;
    placeholder?: string;
    isClearable?: boolean;
    isDisabled?: boolean;
    inputId?: string;
    /** Override for pages outside the SPA, where URL reversing is not initialised */
    searchUrl?: string;
}

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 250;

const isSearchable = (input: string) => input.trim().length >= MIN_QUERY_LENGTH || input.includes('@');

const fetchOptions = async (input: string, kind: string, excludeSelf: boolean, signal: AbortSignal, searchUrl?: string): Promise<PersonOption[]> => {
    const params = new URLSearchParams({ q: input.trim(), kind });
    if (kind === 'person' && !excludeSelf) {
        params.set('exclude_self', 'false');
    }
    const response = await fetch(`${searchUrl ?? reverse('people_search')}?${params.toString()}`, { signal, credentials: 'same-origin' });
    if (!response.ok) {
        // Includes 429 when the per-user search limit is hit; the picker just shows "no results"
        return [];
    }
    return ((await response.json()) as PersonSearchResult[]).map(personOptionFromSearchResult);
};

/**
 * Type-ahead picker for people. The server only ever returns names (plus country, and a heavily
 * masked email when two people would otherwise look identical), never an email address. Typing a
 * complete email address still finds exactly that person.
 */
const PersonPicker: React.FC<PersonPickerProps> = ({
    kind,
    value,
    onChange,
    excludeSelf = true,
    placeholder = 'Type a name to search',
    isClearable = true,
    isDisabled,
    inputId,
    searchUrl,
}) => {
    const timer = useRef<number | undefined>(undefined);
    const controller = useRef<AbortController | null>(null);
    const supersede = useRef<(() => void) | null>(null);

    useEffect(
        () => () => {
            window.clearTimeout(timer.current);
            controller.current?.abort();
        },
        []
    );

    // Debounced: a keystroke supersedes the previous pending search, so only the last one hits the server
    const loadOptions = (input: string) =>
        new Promise<PersonOption[]>(resolve => {
            window.clearTimeout(timer.current);
            controller.current?.abort();
            supersede.current?.();
            supersede.current = () => resolve([]);
            if (!isSearchable(input)) {
                resolve([]);
                return;
            }
            timer.current = window.setTimeout(async () => {
                controller.current = new AbortController();
                try {
                    resolve(await fetchOptions(input, kind, excludeSelf, controller.current.signal, searchUrl));
                } catch {
                    resolve([]);
                }
            }, DEBOUNCE_MS);
        });

    return (
        <AsyncSelect<PersonOption, false>
            inputId={inputId}
            cacheOptions
            // The server does the matching (names, or a complete email); filtering again on the
            // label here would hide an email-matched result.
            filterOption={null}
            loadOptions={loadOptions}
            value={value}
            onChange={option => onChange(option ?? null)}
            getOptionValue={option => String(option.value)}
            getOptionLabel={option => option.name}
            formatOptionLabel={option => (
                <div className="flex items-center gap-2">
                    {option.picture && <img src={option.picture} alt="" className="w-6 h-6 rounded-full object-cover" />}
                    <span>{option.name}</span>
                    {option.country && <span className="text-xs opacity-60">{option.country}</span>}
                    {option.emailHint && <span className="text-xs opacity-60 font-mono">{option.emailHint}</span>}
                </div>
            )}
            noOptionsMessage={({ inputValue }) =>
                isSearchable(inputValue) ? 'No one found' : 'Type at least 3 letters of the name, or a full email address'
            }
            loadingMessage={() => 'Searching...'}
            placeholder={placeholder}
            isClearable={isClearable}
            isDisabled={isDisabled}
            classNamePrefix="my-react-select"
            styles={selectStyles}
        />
    );
};

export default PersonPicker;
