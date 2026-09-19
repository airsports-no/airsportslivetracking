import React, { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Loading } from '../../route-editor/components/basicComponents';
import { CountryStatsRow } from '../api';

const TOP_N = 15;

interface Props {
    rows: CountryStatsRow[] | null;
    loading: boolean;
}

export default function CountryStatsPanel({ rows, loading }: Props) {
    const chartRows = useMemo(() => (rows ?? []).slice(0, TOP_N).map((row) => ({ ...row, label: row.country_name })), [rows]);

    const flagUrl = (code: string) => `${document.configuration.STATIC_FILE_LOCATION}flags/3x2/${code}.svg`;

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h2 className="card-title">Where the platform is used</h2>
                <p className="text-sm text-base-content/70 mb-2">
                    Navigation tasks, contests, and contestants per country, from each task's location. Tasks without a
                    resolved location yet are grouped as "Unknown".
                </p>

                {loading ? (
                    <Loading />
                ) : !rows || rows.length === 0 ? (
                    <div className="text-sm text-base-content/60 py-8 text-center">No data yet.</div>
                ) : (
                    <>
                        <div className="h-96">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartRows} layout="vertical" margin={{ left: 24 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-base-300)" />
                                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                    <YAxis
                                        type="category"
                                        dataKey="label"
                                        tick={{ fontSize: 12 }}
                                        stroke="var(--color-base-content)"
                                        width={120}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'var(--color-base-100)',
                                            border: '1px solid var(--color-base-300)',
                                            borderRadius: '0.5rem',
                                        }}
                                    />
                                    <Bar dataKey="tasks" name="Tasks" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>

                        <div className="overflow-x-auto mt-4">
                            <table className="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Country</th>
                                        <th className="text-right">Contests</th>
                                        <th className="text-right">Tasks</th>
                                        <th className="text-right">Contestants</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row) => (
                                        <tr key={row.country_code || row.country_name}>
                                            <td className="flex items-center gap-2">
                                                {row.country_code && (
                                                    <img src={flagUrl(row.country_code)} alt="" className="h-3 w-5 object-cover rounded-sm" />
                                                )}
                                                {row.country_name}
                                            </td>
                                            <td className="text-right">{row.contests}</td>
                                            <td className="text-right">{row.tasks}</td>
                                            <td className="text-right">{row.contestants}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
