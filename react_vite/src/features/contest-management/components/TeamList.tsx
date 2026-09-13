import React, { useState } from 'react';
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

    return (
        <div>
            {error && <div className="alert alert-error mb-2">{error}</div>}
            <ul className="menu bg-base-100 rounded-box">
                {teams.map(contestTeam => (
                    <li key={contestTeam.id}>
                        <div className="flex items-center justify-between">
                            <span>
                                {contestTeam.team.crew.member1.first_name} {contestTeam.team.crew.member1.last_name}
                                {contestTeam.team.crew.member2 && ` / ${contestTeam.team.crew.member2.first_name} ${contestTeam.team.crew.member2.last_name}`}
                                {' - '}
                                {contestTeam.team.aeroplane.registration}
                            </span>
                            <div className="flex gap-2">
                                <button className="btn btn-xs" onClick={() => onEdit(contestTeam)}>
                                    Edit
                                </button>
                                <button
                                    className="btn btn-xs btn-error"
                                    disabled={removingId === contestTeam.id}
                                    onClick={() => handleRemove(contestTeam)}
                                >
                                    Remove
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
