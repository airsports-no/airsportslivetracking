import React from 'react';

interface Props {
    label: string;
    value: string;
    sublabel?: string;
}

export default function StatCard({ label, value, sublabel }: Props) {
    return (
        <div className="stat bg-base-200 rounded-box">
            <div className="stat-title">{label}</div>
            <div className="stat-value text-primary">{value}</div>
            {sublabel && <div className="stat-desc">{sublabel}</div>}
        </div>
    );
}
