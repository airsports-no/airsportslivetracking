import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { Loading } from '../route-editor/components/basicComponents';
import { fetchContestant, fetchNavigationTask, updateContestantDeclaration } from './api';
import { reverse } from '../../urls';
import { useToast } from '../competition-map/hooks/useToast';

type ContractNavigationFormState = {
    beforeMp: string[];
    afterMp: string[];
};

type DeclarationFormState = {
    compulsoryPointTimes: Record<string, string>;
    declaredEnduranceMinutes: string;
    contractNavigation: ContractNavigationFormState;
};

const toDatetimeLocalValue = (value?: string | null) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const splitContractNavigationDeclaration = (declaredSequence: unknown): ContractNavigationFormState => {
    const values = Array.isArray(declaredSequence) ? declaredSequence.filter((item): item is string => typeof item === 'string') : [];
    const mpIndex = values.indexOf('MP');
    const fpIndex = values.lastIndexOf('FP');
    if (mpIndex === -1 || fpIndex === -1 || fpIndex < mpIndex) {
        return { beforeMp: [], afterMp: [] };
    }
    return {
        beforeMp: values.slice(0, mpIndex).filter((item) => item !== 'SP'),
        afterMp: values.slice(mpIndex + 1, fpIndex),
    };
};

type ContractNavigationEditorProps = {
    availableTurnpoints: string[];
    value: ContractNavigationFormState;
    disabled?: boolean;
    onChange: (value: ContractNavigationFormState) => void;
};

const ContractNavigationEditor: React.FC<ContractNavigationEditorProps> = ({ availableTurnpoints, value, disabled = false, onChange }) => {
    const [draggedToken, setDraggedToken] = useState<string | null>(null);

    const used = new Set([...value.beforeMp, ...value.afterMp]);
    const unassigned = availableTurnpoints.filter((item) => !used.has(item));

    const handleDropToPool = () => {
        if (!draggedToken || disabled) return;
        onChange({
            beforeMp: value.beforeMp.filter((item) => item !== draggedToken),
            afterMp: value.afterMp.filter((item) => item !== draggedToken),
        });
        setDraggedToken(null);
    };

    const handleDropToLane = (lane: 'beforeMp' | 'afterMp', targetIndex?: number) => {
        if (!draggedToken || disabled) return;
        const sourceLane = value.beforeMp.includes(draggedToken) ? 'beforeMp' : value.afterMp.includes(draggedToken) ? 'afterMp' : 'pool';
        let nextBefore = [...value.beforeMp];
        let nextAfter = [...value.afterMp];

        if (sourceLane === 'beforeMp') {
            nextBefore = nextBefore.filter((item) => item !== draggedToken);
        } else if (sourceLane === 'afterMp') {
            nextAfter = nextAfter.filter((item) => item !== draggedToken);
        }

        const targetList = lane === 'beforeMp' ? nextBefore : nextAfter;
        const insertionIndex = targetIndex === undefined ? targetList.length : Math.max(0, Math.min(targetIndex, targetList.length));
        targetList.splice(insertionIndex, 0, draggedToken);

        onChange({ beforeMp: nextBefore, afterMp: nextAfter });
        setDraggedToken(null);
    };

    return (
        <div className="space-y-4">
            <div>
                <div className="label">
                    <span className="label-text font-medium">Available catalogue turnpoints</span>
                </div>
                <div
                    className="min-h-16 rounded-lg border border-dashed border-base-300 bg-base-200/50 p-3 flex flex-wrap gap-2"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                        event.preventDefault();
                        handleDropToPool();
                    }}
                >
                    {unassigned.length > 0 ? (
                        unassigned.map((token) => (
                            <div
                                key={`pool-${token}`}
                                className="rounded border border-base-300 bg-base-100 px-3 py-2 text-sm"
                                draggable={!disabled}
                                onDragStart={() => setDraggedToken(token)}
                            >
                                {token}
                            </div>
                        ))
                    ) : (
                        <span className="text-sm opacity-60">All turnpoints assigned.</span>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {([
                    ['beforeMp', 'Before MP'],
                    ['afterMp', 'After MP'],
                ] as const).map(([lane, label]) => {
                    const items = lane === 'beforeMp' ? value.beforeMp : value.afterMp;
                    return (
                        <div key={lane}>
                            <div className="label">
                                <span className="label-text font-medium">{label}</span>
                            </div>
                            <div
                                className="min-h-24 rounded-lg border border-base-300 bg-base-100 p-3 space-y-2"
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={(event) => {
                                    event.preventDefault();
                                    handleDropToLane(lane);
                                }}
                            >
                                {items.length === 0 ? (
                                    <span className="text-sm opacity-60">Drop turnpoints here.</span>
                                ) : (
                                    items.map((token, index) => (
                                        <div
                                            key={`${lane}-${token}`}
                                            className="rounded border border-base-300 bg-base-200/60 px-3 py-2 text-sm"
                                            draggable={!disabled}
                                            onDragStart={() => setDraggedToken(token)}
                                            onDragOver={(event) => event.preventDefault()}
                                            onDrop={(event) => {
                                                event.preventDefault();
                                                handleDropToLane(lane, index);
                                            }}
                                        >
                                            {token}
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

const ContestantDeclarationPage: React.FC = () => {
    const { contestId, navigationTaskId, contestantId } = useParams();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [navigationTask, setNavigationTask] = useState<any | null>(null);
    const [contestant, setContestant] = useState<any | null>(null);
    const [formState, setFormState] = useState<DeclarationFormState>({
        compulsoryPointTimes: {},
        declaredEnduranceMinutes: '',
        contractNavigation: { beforeMp: [], afterMp: [] },
    });
    const [error, setError] = useState<string | null>(null);
    const { showToast, ToastContainer, toasts, removeToast } = useToast();

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            if (!contestId || !navigationTaskId || !contestantId) {
                setError('Missing declaration route parameters.');
                setLoading(false);
                return;
            }
            setLoading(true);
            setError(null);
            try {
                const [task, contestantData] = await Promise.all([
                    fetchNavigationTask(Number(contestId), Number(navigationTaskId)),
                    fetchContestant(Number(contestId), Number(navigationTaskId), Number(contestantId)),
                ]);
                if (cancelled) return;
                setNavigationTask(task);
                setContestant(contestantData);

                const compiledPayload = contestantData.compiled_effective_route_payload || {};
                const compulsoryPointNames: string[] = compiledPayload.compulsory_point_names || compiledPayload.compulsory_timing_gate_names || [];
                const declarationPayload = contestantData.declaration_payload || {};
                const pointTimes = declarationPayload.compulsory_point_times || {};
                const fuelMetadata = declarationPayload.fuel_metadata || {};
                const contractNavigation = splitContractNavigationDeclaration(declarationPayload.declared_sequence);
                const compulsoryPointTimes = compulsoryPointNames.reduce((acc: Record<string, string>, name: string) => {
                    acc[name] = toDatetimeLocalValue(pointTimes[name]);
                    return acc;
                }, {});
                setFormState({
                    compulsoryPointTimes,
                    declaredEnduranceMinutes: fuelMetadata.declared_endurance_minutes ? String(fuelMetadata.declared_endurance_minutes) : '',
                    contractNavigation,
                });
            } catch (err: any) {
                if (!cancelled) {
                    const message = err?.message || 'Failed to load declaration data.';
                    setError(message);
                    showToast(message, 'error');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        load();
        return () => {
            cancelled = true;
        };
    }, [contestId, navigationTaskId, contestantId, showToast]);

    const compiledPayload = contestant?.compiled_effective_route_payload || {};
    const compulsoryPointNames: string[] = compiledPayload.compulsory_point_names || compiledPayload.compulsory_timing_gate_names || [];
    const freeTargets: Array<any> = compiledPayload.free_targets || [];
    const isLimitedFuel = navigationTask?.task_subtype === 'limited_fuel_turnpoint_hunt';
    const isContractNavigation = navigationTask?.task_subtype === 'contract_navigation_time_controls';
    const availableContractTurnpoints: string[] = compiledPayload.compiled_task_primitives?.catalogue_turnpoint || [];

    const canSave = useMemo(() => {
        if (isContractNavigation) {
            return formState.contractNavigation.beforeMp.length + formState.contractNavigation.afterMp.length > 0;
        }
        return compulsoryPointNames.every((name) => !!formState.compulsoryPointTimes[name]);
    }, [compulsoryPointNames, formState.compulsoryPointTimes, formState.contractNavigation, isContractNavigation]);

    const handleTimeChange = (name: string, value: string) => {
        setFormState((prev) => ({
            ...prev,
            compulsoryPointTimes: {
                ...prev.compulsoryPointTimes,
                [name]: value,
            },
        }));
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!contestId || !navigationTaskId || !contestantId) return;
        setSaving(true);
        setError(null);
        try {
            const declarationPayload: Record<string, any> = {};
            if (isContractNavigation) {
                declarationPayload.declared_sequence = [
                    ...formState.contractNavigation.beforeMp,
                    'MP',
                    ...formState.contractNavigation.afterMp,
                    'FP',
                ];
            } else {
                declarationPayload.compulsory_point_times = Object.fromEntries(
                    Object.entries(formState.compulsoryPointTimes).filter(([, value]) => !!value),
                );
                if (isLimitedFuel && formState.declaredEnduranceMinutes) {
                    declarationPayload.fuel_metadata = {
                        declared_endurance_minutes: Number(formState.declaredEnduranceMinutes),
                    };
                }
            }
            const updatedContestant = await updateContestantDeclaration(
                Number(contestId),
                Number(navigationTaskId),
                Number(contestantId),
                declarationPayload,
            );
            setContestant(updatedContestant);
            showToast('Declaration saved.', 'success');
        } catch (err: any) {
            const message = err?.message || 'Failed to save declaration.';
            setError(message);
            showToast(message, 'error');
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <Loading />;

    if (error && !contestant) {
        return (
            <div className="container mx-auto p-4" data-theme="aviation">
                <ToastContainer toasts={toasts} removeToast={removeToast} />
                <div className="alert alert-error">{error}</div>
            </div>
        );
    }

    return (
        <div className="container mx-auto p-4 max-w-4xl" data-theme="aviation">
            <ToastContainer toasts={toasts} removeToast={removeToast} />
            <div className="flex items-center justify-between mb-4 gap-2">
                <div>
                    <h1 className="text-3xl font-bold">Contestant declaration</h1>
                    <p className="text-sm opacity-70">{contestant?.team?.crew?.member1?.first_name} {contestant?.team?.crew?.member1?.last_name} · {navigationTask?.name}</p>
                </div>
                <a href={reverse('navigationtask_detail', Number(navigationTaskId))} className="btn btn-secondary btn-sm">
                    Back to navigation task
                </a>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="card bg-base-100 shadow-xl">
                    <div className="card-body">
                        <h2 className="card-title">{isContractNavigation ? 'Declaration sequence' : 'Compulsory point declaration'}</h2>
                        <form className="space-y-4" onSubmit={handleSubmit}>
                            {isContractNavigation ? (
                                <ContractNavigationEditor
                                    availableTurnpoints={availableContractTurnpoints}
                                    value={formState.contractNavigation}
                                    onChange={(contractNavigation) => setFormState((prev) => ({ ...prev, contractNavigation }))}
                                    disabled={saving}
                                />
                            ) : (
                                compulsoryPointNames.map((name) => (
                                    <label className="form-control w-full" key={name}>
                                        <span className="label-text font-medium">Predicted time for {name}</span>
                                        <input
                                            type="datetime-local"
                                            step={60}
                                            className="input input-bordered w-full"
                                            value={formState.compulsoryPointTimes[name] || ''}
                                            onChange={(e) => handleTimeChange(name, e.target.value)}
                                            required
                                        />
                                    </label>
                                ))
                            )}
                            {!isContractNavigation && isLimitedFuel && (
                                <label className="form-control w-full">
                                    <span className="label-text font-medium">Declared fuel endurance (minutes)</span>
                                    <input
                                        type="number"
                                        min={1}
                                        className="input input-bordered w-full"
                                        value={formState.declaredEnduranceMinutes}
                                        onChange={(e) => setFormState((prev) => ({ ...prev, declaredEnduranceMinutes: e.target.value }))}
                                    />
                                </label>
                            )}
                            {error && <div className="alert alert-error text-sm">{error}</div>}
                            <div className="card-actions justify-end">
                                <button type="submit" className={`btn btn-primary ${saving ? 'loading' : ''}`} disabled={!canSave || saving}>
                                    Save declaration
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <div className="card bg-base-100 shadow-xl">
                    <div className="card-body">
                        {isContractNavigation ? (
                            <>
                                <h2 className="card-title">Declaration preview</h2>
                                <div className="rounded-lg bg-base-200/60 p-4 text-sm space-y-2">
                                    <div><span className="font-medium">SP</span></div>
                                    <div><span className="font-medium">Before MP:</span> {formState.contractNavigation.beforeMp.join(', ') || '—'}</div>
                                    <div><span className="font-medium">MP</span></div>
                                    <div><span className="font-medium">After MP:</span> {formState.contractNavigation.afterMp.join(', ') || '—'}</div>
                                    <div><span className="font-medium">FP</span></div>
                                </div>
                            </>
                        ) : (
                            <>
                                <h2 className="card-title">Free targets</h2>
                                <p className="text-sm opacity-70">Free targets are unordered and require photo evidence.</p>
                                <div className="overflow-x-auto mt-2">
                                    <table className="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>Target</th>
                                                <th>Score</th>
                                                <th>Photo evidence</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {freeTargets.map((target) => (
                                                <tr key={target.name}>
                                                    <td className="font-medium">{target.name}</td>
                                                    <td>{target.score_value ?? '—'}</td>
                                                    <td>
                                                        {target.evidence?.length
                                                            ? target.evidence.map((item: any) => item.name).join(', ')
                                                            : 'Missing'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ContestantDeclarationPage;
