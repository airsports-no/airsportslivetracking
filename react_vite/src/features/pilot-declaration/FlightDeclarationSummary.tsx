import React, { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fetchDeclaration } from './api';
import { declarationActionText, declarationLabel } from './declarationForm';
import FlightOrderPanel from './FlightOrderPanel';
import { useFlightOrderStatus } from './useFlightOrderStatus';
import { DeclarationStatus, FlightOrderStatus } from './types';

const TONES = {
    warning: 'badge-warning',
    success: 'badge-success',
    info: 'badge-info',
    neutral: 'badge-ghost',
} as const;

interface FlightDeclarationSummaryProps {
    flightId: number;
    declarationStatus?: DeclarationStatus | null;
    flightOrderStatus?: FlightOrderStatus | null;
    /** A flight that is over: the declaration can only be viewed, and the flight order block appears only when there is a download */
    readOnly?: boolean;
}

/** The declaration and the flight order of one of the pilot's own flights, in the list of my flights */
const FlightDeclarationSummary: React.FC<FlightDeclarationSummaryProps> = ({ flightId, declarationStatus, flightOrderStatus, readOnly = false }) => {
    const refresh = useCallback(async () => (await fetchDeclaration(flightId)).flight_order_status, [flightId]);
    const flightOrder = useFlightOrderStatus(flightOrderStatus ?? null, refresh);
    // Read-only: whatever the status says about editing, the pilot only views the declaration of a flight that is over
    const viewStatus = readOnly && declarationStatus ? { ...declarationStatus, can_edit: false } : declarationStatus;
    const label = declarationLabel(viewStatus);
    const showOrder = !readOnly || (flightOrder?.state === 'ready' && Boolean(flightOrder.path));
    return (
        <div className="mt-2 space-y-2" data-testid="flight-declaration-summary">
            {label && declarationStatus && (
                <div className="flex flex-wrap items-center gap-2">
                    <span className={`badge badge-lg whitespace-normal h-auto py-1 ${TONES[label.tone]}`} data-testid="declaration-label">{label.text}</span>
                    {declarationStatus.edit_url && (
                        <Link to={declarationStatus.edit_url} className="btn btn-outline btn-sm min-h-11">
                            {declarationActionText(viewStatus ?? declarationStatus)}
                        </Link>
                    )}
                </div>
            )}
            {showOrder && (
                <FlightOrderPanel status={flightOrder} compact retryBySaving={!readOnly && Boolean(declarationStatus?.can_edit) && declarationStatus?.need !== 'not_needed'} />
            )}
        </div>
    );
};

export default FlightDeclarationSummary;
