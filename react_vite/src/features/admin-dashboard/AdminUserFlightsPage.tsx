import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import PersonPicker from '../../components/common/PersonPicker';
import { PersonOption } from '../../components/common/personOption';
import { FlightSummaryButton } from '../../components/common/FlightSummaryModal';
import { generatePath } from '../../urls';
import { AdminUserFlight, AdminUserFlightsResponse, fetchAdminUserFlights } from './api';

const formatTime = (iso: string) =>
    new Date(iso).toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

const status = (flight: AdminUserFlight): { label: string; badge: string } => {
    if (flight.calculator_finished) return { label: 'Scored', badge: 'badge-success' };
    if (flight.calculator_started) return { label: 'Scoring', badge: 'badge-info' };
    if (new Date(flight.finished_by_time) > new Date()) return { label: 'Upcoming', badge: 'badge-ghost' };
    return { label: 'Not flown', badge: 'badge-ghost' };
};

/** Site admins: pick anyone in the system and see every flight they have flown, as pilot or co-pilot. */
export default function AdminUserFlightsPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const personId = Number(searchParams.get('person')) || null;
    // The last answer and whom it was for: while it is for someone else, the chosen person's flights are loading
    const [result, setResult] = useState<{ personId: number; data?: AdminUserFlightsResponse; error?: string } | null>(null);
    const [filter, setFilter] = useState('');
    // Bumped when a summary modal closes, to list a summary written in it
    const [refreshes, setRefreshes] = useState(0);

    useEffect(() => {
        if (personId === null) return;
        let cancelled = false;
        fetchAdminUserFlights(personId)
            .then((data) => { if (!cancelled) setResult({ personId, data }); })
            .catch((err: Error) => { if (!cancelled) setResult({ personId, error: err.message }); });
        return () => { cancelled = true; };
    }, [personId, refreshes]);

    const current = personId !== null && result?.personId === personId ? result : null;
    const data = current?.data ?? null;
    const error = current?.error ?? null;
    const loading = personId !== null && current === null;

    const flights = useMemo(() => {
        const words = filter.trim().toLowerCase();
        if (!data) return [];
        if (!words) return data.flights;
        return data.flights.filter((flight) =>
            `${flight.contest_name} ${flight.navigation_task_name} ${flight.partner ?? ''} ${flight.aeroplane}`
                .toLowerCase()
                .includes(words),
        );
    }, [data, filter]);

    if (!document.configuration.is_superuser) {
        return (
            <div className="container mx-auto p-4 md:p-8">
                <div className="alert alert-error">Admins only.</div>
            </div>
        );
    }

    const picked: PersonOption | null = data && data.person.id === personId
        ? { value: data.person.id, name: data.person.name, country: '', picture: null, emailHint: '' }
        : null;

    return (
        <div className="container mx-auto p-4 md:p-8 flex flex-col gap-6">
            <h1 className="text-2xl font-bold">User flights</h1>

            <div className="card bg-base-100 shadow-xl">
                <div className="card-body gap-3">
                    <label className="text-sm font-medium" htmlFor="user-flights-person">
                        Anyone in the system, with or without an account
                    </label>
                    <div className="max-w-md">
                        <PersonPicker
                            kind="person"
                            inputId="user-flights-person"
                            value={picked}
                            excludeSelf={false}
                            placeholder="Search by name or e-mail"
                            onChange={(option) => {
                                setFilter('');
                                setSearchParams(option ? { person: String(option.value) } : {});
                            }}
                        />
                    </div>
                    {data && (
                        <p className="text-sm text-base-content/70">
                            {data.person.email} · {data.person.has_account ? 'has an account' : 'no account'} ·{' '}
                            {data.flights.length} {data.flights.length === 1 ? 'flight' : 'flights'}
                        </p>
                    )}
                </div>
            </div>

            {error && <div className="alert alert-error">{error}</div>}
            {loading && <span className="loading loading-spinner" />}

            {data && !loading && (
                <div className="card bg-base-100 shadow-xl">
                    <div className="card-body gap-3">
                        {data.flights.length > 5 && (
                            <input
                                type="search"
                                className="input input-bordered input-sm max-w-xs"
                                placeholder="Filter by contest, task, partner or aircraft"
                                value={filter}
                                onChange={(event) => setFilter(event.target.value)}
                            />
                        )}
                        {flights.length === 0 ? (
                            <p className="text-sm">{data.flights.length === 0 ? 'No flights.' : 'No flights match.'}</p>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Take-off</th>
                                            <th>Contest and task</th>
                                            <th>Role</th>
                                            <th>With</th>
                                            <th>Aircraft</th>
                                            <th>Status</th>
                                            <th className="text-right">Score</th>
                                            <th>AI summaries</th>
                                            <th />
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {flights.map((flight) => {
                                            const state = status(flight);
                                            return (
                                                <tr key={flight.id}>
                                                    <td className="whitespace-nowrap">{formatTime(flight.takeoff_time)}</td>
                                                    <td>
                                                        <div className="font-medium">{flight.contest_name}</div>
                                                        <div className="text-xs text-base-content/70">
                                                            {flight.navigation_task_name}
                                                            {flight.task_type && ` · ${flight.task_type}`} · #{flight.contestant_number}
                                                            {flight.flight_mode === 'simulator' && ' · simulator'}
                                                        </div>
                                                    </td>
                                                    <td className="capitalize">{flight.role}</td>
                                                    <td>{flight.partner ?? '-'}</td>
                                                    <td className="whitespace-nowrap">{flight.aeroplane}</td>
                                                    <td><span className={`badge badge-sm ${state.badge}`}>{state.label}</span></td>
                                                    <td className="text-right">{flight.score === null ? '-' : flight.score.toFixed(0)}</td>
                                                    <td className="text-xs">{flight.summary_styles.join(', ') || '-'}</td>
                                                    <td className="whitespace-nowrap">
                                                        <div className="flex items-center gap-3">
                                                            <a
                                                                className="link"
                                                                href={`${generatePath('COMPETITION_MAP_DETAIL', { contestId: flight.contest_id, navigationTaskId: flight.navigation_task_id })}?contestant=${flight.id}`}
                                                            >
                                                                Map
                                                            </a>
                                                            <Link
                                                                className="link"
                                                                to={generatePath('NAVIGATION_TASK_DETAIL', { contestId: flight.contest_id, navigationTaskId: flight.navigation_task_id })}
                                                            >
                                                                Task
                                                            </Link>
                                                            {flight.calculator_finished && <FlightSummaryButton contestantId={flight.id} onClose={() => setRefreshes((count) => count + 1)} />}
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
