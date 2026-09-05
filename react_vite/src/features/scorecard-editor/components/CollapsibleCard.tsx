import React, { useState } from 'react';
import { ChevronRight } from 'lucide-react';

interface CollapsibleCardProps {
    title: string;
    summary: string;
    headerExtra?: React.ReactNode;
    defaultCollapsed?: boolean;
    children: React.ReactNode;
}

// Every card on the scorecard editor page starts collapsed, showing just its title and a
// one-line summary of its own primary field values - click the header to expand for editing.
// headerExtra (e.g. GateSection's "Reset gate" button) renders as a sibling of the toggle
// button, not nested inside it, so clicking it doesn't also toggle the card.
export const CollapsibleCard: React.FC<CollapsibleCardProps> = ({
    title,
    summary,
    headerExtra,
    defaultCollapsed = true,
    children,
}) => {
    const [collapsed, setCollapsed] = useState(defaultCollapsed);
    return (
        <div className="card bg-base-100 shadow border border-base-300">
            <div className="card-body p-4">
                <div className="flex items-start justify-between gap-2">
                    <button
                        type="button"
                        className="flex items-start gap-2 text-left flex-1 min-w-0"
                        onClick={() => setCollapsed((c) => !c)}
                    >
                        <ChevronRight
                            size={14}
                            className={`shrink-0 mt-1 transition-transform ${collapsed ? '' : 'rotate-90'}`}
                        />
                        <div className="min-w-0">
                            <h3 className="card-title text-sm">{title}</h3>
                            {collapsed && <p className="text-xs text-base-content/60 truncate">{summary}</p>}
                        </div>
                    </button>
                    {headerExtra}
                </div>
                {!collapsed && <div className="mt-2">{children}</div>}
            </div>
        </div>
    );
};
