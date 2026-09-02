import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchNavigationTask } from '../competition-map/api';
import { NavigationTask } from '../competition-map/types';
import { useToast } from '../competition-map/hooks/useToast';
import { fetchScorecard, resetScorecard, saveScorecard } from './api';
import { SCALAR_FIELD_GROUPS } from './fieldMetadata';
import { GateSection } from './components/GateSection';
import { ScalarFieldGroup } from './components/ScalarFieldGroup';
import { buildSavePayload, emptyEditorState, isDirty } from './scorecardEditorLogic';
import { ScorecardData, ScorecardEditorState } from './types';

export default function ScorecardEditorPage() {
    const { contestId, navigationTaskId } = useParams<{ contestId: string; navigationTaskId: string }>();
    const navigate = useNavigate();
    const { showToast, ToastContainer, toasts, removeToast } = useToast();

    const [navigationTask, setNavigationTask] = useState<NavigationTask | null>(null);
    const [scorecard, setScorecard] = useState<ScorecardData | null>(null);
    const [editorState, setEditorState] = useState<ScorecardEditorState>(emptyEditorState());
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    const dirty = useMemo(() => isDirty(editorState), [editorState]);

    useEffect(() => {
        if (!contestId || !navigationTaskId) return;
        let cancelled = false;
        setLoading(true);
        Promise.all([
            fetchNavigationTask(Number(contestId), Number(navigationTaskId)),
            fetchScorecard(Number(contestId), Number(navigationTaskId)),
        ])
            .then(([task, scorecardData]) => {
                if (cancelled) return;
                setNavigationTask(task);
                setScorecard(scorecardData);
                setEditorState(emptyEditorState());
                setError(null);
            })
            .catch((err) => {
                if (!cancelled) setError(err.message);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [contestId, navigationTaskId]);

    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (dirty) {
                e.preventDefault();
                e.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [dirty]);

    const handleSave = async () => {
        if (!scorecard || !contestId || !navigationTaskId) return;
        setSaving(true);
        try {
            const payload = buildSavePayload(editorState);
            const updated = await saveScorecard(Number(contestId), Number(navigationTaskId), payload);
            setScorecard(updated);
            setEditorState(emptyEditorState());
            showToast('Scorecard saved.', 'success');
        } catch (err: any) {
            showToast(err.message ?? 'Failed to save scorecard.', 'error');
        } finally {
            setSaving(false);
        }
    };

    const handleResetToStandard = async () => {
        if (!contestId || !navigationTaskId) return;
        if (!window.confirm('Reset every scoring value on this task back to the standard scorecard? This cannot be undone.')) {
            return;
        }
        setSaving(true);
        try {
            const updated = await resetScorecard(Number(contestId), Number(navigationTaskId));
            setScorecard(updated);
            setEditorState(emptyEditorState());
            showToast('Scorecard reset to standard.', 'success');
        } catch (err: any) {
            showToast(err.message ?? 'Failed to reset scorecard.', 'error');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="container mx-auto p-4 md:p-8">
                <span className="loading loading-spinner loading-lg" />
            </div>
        );
    }

    if (error || !scorecard || !navigationTask) {
        return (
            <div className="container mx-auto p-4 md:p-8">
                <div className="alert alert-error">{error ?? 'Scorecard not found.'}</div>
            </div>
        );
    }

    const canEdit = navigationTask.user_has_change_permission;
    const applicableGates = scorecard.applicable_gate_types;

    return (
        <div className="container mx-auto p-4 md:p-8">
            <ToastContainer toasts={toasts} removeToast={removeToast} />
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h1 className="text-xl font-bold">{navigationTask.name}</h1>
                    <p className="text-sm text-base-content/70">Scoring parameters</p>
                </div>
                <div className="flex gap-2">
                    <button className="btn btn-secondary" onClick={() => navigate(-1)}>
                        Back
                    </button>
                    {canEdit && (
                        <>
                            <button className="btn btn-outline btn-error" onClick={handleResetToStandard} disabled={saving}>
                                Reset to standard
                            </button>
                            <button
                                className={`btn btn-primary ${saving ? 'loading' : ''}`}
                                onClick={handleSave}
                                disabled={!dirty || saving}
                            >
                                Save changes
                            </button>
                        </>
                    )}
                </div>
            </div>

            <p className="text-sm text-base-content/70 mb-6">
                Only fields relevant to this task's route are shown. Values marked with a dot differ from{' '}
                {scorecard.original_scorecard ? 'the standard scorecard' : 'standard'} and can be reset individually.
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="flex flex-col gap-4">
                    {SCALAR_FIELD_GROUPS.map((group) => (
                        <ScalarFieldGroup
                            key={group.title}
                            title={group.title}
                            fields={group.fields}
                            scorecard={scorecard}
                            state={editorState}
                            onChange={setEditorState}
                            disabled={!canEdit || saving}
                        />
                    ))}
                </div>
                <div className="flex flex-col gap-4">
                    {applicableGates.map((gateType) => (
                        <GateSection
                            key={gateType}
                            gateType={gateType}
                            scorecard={scorecard}
                            state={editorState}
                            onChange={setEditorState}
                            disabled={!canEdit || saving}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}
