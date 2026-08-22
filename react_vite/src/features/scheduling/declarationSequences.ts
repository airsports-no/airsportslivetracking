// Pure declaration-sequence logic split out of ContestantDeclarationPage.tsx
// (previously module-private inside a 1200+ line page component). This is
// the *authoring* counterpart to RouteRenderer's *display* logic: it turns
// a contestant's raw declaration_payload/compiled_effective_route_payload
// into (and back out of) the ordered sequences the contract-navigation,
// turnpoint-hunt, and known-circuit declaration forms edit.

export type FreeTarget = {
    name: string;
    score_value?: number;
    evidence?: { name: string }[];
};

export type SequenceLane = {
    beforeMp: string[];
    afterMp: string[];
};

export type ContestantDeclarationData = {
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

export type ContractNavigationFormState = SequenceLane;

export type DeclarationFormState = {
    compulsoryPointTimes: Record<string, string>;
    declaredEnduranceMinutes: string;
    contractNavigation: ContractNavigationFormState;
    contractDeclaredTSeconds: string;
    turnpointHuntSequence: string[];
    turnpointTimeOverrides: Record<string, string>;
};

export const toDatetimeLocalValue = (value?: string | null) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const splitContractNavigationDeclaration = (declaredSequence: unknown): ContractNavigationFormState => {
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

export const buildContractNavigationSequence = (contractNavigation: ContractNavigationFormState): string[] => ([
    'SP',
    ...contractNavigation.beforeMp,
    'MP',
    ...contractNavigation.afterMp,
    'FP',
]);

export const normalizeContractNavigationSequence = (
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

export const getCompiledPayload = (contestant: ContestantDeclarationData | null | undefined) => (
    contestant?.compiled_effective_route_payload || {}
);

export const getCompulsoryPointNames = (contestant: ContestantDeclarationData | null | undefined): string[] => {
    const compiledPayload = getCompiledPayload(contestant);
    return compiledPayload.compulsory_point_names || compiledPayload.compulsory_timing_gate_names || [];
};

export const getTurnpointHuntSequence = (contestant: ContestantDeclarationData | null | undefined): string[] => {
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

export const getContractNavigationSequence = (contestant: ContestantDeclarationData | null | undefined): string[] => {
    const declarationPayload = contestant?.declaration_payload || {};
    const declaredSequence = Array.isArray(declarationPayload.declared_sequence)
        ? declarationPayload.declared_sequence.filter((item): item is string => typeof item === 'string')
        : [];
    if (declaredSequence.length > 0) {
        return declaredSequence;
    }
    return ['SP', 'MP', 'FP'];
};

export const normalizeTurnpointHuntSequence = (
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

export const buildFormState = (contestantData: ContestantDeclarationData): DeclarationFormState => {
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

export const moveItem = (items: string[], fromIndex: number, toIndex: number) => {
    const next = [...items];
    const [item] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, item);
    return next;
};

export const moveItemToInsertionIndex = (items: string[], fromIndex: number, insertionIndex: number) => {
    const next = [...items];
    const [item] = next.splice(fromIndex, 1);
    const adjustedInsertionIndex = fromIndex < insertionIndex ? insertionIndex - 1 : insertionIndex;
    next.splice(Math.max(0, Math.min(adjustedInsertionIndex, next.length)), 0, item);
    return next;
};
