import React from 'react';
import { Globe, Lock } from 'lucide-react';

export type PublicityStatus = 'Public' | 'Private';

interface PublicityIconProps {
    isPublic: boolean;
    size?: number;
}

export const getPublicityStatus = (isPublic: boolean): PublicityStatus => (isPublic ? 'Public' : 'Private');

const PublicityIcon: React.FC<PublicityIconProps> = ({ isPublic, size = 16 }) => {
    const status = getPublicityStatus(isPublic);

    const iconMap: Record<PublicityStatus, React.ReactNode> = {
        Public: <Globe size={size} />,
        Private: <Lock size={size} />,
    };

    return (
        <div className="tooltip" data-tip={status}>
            {iconMap[status]}
        </div>
    );
};

export default PublicityIcon;
