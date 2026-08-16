import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { Loading } from '../route-editor/components/basicComponents';
import { fetchContestant, fetchNavigationTask, updateContestantDeclaration } from './api';
import { reverse } from '../../urls';
import { useToast } from '../competition-map/hooks/useToast';

type FreeTarget = {
    name: string;
    score_value?: number;
    evidence?: { name: string }[];
};

type SequenceLane = {
    beforeMp: string[];
    afterMp: string[];
};

type ContestantDeclarationData = {
    declaration_payload?: Record<string, unknown>;
    compiled_effective_route_payload?: {
        compulsory_point_names?: string[];
        compulsory_timing_gate_names?: string[];
        free_targets?: FreeTarget[];
        free_target_names?: string[];
        time_model?: { t_seconds?: number };
        compiled_task_primitives?: {
            catalogue_turnpoint?: string[];
        };
        waypoint_names?: string[];
    };
};

type ContractNavigationFormState = SequenceLane;

type DeclarationFormState = {
    compulsoryPointTimes: Record<string, string>;
    declaredEnduranceMinutes: string;
    contractNavigation: ContractNavigationFormState;
    contractDeclaredTSeconds: string;
    turnpointHuntSequence: string[];
    turnpointTimeOverrides: Record<string, string>;
};

type DeclarationPageData = {
    navigationTask: Record<string, any> | null;
    contestant: (Record<string, any> & ContestantDeclarationData) | null;
    formState: DeclarationFormState;
};

const EMPTY_FORM_STATE: DeclarationFormState = {
    compulsoryPointTimes: {},
    declaredEnduranceMinutes: '',
    contractNavigation: { beforeMp: [], afterMp: [] },
    contractDeclaredTSeconds: '',
    turnpointHuntSequence: [],
    turnpointTimeOverrides: {},
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

const buildContractNavigationSequence = (contractNavigation: ContractNavigationFormState): string[] => ([
    'SP',
    ...contractNavigation.beforeMp,
    'MP',
    ...contractNavigation.afterMp,
    'FP',
]);

const normalizeContractNavigationSequence = (
    sequence: string[],
    allowedTurnpointNames: string[],
): string[] => {
    const currentSequence = sequence.filter((item) => typeof item === 'string' && item);
    const allowedTurnpoints = new Set(allowedTurnpointNames);
    const mpIndex = currentSequence.indexOf('MP');
    const declaredTurnpoints = currentSequence.filter((item) => allowedTurnpoints.has(item));
    const uniqueTurnpoints = declaredTurnpoints.filter((item, index) => declaredTurnpoints.indexOf(item) === index);
    const beforeMp = uniqueTurnpoints.filter((item) => {
        const itemIndex = currentSequence.indexOf(item);
        return mpIndex === -1 || itemIndex < mpIndex;
    });
    const afterMp = uniqueTurnpoints.filter((item) => !beforeMp.includes(item));
    return ['SP', ...beforeMp, 'MP', ...afterMp, 'FP'];
};

const getCompiledPayload = (contestant: ContestantDeclarationData | null | undefined) => (
    contestant?.compiled_effective_route_payload || {}
);

const getCompulsoryPointNames = (contestant: ContestantDeclarationData | null | undefined): string[] => {
    const compiledPayload = getCompiledPayload(contestant);
    return compiledPayload.compulsory_point_names || compiledPayload.compulsory_timing_gate_names || [];
};

const getTurnpointHuntSequence = (contestant: ContestantDeclarationData | null | undefined): string[] => {
    const compiledPayload = getCompiledPayload(contestant);
    const declarationPayload = contestant?.declaration_payload || {};
    const declaredSequence = Array.isArray(declarationPayload.declared_sequence)
        ? declarationPayload.declared_sequence.filter((item): item is string => typeof item === 'string')
        : [];
    if (declaredSequence.length > 0) {
        return declaredSequence;
    }
    return compiledPayload.free_target_names || [];
};

const getContractNavigationSequence = (contestant: ContestantDeclarationData | null | undefined): string[] => {
    const declarationPayload = contestant?.declaration_payload || {};
    const declaredSequence = Array.isArray(declarationPayload.declared_sequence)
        ? declarationPayload.declared_sequence.filter((item): item is string => typeof item === 'string')
        : [];
    if (declaredSequence.length > 0) {
        return declaredSequence;
    }
    return ['SP', 'MP', 'FP'];
};

const normalizeTurnpointHuntSequence = (
    sequence: string[],
    orderedCompulsoryPointNames: string[],
    allowedFreeTargetNames: string[],
) => {
    const currentSequence = sequence.filter((item) => typeof item === 'string' && item);
    const compulsorySet = new Set(orderedCompulsoryPointNames);
    const freeTargetSet = new Set(allowedFreeTargetNames);
    const declaredFreeTargets = currentSequence.filter((item) => !compulsorySet.has(item) && freeTargetSet.has(item));
    const uniqueFreeTargets = declaredFreeTargets.filter((item, index) => declaredFreeTargets.indexOf(item) === index);

    const slotEntries = uniqueFreeTargets.map((targetName) => {
        const targetIndex = currentSequence.indexOf(targetName);
        const slot = currentSequence.filter((item, index) => compulsorySet.has(item) && index < targetIndex).length;
        return { slot, targetName };
    });

    const freeTargetsBySlot = new Map<number, string[]>();
    for (const { slot, targetName } of slotEntries) {
        const existing = freeTargetsBySlot.get(slot) || [];
        existing.push(targetName);
        freeTargetsBySlot.set(slot, existing);
    }

    const normalized: string[] = [];
    for (let slot = 0; slot <= orderedCompulsoryPointNames.length; slot += 1) {
        normalized.push(...(freeTargetsBySlot.get(slot) || []));
        if (slot < orderedCompulsoryPointNames.length) {
            normalized.push(orderedCompulsoryPointNames[slot]);
        }
    }
    return normalized;
};

const buildFormState = (contestantData: ContestantDeclarationData): DeclarationFormState => {
    const compiledPayload = getCompiledPayload(contestantData);
    const declarationPayload = contestantData.declaration_payload || {};
    const compulsoryPointNames = getCompulsoryPointNames(contestantData);
    const pointTimes = declarationPayload.compulsory_point_times as Record<string, string> | undefined;
    const fuelMetadata = declarationPayload.fuel_metadata as { declared_endurance_minutes?: number } | undefined;
    const declaredTSeconds = declarationPayload.declared_t_seconds;

    const compulsoryPointTimes = compulsoryPointNames.reduce((acc: Record<string, string>, name: string) => {
        acc[name] = toDatetimeLocalValue(pointTimes?.[name]);
        return acc;
    }, {});

    const overridesPayload = declarationPayload.turnpoint_time_overrides as Record<string, string> | undefined;
    const turnpointTimeOverrides = Object.entries(overridesPayload || {}).reduce((acc: Record<string, string>, [name, value]) => {
        acc[name] = toDatetimeLocalValue(value);
        return acc;
    }, {});

    return {
        compulsoryPointTimes,
        declaredEnduranceMinutes: fuelMetadata?.declared_endurance_minutes ? String(fuelMetadata.declared_endurance_minutes) : '',
        contractNavigation: splitContractNavigationDeclaration(getContractNavigationSequence(contestantData)),
        contractDeclaredTSeconds: declaredTSeconds != null
            ? String(declaredTSeconds)
            : String(compiledPayload.time_model?.t_seconds ?? ''),
        turnpointHuntSequence: getTurnpointHuntSequence(contestantData),
        turnpointTimeOverrides,
    };
};

function useContestantDeclarationData(
    contestId: string | undefined,
    navigationTaskId: string | undefined,
    contestantId: string | undefined,
    showToast: (message: string, type?: 'success' | 'error' | 'info' | 'warning') => void,
) {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<DeclarationPageData>({
        navigationTask: null,
        contestant: null,
        formState: EMPTY_FORM_STATE,
    });
    const [error, setError] = useState<string | null>(null);

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
                setData({
                    navigationTask: task,
                    contestant: contestantData,
                    formState: buildFormState(contestantData),
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

    return {
        loading,
        error,
        setError,
        data,
        setNavigationTask: (navigationTask: Record<string, any> | null) => setData((prev) => ({ ...prev, navigationTask })),
        setContestant: (contestant: (Record<string, any> & ContestantDeclarationData) | null) => setData((prev) => ({ ...prev, contestant })),
        setFormState: (next: React.SetStateAction<DeclarationFormState>) => setData((prev) => ({
            ...prev,
            formState: typeof next === 'function' ? (next as (current: DeclarationFormState) => DeclarationFormState)(prev.formState) : next,
        })),
    };
}

type ContractNavigationEditorProps = {
    availableTurnpoints: string[];
    value: ContractNavigationFormState;
    disabled?: boolean;
    onChange: (value: ContractNavigationFormState) => void;
};

const moveItem = (items: string[], fromIndex: number, toIndex: number) => {
    const next = [...items];
    const [item] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, item);
    return next;
};

const moveItemToInsertionIndex = (items: string[], fromIndex: number, insertionIndex: number) => {
    const next = [...items];
    const [item] = next.splice(fromIndex, 1);
    const adjustedInsertionIndex = fromIndex < insertionIndex ? insertionIndex - 1 : insertionIndex;
    next.splice(Math.max(0, Math.min(adjustedInsertionIndex, next.length)), 0, item);
    return next;
};

const ContractNavigationEditor: React.FC<ContractNavigationEditorProps> = ({ availableTurnpoints, value, disabled = false, onChange }) => {
    const [draggedToken, setDraggedToken] = useState<string | null>(null);

    const currentSequence = buildContractNavigationSequence(value);
    const used = new Set([...value.beforeMp, ...value.afterMp]);
    const unassigned = availableTurnpoints.filter((item) => !used.has(item));

    const updateLane = (lane: 'beforeMp' | 'afterMp', updater: (items: string[]) => string[]) => {
        onChange({
            ...value,
            [lane]: updater(lane === 'beforeMp' ? value.beforeMp : value.afterMp),
        });
    };

    const addToLane = (lane: 'beforeMp' | 'afterMp', token: string) => {
        if (disabled) return;
        const target = lane === 'beforeMp' ? value.beforeMp : value.afterMp;
        onChange({
            ...value,
            [lane]: [...target, token],
        });
    };

    const removeFromLanes = (token: string) => {
        onChange({
            beforeMp: value.beforeMp.filter((item) => item !== token),
            afterMp: value.afterMp.filter((item) => item !== token),
        });
    };

    const applyContractSequence = (sequence: string[]) => {
        const normalized = normalizeContractNavigationSequence(sequence, availableTurnpoints);
        onChange(splitContractNavigationDeclaration(normalized));
    };

    const moveAcrossLanes = (token: string, targetLane: 'beforeMp' | 'afterMp') => {
        if (disabled) return;
        const nextBefore = value.beforeMp.filter((item) => item !== token);
        const nextAfter = value.afterMp.filter((item) => item !== token);
        if (targetLane === 'beforeMp') {
            nextBefore.push(token);
        } else {
            nextAfter.push(token);
        }
        onChange({ beforeMp: nextBefore, afterMp: nextAfter });
    };

    const handleMoveWithinContractSequence = (fromIndex: number, toIndex: number) => {
        applyContractSequence(moveItem(currentSequence, fromIndex, toIndex));
    };

    const handleDropToPool = () => {
        if (!draggedToken || disabled) return;
        removeFromLanes(draggedToken);
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
                                className="rounded border border-base-300 bg-base-100 px-3 py-2 text-sm flex items-center gap-2"
                                draggable={!disabled}
                                onDragStart={() => setDraggedToken(token)}
                            >
                                <span>{token}</span>
                                <div className="flex gap-1">
                                    <button type="button" className="btn btn-xs btn-outline" disabled={disabled} onClick={() => addToLane('beforeMp', token)}>
                                        + Before MP
                                    </button>
                                    <button type="button" className="btn btn-xs btn-outline" disabled={disabled} onClick={() => addToLane('afterMp', token)}>
                                        + After MP
                                    </button>
                                </div>
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
                    const otherLane = lane === 'beforeMp' ? 'afterMp' : 'beforeMp';
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
                                            className="rounded border border-base-300 bg-base-200/60 px-3 py-2 text-sm flex items-center justify-between gap-2"
                                            draggable={!disabled}
                                            onDragStart={() => setDraggedToken(token)}
                                            onDragOver={(event) => event.preventDefault()}
                                            onDrop={(event) => {
                                                event.preventDefault();
                                                handleDropToLane(lane, index);
                                            }}
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className="badge badge-outline">{index + 1}</span>
                                                <span>{token}</span>
                                            </div>
                                            <div className="flex gap-1 flex-wrap justify-end">
                                                <button type="button" className="btn btn-xs btn-outline" disabled={disabled || index === 0} onClick={() => handleMoveWithinContractSequence(index, index - 1)}>
                                                    ↑
                                                </button>
                                                <button type="button" className="btn btn-xs btn-outline" disabled={disabled || index === items.length - 1} onClick={() => handleMoveWithinContractSequence(index, index + 1)}>
                                                    ↓
                                                </button>
                                                <button type="button" className="btn btn-xs btn-outline" disabled={disabled} onClick={() => moveAcrossLanes(token, otherLane)}>
                                                    Move to {otherLane === 'beforeMp' ? 'Before' : 'After'} MP
                                                </button>
                                                <button type="button" className="btn btn-xs btn-outline" disabled={disabled} onClick={() => removeFromLanes(token)}>
                                                    Remove
                                                </button>
                                            </div>
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

type ContractNavigationFormProps = {
    declaredTSeconds: string;
    contractNavigation: ContractNavigationFormState;
    availableTurnpoints: string[];
    disabled: boolean;
    onDeclaredTSecondsChange: (value: string) => void;
    onContractNavigationChange: (value: ContractNavigationFormState) => void;
};

function ContractNavigationForm({
    declaredTSeconds,
    contractNavigation,
    availableTurnpoints,
    disabled,
    onDeclaredTSecondsChange,
    onContractNavigationChange,
}: ContractNavigationFormProps) {
    const declaredSequence = buildContractNavigationSequence(contractNavigation);
    return (
        <div className="space-y-4">
            <label className="form-control w-full">
                <span className="label-text font-medium">Declared T: time from SP to MP and from MP to FP (seconds)</span>
                <input
                    type="number"
                    min={1}
                    step="1"
                    className="input input-bordered w-full"
                    value={declaredTSeconds}
                    onChange={(e) => onDeclaredTSecondsChange(e.target.value)}
                    required
                />
            </label>
            <OrderedSequenceEditor
                availableTokens={['SP', ...availableTurnpoints, 'MP', 'FP']}
                value={declaredSequence}
                compulsoryTokenSet={new Set(['SP', 'MP', 'FP'])}
                compulsoryLabelByToken={{
                    SP: 'SP (fixed start)',
                    MP: 'MP (compulsory)',
                    FP: 'FP (fixed finish)',
                }}
                onChange={(sequence) => onContractNavigationChange(splitContractNavigationDeclaration(
                    normalizeContractNavigationSequence(sequence, availableTurnpoints),
                ))}
                disabled={disabled}
            />
        </div>
    );
}

type OrderedSequenceEditorProps = {
    availableTokens: string[];
    value: string[];
    disabled?: boolean;
    compulsoryTokenSet?: Set<string>;
    compulsoryLabelByToken?: Record<string, string>;
    onChange: (value: string[]) => void;
};

function OrderedSequenceEditor({
    availableTokens,
    value,
    disabled = false,
    compulsoryTokenSet = new Set<string>(),
    compulsoryLabelByToken = {},
    onChange,
}: OrderedSequenceEditorProps) {
    const [draggedToken, setDraggedToken] = useState<string | null>(null);
    const [activeDropIndex, setActiveDropIndex] = useState<number | 'end' | null>(null);
    const used = new Set(value);
    const unassigned = availableTokens.filter((item) => !used.has(item));
    const isCompulsoryToken = (token: string) => compulsoryTokenSet.has(token);

    const addToSequence = (token: string, index?: number) => {
        if (disabled) return;
        const next = value.filter((item) => item !== token);
        const insertionIndex = index === undefined ? next.length : Math.max(0, Math.min(index, next.length));
        next.splice(insertionIndex, 0, token);
        onChange(next);
    };

    const removeFromSequence = (token: string) => {
        if (disabled || compulsoryTokenSet.has(token)) return;
        onChange(value.filter((item) => item !== token));
    };

    const handleDropToPool = () => {
        if (!draggedToken || disabled || compulsoryTokenSet.has(draggedToken)) return;
        removeFromSequence(draggedToken);
        setDraggedToken(null);
        setActiveDropIndex(null);
    };

    const handleDropToSequence = (targetIndex?: number) => {
        if (!draggedToken || disabled) return;
        const fromIndex = value.indexOf(draggedToken);
        if (fromIndex === -1) {
            addToSequence(draggedToken, targetIndex);
        } else {
            onChange(moveItemToInsertionIndex(value, fromIndex, targetIndex ?? value.length));
        }
        setDraggedToken(null);
        setActiveDropIndex(null);
    };

    const labelFor = (token: string) => compulsoryLabelByToken[token] || token;

    const renderDropZone = (index?: number) => (
        <div
            key={`drop-zone-${index ?? 'end'}`}
            className={[
                'h-7 rounded border border-dashed transition-colors',
                activeDropIndex === (index ?? 'end')
                    ? 'border-primary bg-primary/15 ring-1 ring-primary/30'
                    : 'border-base-300/50 bg-base-200/30 hover:border-primary/40 hover:bg-primary/5',
            ].join(' ')}
            onDragEnter={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setActiveDropIndex(index ?? 'end');
            }}
            onDragOver={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setActiveDropIndex(index ?? 'end');
            }}
            onDragLeave={(event) => {
                event.preventDefault();
                event.stopPropagation();
                const relatedTarget = event.relatedTarget as Node | null;
                if (!relatedTarget || !event.currentTarget.contains(relatedTarget)) {
                    setActiveDropIndex((current) => (current === (index ?? 'end') ? null : current));
                }
            }}
            onDrop={(event) => {
                event.preventDefault();
                event.stopPropagation();
                handleDropToSequence(index);
            }}
        />
    );

    return (
        <div className="space-y-4">
            <div>
                <div className="label">
                    <span className="label-text font-medium">Available targets</span>
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
                                className="rounded border border-base-300 bg-base-100 px-3 py-2 text-sm flex items-center gap-2"
                                draggable={!disabled}
                                onDragStart={() => {
                                    setDraggedToken(token);
                                    setActiveDropIndex('end');
                                }}
                            >
                                <span>{labelFor(token)}</span>
                                <button type="button" className="btn btn-xs btn-outline" disabled={disabled} onClick={() => addToSequence(token)}>
                                    + Add
                                </button>
                            </div>
                        ))
                    ) : (
                        <span className="text-sm opacity-60">All targets assigned.</span>
                    )}
                </div>
            </div>

            <div>
                <div className="label">
                    <span className="label-text font-medium">Declared order</span>
                </div>
                <div
                    className="min-h-24 rounded-lg border border-base-300 bg-base-100 p-3 space-y-2"
                    onDragOver={(event) => {
                        event.preventDefault();
                        if (draggedToken) {
                            setActiveDropIndex('end');
                        }
                    }}
                    onDragLeave={() => {
                        if (!draggedToken) {
                            setActiveDropIndex(null);
                        }
                    }}
                    onDrop={(event) => {
                        event.preventDefault();
                        handleDropToSequence();
                    }}
                >
                    {value.length === 0 ? (
                        <span className="text-sm opacity-60">Add targets here.</span>
                    ) : (
                        value.map((token, index) => {
                            const isCompulsory = isCompulsoryToken(token);
                            return (
                                <React.Fragment key={`sequence-${token}`}>
                                    {renderDropZone(index)}
                                    <div
                                        className="rounded border border-base-300 bg-base-200/60 px-4 py-3 text-sm flex items-center justify-between gap-3"
                                        draggable={!disabled && !isCompulsory}
                                        onDragStart={() => {
                                            if (!isCompulsory) {
                                                setDraggedToken(token);
                                                setActiveDropIndex(index);
                                            }
                                        }}
                                        onDragEnd={() => {
                                            setDraggedToken(null);
                                            setActiveDropIndex(null);
                                        }}
                                    >
                                        <div className="flex items-center gap-3 flex-1 min-w-0">
                                            <button
                                                type="button"
                                                className="btn btn-sm btn-ghost cursor-grab active:cursor-grabbing px-2"
                                                draggable={!disabled && !isCompulsory}
                                                onDragStart={(event) => {
                                                    event.stopPropagation();
                                                    if (!isCompulsory) {
                                                        setDraggedToken(token);
                                                        setActiveDropIndex(index);
                                                    }
                                                }}
                                                onMouseDown={(event) => event.stopPropagation()}
                                                disabled={disabled || isCompulsory}
                                                aria-label={`Drag ${labelFor(token)}`}
                                            >
                                                ⋮⋮
                                            </button>
                                            <span className="badge badge-outline">{index + 1}</span>
                                            <span className="truncate">{labelFor(token)}</span>
                                            {isCompulsory && <span className="badge badge-primary badge-sm">Compulsory</span>}
                                        </div>
                                        <div className="flex gap-1 flex-wrap justify-end">
                                            <button type="button" className="btn btn-xs btn-outline" disabled={disabled || isCompulsory || index === 0} onClick={() => onChange(moveItem(value, index, index - 1))}>
                                                ↑
                                            </button>
                                            <button type="button" className="btn btn-xs btn-outline" disabled={disabled || isCompulsory || index === value.length - 1} onClick={() => onChange(moveItem(value, index, index + 1))}>
                                                ↓
                                            </button>
                                            <button type="button" className="btn btn-xs btn-outline" disabled={disabled || isCompulsory} onClick={() => removeFromSequence(token)}>
                                                Remove
                                            </button>
                                        </div>
                                    </div>
                                </React.Fragment>
                            );
                        })
                    )}
                    {value.length > 0 && renderDropZone()}
                </div>
            </div>
        </div>
    );
}

type TurnpointHuntFormProps = {
    compulsoryPointNames: string[];
    compulsoryPointTimes: Record<string, string>;
    declaredEnduranceMinutes: string;
    isLimitedFuel: boolean;
    declaredSequence: string[];
    availableTokens: string[];
    compulsoryTokenSet: Set<string>;
    compulsoryLabelByToken: Record<string, string>;
    disabled: boolean;
    onTimeChange: (name: string, value: string) => void;
    onDeclaredEnduranceMinutesChange: (value: string) => void;
    onDeclaredSequenceChange: (value: string[]) => void;
};

function TurnpointHuntForm({
    compulsoryPointNames,
    compulsoryPointTimes,
    declaredEnduranceMinutes,
    isLimitedFuel,
    declaredSequence,
    availableTokens,
    compulsoryTokenSet,
    compulsoryLabelByToken,
    disabled,
    onTimeChange,
    onDeclaredEnduranceMinutesChange,
    onDeclaredSequenceChange,
}: TurnpointHuntFormProps) {
    return (
        <>
            {compulsoryPointNames.map((name) => (
                <label className="form-control w-full" key={name}>
                    <span className="label-text font-medium">Predicted time for {name}</span>
                    <input
                        type="datetime-local"
                        step={60}
                        className="input input-bordered w-full"
                        value={compulsoryPointTimes[name] || ''}
                        onChange={(e) => onTimeChange(name, e.target.value)}
                        required
                    />
                </label>
            ))}
            <OrderedSequenceEditor
                availableTokens={availableTokens}
                value={declaredSequence}
                compulsoryTokenSet={compulsoryTokenSet}
                compulsoryLabelByToken={compulsoryLabelByToken}
                onChange={onDeclaredSequenceChange}
                disabled={disabled}
            />
            {isLimitedFuel && (
                <label className="form-control w-full">
                    <span className="label-text font-medium">Declared fuel endurance (minutes)</span>
                    <input
                        type="number"
                        min={1}
                        className="input input-bordered w-full"
                        value={declaredEnduranceMinutes}
                        onChange={(e) => onDeclaredEnduranceMinutesChange(e.target.value)}
                    />
                </label>
            )}
        </>
    );
}

type KnownCircuitFormProps = {
    waypointNames: string[];
    turnpointTimeOverrides: Record<string, string>;
    disabled: boolean;
    onOverrideChange: (name: string, value: string) => void;
};

function KnownCircuitForm({
    waypointNames,
    turnpointTimeOverrides,
    disabled,
    onOverrideChange,
}: KnownCircuitFormProps) {
    return (
        <>
            <p className="text-sm opacity-70">
                Optional: declare a specific time at any turnpoint to override the uniform declared-speed time for
                that point only. Leave a point blank to fly it at the constant declared speed.
            </p>
            {waypointNames.map((name) => (
                <label className="form-control w-full" key={name}>
                    <span className="label-text font-medium">Declared time override for {name} (optional)</span>
                    <input
                        type="datetime-local"
                        step={60}
                        className="input input-bordered w-full"
                        value={turnpointTimeOverrides[name] || ''}
                        onChange={(e) => onOverrideChange(name, e.target.value)}
                        disabled={disabled}
                    />
                </label>
            ))}
        </>
    );
}

type DeclarationPreviewProps = {
    isContractNavigation: boolean;
    isKnownCircuit: boolean;
    contractDeclaredTSeconds: string;
    contractNavigation: ContractNavigationFormState;
    freeTargets: FreeTarget[];
    turnpointHuntSequence: string[];
    compulsoryPointTimes: Record<string, string>;
    compulsoryPointNames: string[];
    knownCircuitWaypointNames: string[];
    turnpointTimeOverrides: Record<string, string>;
};

function DeclarationPreview({
    isContractNavigation,
    isKnownCircuit,
    contractDeclaredTSeconds,
    contractNavigation,
    freeTargets,
    turnpointHuntSequence,
    compulsoryPointTimes,
    compulsoryPointNames,
    knownCircuitWaypointNames,
    turnpointTimeOverrides,
}: DeclarationPreviewProps) {
    if (isContractNavigation) {
        const fullContractSequence = buildContractNavigationSequence(contractNavigation);
        return (
            <>
                <h2 className="card-title">Declaration preview</h2>
                <div className="rounded-lg bg-base-200/60 p-4 text-sm space-y-2">
                    <div><span className="font-medium">Declared T:</span> {contractDeclaredTSeconds || '—'} s (SP→MP and MP→FP)</div>
                    <div><span className="font-medium">SP</span></div>
                    <div><span className="font-medium">Before MP:</span> {contractNavigation.beforeMp.join(', ') || '—'}</div>
                    <div><span className="font-medium">MP</span></div>
                    <div><span className="font-medium">After MP:</span> {contractNavigation.afterMp.join(', ') || '—'}</div>
                    <div><span className="font-medium">FP</span></div>
                    <div><span className="font-medium">Full sequence:</span> {fullContractSequence.join(' → ')}</div>
                </div>
                <div className="overflow-x-auto mt-2">
                    <table className="table table-sm">
                        <thead>
                            <tr>
                                <th>Target</th>
                                <th>Type</th>
                            </tr>
                        </thead>
                        <tbody>
                            {fullContractSequence.map((name) => (
                                <tr key={name}>
                                    <td className="font-medium">{name}</td>
                                    <td>{name === 'SP' ? 'Fixed start' : name === 'FP' ? 'Fixed finish' : name === 'MP' ? 'Compulsory midpoint' : 'Free target'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </>
        );
    }

    if (isKnownCircuit) {
        return (
            <>
                <h2 className="card-title">Declared turnpoint overrides</h2>
                <p className="text-sm opacity-70">Points without an override fly at the uniform declared speed; overridden points use the declared time exactly.</p>
                <div className="overflow-x-auto mt-2">
                    <table className="table table-sm">
                        <thead>
                            <tr>
                                <th>Turnpoint</th>
                                <th>Declared time override</th>
                            </tr>
                        </thead>
                        <tbody>
                            {knownCircuitWaypointNames.map((name) => (
                                <tr key={name}>
                                    <td className="font-medium">{name}</td>
                                    <td>{turnpointTimeOverrides[name] || 'Uniform declared speed'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </>
        );
    }

    return (
        <>
            <h2 className="card-title">Declared route</h2>
            <p className="text-sm opacity-70">The three compulsory points are ordered automatically by predicted time. Free targets may be placed anywhere before, between, or after them.</p>
            <div className="rounded-lg bg-base-200/60 p-4 text-sm space-y-2 mt-2">
                <div><span className="font-medium">Full sequence:</span> {turnpointHuntSequence.join(' → ') || '—'}</div>
            </div>
            <div className="overflow-x-auto mt-2">
                <table className="table table-sm">
                    <thead>
                        <tr>
                            <th>Target</th>
                            <th>Type</th>
                            <th>Predicted time</th>
                            <th>Score</th>
                            <th>Authored observation photos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {turnpointHuntSequence.map((name) => {
                            const target = freeTargets.find((item) => item.name === name);
                            const isCompulsory = compulsoryPointNames.includes(name);
                            return (
                                <tr key={name}>
                                    <td className="font-medium">{name}</td>
                                    <td>{isCompulsory ? 'Compulsory' : 'Free target'}</td>
                                    <td>{compulsoryPointTimes[name] || '—'}</td>
                                    <td>{target?.score_value ?? '—'}</td>
                                    <td>{target?.evidence?.length ? target.evidence.map((item) => item.name).join(', ') : (isCompulsory ? '—' : 'None authored')}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </>
    );
}

const ContestantDeclarationPage: React.FC = () => {
    const { contestId, navigationTaskId, contestantId } = useParams();
    const [saving, setSaving] = useState(false);
    const { showToast, ToastContainer, toasts, removeToast } = useToast();
    const {
        loading,
        error,
        setError,
        data,
        setContestant,
        setFormState,
    } = useContestantDeclarationData(contestId, navigationTaskId, contestantId, showToast);

    const { navigationTask, contestant, formState } = data;
    const compiledPayload = getCompiledPayload(contestant);
    const compulsoryPointNames = getCompulsoryPointNames(contestant);
    const freeTargets = compiledPayload.free_targets || [];
    const isLimitedFuel = navigationTask?.task_subtype === 'limited_fuel_turnpoint_hunt';
    const isContractNavigation = navigationTask?.task_subtype === 'contract_navigation_time_controls';
    const isKnownCircuit = navigationTask?.task_subtype === 'known_circuit';
    const knownCircuitWaypointNames: string[] = compiledPayload.waypoint_names || [];
    const compulsoryPointTimesByName = formState.compulsoryPointTimes;
    const orderedCompulsoryPointNames = compulsoryPointNames
        .filter((name) => !!compulsoryPointTimesByName[name])
        .sort((left, right) => {
            const leftTime = compulsoryPointTimesByName[left];
            const rightTime = compulsoryPointTimesByName[right];
            return leftTime.localeCompare(rightTime);
        });
    const compulsoryTokenSet = new Set(orderedCompulsoryPointNames);
    const compulsoryLabelByToken = orderedCompulsoryPointNames.reduce((acc: Record<string, string>, name, index) => {
        acc[name] = `${name} (${index + 1}${index === 0 ? 'st' : index === 1 ? 'nd' : index === 2 ? 'rd' : 'th'} compulsory)`;
        return acc;
    }, {});
    const turnpointHuntAvailableTokens: string[] = [
        ...orderedCompulsoryPointNames,
        ...(compiledPayload.free_target_names || []).filter((item: string) => !orderedCompulsoryPointNames.includes(item)),
    ];
    const normalizedTurnpointHuntSequence = normalizeTurnpointHuntSequence(
        formState.turnpointHuntSequence,
        orderedCompulsoryPointNames,
        (compiledPayload.free_target_names || []).filter((item: string) => !orderedCompulsoryPointNames.includes(item)),
    );
    const freeTargetsByName = freeTargets.reduce((acc: Record<string, FreeTarget>, item: FreeTarget) => {
        acc[item.name] = item;
        return acc;
    }, {});
    const availableContractTurnpoints: string[] = (
        compiledPayload.free_target_names
        || compiledPayload.compiled_task_primitives?.catalogue_turnpoint
        || navigationTask?.task_catalogue_targets?.map((item: any) => item.name)
        || []
    ).filter((item: string) => item !== 'SP' && item !== 'MP' && item !== 'FP');

    const canSave = useMemo(() => {
        if (isContractNavigation) {
            return (
                formState.contractNavigation.beforeMp.length + formState.contractNavigation.afterMp.length > 0
                && Number(formState.contractDeclaredTSeconds) > 0
            );
        }
        if (isKnownCircuit) {
            // Every turnpoint override is optional, so the declaration is always saveable.
            return true;
        }
        return compulsoryPointNames.every((name) => !!formState.compulsoryPointTimes[name])
            && normalizedTurnpointHuntSequence.length >= orderedCompulsoryPointNames.length;
    }, [compulsoryPointNames, formState.compulsoryPointTimes, formState.contractNavigation, formState.contractDeclaredTSeconds, isContractNavigation, isKnownCircuit, normalizedTurnpointHuntSequence.length, orderedCompulsoryPointNames.length]);

    const handleTimeChange = (name: string, value: string) => {
        setFormState((prev) => {
            const compulsoryPointTimes = {
                ...prev.compulsoryPointTimes,
                [name]: value,
            };
            const nextOrderedCompulsoryPointNames = compulsoryPointNames
                .filter((pointName) => !!compulsoryPointTimes[pointName])
                .sort((left, right) => compulsoryPointTimes[left].localeCompare(compulsoryPointTimes[right]));
            return {
                ...prev,
                compulsoryPointTimes,
                turnpointHuntSequence: normalizeTurnpointHuntSequence(
                    prev.turnpointHuntSequence,
                    nextOrderedCompulsoryPointNames,
                    (compiledPayload.free_target_names || []).filter((item: string) => !nextOrderedCompulsoryPointNames.includes(item)),
                ),
            };
        });
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!contestId || !navigationTaskId || !contestantId) return;
        setSaving(true);
        setError(null);
        try {
            const declarationPayload: Record<string, any> = {};
            if (isContractNavigation) {
                declarationPayload.declared_sequence = buildContractNavigationSequence(formState.contractNavigation);
                declarationPayload.declared_t_seconds = Number(formState.contractDeclaredTSeconds || compiledPayload.time_model?.t_seconds || 0);
            } else if (isKnownCircuit) {
                declarationPayload.turnpoint_time_overrides = Object.fromEntries(
                    Object.entries(formState.turnpointTimeOverrides).filter(([, value]) => !!value),
                );
            } else {
                declarationPayload.compulsory_point_times = Object.fromEntries(
                    Object.entries(formState.compulsoryPointTimes).filter(([, value]) => !!value),
                );
                declarationPayload.declared_sequence = normalizedTurnpointHuntSequence;
                if (isLimitedFuel && formState.declaredEnduranceMinutes) {
                    declarationPayload.fuel_metadata = {
                        declared_endurance_minutes: Number(formState.declaredEnduranceMinutes),
                    };
                }
            }
            await updateContestantDeclaration(
                Number(contestId),
                Number(navigationTaskId),
                Number(contestantId),
                declarationPayload,
            );
            const refreshedContestant = await fetchContestant(
                Number(contestId),
                Number(navigationTaskId),
                Number(contestantId),
            );
            setContestant(refreshedContestant);
            setFormState(buildFormState(refreshedContestant));
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
                        <h2 className="card-title">{isContractNavigation ? 'Declaration sequence and T' : isKnownCircuit ? 'Known circuit turnpoint overrides' : 'Compulsory point declaration'}</h2>
                        <form className="space-y-4" onSubmit={handleSubmit}>
                            {isContractNavigation ? (
                                <ContractNavigationForm
                                    declaredTSeconds={formState.contractDeclaredTSeconds}
                                    contractNavigation={formState.contractNavigation}
                                    availableTurnpoints={availableContractTurnpoints}
                                    disabled={saving}
                                    onDeclaredTSecondsChange={(value) => setFormState((prev) => ({ ...prev, contractDeclaredTSeconds: value }))}
                                    onContractNavigationChange={(contractNavigation) => setFormState((prev) => ({ ...prev, contractNavigation }))}
                                />
                            ) : isKnownCircuit ? (
                                <KnownCircuitForm
                                    waypointNames={knownCircuitWaypointNames}
                                    turnpointTimeOverrides={formState.turnpointTimeOverrides}
                                    disabled={saving}
                                    onOverrideChange={(name, value) => setFormState((prev) => ({
                                        ...prev,
                                        turnpointTimeOverrides: { ...prev.turnpointTimeOverrides, [name]: value },
                                    }))}
                                />
                            ) : (
                                <TurnpointHuntForm
                                    compulsoryPointNames={compulsoryPointNames}
                                    compulsoryPointTimes={formState.compulsoryPointTimes}
                                    declaredEnduranceMinutes={formState.declaredEnduranceMinutes}
                                    isLimitedFuel={isLimitedFuel}
                                    declaredSequence={normalizedTurnpointHuntSequence}
                                    availableTokens={turnpointHuntAvailableTokens}
                                    compulsoryTokenSet={compulsoryTokenSet}
                                    compulsoryLabelByToken={compulsoryLabelByToken}
                                    disabled={saving}
                                    onTimeChange={handleTimeChange}
                                    onDeclaredEnduranceMinutesChange={(value) => setFormState((prev) => ({ ...prev, declaredEnduranceMinutes: value }))}
                                    onDeclaredSequenceChange={(turnpointHuntSequence) => setFormState((prev) => ({
                                        ...prev,
                                        turnpointHuntSequence: normalizeTurnpointHuntSequence(
                                            turnpointHuntSequence,
                                            orderedCompulsoryPointNames,
                                            (compiledPayload.free_target_names || []).filter((item: string) => !orderedCompulsoryPointNames.includes(item)),
                                        ),
                                    }))}
                                />
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
                        <DeclarationPreview
                            isContractNavigation={isContractNavigation}
                            isKnownCircuit={isKnownCircuit}
                            contractDeclaredTSeconds={formState.contractDeclaredTSeconds}
                            contractNavigation={formState.contractNavigation}
                            freeTargets={freeTargets}
                            turnpointHuntSequence={normalizedTurnpointHuntSequence}
                            compulsoryPointTimes={formState.compulsoryPointTimes}
                            compulsoryPointNames={orderedCompulsoryPointNames}
                            knownCircuitWaypointNames={knownCircuitWaypointNames}
                            turnpointTimeOverrides={formState.turnpointTimeOverrides}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ContestantDeclarationPage;
