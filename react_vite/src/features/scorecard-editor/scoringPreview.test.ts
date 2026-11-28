import { describe, expect, it } from 'vitest';
import { previewOverrides } from './scoringPreview';
import { emptyEditorState } from './scorecardEditorLogic';

describe('previewOverrides', () => {
    it('is empty while nothing that changes the wording is edited', () => {
        expect(previewOverrides(emptyEditorState())).toEqual({});
        const state = emptyEditorState();
        state.editedScalars = { corridor_grace_time: 9, initial_score: 10 };
        expect(previewOverrides(state)).toEqual({});
    });

    it('carries the edited scoring values as query parameters', () => {
        const state = emptyEditorState();
        state.editedScalars = { qmax_policy: 'theoretical', task_value: 800, backtracking_penalty_percentage: 25, corridor_grace_time: 9 };
        expect(previewOverrides(state)).toEqual({ qmax_policy: 'theoretical', task_value: '800', backtracking_penalty_percentage: '25' });
    });

    it('sends a cleared value as blank, which means the task type’s default', () => {
        const state = emptyEditorState();
        state.editedScalars = { scoring_model: '', qmax_policy: null, speed_term_value: 0 };
        expect(previewOverrides(state)).toEqual({ scoring_model: '', qmax_policy: '', speed_term_value: '0' });
    });
});
