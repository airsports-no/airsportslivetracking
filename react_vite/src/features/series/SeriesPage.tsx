import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, Globe, Lock, Plus, Trash2 } from 'lucide-react';
import { generatePath, reverse } from '../../urls';
import { Loading } from '../route-editor/components/basicComponents';
import ContestSearch from './ContestSearch';
import SeriesRequests from './SeriesRequests';
import SeriesPermissions from './SeriesPermissions';
import StandingsTable from './StandingsTable';
import {
    AddableContest,
    EntrantIdentity,
    ScoringMethod,
    SeriesDetail,
    SeriesRequest,
    Standings,
    addContestToSeries,
    deleteSeries,
    enrolContest,
    fetchAddableContests,
    fetchSeries,
    fetchSeriesRequests,
    fetchStandings,
    removeContestFromSeries,
    updateLeg,
    updateSeries,
} from './api';

const parseTable = (text: string): number[] =>
    text
        .split(/[\s,;]+/)
        .filter(Boolean)
        .map(Number);

/**
 * One series: the ranking over its legs for everybody and, for the people who manage it, the settings and the legs. The
 * legs are contests; the series only ranks them and changes nothing in them.
 */
const SeriesPage: React.FC = () => {
    const { seriesId } = useParams<{ seriesId: string }>();
    const navigate = useNavigate();
    const id = Number(seriesId);
    const [series, setSeries] = useState<SeriesDetail | null>(null);
    const [standings, setStandings] = useState<Standings | null>(null);
    const [addable, setAddable] = useState<AddableContest[]>([]);
    const [requests, setRequests] = useState<SeriesRequest[]>([]);
    const [notice, setNotice] = useState<string | null>(null);
    const [contestChoice, setContestChoice] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [reloads, setReloads] = useState(0);
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [scoring, setScoring] = useState<ScoringMethod>('placements');
    const [identity, setIdentity] = useState<EntrantIdentity>('pilot');
    const [bestCounted, setBestCounted] = useState('');
    const [table, setTable] = useState('');
    const [isPublic, setIsPublic] = useState(false);

    const reload = () => setReloads(count => count + 1);

    useEffect(() => {
        let cancelled = false;
        Promise.all([fetchSeries(id), fetchStandings(id)])
            .then(([detail, ranking]) => {
                if (cancelled) return;
                setSeries(detail);
                setStandings(ranking);
                setName(detail.name);
                setDescription(detail.description);
                setScoring(detail.scoring_method);
                setIdentity(detail.entrant_identity);
                setBestCounted(detail.best_results_counted == null ? '' : String(detail.best_results_counted));
                setTable(detail.points_table.join(', '));
                setIsPublic(detail.is_public);
                setError(null);
                if (detail.can_manage) {
                    fetchAddableContests(id)
                        .then(contests => {
                            if (!cancelled) setAddable(contests);
                        })
                        .catch(() => {});
                    fetchSeriesRequests({ series: id })
                        .then(waiting => {
                            if (!cancelled) setRequests(waiting);
                        })
                        .catch(() => {});
                }
            })
            .catch(e => {
                if (!cancelled) setError((e as Error).message);
            });
        return () => {
            cancelled = true;
        };
    }, [id, reloads]);

    const run = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError(null);
        try {
            await action();
            reload();
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    if (!series || !standings) {
        return error ? <div role="alert" className="alert alert-error m-4">{error}</div> : <div className="p-8 flex justify-center"><Loading /></div>;
    }

    const save = (event: React.FormEvent) => {
        event.preventDefault();
        run(() =>
            updateSeries(id, {
                name,
                description,
                is_public: isPublic,
                scoring_method: scoring,
                entrant_identity: identity,
                best_results_counted: bestCounted.trim() === '' ? null : Number(bestCounted),
                points_table: parseTable(table),
            }),
        );
    };

    return (
        <div className="max-w-5xl mx-auto p-4 space-y-6">
            <Link to={generatePath('SERIES_LIST', {})} className="btn btn-ghost btn-sm gap-1"><ArrowLeft size={16} /> Series</Link>
            {error && <div role="alert" className="alert alert-error">{error}</div>}

            <div className="space-y-1">
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    {series.name}
                    {series.is_public ? <Globe size={18} aria-label="Public" /> : <Lock size={18} aria-label="Private" />}
                </h1>
                {series.description && <p className="opacity-70">{series.description}</p>}
                <p className="text-sm opacity-70">
                    {series.scoring_method === 'placements'
                        ? 'The places in the legs are added up: the lowest total wins.'
                        : 'Each place gives points: the highest total wins.'}
                    {' '}
                    {series.entrant_identity === 'crew' ? 'A crew is the same pilot and navigator.' : 'The pilot is ranked, whoever the navigator or the aeroplane is.'}
                    {series.best_results_counted != null && ` Only the best ${series.best_results_counted} legs count.`}
                    {series.scoring_method === 'placements' && ' A leg without a result gives one place more than the number of teams in it.'}
                </p>
            </div>

            <div className="card bg-base-100 border border-base-300">
                <div className="card-body p-4">
                    <StandingsTable standings={standings} />
                    {standings.rows.length > 0 && (
                        <div className="flex justify-end">
                            <a className="btn btn-ghost btn-xs gap-1" href={reverse('series-standings-csv', id)}><Download size={12} /> CSV</a>
                        </div>
                    )}
                </div>
            </div>

            {series.can_manage && (
                <>
                    <SeriesRequests requests={requests} onChanged={reload} heading="Contests waiting to join" />
                    <div className="card bg-base-200 border border-base-300">
                        <div className="card-body p-5 space-y-2">
                            <h2 className="card-title text-lg">Legs</h2>
                            <p className="text-sm opacity-70">
                                Each leg is one event of the cup, a contest of its own. {series.is_public ? 'A public series can only contain public contests. ' : ''}
                                Legs are shown in the order of their number. The weight says how much a leg counts: 2 makes the places in that leg count double.
                                Taking a contest out of the series does not change the contest.
                            </p>
                            {series.legs.length === 0 && <p className="text-sm opacity-70">No contest is a leg of the series yet.</p>}
                            {series.legs.map(leg => (
                                <div key={leg.contest_id} className="bg-base-100 rounded-lg p-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                                    <Link className="link font-semibold" to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: leg.contest_id })}>{leg.name}</Link>
                                    <div className="flex items-center gap-2">
                                        <label className="flex items-center gap-1 text-xs">Leg
                                            <input
                                                className="input input-bordered input-xs w-16"
                                                type="number"
                                                min={0}
                                                defaultValue={leg.leg_number}
                                                onBlur={e => e.target.value !== String(leg.leg_number) && run(() => updateLeg(id, leg.contest_id, { leg_number: Number(e.target.value) }))}
                                            />
                                        </label>
                                        <label className="flex items-center gap-1 text-xs">Weight
                                            <input
                                                className="input input-bordered input-xs w-16"
                                                type="number"
                                                min={0.1}
                                                step={0.1}
                                                defaultValue={leg.weight}
                                                onBlur={e => e.target.value !== String(leg.weight) && run(() => updateLeg(id, leg.contest_id, { weight: Number(e.target.value) }))}
                                            />
                                        </label>
                                        <button className="btn btn-xs btn-outline btn-error" disabled={busy} onClick={() => run(() => removeContestFromSeries(id, leg.contest_id))}>
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            ))}
                            {addable.length > 0 ? (
                                <div className="flex gap-2 pt-1">
                                    <select className="select select-bordered select-sm flex-1" value={contestChoice} onChange={e => setContestChoice(e.target.value)}>
                                        <option value="">Add one of your contests as a leg…</option>
                                        {addable.map(contest => (
                                            <option key={contest.id} value={contest.id}>{contest.name}</option>
                                        ))}
                                    </select>
                                    <button
                                        className="btn btn-primary btn-sm gap-1"
                                        disabled={busy || !contestChoice}
                                        onClick={() => run(async () => {
                                            await addContestToSeries(id, Number(contestChoice));
                                            setContestChoice('');
                                        })}
                                    >
                                        <Plus size={14} /> Add
                                    </button>
                                </div>
                            ) : (
                                <p className="text-xs opacity-60">{series.is_public ? 'Only public contests you manage can be added.' : 'Only contests you manage can be added.'}</p>
                            )}
                            <div className="pt-2 space-y-1">
                                <div className="text-sm font-semibold">Invite a contest run by somebody else</div>
                                <p className="text-xs opacity-70">
                                    Search for the contest by name. The people who manage it get a request and decide whether it becomes a leg; you can
                                    cancel the request until they answer.
                                </p>
                                <ContestSearch
                                    disabled={busy}
                                    onPick={contest =>
                                        run(async () => {
                                            const outcome = await enrolContest(id, contest.id);
                                            setNotice(outcome.added ? `${contest.name} is a leg of the series.` : `The managers of ${contest.name} have been asked.`);
                                        })
                                    }
                                />
                                {notice && <div className="text-xs text-success">{notice}</div>}
                            </div>
                        </div>
                    </div>

                    <form onSubmit={save} className="card bg-base-200 border border-base-300">
                        <div className="card-body p-5 space-y-3">
                            <h2 className="card-title text-lg">Settings</h2>
                            <input className="input input-bordered w-full" maxLength={100} value={name} onChange={e => setName(e.target.value)} required />
                            <textarea className="textarea textarea-bordered w-full" placeholder="Description (optional)" value={description} onChange={e => setDescription(e.target.value)} />
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <label className="form-control">
                                    <span className="label-text">Scoring</span>
                                    <select className="select select-bordered select-sm" value={scoring} onChange={e => setScoring(e.target.value as ScoringMethod)}>
                                        <option value="placements">Add up the places, lowest total wins</option>
                                        <option value="points_table">Points for each place, highest total wins</option>
                                    </select>
                                </label>
                                <label className="form-control">
                                    <span className="label-text">Who is ranked (the same pilot, or the same crew, in every leg)</span>
                                    <select className="select select-bordered select-sm" value={identity} onChange={e => setIdentity(e.target.value as EntrantIdentity)}>
                                        <option value="pilot">The pilot</option>
                                        <option value="crew">The crew (same pilot and navigator)</option>
                                    </select>
                                </label>
                                <label className="form-control">
                                    <span className="label-text">Only the best … legs count (empty: all legs count). Use it for a season where a bad day may be dropped.</span>
                                    <input className="input input-bordered input-sm" type="number" min={1} value={bestCounted} onChange={e => setBestCounted(e.target.value)} />
                                </label>
                                {scoring === 'points_table' && (
                                    <label className="form-control">
                                        <span className="label-text">Points for first, second, third… place, separated by commas (nothing is given beyond the end of the list)</span>
                                        <input className="input input-bordered input-sm" value={table} onChange={e => setTable(e.target.value)} />
                                    </label>
                                )}
                            </div>
                            <label className="label cursor-pointer justify-start gap-3">
                                <input type="checkbox" className="checkbox checkbox-sm" checked={isPublic} onChange={e => setIsPublic(e.target.checked)} />
                                <span className="label-text">Public: listed for everybody. Every leg must then be a public contest, and a leg cannot be made private. Private: only the people given access under Permissions below can see the series.</span>
                            </label>
                            <div className="card-actions justify-between">
                                {series.can_delete ? <button
                                    type="button"
                                    className="btn btn-outline btn-error btn-sm gap-1"
                                    disabled={busy}
                                    onClick={async () => {
                                        if (!window.confirm(`Delete the series ${series.name}? The contests stay as they are.`)) return;
                                        setBusy(true);
                                        try {
                                            await deleteSeries(id);
                                            navigate(generatePath('SERIES_LIST', {}));
                                        } catch (e) {
                                            setError((e as Error).message);
                                            setBusy(false);
                                        }
                                    }}
                                >
                                    <Trash2 size={14} /> Delete series
                                </button> : <span />}
                                <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !name.trim()}>Save</button>
                            </div>
                        </div>
                    </form>
                    <SeriesPermissions seriesId={id} />
                </>
            )}
        </div>
    );
};

export default SeriesPage;
