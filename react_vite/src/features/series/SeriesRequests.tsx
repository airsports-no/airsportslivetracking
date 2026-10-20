import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { generatePath } from '../../urls';
import { SeriesRequest, acceptSeriesRequest, cancelSeriesRequest, declineSeriesRequest } from './api';

interface Props {
    requests: SeriesRequest[];
    /** Called after one has been answered or taken back, so the caller can load again */
    onChanged: () => void;
    /** What to say about the side that is not the viewer's: shown as the other party */
    heading?: string;
}

/**
 * Requests for contests to join series. Those the user can answer have Accept and Decline, those the user's own side
 * made have Cancel.
 */
const SeriesRequests: React.FC<Props> = ({ requests, onChanged, heading = 'Requests' }) => {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (requests.length === 0) return null;

    const run = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError(null);
        try {
            await action();
            onChanged();
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="card bg-base-200 border border-base-300">
            <div className="card-body p-5 space-y-2">
                <h2 className="card-title text-lg">{heading}</h2>
                {error && <div role="alert" className="alert alert-error text-sm py-2">{error}</div>}
                {requests.map(request => (
                    <div key={request.id} className="bg-base-100 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm">
                        <div>
                            <Link className="link font-semibold" to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: request.contest_id })}>{request.contest_name}</Link>
                            {' in '}
                            <Link className="link font-semibold" to={generatePath('SERIES_DETAIL', { seriesId: request.series_id })}>{request.series_name}</Link>
                            <div className="text-xs opacity-70">
                                {request.from_side === 'series' ? 'The series invites the contest' : 'The contest asks to join the series'}
                                {request.requested_by_name ? ` · ${request.requested_by_name}` : ''}
                            </div>
                        </div>
                        <div className="flex gap-2">
                            {request.can_answer && (
                                <>
                                    <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(() => acceptSeriesRequest(request.id))}>Accept</button>
                                    <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => run(() => declineSeriesRequest(request.id))}>Decline</button>
                                </>
                            )}
                            {request.can_cancel && (
                                <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => run(() => cancelSeriesRequest(request.id))}>Cancel request</button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default SeriesRequests;
