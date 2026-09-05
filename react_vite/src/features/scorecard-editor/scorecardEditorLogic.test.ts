import { describe, expect, it } from 'vitest';
import {
    buildSavePayload,
    emptyEditorState,
    formatCardSummary,
    getGateFieldValue,
    getScalarValue,
    isDirty,
    isGateFieldOverridden,
    isScalarFieldOverridden,
    resetGateFieldToOriginal,
    resetGateToOriginal,
    resetScalarFieldToOriginal,
    setGateFieldValue,
    setScalarValue,
} from './scorecardEditorLogic';
import { ScorecardData } from './types';

function makeScorecard(overrides: Partial<ScorecardData> = {}): ScorecardData {
    return {
        shortcut_name: 'test',
        valid_from: '2026-01-01T00:00:00Z',
        free_text: '',
        score_sorting_direction: 'asc',
        initial_score: 0,
        task_type: ['precision'],
        corridor_width: 0.5,
        visible_fields: [],
        backtracking_penalty: 200,
        gatescore_set: [
            {
                gate_type: 'tp',
                graceperiod_before: 2,
                graceperiod_after: 2,
                maximum_penalty: 100,
                visible_fields: [],
            },
        ],
        applicable_gate_types: ['tp'],
        original_scorecard: null,
        ...overrides,
    };
}

describe('getScalarValue / setScalarValue', () => {
    it('returns the scorecard value when the field has not been touched', () => {
        const scorecard = makeScorecard({ backtracking_penalty: 200 });
        expect(getScalarValue(scorecard, emptyEditorState(), 'backtracking_penalty')).toBe(200);
    });

    it('returns the edited value once the field has been touched', () => {
        const scorecard = makeScorecard({ backtracking_penalty: 200 });
        const state = setScalarValue(emptyEditorState(), 'backtracking_penalty', 999);
        expect(getScalarValue(scorecard, state, 'backtracking_penalty')).toBe(999);
    });
});

describe('getGateFieldValue / setGateFieldValue', () => {
    it('returns the gate value when untouched, edited value once touched', () => {
        const scorecard = makeScorecard();
        expect(getGateFieldValue(scorecard, emptyEditorState(), 'tp', 'graceperiod_before')).toBe(2);
        const state = setGateFieldValue(emptyEditorState(), 'tp', 'graceperiod_before', 5);
        expect(getGateFieldValue(scorecard, state, 'tp', 'graceperiod_before')).toBe(5);
    });

    it('does not affect other gates', () => {
        const scorecard = makeScorecard({
            gatescore_set: [
                { gate_type: 'tp', graceperiod_before: 2, visible_fields: [] },
                { gate_type: 'sp', graceperiod_before: 3, visible_fields: [] },
            ],
        });
        const state = setGateFieldValue(emptyEditorState(), 'tp', 'graceperiod_before', 99);
        expect(getGateFieldValue(scorecard, state, 'sp', 'graceperiod_before')).toBe(3);
    });
});

describe('isDirty', () => {
    it('is false for a fresh state', () => {
        expect(isDirty(emptyEditorState())).toBe(false);
    });

    it('is true once a scalar or gate field is touched', () => {
        expect(isDirty(setScalarValue(emptyEditorState(), 'backtracking_penalty', 1))).toBe(true);
        expect(isDirty(setGateFieldValue(emptyEditorState(), 'tp', 'graceperiod_before', 1))).toBe(true);
    });
});

describe('isScalarFieldOverridden / isGateFieldOverridden', () => {
    it('is false when there is no original scorecard to compare against', () => {
        const scorecard = makeScorecard({ original_scorecard: null });
        expect(isScalarFieldOverridden(scorecard, emptyEditorState(), 'backtracking_penalty')).toBe(false);
    });

    it('is false when the effective value matches the original', () => {
        const original = makeScorecard({ backtracking_penalty: 200 });
        const scorecard = makeScorecard({ backtracking_penalty: 200, original_scorecard: original });
        expect(isScalarFieldOverridden(scorecard, emptyEditorState(), 'backtracking_penalty')).toBe(false);
    });

    it('is true once an edit diverges from the original, even before saving', () => {
        const original = makeScorecard({ backtracking_penalty: 200 });
        const scorecard = makeScorecard({ backtracking_penalty: 200, original_scorecard: original });
        const state = setScalarValue(emptyEditorState(), 'backtracking_penalty', 999);
        expect(isScalarFieldOverridden(scorecard, state, 'backtracking_penalty')).toBe(true);
    });

    it('detects a gate field that already differs from the original, with no local edit', () => {
        const original = makeScorecard({
            gatescore_set: [{ gate_type: 'tp', graceperiod_before: 2, visible_fields: [] }],
        });
        const scorecard = makeScorecard({
            gatescore_set: [{ gate_type: 'tp', graceperiod_before: 9, visible_fields: [] }],
            original_scorecard: original,
        });
        expect(isGateFieldOverridden(scorecard, emptyEditorState(), 'tp', 'graceperiod_before')).toBe(true);
    });
});

describe('resetScalarFieldToOriginal / resetGateFieldToOriginal / resetGateToOriginal', () => {
    it('stages the original value without touching the live scorecard', () => {
        const original = makeScorecard({ backtracking_penalty: 200 });
        const scorecard = makeScorecard({ backtracking_penalty: 999, original_scorecard: original });
        const state = resetScalarFieldToOriginal(scorecard, emptyEditorState(), 'backtracking_penalty');
        expect(getScalarValue(scorecard, state, 'backtracking_penalty')).toBe(200);
        expect(scorecard.backtracking_penalty).toBe(999); // untouched until an actual save
    });

    it('resets a single gate field', () => {
        const original = makeScorecard({
            gatescore_set: [{ gate_type: 'tp', graceperiod_before: 2, visible_fields: [] }],
        });
        const scorecard = makeScorecard({
            gatescore_set: [{ gate_type: 'tp', graceperiod_before: 55, visible_fields: [] }],
            original_scorecard: original,
        });
        const state = resetGateFieldToOriginal(scorecard, emptyEditorState(), 'tp', 'graceperiod_before');
        expect(getGateFieldValue(scorecard, state, 'tp', 'graceperiod_before')).toBe(2);
    });

    it('resets every field of a gate at once', () => {
        const original = makeScorecard({
            gatescore_set: [
                { gate_type: 'tp', graceperiod_before: 2, graceperiod_after: 3, maximum_penalty: 50, visible_fields: [] },
            ],
        });
        const scorecard = makeScorecard({
            gatescore_set: [
                { gate_type: 'tp', graceperiod_before: 99, graceperiod_after: 99, maximum_penalty: 99, visible_fields: [] },
            ],
            original_scorecard: original,
        });
        const state = resetGateToOriginal(scorecard, emptyEditorState(), 'tp');
        expect(getGateFieldValue(scorecard, state, 'tp', 'graceperiod_before')).toBe(2);
        expect(getGateFieldValue(scorecard, state, 'tp', 'graceperiod_after')).toBe(3);
        expect(getGateFieldValue(scorecard, state, 'tp', 'maximum_penalty')).toBe(50);
    });
});

describe('buildSavePayload', () => {
    it('is empty (besides gatescore_set: []) when nothing was touched', () => {
        expect(buildSavePayload(emptyEditorState())).toEqual({ gatescore_set: [] });
    });

    it('includes only touched scalar fields', () => {
        const state = setScalarValue(emptyEditorState(), 'backtracking_penalty', 999);
        const payload = buildSavePayload(state);
        expect(payload.backtracking_penalty).toBe(999);
        expect(payload).not.toHaveProperty('corridor_outside_penalty');
    });

    it('includes only touched gate fields, grouped by gate_type', () => {
        let state = setGateFieldValue(emptyEditorState(), 'tp', 'graceperiod_before', 5);
        state = setGateFieldValue(state, 'tp', 'maximum_penalty', 150);
        state = setGateFieldValue(state, 'sp', 'graceperiod_after', 4);
        const payload = buildSavePayload(state);
        expect(payload.gatescore_set).toEqual(
            expect.arrayContaining([
                { gate_type: 'tp', graceperiod_before: 5, maximum_penalty: 150 },
                { gate_type: 'sp', graceperiod_after: 4 },
            ]),
        );
        expect(payload.gatescore_set).toHaveLength(2);
    });

    it('never includes a field the user did not touch, even if it looks falsy/blank', () => {
        // Regression guard for the bug this whole feature exists to avoid: a blank/untouched
        // numeric field must never silently reach the API as null.
        const state = setScalarValue(emptyEditorState(), 'backtracking_penalty', 0);
        const payload = buildSavePayload(state);
        expect(payload).toEqual({ backtracking_penalty: 0, gatescore_set: [] });
        expect('corridor_maximum_penalty' in payload).toBe(false);
    });
});

describe('formatCardSummary', () => {
    it('joins label/value/unit entries with a middle dot', () => {
        expect(
            formatCardSummary([
                { label: 'Grace period before', value: 2, unit: 's' },
                { label: 'Maximum penalty', value: 100 },
            ]),
        ).toBe('Grace period before: 2s · Maximum penalty: 100');
    });

    it('renders booleans as Yes/No', () => {
        expect(formatCardSummary([{ label: 'Per leg', value: true }])).toBe('Per leg: Yes');
        expect(formatCardSummary([{ label: 'Per leg', value: false }])).toBe('Per leg: No');
    });

    it('skips entries with no value at all', () => {
        expect(
            formatCardSummary([
                { label: 'Set', value: 5 },
                { label: 'Unset', value: null },
                { label: 'Also unset', value: undefined },
                { label: 'Blank', value: '' },
            ]),
        ).toBe('Set: 5');
    });

    it('falls back to a placeholder when nothing is set', () => {
        expect(formatCardSummary([{ label: 'Unset', value: null }])).toBe('No values configured');
        expect(formatCardSummary([])).toBe('No values configured');
    });

    it('does not skip a real falsy numeric value like 0', () => {
        expect(formatCardSummary([{ label: 'Backtracking penalty', value: 0 }])).toBe('Backtracking penalty: 0');
    });
});
