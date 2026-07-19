import React from 'react';
import { AvailableTokenGrant } from '../types';

interface Props {
    grants?: AvailableTokenGrant[];
    currentTokenGrantId?: number | null;
    onAssign: (tokenGrantId: number) => Promise<void> | void;
    onReplace?: (tokenGrantId: number) => Promise<void> | void;
    disabled?: boolean;
}

const ContestTokenPanel: React.FC<Props> = ({ grants = [], currentTokenGrantId, onAssign, onReplace, disabled = false }) => {
    if (!grants.length) {
        return (
            <div className="alert alert-warning shadow-sm">
                <div>
                    <div className="font-bold">No tokens available</div>
                    <div className="text-sm opacity-80">Ask support/admin to assign token grants to your user before creating or upgrading a contest.</div>
                </div>
            </div>
        );
    }

    return (
        <div className="card bg-base-100 shadow-md border border-base-300">
            <div className="card-body p-4 gap-3">
                <h3 className="card-title text-lg">Contest token</h3>
                <div className="text-sm opacity-75">
                    Choose which token package defines this contest’s limits. Replacing a token consumes the new token as well; spent tokens are never restored, even if the contest is deleted.
                </div>
                <div className="space-y-2">
                    {grants.map(grant => {
                        const isAssigned = currentTokenGrantId === grant.id;
                        return (
                            <div key={grant.id} className="flex items-center justify-between gap-3 border border-base-300 rounded-lg p-3">
                                <div>
                                    <div className="font-semibold flex items-center gap-2">
                                        {grant.token_type_name}
                                        {isAssigned && <span className="badge badge-success badge-sm">Assigned</span>}
                                    </div>
                                    <div className="text-sm opacity-75">
                                        Remaining: {grant.quantity_remaining} / {grant.quantity_total}
                                    </div>
                                </div>
                                <button
                                    className={`btn btn-sm ${isAssigned ? 'btn-outline' : 'btn-primary'}`}
                                    disabled={disabled || (isAssigned && !onReplace)}
                                    onClick={() => isAssigned ? onReplace?.(grant.id) : onAssign(grant.id)}
                                >
                                    {isAssigned ? 'Replace token' : 'Assign token'}
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default ContestTokenPanel;
