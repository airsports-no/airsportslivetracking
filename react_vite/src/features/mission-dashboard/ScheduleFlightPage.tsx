import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { fetchContest, fetchMyContestTeams } from './api';
import { Contest, MyContestTeam } from './types';
import ScheduleFlightForm from './components/ScheduleFlightForm';
import { Loading } from '../route-editor/components/basicComponents';
import { generatePath, reverse } from '../../urls';

const ScheduleFlightPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const contestId = Number(searchParams.get('contestId'));
    const navigationTaskId = Number(searchParams.get('navigationTaskId'));

    const [contest, setContest] = useState<Contest | null>(null);
    const [myContestTeams, setMyContestTeams] = useState<MyContestTeam[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!contestId || !navigationTaskId) {
            setError("Missing contestId or navigationTaskId query parameters.");
            setLoading(false);
            return;
        }

        const loadData = async () => {
            try {
                const [contestData, teamsData] = await Promise.all([
                    fetchContest(contestId),
                    fetchMyContestTeams()
                ]);
                setContest(contestData);
                setMyContestTeams(teamsData);
                setLoading(false);
            } catch (err: any) {
                if (err.status === 401 || err.status === 403) {
                    const next = encodeURIComponent(window.location.pathname + window.location.search);
                    let loginUrl = reverse('login');
                    if (loginUrl.includes('url-initialization-failed')) {
                        loginUrl = '/accounts/login/';
                    }
                    window.location.href = `${loginUrl}?next=${next}`;
                    return;
                }
                setError((err as Error).message);
                setLoading(false);
            }
        };


        loadData();
    }, [contestId, navigationTaskId]);

    if (loading) return <div className="min-h-screen flex items-center justify-center bg-base-200"><Loading /></div>;
    if (error) return <div className="min-h-screen flex flex-col items-center justify-center bg-base-200 p-4"><div className="alert alert-error max-w-md">{error}</div><button className="btn btn-ghost mt-4" onClick={() => navigate(-1)}>Back</button></div>;
    if (!contest) return <div className="min-h-screen flex items-center justify-center bg-base-200"><div className="alert alert-warning">Contest not found.</div></div>;

    return (
        <div className="min-h-screen bg-base-200 p-4 md:p-8">
            <div className="max-w-4xl mx-auto">
                <ScheduleFlightForm
                    contest={contest}
                    navigationTaskId={navigationTaskId}
                    myContestTeams={myContestTeams}
                    onClose={(warnings?: string[]) => {
                        if (warnings && warnings.length > 0) {
                            // In a real app we might want to pass these back via state or toast
                            console.warn("Warnings from scheduling:", warnings);
                        }
                        // Navigate back to the competition map
                        navigate(generatePath('COMPETITION_MAP_DETAIL', { contestId, navigationTaskId }));
                    }}
                />
            </div>
        </div>
    );
};

export default ScheduleFlightPage;
