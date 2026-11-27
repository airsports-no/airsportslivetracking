import { FieldMeta, GATE_FIELD_ORDER } from './fieldMetadata';
import { GateFieldName, GateScoreData, ScalarFieldName, ScorecardData, ScorecardEditorState } from './types';

export function emptyEditorState(): ScorecardEditorState {
    return { editedScalars: {}, editedGates: {} };
}

export function isDirty(state: ScorecardEditorState): boolean {
    return Object.keys(state.editedScalars).length > 0 || Object.keys(state.editedGates).length > 0;
}

// The value the editor should actually show/save for a scalar field: whatever the user typed,
// if they touched it, otherwise the value the scorecard already has.
export function getScalarValue(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    field: ScalarFieldName,
): number | boolean | string | null | undefined {
    if (field in state.editedScalars) {
        return state.editedScalars[field];
    }
    return scorecard[field] as number | boolean | string | undefined;
}

export function getGateFieldValue(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    gateType: string,
    field: GateFieldName,
): number | undefined {
    const editedGate = state.editedGates[gateType];
    if (editedGate && field in editedGate) {
        return editedGate[field];
    }
    const gate = scorecard.gatescore_set.find((g) => g.gate_type === gateType);
    return gate?.[field] as number | undefined;
}

export function setScalarValue(
    state: ScorecardEditorState,
    field: ScalarFieldName,
    value: number | boolean | string | null,
): ScorecardEditorState {
    return { ...state, editedScalars: { ...state.editedScalars, [field]: value } };
}

export function setGateFieldValue(
    state: ScorecardEditorState,
    gateType: string,
    field: GateFieldName,
    value: number,
): ScorecardEditorState {
    return {
        ...state,
        editedGates: {
            ...state.editedGates,
            [gateType]: { ...state.editedGates[gateType], [field]: value },
        },
    };
}

// A field "differs from standard" if its effective current value (edited-or-original) doesn't
// match the task's original_scorecard - drives the diff marker and the per-field reset control.
export function isScalarFieldOverridden(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    field: ScalarFieldName,
): boolean {
    const original = scorecard.original_scorecard;
    if (!original) return false;
    return getScalarValue(scorecard, state, field) !== original[field];
}

export function isGateFieldOverridden(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    gateType: string,
    field: GateFieldName,
): boolean {
    const original = scorecard.original_scorecard;
    if (!original) return false;
    const originalGate = original.gatescore_set.find((g) => g.gate_type === gateType);
    const originalValue = originalGate?.[field];
    return getGateFieldValue(scorecard, state, gateType, field) !== originalValue;
}

// The standard scorecard's own value for a field - what the "differs from standard" badge's
// tooltip shows alongside "differs", so the user doesn't have to reset-and-compare to find out
// what the default actually was.
export function getOriginalScalarValue(
    scorecard: ScorecardData,
    field: ScalarFieldName,
): number | boolean | string | null | undefined {
    return scorecard.original_scorecard?.[field] as number | boolean | string | null | undefined;
}

export function getOriginalGateFieldValue(
    scorecard: ScorecardData,
    gateType: string,
    field: GateFieldName,
): number | undefined {
    const originalGate = scorecard.original_scorecard?.gatescore_set.find((g) => g.gate_type === gateType);
    return originalGate?.[field] as number | undefined;
}

// Renders a raw field value the same way a human reads it elsewhere on this page: Yes/No for
// booleans, the matching option label for a choice field, otherwise the raw value plus its unit.
export function formatFieldValueForDisplay(
    meta: FieldMeta,
    value: number | boolean | string | null | undefined,
): string {
    if (value === null || value === undefined || value === '') return 'not set';
    if (meta.kind === 'boolean') return value ? 'Yes' : 'No';
    if (meta.kind === 'choice') {
        const choice = meta.choices?.find((option) => option.value === String(value));
        return choice ? choice.label : String(value);
    }
    return `${value}${meta.unit ? ` ${meta.unit}` : ''}`;
}

// Stage the original scorecard's value for one field into edit state (applied on the next
// Save, consistent with every other edit on the page - see the Phase 3 plan).
export function resetScalarFieldToOriginal(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    field: ScalarFieldName,
): ScorecardEditorState {
    const original = scorecard.original_scorecard;
    if (!original) return state;
    return setScalarValue(state, field, (original[field] as number | boolean | string | null) ?? null);
}

export function resetGateFieldToOriginal(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    gateType: string,
    field: GateFieldName,
): ScorecardEditorState {
    const original = scorecard.original_scorecard;
    if (!original) return state;
    const originalGate = original.gatescore_set.find((g) => g.gate_type === gateType);
    if (!originalGate || originalGate[field] === undefined) return state;
    return setGateFieldValue(state, gateType, field, originalGate[field] as number);
}

// Stage every field of one gate back to the original scorecard's values.
export function resetGateToOriginal(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    gateType: string,
): ScorecardEditorState {
    const original = scorecard.original_scorecard;
    const originalGate = original?.gatescore_set.find((g) => g.gate_type === gateType);
    if (!originalGate) return state;
    let next = state;
    for (const field of GATE_FIELD_ORDER) {
        if (originalGate[field] !== undefined) {
            next = setGateFieldValue(next, gateType, field, originalGate[field] as number);
        }
    }
    return next;
}

export interface SavePayload {
    [key: string]: unknown;
    gatescore_set: (Partial<Record<GateFieldName, number>> & { gate_type: string })[];
}

// Only fields the user actually touched are ever sent - see ScorecardEditorState's own
// documentation in types.ts for why (never let a field the user didn't edit reach the API as
// a stray blank/null). The API's serializer has every field required=False and its update()
// only ever sets keys actually present in the body, so a body containing just the touched
// subset is a normal, valid PUT - no partial=True needed on the caller's side.
export function buildSavePayload(state: ScorecardEditorState): SavePayload {
    const payload: SavePayload = { ...state.editedScalars, gatescore_set: [] };
    for (const [gateType, fields] of Object.entries(state.editedGates)) {
        if (Object.keys(fields).length === 0) continue;
        payload.gatescore_set.push({ gate_type: gateType, ...fields });
    }
    return payload;
}

export function findGate(scorecard: ScorecardData, gateType: string): GateScoreData | undefined {
    return scorecard.gatescore_set.find((g) => g.gate_type === gateType);
}

export interface SummaryEntry {
    label: string;
    value: number | boolean | string | null | undefined;
    unit?: string;
}

// The one-line summary shown on a collapsed card - "the current value of the common fields",
// per the design decision. A boolean renders as Yes/No; a field with no value at all (null/
// undefined/empty string) is skipped rather than shown as blank.
export function formatCardSummary(entries: SummaryEntry[]): string {
    const parts = entries
        .filter((entry) => entry.value !== null && entry.value !== undefined && entry.value !== '')
        .map((entry) => {
            const displayValue = typeof entry.value === 'boolean' ? (entry.value ? 'Yes' : 'No') : String(entry.value);
            return `${entry.label}: ${displayValue}${entry.unit ?? ''}`;
        });
    return parts.length > 0 ? parts.join(' · ') : 'No values configured';
}

// The scoring model fields apply only to a task type that can use the quality model (the API says so), and are
// shown at once in the General card, not behind "Advanced".
export const QUALITY_SCORING_FIELDS: ScalarFieldName[] = ['scoring_model', 'qmax_policy', 'task_value'];

// Fields a task of the quality model does not use: the task score starts at zero and the highest score always wins.
export const IGNORED_BY_QUALITY_SCORING: ScalarFieldName[] = ['initial_score', 'score_sorting_direction'];

// Whether the task scores with the quality model with the edits so far: what the user chose, or, where they left it
// at "Task type default", what the task type does.
export function usesQualityScoring(scorecard: ScorecardData, state: ScorecardEditorState): boolean {
    if (!scorecard.can_use_quality_scoring) return false;
    const chosen = getScalarValue(scorecard, state, 'scoring_model');
    if (chosen === 'quality') return true;
    if (chosen === 'penalties') return false;
    return scorecard.default_scoring_model === 'quality';
}

export interface FieldAvailability {
    hidden: boolean;
    // Shown under a field that cannot be edited now, in words.
    disabledReason?: string;
}

export function fieldAvailability(
    scorecard: ScorecardData,
    state: ScorecardEditorState,
    field: ScalarFieldName,
): FieldAvailability {
    if (QUALITY_SCORING_FIELDS.includes(field)) {
        if (!scorecard.can_use_quality_scoring) return { hidden: true };
        if (field !== 'scoring_model' && !usesQualityScoring(scorecard, state)) {
            return { hidden: false, disabledReason: 'Used only with the quality score model.' };
        }
        return { hidden: false };
    }
    if (IGNORED_BY_QUALITY_SCORING.includes(field) && usesQualityScoring(scorecard, state)) {
        return {
            hidden: false,
            disabledReason:
                field === 'initial_score'
                    ? 'Not used with the quality score: the task score is derived from the flights and starts at 0.'
                    : 'Not used with the quality score: the highest task score always wins.',
        };
    }
    return { hidden: false };
}
