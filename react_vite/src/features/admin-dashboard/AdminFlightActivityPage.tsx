import React, { useEffect, useMemo, useState } from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';
import { Loading } from '../route-editor/components/basicComponents';
import { useToast } from '../competition-map/hooks/useToast';
import { fetchAdminFlightStats, fetchUpcomingContestants, FlightStatsBin, FlightStatsResponse, UpcomingContestant } from './api';
import { groupUpcomingContestants, UpcomingGrouping } from './groupUpcoming';

const BIN_OPTIONS: { value: FlightStatsBin; label: string }[] = [
    { value: 'hour', label: 'Hour' },
    { value: 'day', label: 'Day' },
    { value: 'week', label: 'Week' },
    { value: 'month', label: 'Month' },
    { value: 'year', label: 'Year' },
];

const RANGE_PRESETS: { days: number; label: string }[] = [
    { days: 14, label: '14d' },
    { days: 30, label: '30d' },
    { days: 90, label: '90d' },
    { days: 365, label: '1y' },
    { days: 3 * 365, label: '3y' },
    { days: 5 * 365, label: '5y' },
];

const STATUS_COLORS = {
    awaiting_start: 'var(--color-info)',
    flying: 'var(--color-warning)',
    finished: 'var(--color-success)',
};

const bucketFormatter = (bin: FlightStatsBin) => {
    const options: Intl.DateTimeFormatOptions =
        bin === 'hour'
            ? { month: 'short', day: 'numeric', hour: 'numeric' }
            : bin === 'day' || bin === 'week'
              ? { month: 'short', day: 'numeric' }
              : bin === 'month'
                ? { month: 'short', year: 'numeric' }
                : { year: 'numeric' };
    const formatter = new Intl.DateTimeFormat(undefined, options);
    return (isoString: string) => formatter.format(new Date(isoString));
};

function FlightStatusChart() {
    const { showToast } = useToast();
    const [days, setDays] = useState(30);
    const [bin, setBin] = useState<FlightStatsBin>('day');
    const [data, setData] = useState<FlightStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        fetchAdminFlightStats(days, bin)
            .then((response) => {
                if (!cancelled) setData(response);
            })
            .catch((err: any) => {
                if (!cancelled) showToast(err.message ?? 'Failed to load flight stats.', 'error');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [days, bin, showToast]);

    const formatBucket = useMemo(() => bucketFormatter(bin), [bin]);

    const chartData = useMemo(
        () =>
            (data?.series ?? []).map((row) => ({
                ...row,
                label: formatBucket(row.bucket_start),
            })),
        [data, formatBucket],
    );

    const personsData = useMemo(
        () =>
            (data?.unique_persons_series ?? []).map((row) => ({
                ...row,
                label: formatBucket(row.bucket_start),
            })),
        [data, formatBucket],
    );

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                    <div>
                        <h2 className="card-title">Contestants flying over time</h2>
                        <p className="text-sm text-base-content/70">
                            Calculator-started contestants only, split by whether they have crossed the starting and
                            finish lines. Times shown in UTC.
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="join">
                            {RANGE_PRESETS.map((preset) => (
                                <button
                                    key={preset.days}
                                    className={`btn btn-sm join-item ${days === preset.days ? 'btn-primary' : 'btn-ghost'}`}
                                    onClick={() => setDays(preset.days)}
                                >
                                    {preset.label}
                                </button>
                            ))}
                        </div>
                        <select
                            className="select select-sm select-bordered"
                            value={bin}
                            onChange={(e) => setBin(e.target.value as FlightStatsBin)}
                        >
                            {BIN_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {loading ? (
                    <Loading />
                ) : chartData.length === 0 ? (
                    <div className="text-sm text-base-content/60 py-8 text-center">
                        No calculator-started contestants in this window.
                    </div>
                ) : (
                    <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData} barCategoryGap="20%">
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-base-300)" />
                                <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                <Tooltip
                                    contentStyle={{
                                        background: 'var(--color-base-100)',
                                        border: '1px solid var(--color-base-300)',
                                        borderRadius: '0.5rem',
                                    }}
                                />
                                <Legend
                                    formatter={(value) =>
                                        value === 'awaiting_start' ? 'Awaiting start' : value === 'flying' ? 'Flying' : 'Finished'
                                    }
                                />
                                <Bar dataKey="awaiting_start" stackId="status" fill={STATUS_COLORS.awaiting_start} radius={[0, 0, 0, 0]} />
                                <Bar dataKey="flying" stackId="status" fill={STATUS_COLORS.flying} />
                                <Bar dataKey="finished" stackId="status" fill={STATUS_COLORS.finished} radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}

                <div className="divider" />

                <h3 className="font-semibold text-sm text-base-content/80">Unique participants</h3>
                <p className="text-xs text-base-content/60 mb-2">
                    Distinct pilots and copilots among calculator-started contestants, bucketed the same as the chart
                    above.
                </p>
                {loading ? (
                    <Loading />
                ) : personsData.length === 0 ? (
                    <div className="text-sm text-base-content/60 py-4 text-center">No data in this window.</div>
                ) : (
                    <div className="h-56">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={personsData} barCategoryGap="20%">
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-base-300)" />
                                <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                <Tooltip
                                    contentStyle={{
                                        background: 'var(--color-base-100)',
                                        border: '1px solid var(--color-base-300)',
                                        borderRadius: '0.5rem',
                                    }}
                                />
                                <Bar dataKey="count" name="Unique participants" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>
        </div>
    );
}

const GROUPING_OPTIONS: { value: UpcomingGrouping; label: string }[] = [
    { value: 'day', label: 'Day' },
    { value: 'week', label: 'Week' },
    { value: 'month', label: 'Month' },
];

function UpcomingContestantsList() {
    const { showToast } = useToast();
    const [days, setDays] = useState(14);
    const [grouping, setGrouping] = useState<UpcomingGrouping>('day');
    const [contestants, setContestants] = useState<UpcomingContestant[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        fetchUpcomingContestants(days)
            .then((response) => {
                if (!cancelled) setContestants(response);
            })
            .catch((err: any) => {
                if (!cancelled) showToast(err.message ?? 'Failed to load upcoming contestants.', 'error');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [days, showToast]);

    const groups = useMemo(() => groupUpcomingContestants(contestants, grouping), [contestants, grouping]);

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                    <div>
                        <h2 className="card-title">Upcoming contestants</h2>
                        <p className="text-sm text-base-content/70">
                            Every contestant with a future takeoff time, so expected activity over the next few days or
                            weeks is visible at a glance.
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="join">
                            {[14, 30, 90].map((preset) => (
                                <button
                                    key={preset}
                                    className={`btn btn-sm join-item ${days === preset ? 'btn-primary' : 'btn-ghost'}`}
                                    onClick={() => setDays(preset)}
                                >
                                    {preset}d
                                </button>
                            ))}
                        </div>
                        <select
                            className="select select-sm select-bordered"
                            value={grouping}
                            onChange={(e) => setGrouping(e.target.value as UpcomingGrouping)}
                        >
                            {GROUPING_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                    Group by {option.label.toLowerCase()}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {loading ? (
                    <Loading />
                ) : groups.length === 0 ? (
                    <div className="text-sm text-base-content/60 py-8 text-center">
                        No contestants scheduled in the next {days} days.
                    </div>
                ) : (
                    <div className="flex flex-col gap-4 max-h-[32rem] overflow-y-auto">
                        {groups.map((group) => (
                            <div key={group.key}>
                                <div className="flex items-center gap-2 mb-1">
                                    <h3 className="font-semibold text-sm">{group.label}</h3>
                                    <span className="badge badge-neutral badge-sm">{group.contestants.length}</span>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>Takeoff</th>
                                                <th>Contest</th>
                                                <th>Task</th>
                                                <th>Team</th>
                                                <th>Aeroplane</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {group.contestants.map((contestant) => (
                                                <tr key={contestant.id}>
                                                    <td className="whitespace-nowrap">
                                                        {new Date(contestant.takeoff_time).toLocaleString(undefined, {
                                                            weekday: 'short',
                                                            month: 'short',
                                                            day: 'numeric',
                                                            hour: '2-digit',
                                                            minute: '2-digit',
                                                        })}
                                                    </td>
                                                    <td>{contestant.contest_name}</td>
                                                    <td>{contestant.navigation_task_name}</td>
                                                    <td>{contestant.team}</td>
                                                    <td>{contestant.aeroplane}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

export default function AdminFlightActivityPage() {
    if (!document.configuration.is_superuser) {
        return (
            <div className="container mx-auto p-4 md:p-8">
                <div className="alert alert-error">Admins only.</div>
            </div>
        );
    }

    return (
        <div className="container mx-auto p-4 md:p-8 flex flex-col gap-6">
            <h1 className="text-2xl font-bold">Flight activity</h1>
            <FlightStatusChart />
            <UpcomingContestantsList />
        </div>
    );
}
