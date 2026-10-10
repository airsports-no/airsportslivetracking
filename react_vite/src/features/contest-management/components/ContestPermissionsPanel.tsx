import React from 'react';
import { ContestPermissionGrant } from '../../mission-dashboard/api';
import PersonPicker from '../../../components/common/PersonPicker';
import { PersonOption } from '../../../components/common/personOption';

interface Props {
    grants: ContestPermissionGrant[];
    currentUserId: number;
    loading?: boolean;
    onAdd: (identifier: string, level: string) => Promise<void>;
    onChange: (userId: number, level: string) => Promise<void>;
    onRemove: (userId: number) => Promise<void>;
}

const LEVELS = ['nothing', 'view', 'change', 'delete'] as const;

// Modeled on ManagedClubPanel.tsx - the closest existing analogue for "who can manage this thing".
const ContestPermissionsPanel: React.FC<Props> = ({ grants, currentUserId, loading, onAdd, onChange, onRemove }) => {
    const [person, setPerson] = React.useState<PersonOption | null>(null);
    const [level, setLevel] = React.useState<string>('view');
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    const add = async () => {
        if (!person) return;
        setBusy(true);
        setError(null);
        try {
            // The server accepts a user id as the identifier, so no email is ever needed here
            await onAdd(String(person.value), level);
            setPerson(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add permission');
        } finally {
            setBusy(false);
        }
    };

    const change = async (userId: number, newLevel: string) => {
        setBusy(true);
        setError(null);
        try {
            await onChange(userId, newLevel);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to change permission');
        } finally {
            setBusy(false);
        }
    };

    const remove = async (userId: number) => {
        setBusy(true);
        setError(null);
        try {
            await onRemove(userId);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to remove permission');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="card bg-base-200 shadow-sm border border-base-300">
            <div className="card-body p-5">
                <h3 className="card-title text-lg">Permissions</h3>
                {error && <div className="alert alert-error text-sm py-2">{error}</div>}
                {loading ? (
                    <span className="loading loading-spinner loading-sm"></span>
                ) : (
                <>
                <div className="space-y-2">
                    {grants.map(grant => {
                        const isSelf = grant.user_id === currentUserId;
                        return (
                            <div key={grant.user_id} className="flex items-center justify-between gap-2 bg-base-100 rounded-lg p-3 text-sm">
                                <span>
                                    {grant.name || '(no name)'}{' '}
                                    <span className="opacity-60 font-mono text-xs">{grant.email_hint}</span>
                                </span>
                                <div className="flex items-center gap-2">
                                    <select
                                        className="select select-bordered select-xs"
                                        value={grant.level}
                                        disabled={busy}
                                        onChange={e => change(grant.user_id, e.target.value)}
                                    >
                                        {LEVELS.map(l => (
                                            <option key={l} value={l}>{l}</option>
                                        ))}
                                    </select>
                                    <button
                                        className="btn btn-xs btn-outline btn-error"
                                        disabled={busy || isSelf}
                                        title={isSelf ? "You cannot remove your own permissions" : undefined}
                                        onClick={() => remove(grant.user_id)}
                                    >
                                        Remove
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
                <div className="flex flex-col md:flex-row gap-2 pt-2">
                    <div className="flex-1 min-w-0">
                        <PersonPicker
                            kind="user"
                            value={person}
                            onChange={setPerson}
                            placeholder="Type a name to search for a user"
                        />
                    </div>
                    <select className="select select-bordered select-sm" value={level} onChange={e => setLevel(e.target.value)}>
                        {LEVELS.filter(l => l !== 'nothing').map(l => (
                            <option key={l} value={l}>{l}</option>
                        ))}
                    </select>
                    <button className="btn btn-primary btn-sm" disabled={busy || !person} onClick={add}>
                        Add
                    </button>
                </div>
                </>
                )}
            </div>
        </div>
    );
};

export default ContestPermissionsPanel;
