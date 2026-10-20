import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Copy, Link2, Plus, Trash2, UserPlus } from 'lucide-react';
import { generatePath } from '../../urls';
import PersonPicker from '../../components/common/PersonPicker';
import { PersonOption } from '../../components/common/personOption';
import { Loading } from '../route-editor/components/basicComponents';
import {
    ShareableContest,
    SquadronDetail,
    SquadronRole,
    addContestToSquadron,
    deleteSquadron,
    disableSquadronInviteLink,
    enableSquadronInviteLink,
    fetchShareableContests,
    fetchSquadron,
    inviteLinkUrl,
    inviteToSquadron,
    leaveSquadron,
    removeContestFromSquadron,
    removeSquadronMember,
    revokeSquadronInvitation,
    setSquadronMemberRole,
    updateSquadron,
} from './api';

const ROLE_LABELS: Record<SquadronRole, string> = { admin: 'Admin', member: 'Member' };

/**
 * One squadron: its members and, for an admin, who can be invited and which roles people have. Admins manage the members
 * only; a squadron gives nobody the right to manage a contest.
 */
const SquadronDetailPage: React.FC = () => {
    const { squadronId } = useParams<{ squadronId: string }>();
    const navigate = useNavigate();
    const id = Number(squadronId);
    const [squadron, setSquadron] = useState<SquadronDetail | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [person, setPerson] = useState<PersonOption | null>(null);
    const [email, setEmail] = useState('');
    const [inviteRole, setInviteRole] = useState<SquadronRole>('member');
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [shareable, setShareable] = useState<ShareableContest[]>([]);
    const [contestChoice, setContestChoice] = useState('');
    const [copied, setCopied] = useState(false);

    const [reloads, setReloads] = useState(0);
    const load = () => setReloads(count => count + 1);

    useEffect(() => {
        let cancelled = false;
        fetchShareableContests(id)
            .then(contests => {
                if (!cancelled) setShareable(contests);
            })
            .catch(() => {});
        fetchSquadron(id)
            .then(data => {
                if (cancelled) return;
                setSquadron(data);
                setName(data.name);
                setDescription(data.description);
                setError(null);
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
            load();
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    const backToList = () => navigate(generatePath('SQUADRONS', {}));

    if (!squadron) {
        return error ? <div role="alert" className="alert alert-error m-4">{error}</div> : <div className="p-8 flex justify-center"><Loading /></div>;
    }

    const isAdmin = squadron.my_role === 'admin';
    const adminCount = squadron.members.filter(member => member.role === 'admin').length;
    const invitee = person ? String(person.value) : email.trim();

    const invite = (event: React.FormEvent) => {
        event.preventDefault();
        run(async () => {
            await inviteToSquadron(id, invitee, inviteRole);
            setPerson(null);
            setEmail('');
        });
    };

    return (
        <div className="max-w-3xl mx-auto p-4 space-y-6">
            <Link to={generatePath('SQUADRONS', {})} className="btn btn-ghost btn-sm gap-1"><ArrowLeft size={16} /> Squadrons</Link>

            {error && <div role="alert" className="alert alert-error">{error}</div>}

            <div className="space-y-1">
                <h1 className="text-2xl font-bold">{squadron.name}</h1>
                {squadron.description && <p className="opacity-70">{squadron.description}</p>}
                <p className="text-sm opacity-70">
                    {isAdmin
                        ? 'You are an admin: you invite and remove people, and you can take away any contest. Members can see and take part in the contests shared with the squadron, but not change them.'
                        : 'You are a member: you can see and take part in the contests shared with this squadron. Only an admin invites people.'}
                </p>
            </div>

            <div className="card bg-base-200 border border-base-300">
                <div className="card-body p-5 space-y-2">
                    <h2 className="card-title text-lg">Members</h2>
                    {squadron.members.map(member => {
                        const isLastAdmin = member.role === 'admin' && adminCount <= 1;
                        return (
                            <div key={member.id} className="bg-base-100 rounded-lg p-3 flex items-center justify-between gap-2 text-sm">
                                <span>
                                    {member.name || '(no name)'} <span className="opacity-60 font-mono text-xs">{member.email_hint}</span>
                                </span>
                                <div className="flex items-center gap-2">
                                    {isAdmin ? (
                                        <select
                                            className="select select-bordered select-xs"
                                            value={member.role}
                                            disabled={busy || isLastAdmin}
                                            title={isLastAdmin ? 'A squadron needs at least one admin' : undefined}
                                            onChange={e => run(() => setSquadronMemberRole(id, member.id, e.target.value as SquadronRole))}
                                        >
                                            <option value="member">{ROLE_LABELS.member}</option>
                                            <option value="admin">{ROLE_LABELS.admin}</option>
                                        </select>
                                    ) : (
                                        <span className="badge badge-outline">{ROLE_LABELS[member.role]}</span>
                                    )}
                                    {isAdmin && member.user_id !== (document.configuration.userId ?? -1) && (
                                        <button className="btn btn-xs btn-outline btn-error" disabled={busy} onClick={() => run(() => removeSquadronMember(id, member.id))}>
                                            Remove
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {isAdmin && (
                <div className="card bg-base-200 border border-base-300">
                    <div className="card-body p-5 space-y-3">
                        <h2 className="card-title text-lg flex items-center gap-2"><UserPlus size={18} /> Invite</h2>
                        <p className="text-sm opacity-70">They join when they accept. Find somebody who has an account by name, or type an e-mail address.</p>
                        {squadron.invitations.map(invitation => (
                            <div key={invitation.id} className="bg-base-100 rounded-lg p-3 flex items-center justify-between gap-2 text-sm">
                                <span>
                                    <span className="font-mono text-xs">{invitation.email_hint}</span> invited as {invitation.role}
                                </span>
                                <button className="btn btn-xs btn-outline" disabled={busy} onClick={() => run(() => revokeSquadronInvitation(id, invitation.id))}>
                                    Cancel
                                </button>
                            </div>
                        ))}
                        <form onSubmit={invite} className="flex flex-col md:flex-row gap-2">
                            <div className="flex-1 min-w-0 space-y-2">
                                <PersonPicker kind="user" value={person} onChange={setPerson} placeholder="Type a name to search for a user" />
                                {!person && (
                                    <input
                                        className="input input-bordered input-sm w-full"
                                        type="email"
                                        placeholder="…or an e-mail address"
                                        value={email}
                                        onChange={e => setEmail(e.target.value)}
                                    />
                                )}
                            </div>
                            <select className="select select-bordered select-sm" value={inviteRole} onChange={e => setInviteRole(e.target.value as SquadronRole)}>
                                <option value="member">{ROLE_LABELS.member}</option>
                                <option value="admin">{ROLE_LABELS.admin}</option>
                            </select>
                            <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !invitee}>Invite</button>
                        </form>
                    </div>
                </div>
            )}

            {isAdmin && (
                <div className="card bg-base-200 border border-base-300">
                    <div className="card-body p-5 space-y-2">
                        <h2 className="card-title text-lg flex items-center gap-2"><Link2 size={18} /> Invite link</h2>
                        <p className="text-sm opacity-70">
                            Post the link in your group chat. Anybody who is logged in and opens it can join as a member by pressing Join. Anyone
                            with the link can use it, so switch it off, or make a new one, when it has been shared too widely.
                        </p>
                        {squadron.invite_token ? (
                            <>
                                <div className="join w-full">
                                    <input className="input input-bordered input-sm join-item w-full font-mono text-xs" readOnly value={inviteLinkUrl(squadron.invite_token)} onFocus={e => e.target.select()} />
                                    <button
                                        className="btn btn-sm join-item gap-1"
                                        onClick={async () => {
                                            try {
                                                await navigator.clipboard.writeText(inviteLinkUrl(squadron.invite_token!));
                                                setCopied(true);
                                                setTimeout(() => setCopied(false), 2000);
                                            } catch {
                                                setError('Could not copy the link. Select it and copy it by hand.');
                                            }
                                        }}
                                    >
                                        <Copy size={14} /> {copied ? 'Copied' : 'Copy'}
                                    </button>
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <button
                                        className="btn btn-outline btn-sm"
                                        disabled={busy}
                                        onClick={() => {
                                            if (window.confirm('Make a new link? The old one stops working.')) run(() => enableSquadronInviteLink(id));
                                        }}
                                    >
                                        New link
                                    </button>
                                    <button className="btn btn-outline btn-error btn-sm" disabled={busy} onClick={() => run(() => disableSquadronInviteLink(id))}>
                                        Switch off
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="flex justify-end">
                                <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(() => enableSquadronInviteLink(id))}>
                                    Create an invite link
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}

            <div className="card bg-base-200 border border-base-300">
                <div className="card-body p-5 space-y-2">
                    <h2 className="card-title text-lg">Contests</h2>
                    <p className="text-sm opacity-70">
                        Everybody in the squadron can see these contests, also when they are private, and take part in them. They cannot
                        change them. Add a contest you manage to give the whole squadron access to it; take it away again with Remove. You can
                        remove the contests you added{isAdmin ? ', and as an admin any of them' : ''}.
                    </p>
                    {squadron.contests.length === 0 && <p className="text-sm opacity-70">No contest is shared with the squadron yet.</p>}
                    {squadron.contests.map(contest => (
                        <div key={contest.id} className="bg-base-100 rounded-lg p-3 flex items-center justify-between gap-2 text-sm">
                            <span>
                                <Link className="link font-semibold" to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contest.id })}>{contest.name}</Link>
                                <span className="opacity-60 text-xs ml-2">
                                    {contest.shared_by_me ? 'added by you' : contest.shared_by_name ? `added by ${contest.shared_by_name}` : ''}
                                </span>
                            </span>
                            {contest.can_remove && (
                                <button className="btn btn-xs btn-outline btn-error" disabled={busy} onClick={() => run(() => removeContestFromSquadron(id, contest.id))}>
                                    Remove
                                </button>
                            )}
                        </div>
                    ))}
                    {shareable.length > 0 ? (
                        <div className="flex gap-2 pt-1">
                            <select className="select select-bordered select-sm flex-1" value={contestChoice} onChange={e => setContestChoice(e.target.value)}>
                                <option value="">Add a contest you manage…</option>
                                {shareable.map(contest => (
                                    <option key={contest.id} value={contest.id}>{contest.name}</option>
                                ))}
                            </select>
                            <button
                                className="btn btn-primary btn-sm gap-1"
                                disabled={busy || !contestChoice}
                                onClick={() => run(async () => {
                                    await addContestToSquadron(id, Number(contestChoice));
                                    setContestChoice('');
                                })}
                            >
                                <Plus size={14} /> Add
                            </button>
                        </div>
                    ) : (
                        <p className="text-xs opacity-60">Only contests you manage can be added, and every one of them is already shared with this squadron.</p>
                    )}
                </div>
            </div>

            {isAdmin && (
                <form
                    className="card bg-base-200 border border-base-300"
                    onSubmit={event => {
                        event.preventDefault();
                        run(() => updateSquadron(id, name, description));
                    }}
                >
                    <div className="card-body p-5 space-y-3">
                        <h2 className="card-title text-lg">Details</h2>
                        <input className="input input-bordered w-full" maxLength={100} value={name} onChange={e => setName(e.target.value)} required />
                        <textarea className="textarea textarea-bordered w-full" value={description} onChange={e => setDescription(e.target.value)} />
                        <div className="card-actions justify-end">
                            <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !name.trim()}>Save</button>
                        </div>
                    </div>
                </form>
            )}

            <div className="flex flex-wrap gap-2 justify-end">
                <button
                    className="btn btn-outline btn-sm"
                    disabled={busy}
                    onClick={async () => {
                        if (!window.confirm(`Leave ${squadron.name}? You lose access to the contests shared only with it.`)) return;
                        setBusy(true);
                        try {
                            await leaveSquadron(id);
                            backToList();
                        } catch (e) {
                            setError((e as Error).message);
                            setBusy(false);
                        }
                    }}
                >
                    Leave squadron
                </button>
                {isAdmin && (
                    <button
                        className="btn btn-outline btn-error btn-sm gap-1"
                        disabled={busy}
                        onClick={async () => {
                            if (!window.confirm(`Delete ${squadron.name}? Its members lose access to the contests shared only with it.`)) return;
                            setBusy(true);
                            try {
                                await deleteSquadron(id);
                                backToList();
                            } catch (e) {
                                setError((e as Error).message);
                                setBusy(false);
                            }
                        }}
                    >
                        <Trash2 size={14} /> Delete squadron
                    </button>
                )}
            </div>
        </div>
    );
};

export default SquadronDetailPage;
