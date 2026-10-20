import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { generatePath } from '../../../urls';
import SeriesRequests from '../../series/SeriesRequests';
import {
    Series,
    SeriesRequest,
    enrolContest,
    fetchSeriesList,
    fetchSeriesOfContest,
    fetchSeriesRequests,
    removeContestFromSeries,
} from '../../series/api';

interface Props {
    contestId: number;
}

/**
 * The series a contest is a leg of, with the requests to join one: the managers of a contest ask to join a series, or answer
 * the invitation of a series. Leaving is always possible.
 */
const ContestSeriesPanel: React.FC<Props> = ({ contestId }) => {
    const [memberOf, setMemberOf] = useState<Series[] | null>(null);
    const [candidates, setCandidates] = useState<Series[]>([]);
    const [requests, setRequests] = useState<SeriesRequest[]>([]);
    const [choice, setChoice] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [reloads, setReloads] = useState(0);

    useEffect(() => {
        let cancelled = false;
        Promise.all([fetchSeriesOfContest(contestId), fetchSeriesList(), fetchSeriesRequests({ contest: contestId })])
            .then(([legOf, all, waiting]) => {
                if (cancelled) return;
                setMemberOf(legOf);
                setCandidates(all);
                setRequests(waiting);
                setError(null);
            })
            .catch(e => {
                if (!cancelled) setError((e as Error).message);
            });
        return () => {
            cancelled = true;
        };
    }, [contestId, reloads]);

    const run = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError(null);
        try {
            await action();
            setChoice('');
            setReloads(count => count + 1);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    const asked = new Set(requests.map(request => request.series_id));
    const available = candidates.filter(series => !memberOf?.some(item => item.id === series.id) && !asked.has(series.id));

    return (
        <>
            <SeriesRequests requests={requests} onChanged={() => setReloads(count => count + 1)} heading="Series requests for this contest" />
            <div className="card bg-base-200 shadow-sm border border-base-300">
                <div className="card-body p-5 space-y-2">
                    <h3 className="card-title text-lg">Series</h3>
                    <p className="text-sm opacity-70">
                        A series is a cup or championship held as several separate contests. It adds up how each team did in all of them and shows
                        one table. Make this contest a leg of a series if it is one event of such a cup; it stays a contest of its own. If you
                        manage the series the contest joins at once, otherwise the managers of the series get a request and decide.
                    </p>
                    {error && <div className="alert alert-error text-sm py-2">{error}</div>}
                    {memberOf?.map(series => (
                        <div key={series.id} className="flex items-center justify-between gap-2 bg-base-100 rounded-lg p-3 text-sm">
                            <Link className="link" to={generatePath('SERIES_DETAIL', { seriesId: series.id })}>{series.name}</Link>
                            <button className="btn btn-xs btn-outline btn-error" disabled={busy} onClick={() => run(() => removeContestFromSeries(series.id, contestId))}>
                                Leave
                            </button>
                        </div>
                    ))}
                    {memberOf?.length === 0 && <p className="text-sm opacity-70">Not part of any series. A single event does not need one.</p>}
                    {available.length > 0 && (
                        <div className="flex gap-2 pt-1">
                            <select className="select select-bordered select-sm flex-1" value={choice} onChange={e => setChoice(e.target.value)}>
                                <option value="">Choose a series to join…</option>
                                {available.map(series => (
                                    <option key={series.id} value={series.id}>{series.name}</option>
                                ))}
                            </select>
                            <button
                                className="btn btn-primary btn-sm"
                                disabled={busy || !choice}
                                onClick={() =>
                                    run(async () => {
                                        const outcome = await enrolContest(Number(choice), contestId);
                                        setNotice(outcome.added ? 'The contest is a leg of the series.' : 'The series managers have been asked.');
                                    })
                                }
                            >
                                Ask
                            </button>
                        </div>
                    )}
                    {notice && <div className="text-xs text-success">{notice}</div>}
                </div>
            </div>
        </>
    );
};

export default ContestSeriesPanel;
