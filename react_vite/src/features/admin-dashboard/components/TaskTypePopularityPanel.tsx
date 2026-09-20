import React, { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Loading } from '../../route-editor/components/basicComponents';

const prettify = (subtype: string) =>
    subtype
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

interface Props {
    rows: { task_subtype: string; count: number }[] | null;
    loading: boolean;
}

export default function TaskTypePopularityPanel({ rows, loading }: Props) {
    const chartRows = useMemo(
        () => (rows ?? []).map((row) => ({ ...row, label: prettify(row.task_subtype) })),
        [rows],
    );

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h2 className="card-title">Task type popularity</h2>
                <p className="text-sm text-base-content/70 mb-2">Which navigation task types actually get used.</p>

                {loading ? (
                    <Loading />
                ) : chartRows.length === 0 ? (
                    <div className="text-sm text-base-content/60 py-8 text-center">No tasks yet.</div>
                ) : (
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartRows} layout="vertical" margin={{ left: 24 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-base-300)" />
                                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                <YAxis type="category" dataKey="label" tick={{ fontSize: 12 }} stroke="var(--color-base-content)" width={160} />
                                <Tooltip
                                    contentStyle={{
                                        background: 'var(--color-base-100)',
                                        border: '1px solid var(--color-base-300)',
                                        borderRadius: '0.5rem',
                                    }}
                                />
                                <Bar dataKey="count" name="Tasks" fill="var(--color-accent)" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>
        </div>
    );
}
