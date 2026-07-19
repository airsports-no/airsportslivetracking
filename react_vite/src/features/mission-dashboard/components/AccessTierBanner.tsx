import React from 'react';
import { AccessStatus } from '../types';

interface Props {
    accessStatus?: AccessStatus;
}

const formatLimit = (value: number | null | undefined) => (value == null ? 'Unlimited' : String(value));

const AccessTierBanner: React.FC<Props> = ({ accessStatus }) => {
    if (!accessStatus) return null;

    const isToken = accessStatus.source_type === 'contest_token';
    const isClubPass = accessStatus.source_type === 'club_pass';
    const badgeClass = isToken ? 'badge badge-primary' : isClubPass ? 'badge badge-success' : 'badge badge-info';
    const message = isToken
        ? 'This contest is using a dedicated token package. Replacing the token will consume a new token; previous tokens stay spent.'
        : isClubPass
            ? 'This contest inherits access from an active club pass.'
            : 'This contest is currently using the default free/pass fallback rules.';

    return (
        <div className="alert alert-info mb-4 shadow-sm">
            <div className="w-full">
                <div className="flex items-center gap-2 mb-1">
                    <span className={badgeClass}>{accessStatus.tier_label}</span>
                    <span className="text-xs opacity-70">Source: {accessStatus.source_type}</span>
                </div>
                <div className="text-sm opacity-80">
                    Teams: {accessStatus.contestants_used} / {formatLimit(accessStatus.contestant_limit)} · Tasks: {accessStatus.tasks_used} / {formatLimit(accessStatus.task_limit)}
                </div>
                <div className="text-xs opacity-70">{message}</div>
            </div>
        </div>
    );
};

export default AccessTierBanner;
