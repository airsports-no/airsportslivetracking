import { GATE_FIELD_ORDER } from './fieldMetadata';
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
