import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Users } from 'lucide-react';
import { generatePath, reverse } from '../../urls';
import { Loading } from '../route-editor/components/basicComponents';
import { ApiError, JoinPreview, fetchJoinPreview, joinSquadronViaLink } from './api';

/**
 * Where a squadron's invite link leads. A visitor who is not logged in is sent to log in and brought back; a logged-in
 * one sees which squadron it is and joins, as a member, by pressing Join. Pressing Join is the acceptance.
 */
const SquadronJoinPage: React.FC = () => {
    const { token } = useParams<{ token: string }>();
    const navigate = useNavigate();
    const [preview, setPreview] = useState<JoinPreview | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (!document.configuration.isAuthenticated) {
            const next = encodeURIComponent(window.location.pathname);
            let loginUrl = reverse('login');
            if (loginUrl.includes('url-initialization-failed')) {
                loginUrl = '/accounts/login/';
            }
            window.location.href = `${loginUrl}?next=${next}`;
            return;
        }
        let cancelled = false;
        fetchJoinPreview(token ?? '')
            .then(data => {
                if (!cancelled) setPreview(data);
            })
            .catch(e => {
                if (cancelled) return;
                setError(e instanceof ApiError && e.status === 404 ? 'This invite link does not work any more. Ask the squadron admin for a new one.' : (e as Error).message);
            });
        return () => {
            cancelled = true;
        };
    }, [token]);

    const join = async () => {
        setBusy(true);
        setError(null);
        try {
            const joined = await joinSquadronViaLink(token ?? '');
            navigate(generatePath('SQUADRON_DETAIL', { squadronId: joined.id }));
        } catch (e) {
            setError((e as Error).message);
            setBusy(false);
        }
    };

    if (error) {
        return (
            <div className="max-w-md mx-auto p-4 space-y-4">
                <div role="alert" className="alert alert-error">{error}</div>
                <Link to={generatePath('SQUADRONS', {})} className="btn btn-ghost btn-sm">Your squadrons</Link>
            </div>
        );
    }
    if (!preview) {
        return <div className="p-8 flex justify-center"><Loading /></div>;
    }

    return (
        <div className="max-w-md mx-auto p-4">
            <div className="card bg-base-100 border border-base-300 shadow">
                <div className="card-body space-y-2">
                    <h1 className="card-title flex items-center gap-2"><Users size={22} /> {preview.name}</h1>
                    {preview.description && <p className="opacity-80">{preview.description}</p>}
                    <p className="text-sm opacity-70">
                        {preview.member_count} {preview.member_count === 1 ? 'member' : 'members'}. When an organiser shares a contest with the
                        squadron, all its members can see it, also when it is private, and take part in it.
                    </p>
                    <div className="card-actions justify-end pt-2">
                        {preview.already_member ? (
                            <Link to={generatePath('SQUADRONS', {})} className="btn btn-primary">You are already in it</Link>
                        ) : (
                            <button className="btn btn-primary" disabled={busy} onClick={join}>Join the squadron</button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SquadronJoinPage;
