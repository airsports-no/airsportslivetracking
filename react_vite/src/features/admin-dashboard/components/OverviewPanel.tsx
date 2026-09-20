import React from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Loading } from '../../route-editor/components/basicComponents';
import { OverviewStats } from '../api';
import StatCard from './StatCard';

const numberFormatter = new Intl.NumberFormat();

interface Props {
    overview: OverviewStats | null;
    loading: boolean;
}

function TopListChart({ title, rows, dataKey, labelKey }: { title: string; rows: { count: number }[]; dataKey: string; labelKey: string }) {
    if (rows.length === 0) {
        return (
            <div>
                <h3 className="font-semibold text-sm text-base-content/80 mb-2">{title}</h3>
                <div className="text-sm text-base-content/60 py-4 text-center">No data yet.</div>
            </div>
        );
    }
    return (
        <div>
            <h3 className="font-semibold text-sm text-base-content/80 mb-2">{title}</h3>
            <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={rows} layout="vertical" margin={{ left: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-base-300)" />
                        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                        <YAxis type="category" dataKey={labelKey} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" width={120} />
                        <Tooltip
                            contentStyle={{
                                background: 'var(--color-base-100)',
                                border: '1px solid var(--color-base-300)',
                                borderRadius: '0.5rem',
                            }}
                        />
                        <Bar dataKey={dataKey} fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

export default function OverviewPanel({ overview, loading }: Props) {
    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h2 className="card-title">Platform overview</h2>
                <p className="text-sm text-base-content/70 mb-2">
                    Headline scale numbers - useful for a quick pulse check or a marketing/impact summary.
                </p>

                {loading || !overview ? (
                    <Loading />
                ) : (
                    <>
                        <div className="stats stats-vertical sm:stats-horizontal shadow mb-4 flex-wrap">
                            <StatCard label="Contests" value={numberFormatter.format(overview.number_of_contests)} />
                            <StatCard label="Navigation tasks" value={numberFormatter.format(overview.number_of_tasks)} />
                            <StatCard label="Contestants" value={numberFormatter.format(overview.number_of_contestants)} />
                            <StatCard label="Pilots & copilots" value={numberFormatter.format(overview.number_of_persons)} />
                            <StatCard label="Countries reached" value={numberFormatter.format(overview.number_of_countries_reached)} />
                            <StatCard
                                label="GPS positions tracked"
                                value={numberFormatter.format(overview.total_gps_positions)}
                                sublabel="Approximate"
                            />
                        </div>
                        <div className="stats stats-vertical sm:stats-horizontal shadow mb-6 flex-wrap">
                            <StatCard
                                label="Contestants that started flying"
                                value={numberFormatter.format(overview.number_of_started_contestants)}
                            />
                            <StatCard
                                label="...crossed the starting line"
                                value={numberFormatter.format(overview.number_of_contestants_crossed_starting)}
                            />
                            <StatCard
                                label="Unique pilots/copilots who have flown"
                                value={numberFormatter.format(overview.number_of_persons_crossed_starting)}
                            />
                            <StatCard label="Average airspeed" value={`${overview.average_air_speed.toFixed(0)} kt`} />
                            <StatCard label="Scored anomalies" value={numberFormatter.format(overview.total_anomalies)} />
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <TopListChart
                                title="Top clubs"
                                rows={overview.top_clubs.map((row) => ({ ...row, label: row.name }))}
                                dataKey="count"
                                labelKey="label"
                            />
                            <TopListChart
                                title="Top aircraft types"
                                rows={overview.top_aircraft_types.map((row) => ({ ...row, label: row.type }))}
                                dataKey="count"
                                labelKey="label"
                            />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
