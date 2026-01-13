import React, { useMemo } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { ContestResults, ContestSummary } from '../types';
import { ASTable } from '../../route-editor/components/filteredSearchableTable';

interface LeaderboardProps {
    results: ContestResults | null;
}

interface LeaderboardData {
    rank: number;
    name: string;
    score: number;
}

const Leaderboard: React.FC<LeaderboardProps> = ({ results }) => {

    const data = useMemo(() => {
        if (!results || !results.contestsummary_set) {
            return [];
        }

        const sorted = [...results.contestsummary_set].sort((a, b) => {
            if (results.summary_score_sorting_direction === 'desc') {
                return b.points - a.points;
            }
            return a.points - b.points;
        });

        return sorted.map((summary, index) => ({
            rank: index + 1,
            name: `${summary.team.crew.member1.first_name} ${summary.team.crew.member1.last_name}`,
            score: summary.points
        }));
    }, [results]);

    const columns = useMemo<ColumnDef<LeaderboardData>[]>(() => [
        {
            header: 'Rank',
            accessorKey: 'rank',
        },
        {
            header: 'Name',
            accessorKey: 'name',
        },
        {
            header: 'Score',
            accessorKey: 'score',
            cell: ({ getValue }) => (getValue() as number).toFixed(0),
        },
    ], []);

    if (!results) {
        return <div className="card bg-base-200 shadow-xl"><div className="card-body">No results available yet.</div></div>;
    }

    return (
        <div className="card bg-base-200 shadow-xl">
            <div className="card-body">
                <ASTable columns={columns} data={data} />
            </div>
        </div>
    );
};

export default Leaderboard;
