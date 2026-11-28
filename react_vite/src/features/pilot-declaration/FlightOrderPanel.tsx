import React from 'react';
import { CheckCircle2, Download, Loader2, TriangleAlert } from 'lucide-react';
import { FlightOrderStatus } from './types';
import { isEmbeddedInApp } from '../../utils/appBridge';

const madeAt = (iso: string | null): string => {
    if (!iso) return '';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
};

interface FlightOrderPanelProps {
    status: FlightOrderStatus | null | undefined;
    /** Compact for a list of flights */
    compact?: boolean;
    /** Saving the declaration again makes a new attempt: say so when the flight order failed */
    retryBySaving?: boolean;
}

/** What the pilot sees of the flight order. Nothing when the system does not make it for this flight. */
const FlightOrderPanel: React.FC<FlightOrderPanelProps> = ({ status, compact = false, retryBySaving = false }) => {
    if (!status || status.state === 'not_available') return null;
    // The apps' web views do not open new windows: the page opens where the pilot is, as the app's own links do
    const openInPlace = isEmbeddedInApp();
    const gap = compact ? 'mt-2' : 'mt-4';

    if (status.state === 'waiting_for_declaration') {
        return (
            <p className={`${gap} text-sm opacity-80`} data-testid="flight-order-waiting">
                Your flight order is made when your declaration is complete.
            </p>
        );
    }
    if (status.state === 'being_made') {
        return (
            <div className={`${gap} flex items-center gap-2 text-sm`} role="status" data-testid="flight-order-being-made">
                <Loader2 size={18} className="animate-spin shrink-0" aria-hidden="true" />
                <span>Your flight order is being made. This updates by itself.</span>
            </div>
        );
    }
    if (status.state === 'ready' && status.path) {
        const made = madeAt(status.created_at);
        return (
            <div className={gap} data-testid="flight-order-ready">
                <p className="flex items-center gap-2 text-sm">
                    <CheckCircle2 size={18} className="text-success shrink-0" aria-hidden="true" />
                    <span>Your flight order is ready{made ? ` (made ${made})` : ''}.</span>
                </p>
                <a
                    href={status.path}
                    className="btn btn-primary min-h-11 mt-2 gap-2"
                    {...(openInPlace ? {} : { target: '_blank', rel: 'noopener noreferrer' })}
                >
                    <Download size={18} aria-hidden="true" />
                    Download flight order
                </a>
            </div>
        );
    }
    return (
        <div className={`${gap} alert alert-warning text-sm`} role="alert" data-testid="flight-order-failed">
            <TriangleAlert size={18} className="shrink-0" aria-hidden="true" />
            <div>
                <p>{status.reason || 'The flight order could not be made.'}</p>
                {retryBySaving && <p className="opacity-80">Save your declaration again to try again.</p>}
            </div>
        </div>
    );
};

export default FlightOrderPanel;
