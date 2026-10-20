import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Globe, Lock, Medal, Plus } from 'lucide-react';
import { generatePath } from '../../urls';
import ConceptHint, { DOCS_BASE_URL } from '../../components/common/ConceptHint';
import { Loading } from '../route-editor/components/basicComponents';
import SeriesRequests from './SeriesRequests';
import { Series, SeriesRequest, createSeries, fetchSeriesList, fetchSeriesRequests } from './api';

/**
 * The series the user can see: a series ranks the teams of several contests together, for a cup or championship held at
 * different places. Organisers can start one.
 */
const SeriesListPage: React.FC = () => {
    const [series, setSeries] = useState<Series[] | null>(null);
    const [requests, setRequests] = useState<SeriesRequest[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [name, setName] = useState('');
    const [reloads, setReloads] = useState(0);

    useEffect(() => {
        let cancelled = false;
        Promise.all([fetchSeriesList(), document.configuration.isAuthenticated ? fetchSeriesRequests() : Promise.resolve([])])
            .then(([list, waiting]) => {
                if (cancelled) return;
                setSeries(list);
                setRequests(waiting);
                setError(null);
            })
            .catch(e => {
                if (!cancelled) setError((e as Error).message);
            });
        return () => {
            cancelled = true;
        };
    }, [reloads]);

    const create = async (event: React.FormEvent) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        try {
            await createSeries({ name });
            setName('');
            setReloads(count => count + 1);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    if (!series) {
        return error ? <div role="alert" className="alert alert-error m-4">{error}</div> : <div className="p-8 flex justify-center"><Loading /></div>;
    }

    return (
        <div className="max-w-3xl mx-auto p-4 space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2"><Medal size={24} /> Series</h1>
                <p className="text-sm opacity-70">
                    A series ranks the teams of several contests together: a cup or championship held at different places. Each contest is one leg.
                </p>
            </div>
            <ConceptHint id="series-intro" title="What is a series for?" learnMoreUrl={`${DOCS_BASE_URL}/14_Series`}>
                <p>
                    Use a series when a cup, league or championship is held as <strong>separate events</strong>, for example four contests at
                    four airfields. Each event stays its own contest. The series adds up how every team did in them and shows one table.
                    One event with several tasks does not need a series: the contest results already add its tasks up.
                </p>
                <ol className="list-decimal ml-5 mt-2 space-y-0.5">
                    <li>Start a series below (organisers only).</li>
                    <li>Add the contests as legs. If somebody else manages a contest, its managers get a request and decide.</li>
                    <li>Choose how to score: add up the places (lowest wins) or give points for each place. The standings update as the contests are scored.</li>
                </ol>
            </ConceptHint>
            {error && <div role="alert" className="alert alert-error">{error}</div>}
            <SeriesRequests requests={requests} onChanged={() => setReloads(count => count + 1)} heading="Contests waiting to join a series" />
            <div className="space-y-2">
                {series.length === 0 && (
                    <p className="opacity-70">
                        There are no series to show yet.{document.configuration.isOrganizer ? ' Start one below.' : ' Organisers start a series for a cup or championship; public series are listed here.'}
                    </p>
                )}
                {series.map(item => (
                    <Link
                        key={item.id}
                        to={generatePath('SERIES_DETAIL', { seriesId: item.id })}
                        className="card bg-base-100 border border-base-300 hover:border-primary transition-colors"
                    >
                        <div className="card-body p-4 flex-row items-center justify-between">
                            <div>
                                <div className="font-semibold flex items-center gap-2">
                                    {item.name}
                                    {item.is_public ? <Globe size={14} aria-label="Public" /> : <Lock size={14} aria-label="Private" />}
                                </div>
                                {item.description && <div className="text-sm opacity-70">{item.description}</div>}
                            </div>
                            <div className="text-sm opacity-70 whitespace-nowrap">
                                {item.leg_count} {item.leg_count === 1 ? 'leg' : 'legs'}
                                {item.can_manage && <span className="badge badge-outline badge-sm ml-2">you manage it</span>}
                            </div>
                        </div>
                    </Link>
                ))}
            </div>
            {document.configuration.isOrganizer && (
                <form onSubmit={create} className="card bg-base-200 border border-base-300">
                    <div className="card-body p-5 space-y-3">
                        <h2 className="card-title text-lg flex items-center gap-2"><Plus size={18} /> Start a series</h2>
                        <p className="text-sm opacity-70">You manage the series. Next you add the contests and choose how the teams are scored.</p>
                        <input className="input input-bordered w-full" placeholder="Name, for example Norwegian Cup 2026" maxLength={100} value={name} onChange={e => setName(e.target.value)} required />
                        <div className="card-actions justify-end">
                            <button className="btn btn-primary" type="submit" disabled={busy || !name.trim()}>Create</button>
                        </div>
                    </div>
                </form>
            )}
        </div>
    );
};

export default SeriesListPage;
