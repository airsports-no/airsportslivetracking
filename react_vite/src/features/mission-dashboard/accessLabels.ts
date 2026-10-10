/** Plain-language names for the internal source types, for display. */
export const accessSourceLabel = (sourceType: string | undefined): string => {
    switch (sourceType) {
        case 'contest_token':
            return 'Event token assigned to this contest';
        case 'club_pass':
            return 'Your club pass';
        case 'free_defaults':
            return 'Free tier (no token needed)';
        case 'manual_override':
            return 'Set manually by an administrator';
        default:
            return sourceType ?? 'Unknown';
    }
};
