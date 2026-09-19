import React, { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Loading } from '../../route-editor/components/basicComponents';
import { RepeatParticipationStats } from '../api';

const mergeDistributions = (teams: RepeatParticipationStats['distribution'], persons: RepeatParticipationStats['distribution']) => {
    const byContests = new Map<string, { contests: string; teams: number; persons: number }>();
    for (const row of teams) {
        const key = String(row.contests);
        byContests.set(key, { contests: key, teams: row.count, persons: 0 });
    }
    for (const row of persons) {
        const key = String(row.contests);
        const existing = byContests.get(key);
        if (existing) {
            existing.persons = row.count;
        } else {
            byContests.set(key, { contests: key, teams: 0, persons: row.count });
        }
    }
    return Array.from(byContests.values()).sort((a, b) => {
        if (a.contests === '5+') return 1;
        if (b.contests === '5+') return -1;
        return Number(a.contests) - Number(b.contests);
    });
};

function StatCard({ label, value, sublabel }: { label: string; value: string; sublabel: string }) {
    return (
        <div className="stat bg-base-200 rounded-box">
            <div className="stat-title">{label}</div>
            <div className="stat-value text-primary">{value}</div>
            <div className="stat-desc">{sublabel}</div>
        </div>
    );
}

interface Props {
    data: { teams: RepeatParticipationStats; persons: RepeatParticipationStats } | null;
    loading: boolean;
}

export default function RetentionPanel({ data, loading }: Props) {
    const chartData = useMemo(
        () => (data ? mergeDistributions(data.teams.distribution, data.persons.distribution) : []),
        [data],
    );

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h2 className="card-title">Retention - is the platform sticky?</h2>
                <p className="text-sm text-base-content/70 mb-2">
                    Teams and pilots/copilots who come back for more than one contest, versus one-and-done.
                </p>

                {loading || !data ? (
                    <Loading />
                ) : (
                    <>
                        <div className="stats stats-vertical sm:stats-horizontal shadow mb-4">
                            <StatCard
                                label="Returning teams"
                                value={`${data.teams.returning_pct}%`}
                                sublabel={`${data.teams.returning} of ${data.teams.total} teams flew 2+ contests`}
                            />
                            <StatCard
                                label="Returning pilots/copilots"
                                value={`${data.persons.returning_pct}%`}
                                sublabel={`${data.persons.returning} of ${data.persons.total} people flew 2+ contests`}
                            />
                        </div>

                        {chartData.length === 0 ? (
                            <div className="text-sm text-base-content/60 py-8 text-center">No participation data yet.</div>
                        ) : (
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData} barCategoryGap="20%">
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-base-300)" />
                                        <XAxis
                                            dataKey="contests"
                                            tick={{ fontSize: 12 }}
                                            stroke="var(--color-base-content)"
                                            label={{ value: 'Contests attended', position: 'insideBottom', offset: -5, fontSize: 12 }}
                                        />
                                        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="var(--color-base-content)" />
                                        <Tooltip
                                            contentStyle={{
                                                background: 'var(--color-base-100)',
                                                border: '1px solid var(--color-base-300)',
                                                borderRadius: '0.5rem',
                                            }}
                                        />
                                        <Legend />
                                        <Bar dataKey="teams" name="Teams" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="persons" name="Pilots/copilots" fill="var(--color-secondary)" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
