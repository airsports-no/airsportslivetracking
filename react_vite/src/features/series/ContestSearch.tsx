import React, { useEffect, useState } from 'react';
import { ContestSearchResult, searchContests } from './api';

interface Props {
    onPick: (contest: ContestSearchResult) => void;
    disabled?: boolean;
    placeholder?: string;
}

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 300;

/** Find a public contest by part of its name and pick it */
const ContestSearch: React.FC<Props> = ({ onPick, disabled, placeholder = 'Search for a public contest by name' }) => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<ContestSearchResult[]>([]);
    const [error, setError] = useState<string | null>(null);

    const searchable = query.trim().length >= MIN_QUERY_LENGTH;

    useEffect(() => {
        if (!searchable) return;
        let cancelled = false;
        const timer = setTimeout(() => {
            searchContests(query.trim())
                .then(found => {
                    if (cancelled) return;
                    setResults(found);
                    setError(null);
                })
                .catch(e => {
                    if (!cancelled) setError((e as Error).message);
                });
        }, DEBOUNCE_MS);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [query, searchable]);

    return (
        <div className="space-y-1">
            <input className="input input-bordered input-sm w-full" placeholder={placeholder} value={query} onChange={e => setQuery(e.target.value)} disabled={disabled} />
            {error && <div className="text-xs text-error">{error}</div>}
            {searchable && results.length > 0 && (
                <ul className="menu menu-sm bg-base-100 rounded-lg border border-base-300 max-h-48 overflow-y-auto flex-nowrap">
                    {results.map(contest => (
                        <li key={contest.id}>
                            <button
                                type="button"
                                disabled={disabled}
                                onClick={() => {
                                    onPick(contest);
                                    setQuery('');
                                    setResults([]);
                                }}
                            >
                                {contest.name}
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            {searchable && results.length === 0 && !error && <div className="text-xs opacity-60">No public contest found.</div>}
        </div>
    );
};

export default ContestSearch;
