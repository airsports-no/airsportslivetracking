import { ScoringExplanation } from '../../utils/taskScore';

// Explanations as the API sends them, for the tests of the screens that show them.
export const qualityExplanation: ScoringExplanation = {
    scoring_model: 'quality',
    task_value: 1000,
    qmax_policy: 'best_in_task',
    task_type: 'curve_navigation_time_estimation',
    task_type_name: '2.A1 Curve navigation with time estimation',
    headline: '2.A1: the best pilot in the task gets 1000 points.',
    raw_points: ['The hidden gates share 1000 points equally.', 'Each timed turn point is worth 180 points.'],
    task_score: 'The task score is 1000 times the raw points divided by the raw points of the best pilot in the task.',
    relative_terms: [],
    percentage_penalties: ['Backtracking: each backtrack costs 50% of the task score.'],
    provisional: {
        depends_on_other_pilots: true,
        text: 'Scores are provisional until every flight in the task is finished.',
        short: 'Provisional: scores are scaled against the best pilot in the task.',
    },
    qmax: {
        offered: true,
        selected: 'best_in_task',
        default: 'best_in_task',
        options: [
            { value: 'best_in_task', label: 'Scaled against the best pilot', description: 'The rules’ default.', is_default: true, is_selected: true, fixed_at_landing: false },
            { value: 'theoretical', label: 'Scaled against a perfect flight', description: 'Fixed when they land.', is_default: false, is_selected: false, fixed_at_landing: true },
        ],
    },
    depends_on_other_pilots: true,
    creation_note: 'Scores are scaled against the best pilot in the task and can change until everyone has flown.',
    route_used: false,
};

export const penaltyExplanation: ScoringExplanation = {
    scoring_model: 'penalties',
    task_value: null,
    qmax_policy: null,
    task_type: 'legacy_precision',
    task_type_name: 'Legacy precision navigation',
    headline: 'Penalty points are added up; the lowest total wins. Scores do not depend on the other pilots.',
    raw_points: ['Mistakes add penalty points; the score is the total.'],
    task_score: 'The score is worked out from the pilot’s own flight only.',
    relative_terms: [],
    percentage_penalties: [],
    provisional: { depends_on_other_pilots: false, text: 'Scores do not depend on the other pilots.', short: 'Scores do not depend on the other pilots.' },
    qmax: { offered: false, selected: null, default: null, options: [] },
    depends_on_other_pilots: false,
    creation_note: null,
    route_used: false,
};
