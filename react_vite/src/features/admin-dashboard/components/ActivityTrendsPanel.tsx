import React, { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Loading } from '../../route-editor/components/basicComponents';
import { useToast } from '../../competition-map/hooks/useToast';
import { fetchAdminActivityTrends, FlightStatsBin } from '../api';
import { bucketFormatter } from '../bucketFormatter';

const BIN_OPTIONS: { value: FlightStatsBin; label: string }[] = [
    { value: 'day', label: 'Day' },
    { value: 'week', label: 'Week' },
    { value: 'month', label: 'Month' },
    { value: 'year', label: 'Year' },
];

const RANGE_PRESETS = [
    { days: 90, label: '90d' },
    { days: 365, label: '1y' },
    { days: 3 * 365, label: '3y' },
    { days: 5 * 365, label: '5y' },
];

type ViewMode = 'period' | 'cumulative';

export default function ActivityTrendsPanel() {
    const { showToast } = useToast();
    const [days, setDays] = useState(365);
    const [bin, setBin] = useState<FlightStatsBin>('month');
    const [viewMode, setViewMode] = useState<ViewMode>('period');
    const [rows, setRows] = useState<{ bucket_start: string; contests: number; tasks: number }[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        fetchAdminActivityTrends(days, bin)
            .then((response) => {
                if (!cancelled) setRows(response.series);
            })
            .catch((err: any) => {
                if (!cancelled) showToast(err.message ?? 'Failed to load activity trends.', 'error');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [days, bin, showToast]);

    const formatBucket = useMemo(() => bucketFormatter(bin), [bin]);
    const chartData = useMemo(() => {
        const withLabels = rows.map((row) => ({ ...row, label: formatBucket(row.bucket_start) }));
        if (viewMode === 'period') return withLabels;
        let contestsRunningTotal = 0;
        let tasksRunningTotal = 0;
        return withLabels.map((row) => {
            contestsRunningTotal += row.contests;
            tasksRunningTotal += row.tasks;
            return { ...row, contests: contestsRunningTotal, tasks: tasksRunningTotal };
        });
    }, [rows, formatBucket, viewMode]);

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                    <div>
                        <h2 className="card-title">Growth over time</h2>
                        <p className="text-sm text-base-content/70">
                            Contests and navigation tasks by when they happened (start time - neither model records
                            when it was created).
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="join">
                            <button
                                className={`btn btn-sm join-item ${viewMode === 'period' ? 'btn-primary' : 'btn-ghost'}`}
                                onClick={() => setViewMode('period')}
                            >
                                Per period
                            </button>
                            <button
                                className={`btn btn-sm join-item ${viewMode === 'cumulative' ? 'btn-primary' : 'btn-ghost'}`}
                                onClick={() => setViewMode('cumulative')}
                            >
                                Cumulative
                            </button>
                        </div>
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
                    <div className="text-sm text-base-content/60 py-8 text-center">No activity in this window.</div>
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
                                <Legend />
                                <Bar dataKey="contests" name="Contests" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="tasks" name="Tasks" fill="var(--color-secondary)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>
        </div>
    );
}
