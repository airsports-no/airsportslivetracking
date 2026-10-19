import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, Plus, Trophy, Users } from 'lucide-react';
import { generatePath } from '../../urls';
import { Loading } from '../route-editor/components/basicComponents';
import {
    ContestAccess,
    Squadron,
    SquadronInvitation,
    acceptSquadronInvitation,
    createSquadron,
    declineSquadronInvitation,
    fetchContestAccess,
    fetchMySquadronInvitations,
    fetchMySquadrons,
} from './api';

const formatDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

/**
 * The squadrons the user is in, the invitations waiting for an answer and a form to start a new squadron. A squadron is a
 * group of people who compete together: a contest shared with it is open to all its members.
 */
const SquadronsPage: React.FC = () => {
    const [squadrons, setSquadrons] = useState<Squadron[] | null>(null);
    const [invitations, setInvitations] = useState<SquadronInvitation[]>([]);
    const [access, setAccess] = useState<ContestAccess[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');

    const [reloads, setReloads] = useState(0);
    const load = () => setReloads(count => count + 1);

    useEffect(() => {
        let cancelled = false;
        Promise.all([fetchMySquadrons(), fetchMySquadronInvitations(), fetchContestAccess()])
            .then(([mine, pending, contests]) => {
                if (cancelled) return;
                setSquadrons(mine);
                setInvitations(pending);
                setAccess(contests);
                setError(null);
            })
            .catch(e => {
                if (!cancelled) setError((e as Error).message);
            });
        return () => {
            cancelled = true;
        };
    }, [reloads]);

    const run = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError(null);
        try {
            await action();
            load();
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    const create = (event: React.FormEvent) => {
        event.preventDefault();
        run(async () => {
            await createSquadron(name, description);
            setName('');
            setDescription('');
        });
    };

    if (!squadrons) {
        return error ? <div role="alert" className="alert alert-error m-4">{error}</div> : <div className="p-8 flex justify-center"><Loading /></div>;
    }

    return (
        <div className="max-w-3xl mx-auto p-4 space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2"><Users size={24} /> Squadrons</h1>
                <p className="text-sm opacity-70">
                    A squadron is a group of people who compete together. When an organiser shares a contest with a squadron, every
                    member can see it, also when it is private, and take part in it.
                </p>
            </div>

            {error && <div role="alert" className="alert alert-error">{error}</div>}

            {invitations.length > 0 && (
                <div className="card bg-base-200 border border-base-300">
                    <div className="card-body p-5 space-y-2">
                        <h2 className="card-title text-lg flex items-center gap-2"><Mail size={18} /> Invitations</h2>
                        {invitations.map(invitation => (
                            <div key={invitation.id} className="bg-base-100 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                <div>
                                    <div className="font-semibold">{invitation.squadron_name}</div>
                                    <div className="text-sm opacity-70">
                                        {invitation.invited_by_name ? `${invitation.invited_by_name} invited you` : 'You are invited'}
                                        {invitation.role === 'admin' ? ' as an admin' : ''}
                                        {invitation.squadron_description ? ` · ${invitation.squadron_description}` : ''}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(() => acceptSquadronInvitation(invitation.id))}>
                                        Join
                                    </button>
                                    <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => run(() => declineSquadronInvitation(invitation.id))}>
                                        Decline
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div className="space-y-2">
                {squadrons.length === 0 && <p className="opacity-70">You are not in any squadron yet.</p>}
                {squadrons.map(squadron => (
                    <Link
                        key={squadron.id}
                        to={generatePath('SQUADRON_DETAIL', { squadronId: squadron.id })}
                        className="card bg-base-100 border border-base-300 hover:border-primary transition-colors"
                    >
                        <div className="card-body p-4 flex-row items-center justify-between">
                            <div>
                                <div className="font-semibold">{squadron.name}</div>
                                {squadron.description && <div className="text-sm opacity-70">{squadron.description}</div>}
                            </div>
                            <div className="text-sm opacity-70 text-right whitespace-nowrap space-y-1">
                                <div className={`badge badge-sm ${squadron.my_role === 'admin' ? 'badge-primary' : 'badge-outline'}`}>
                                    {squadron.my_role === 'admin' ? 'You are an admin' : 'You are a member'}
                                </div>
                                <div>
                                    {squadron.member_count} {squadron.member_count === 1 ? 'member' : 'members'}
                                    {' · '}
                                    {squadron.contest_count} {squadron.contest_count === 1 ? 'contest' : 'contests'}
                                </div>
                            </div>
                        </div>
                    </Link>
                ))}
            </div>

            {access.length > 0 && (
                <div className="card bg-base-200 border border-base-300">
                    <div className="card-body p-5 space-y-2">
                        <h2 className="card-title text-lg flex items-center gap-2"><Trophy size={18} /> Contests you can open through your squadrons</h2>
                        <p className="text-sm opacity-70">A contest shared with several of your squadrons is listed once, with all of them.</p>
                        {access.map(contest => (
                            <div key={contest.id} className="bg-base-100 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                <div>
                                    <Link className="link font-semibold" to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contest.id })}>
                                        {contest.name}
                                    </Link>
                                    <div className="text-xs opacity-70">{formatDate(contest.start_time)}</div>
                                </div>
                                <div className="flex flex-wrap gap-1">
                                    {contest.squadrons.map(squadron => (
                                        <Link
                                            key={squadron.id}
                                            className="badge badge-outline hover:badge-primary"
                                            to={generatePath('SQUADRON_DETAIL', { squadronId: squadron.id })}
                                            title={`Shared with ${squadron.name}`}
                                        >
                                            {squadron.name}
                                        </Link>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <form onSubmit={create} className="card bg-base-200 border border-base-300">
                <div className="card-body p-5 space-y-3">
                    <h2 className="card-title text-lg flex items-center gap-2"><Plus size={18} /> Start a squadron</h2>
                    <input
                        className="input input-bordered w-full"
                        placeholder="Name"
                        maxLength={100}
                        value={name}
                        onChange={e => setName(e.target.value)}
                        required
                    />
                    <textarea
                        className="textarea textarea-bordered w-full"
                        placeholder="What is it for? (optional)"
                        value={description}
                        onChange={e => setDescription(e.target.value)}
                    />
                    <div className="card-actions justify-end">
                        <button className="btn btn-primary" disabled={busy || !name.trim()} type="submit">Create</button>
                    </div>
                </div>
            </form>
        </div>
    );
};

export default SquadronsPage;
