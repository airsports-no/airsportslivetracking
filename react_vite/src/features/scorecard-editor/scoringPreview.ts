import { ScorecardEditorState } from './types';

// The scorecard values that change how the task is scored in words (the backend's PREVIEW_OVERRIDE_FIELDS): the editor
// asks for the explanation again with these when they are edited, so the text follows what is about to be saved.
export const PREVIEW_FIELDS = ['scoring_model', 'qmax_policy', 'task_value', 'backtracking_penalty_percentage', 'speed_term_value'] as const;

/** The edited preview values as query parameters; a cleared value is blank, which means the task type's default. */
export function previewOverrides(state: ScorecardEditorState): Record<string, string> {
    const overrides: Record<string, string> = {};
    for (const field of PREVIEW_FIELDS) {
        if (!(field in state.editedScalars)) continue;
        const value = state.editedScalars[field];
        overrides[field] = value === null || value === undefined ? '' : String(value);
    }
    return overrides;
}
