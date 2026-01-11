import React, { useMemo } from 'react';
import { ColumnDef } from '@tanstack/react-table';
import { Contest } from '../../schedule-flight/types';
import { ASTable } from '../../route-editor/components/filteredSearchableTable';

interface LeaderboardProps {
    contest: Contest;
}

interface LeaderboardData {
    rank: number;
    name: string;
    score: number;
}

const Leaderboard: React.FC<LeaderboardProps> = ({ contest }) => {

    const data = useMemo(() => {
        const allContestants = contest.navigationtask_set.flatMap(task => 
            (task.contestant_set || []).map(c => ({
                name: `${c.team.crew.member1.first_name} ${c.team.crew.member1.last_name}`,
                score: c.contestanttrack.score
            }))
        );
        
        // This is a simplified aggregation. A real implementation might need more complex logic
        // to handle multiple tasks per contestant. For now, we just list all participants.
        const sorted = allContestants.sort((a, b) => {
            if (contest.summary_score_sorting_direction === 'desc') {
                return b.score - a.score;
            }
            return a.score - b.score;
        });

        return sorted.map((c, index) => ({
            rank: index + 1,
            name: c.name,
            score: c.score
        }));
    }, [contest]);

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

    return (
        <div className="card bg-base-200 shadow-xl">
            <div className="card-body">
                <ASTable columns={columns} data={data} />
            </div>
        </div>
    );
};

export default Leaderboard;
