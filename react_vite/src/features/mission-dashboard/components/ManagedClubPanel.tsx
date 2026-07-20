import React from 'react';

interface ClubManagerMembership {
    id: number;
    user: number;
    user_email: string;
    role: string;
    is_active: boolean;
}

interface ManagedClubPanelProps {
    clubName?: string | null;
    memberships?: ClubManagerMembership[];
    onAddManager: (identifier: string, role: string) => Promise<void>;
    onDeactivateManager: (membershipId: number) => Promise<void>;
}

const ManagedClubPanel: React.FC<ManagedClubPanelProps> = ({ clubName, memberships = [], onAddManager, onDeactivateManager }) => {
    const [identifier, setIdentifier] = React.useState('');
    const [role, setRole] = React.useState('manager');
    const [busy, setBusy] = React.useState(false);

    if (!clubName) return null;

    const submit = async () => {
        if (!identifier.trim()) return;
        setBusy(true);
        try {
            await onAddManager(identifier.trim(), role);
            setIdentifier('');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="card bg-base-200 shadow-sm">
            <div className="card-body">
                <h3 className="card-title">Club managers</h3>
                <p className="text-sm opacity-80">{clubName}</p>
                <div className="space-y-2">
                    {memberships.length === 0 ? (
                        <p className="text-sm opacity-70">No active club managers listed.</p>
                    ) : memberships.map((membership) => (
                        <div key={membership.id} className="flex items-center justify-between gap-2 border rounded p-2">
                            <div>
                                <div className="font-medium">{membership.user_email}</div>
                                <div className="text-xs opacity-70">Role: {membership.role}</div>
                            </div>
                            <button className="btn btn-xs btn-outline btn-error" onClick={() => onDeactivateManager(membership.id)}>
                                Remove
                            </button>
                        </div>
                    ))}
                </div>
                <div className="flex flex-col md:flex-row gap-2 pt-2">
                    <input
                        className="input input-bordered input-sm flex-1"
                        placeholder="Manager user id or email"
                        value={identifier}
                        onChange={(e) => setIdentifier(e.target.value)}
                    />
                    <select className="select select-bordered select-sm" value={role} onChange={(e) => setRole(e.target.value)}>
                        <option value="manager">manager</option>
                        <option value="owner">owner</option>
                    </select>
                    <button className="btn btn-primary btn-sm" disabled={busy || !identifier.trim()} onClick={submit}>
                        Add manager
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ManagedClubPanel;
