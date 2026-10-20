import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { generatePath } from '../../../urls';
import {
    SharedSquadron,
    Squadron,
    fetchContestSquadrons,
    fetchMySquadrons,
    shareContestWithSquadron,
    unshareContestWithSquadron,
} from '../../squadrons/api';

interface Props {
    contestId: number;
}

/**
 * Share a contest with squadrons: every member of a squadron the contest is shared with can see it, also when it is
 * private, and take part in it. Only squadrons the user is in can be added.
 */
const ContestSquadronsPanel: React.FC<Props> = ({ contestId }) => {
    const [shared, setShared] = useState<SharedSquadron[] | null>(null);
    const [mine, setMine] = useState<Squadron[]>([]);
    const [choice, setChoice] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        Promise.all([fetchContestSquadrons(contestId), fetchMySquadrons()])
            .then(([sharedWith, squadrons]) => {
                if (cancelled) return;
                setShared(sharedWith);
                setMine(squadrons);
                setError(null);
            })
            .catch(e => {
                if (!cancelled) setError((e as Error).message);
            });
        return () => {
            cancelled = true;
        };
    }, [contestId]);

    const run = async (action: () => Promise<SharedSquadron[]>) => {
        setBusy(true);
        setError(null);
        try {
            setShared(await action());
            setChoice('');
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    const available = mine.filter(squadron => !shared?.some(item => item.id === squadron.id));

    return (
        <div className="card bg-base-200 shadow-sm border border-base-300">
            <div className="card-body p-5 space-y-2">
                <h3 className="card-title text-lg">Squadrons</h3>
                <p className="text-sm opacity-70">
                    A squadron is a group of people, for example a club or a team. Share this contest with a squadron and everybody in it can
                    see the contest, also its private tasks, and register and fly in it. They cannot change anything. Use it for a private
                    contest that a whole group should have access to; a public contest is open to everybody anyway.
                </p>
                {error && <div className="alert alert-error text-sm py-2">{error}</div>}
                {shared?.map(squadron => (
                    <div key={squadron.id} className="flex items-center justify-between gap-2 bg-base-100 rounded-lg p-3 text-sm">
                        <span>
                            <Link className="link" to={generatePath('SQUADRON_DETAIL', { squadronId: squadron.id })}>{squadron.name}</Link>
                            {squadron.shared_by_name && <span className="opacity-60 text-xs ml-2">added by {squadron.shared_by_name}</span>}
                        </span>
                        {squadron.can_remove && (
                            <button className="btn btn-xs btn-outline btn-error" disabled={busy} onClick={() => run(() => unshareContestWithSquadron(contestId, squadron.id))}>
                                Stop sharing
                            </button>
                        )}
                    </div>
                ))}
                {shared?.length === 0 && <p className="text-sm opacity-70">Not shared with any squadron yet. Only the people you give access to individually can see this contest if it is private.</p>}
                {available.length > 0 ? (
                    <div className="flex gap-2 pt-1">
                        <select className="select select-bordered select-sm flex-1" value={choice} onChange={e => setChoice(e.target.value)}>
                            <option value="">Choose a squadron to share with…</option>
                            {available.map(squadron => (
                                <option key={squadron.id} value={squadron.id}>{squadron.name}</option>
                            ))}
                        </select>
                        <button className="btn btn-primary btn-sm" disabled={busy || !choice} onClick={() => run(() => shareContestWithSquadron(contestId, Number(choice)))}>
                            Share
                        </button>
                    </div>
                ) : (
                    <p className="text-sm opacity-70">
                        {mine.length === 0 ? 'You are not in a squadron yet: start one for your club or team, then come back and share this contest with it. ' : ''}
                        <Link className="link" to={generatePath('SQUADRONS', {})}>{mine.length === 0 ? 'Start a squadron' : 'Manage your squadrons'}</Link>
                    </p>
                )}
            </div>
        </div>
    );
};

export default ContestSquadronsPanel;
