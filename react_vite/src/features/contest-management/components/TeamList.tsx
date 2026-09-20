import React, { useState } from 'react';
import { Pencil, X } from 'lucide-react';
import { ContestTeamListItem } from '../types';
import * as api from '../api';

interface TeamListProps {
    contestId: number;
    teams: ContestTeamListItem[];
    onEdit: (contestTeam: ContestTeamListItem) => void;
    onRemoved: (contestTeamId: number) => void;
}

const TeamList: React.FC<TeamListProps> = ({ contestId, teams, onEdit, onRemoved }) => {
    const [removingId, setRemovingId] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleRemove = async (contestTeam: ContestTeamListItem) => {
        if (!window.confirm(`Remove ${contestTeam.team.crew.member1.first_name} ${contestTeam.team.crew.member1.last_name}'s team from this contest?`)) {
            return;
        }
        setRemovingId(contestTeam.id);
        setError(null);
        try {
            await api.removeTeamFromContest(contestId, contestTeam.id);
            onRemoved(contestTeam.id);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setRemovingId(null);
        }
    };

    if (teams.length === 0) {
        return <p className="text-sm text-gray-500">No teams registered yet.</p>;
    }

    const sortedTeams = [...teams].sort((a, b) =>
        a.team.crew.member1.last_name.localeCompare(b.team.crew.member1.last_name)
    );

    return (
        <div>
            {error && <div className="alert alert-error mb-2">{error}</div>}
            <ul className="menu bg-base-100 rounded-box">
                {sortedTeams.map(contestTeam => (
                    <li key={contestTeam.id}>
                        <div className="flex flex-nowrap items-center justify-between gap-2">
                            <span className="flex items-center gap-2 min-w-0 flex-1">
                                {contestTeam.team.crew.member1.picture && (
                                    <img
                                        src={contestTeam.team.crew.member1.picture}
                                        alt=""
                                        className="w-6 h-6 rounded-full object-cover flex-shrink-0"
                                    />
                                )}
                                <span className="truncate">
                                    {contestTeam.team.crew.member1.first_name} {contestTeam.team.crew.member1.last_name}
                                    {contestTeam.team.crew.member2 && ` / ${contestTeam.team.crew.member2.first_name} ${contestTeam.team.crew.member2.last_name}`}
                                    {' - '}
                                    {contestTeam.team.aeroplane.registration}
                                </span>
                            </span>
                            <div className="flex gap-1 flex-shrink-0">
                                <button
                                    className="btn btn-xs btn-square"
                                    onClick={() => onEdit(contestTeam)}
                                    aria-label="Edit team"
                                    title="Edit team"
                                >
                                    <Pencil size={14} />
                                </button>
                                <button
                                    className="btn btn-xs btn-error btn-square"
                                    disabled={removingId === contestTeam.id}
                                    onClick={() => handleRemove(contestTeam)}
                                    aria-label="Remove team"
                                    title="Remove team"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default TeamList;
