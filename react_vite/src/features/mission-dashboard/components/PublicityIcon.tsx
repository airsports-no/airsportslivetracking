import React from 'react';
import { Globe, Link as LinkIcon, Lock } from 'lucide-react';

export type PublicityStatus = 'Public' | 'Unlisted' | 'Private';

interface PublicityIconProps {
    isPublic: boolean;
    isFeatured: boolean;
    size?: number;
}

export const getPublicityStatus = (isPublic: boolean, isFeatured: boolean): PublicityStatus => {
    if (isPublic && isFeatured) {
        return 'Public';
    }
    if (isPublic && !isFeatured) {
        return 'Unlisted';
    }
    return 'Private';
}

const PublicityIcon: React.FC<PublicityIconProps> = ({ isPublic, isFeatured, size = 16 }) => {
    const status = getPublicityStatus(isPublic, isFeatured);

    const iconMap: Record<PublicityStatus, React.ReactNode> = {
        Public: <Globe size={size} />,
        Unlisted: <LinkIcon size={size} />,
        Private: <Lock size={size} />,
    };

    return (
        <div className="tooltip" data-tip={status}>
            {iconMap[status]}
        </div>
    );
};

export default PublicityIcon;
