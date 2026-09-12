import React, { useEffect, useState } from 'react';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { fetchContests } from '../../mission-dashboard/api';
import { Contest } from '../../mission-dashboard/types';
import * as api from '../api';
import { ContestTeamListItem } from '../types';

interface ImportTeamsPanelProps {
    contestId: number;
    onImported: (imported: ContestTeamListItem[]) => void;
    onCancel: () => void;
}

// Port of import_contest_team_from_contest (views.py) - copies every ContestTeam registered in a
// chosen source contest into this one. Source-contest choices must match import_teams' own
// visibility check (view_contest or public+featured) - omitting the isEditor filter here gets the
// same "view_contest OR public+featured" base queryset ContestViewSet.get_queryset() applies,
// rather than the narrower editor-only set (a mismatch CodeRabbit correctly flagged in review).
const ImportTeamsPanel: React.FC<ImportTeamsPanelProps> = ({ contestId, onImported, onCancel }) => {
    const [candidates, setCandidates] = useState<Contest[]>([]);
    const [sourceContestId, setSourceContestId] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchContests({ excludeTasks: true })
            .then(contests => setCandidates(contests.filter(contest => contest.id !== contestId)))
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    }, [contestId]);

    const handleImport = async () => {
        if (!sourceContestId) return;
        setSubmitting(true);
        setError(null);
        try {
            const imported = await api.importTeams(contestId, sourceContestId);
            onImported(imported);
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <span className="loading loading-spinner"></span>;

    return (
        <div className="card bg-base-100 shadow-xl max-w-lg w-full mx-auto">
            <div className="card-body">
                <h2 className="card-title">Import teams from another contest</h2>
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Source contest</span></div>
                    <Select
                        options={candidates.map(contest => ({ value: contest.id, label: contest.name }))}
                        onChange={selected => setSourceContestId(selected ? selected.value : null)}
                        placeholder="Choose a contest to copy teams from"
                        classNamePrefix="my-react-select"
                        styles={selectStyles}
                    />
                </label>
                <p className="text-xs text-gray-500 mt-1">
                    Every team registered in the source contest will be copied here. Running this twice will duplicate
                    registrations, same as the legacy import page.
                </p>

                {error && <div className="alert alert-error mt-2">{error}</div>}

                <div className="card-actions justify-end mt-4">
                    <button type="button" className="btn btn-ghost" onClick={onCancel}>
                        Cancel
                    </button>
                    <button type="button" className="btn btn-primary" disabled={!sourceContestId || submitting} onClick={handleImport}>
                        {submitting && <span className="loading loading-spinner"></span>}
                        Import teams
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ImportTeamsPanel;
