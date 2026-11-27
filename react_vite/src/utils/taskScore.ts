// How the score of a task is shown. The scoring model decides: a task of the "penalties" model keeps its cumulative
// points exactly as before; a task of the "quality" model (the CIMA tasks) has a task score P, a whole number out of the
// task value, derived at task level from every contestant's raw quality score Q (see display/services/task_scoring.py).
// Everything that formats, sorts or explains a score reads it here, so the two models cannot drift apart between screens.

export type ScoringModel = 'penalties' | 'quality';
export type QmaxPolicy = 'best_in_task' | 'theoretical' | 'absolute';

/** The scoring fields of a navigation task (or a scorecard) as the API sends them; all optional for older payloads. */
export interface TaskScoring {
    scoring_model?: string | null;
    qmax_policy?: string | null;
    task_value?: number | null;
    scores_provisional?: boolean | null;
    /** The absolute policy's scale: Q divided by this scores the whole task value. */
    qmax_absolute_reference?: number | null;
    /**
     * What the task score is out of: the task value, but the raw quality of a perfect flight (250) where the score is Q
     * itself and ignores the task value (the circle); null where that is not known.
     */
    score_scale?: number | null;
    /**
     * The score types whose log entries are a measure and not points of Q (2.A3's V, 2.A4's S), by score type, as the
     * backend's task type registry declares them. `is_change`: each entry changes the measure ("V +1"); otherwise an
     * entry is the value of the measure ("S = 62.4 kt").
     */
    score_measures?: Record<string, ScoreMeasure> | null;
    /** The full plain-language explanation of how the task is scored (the navigation task's payload). */
    scoring_explanation?: ScoringExplanation | null;
    /** The short "why is this provisional" text, where only that is sent (the contest results). */
    provisional_explanation?: string | null;
}

/** One way to scale the task score, as the backend's explanation of the task describes it. */
export interface QmaxOption {
    value: QmaxPolicy;
    label: string;
    description: string;
    is_default: boolean;
    is_selected: boolean;
    /** True where a pilot's own score is fixed at landing under this choice. */
    fixed_at_landing: boolean;
}

/**
 * How a task is scored, in plain language, written once by the backend (display/services/scoring_explanation.py) from
 * the task type and the scorecard. Screens show it; they never write their own version of it.
 */
export interface ScoringExplanation {
    scoring_model: ScoringModel;
    task_value: number | null;
    qmax_policy: QmaxPolicy | null;
    task_type: string;
    task_type_name: string;
    headline: string;
    raw_points: string[];
    task_score: string;
    relative_terms: string[];
    percentage_penalties: string[];
    provisional: { depends_on_other_pilots: boolean; text: string; short: string };
    qmax: { offered: boolean; selected: QmaxPolicy | null; default: QmaxPolicy | null; options: QmaxOption[] };
    depends_on_other_pilots: boolean;
    /** The short note for task creation; null for a task of the penalty model. */
    creation_note: string | null;
    route_used: boolean;
}

export interface ScoreMeasure {
    symbol: string;
    unit: string;
    is_change: boolean;
}

/** The parts of a contestant's track that a score is made from. */
export interface TrackScore {
    score?: number | null;
    calculator_started?: boolean | null;
    calculator_finished?: boolean | null;
    raw_quality?: number | null;
    quality_theoretical_maximum?: number | null;
    percentage_penalty?: number | null;
}

/** The parts of a score log entry the display needs. */
export interface LogEntryScore {
    points: number;
    score_kind?: string | null;
    score_type?: string | null;
}

export const PROVISIONAL_HELP =
    'Scores are scaled to the best flight in the task and can change until all flights are finished.';

/** Why the scores are provisional, from the backend's explanation of the task where it has one. */
export const provisionalHelp = (scoring?: TaskScoring | null): string =>
    scoring?.scoring_explanation?.provisional?.short || scoring?.provisional_explanation || PROVISIONAL_HELP;

export const RAW_POINTS_LEGEND =
    'The points in this log are raw quality points (Q). The task score is worked out from Q: it is scaled to the best ' +
    'flight in the task, and percentage penalties are taken off afterwards.';

export const DNF_LABEL = 'DNF';
export const DNF_TITLE = 'Did Not Fly: scores zero';

const MINUS = '−';

export const isQualityTask = (scoring?: TaskScoring | null): boolean => scoring?.scoring_model === 'quality';

/** Highest first for a quality task, whatever the scorecard's own direction; the scorecard's direction otherwise. */
export const sortDirection = (scoring: TaskScoring | null | undefined, scorecardDirection: 'asc' | 'desc'): 'asc' | 'desc' =>
    isQualityTask(scoring) ? 'desc' : scorecardDirection;

/** A number without trailing zeros: 12 -> "12", 12.5 -> "12.5", 12.04 -> "12". At most one decimal. */
export const trimmedNumber = (value: number): string => String(Math.round(value * 10) / 10);

/** A whole number, 0.5 rounded up (the rule of the backend: 874.5 is 875, not 874). */
export const roundHalfUp = (value: number): number => Math.floor(Math.round(value * 1e9) / 1e9 + 0.5);

/** The score as a number: a whole number for a quality task, `fractionDigits` decimals (0 by default, as before) otherwise. */
export const formatTaskScore = (score: number, scoring?: TaskScoring | null, fractionDigits = 0): string =>
    isQualityTask(scoring) ? String(roundHalfUp(score)) : score.toFixed(fractionDigits);

/**
 * What a quality task's score is out of, or null for no "of": the backend's `score_scale`. An older payload without it
 * gets the task value, except under the absolute policy without a scale, where the score is Q itself and the task value
 * would be wrong (the circle).
 */
export const scoreScale = (scoring?: TaskScoring | null): number | null => {
    if (!isQualityTask(scoring)) return null;
    if (scoring?.score_scale !== undefined) return scoring.score_scale || null;
    if (scoring?.qmax_policy === 'absolute' && !scoring.qmax_absolute_reference) return null;
    return scoring?.task_value || null;
};

/** "874 / 1000" where the scale is known, else just the score. Penalty tasks: the score as before. */
export const formatScoreOutOf = (score: number, scoring?: TaskScoring | null, fractionDigits = 0): string => {
    const text = formatTaskScore(score, scoring, fractionDigits);
    const scale = scoreScale(scoring);
    return scale ? `${text} / ${trimmedNumber(scale)}` : text;
};

/** The heading of the score column: "Score (of 1000)" for a quality task, "Score" otherwise. */
export const scoreHeading = (scoring?: TaskScoring | null, base = 'Score'): string => {
    const scale = scoreScale(scoring);
    return scale ? `${base} (of ${trimmedNumber(scale)})` : base;
};

/** Sorts in place of a copy: `items` ordered by their score in the task's direction (stable; equal scores keep their order). */
export function sortByScore<T>(items: readonly T[], getScore: (item: T) => number, scoring: TaskScoring | null | undefined, scorecardDirection: 'asc' | 'desc'): T[] {
    const direction = sortDirection(scoring, scorecardDirection);
    return [...items].sort((a, b) => (direction === 'desc' ? getScore(b) - getScore(a) : getScore(a) - getScore(b)));
}

/**
 * Whether a pilot's score can change because other pilots fly: the backend's explanation says so; an older payload
 * without it is taken to, except under the absolute policy, a fixed scale that never does.
 */
export const scoresDependOnOtherPilots = (scoring?: TaskScoring | null): boolean => {
    if (!isQualityTask(scoring)) return false;
    const explained = scoring?.scoring_explanation?.depends_on_other_pilots;
    return typeof explained === 'boolean' ? explained : scoring?.qmax_policy !== 'absolute';
};

/**
 * Whether the scores of the task can still change because of other flights. A quality task whose scores depend on the
 * other pilots is provisional until every flight is finished; a task of the other model, or a fixed scale (2.A7, 2.A8),
 * never is. With the tracks of the task the answer follows them (so a live page notices the last flight finishing), else
 * the flag the API sent.
 */
export function scoresAreProvisional(scoring: TaskScoring | null | undefined, tracks?: readonly (TrackScore | null | undefined)[]): boolean {
    if (!scoresDependOnOtherPilots(scoring)) return false;
    if (tracks && tracks.length > 0) return tracks.some(track => !track?.calculator_finished);
    return !!scoring?.scores_provisional;
}

/** A contestant of a quality task whose flight never started scores zero and is shown as "DNF" (Did Not Fly). */
export const didNotFly = (scoring: TaskScoring | null | undefined, track: TrackScore | null | undefined): boolean =>
    isQualityTask(scoring) && !track?.calculator_started;

/** Whether a log entry counts against the contestant. On a quality task the sign is the raw contribution to Q. */
export function isPenaltyEntry(entry: LogEntryScore, scoring: TaskScoring | null | undefined, pointsArePenalties: boolean): boolean {
    if (!isQualityTask(scoring)) return pointsArePenalties ? entry.points > 0 : entry.points < 0;
    if (entry.score_kind === 'penalty' || entry.score_kind === 'percentage_penalty') return entry.points !== 0;
    if (entry.score_kind === 'achievement') return false;
    return entry.points < 0;
}

export interface LogPointsText {
    text: string;
    penalty: boolean;
    /** What the number is, for a tooltip. */
    title: string;
}

/**
 * A quality task's log entry in its own terms: raw points with their meaning ("-12 raw", "+100 raw") or the percentage
 * of the task score ("-50% of task score"). Never looks like points of the task score.
 */
export function describeQualityLogEntry(entry: LogEntryScore, scoring?: TaskScoring | null): LogPointsText {
    const measure = entry.score_type ? scoring?.score_measures?.[entry.score_type] : undefined;
    if (measure) return describeMeasureLogEntry(entry, measure);
    if (entry.score_kind === 'percentage_penalty') {
        const text = `${MINUS}${trimmedNumber(entry.points)}% of task score`;
        return { text, penalty: entry.points !== 0, title: `A percentage penalty: ${trimmedNumber(entry.points)}% of the task score is taken off after scoring` };
    }
    if (entry.points === 0) return { text: '0 raw', penalty: false, title: 'Raw quality points (Q): no change' };
    const negative = entry.score_kind === 'penalty' ? true : entry.score_kind === 'achievement' ? false : entry.points < 0;
    // The sign of a stored penalty is already negative; show the magnitude with the sign of its meaning
    const magnitude = Math.abs(entry.points);
    return {
        text: `${negative ? MINUS : '+'}${trimmedNumber(magnitude)} raw`,
        penalty: negative,
        title: negative ? 'Raw quality points (Q) lost' : 'Raw quality points (Q) earned',
    };
}

/** An entry that carries a measure: "V +1" or "S = 62.4 kt", never "raw" points. */
function describeMeasureLogEntry(entry: LogEntryScore, measure: ScoreMeasure): LogPointsText {
    const title = `${measure.symbol} is a measure, not points of Q: it is compared with the best flight of the task`;
    if (measure.is_change) {
        const negative = entry.points < 0;
        const text = entry.points === 0 ? `${measure.symbol} 0` : `${measure.symbol} ${negative ? MINUS : '+'}${trimmedNumber(Math.abs(entry.points))}`;
        return { text, penalty: negative, title };
    }
    const unit = measure.unit ? ` ${measure.unit}` : '';
    return { text: `${measure.symbol} = ${trimmedNumber(entry.points)}${unit}`, penalty: false, title };
}

/** The log entry's points as the panel and the map show them: unchanged for a penalty task. */
export function logPointsText(entry: LogEntryScore, scoring: TaskScoring | null | undefined, pointsArePenalties: boolean): LogPointsText {
    if (isQualityTask(scoring)) return describeQualityLogEntry(entry, scoring);
    const sign = entry.points > 0 ? '+' : '';
    return {
        text: entry.points === 0 ? '0' : `${sign}${entry.points.toFixed(0)}`,
        penalty: isPenaltyEntry(entry, scoring, pointsArePenalties),
        title: '',
    };
}

export interface ScoreArithmetic {
    rawQuality: number;
    /** What Q is divided by: the best Q in the task, the contestant's own maximum, or the absolute scale; null when none. */
    reference: number | null;
    /** "best", "maximum" or "scale": how to call the reference. */
    referenceKind: 'best' | 'maximum' | 'scale' | null;
    /** P before the percentage penalties. */
    scaled: number;
    percentagePenalty: number;
    final: number;
    /** "Q 812 of best 930 -> 873; -50% -> 437" */
    text: string;
}

/** The contestant's score worked out step by step, so a person can redo it. Null for a contestant who did not fly. */
export function scoreArithmetic(
    scoring: TaskScoring | null | undefined,
    track: TrackScore | null | undefined,
    allTracks: readonly (TrackScore | null | undefined)[],
): ScoreArithmetic | null {
    if (!isQualityTask(scoring) || !track?.calculator_started || track.raw_quality == null) return null;
    const q = track.raw_quality;
    const taskValue = scoring?.task_value ?? 1000;
    let reference: number | null = null;
    let referenceKind: ScoreArithmetic['referenceKind'] = null;
    if (scoring?.qmax_policy === 'absolute') {
        reference = scoring.qmax_absolute_reference ?? null;
        referenceKind = reference != null ? 'scale' : null;
    } else if (scoring?.qmax_policy === 'theoretical') {
        reference = track.quality_theoretical_maximum ?? null;
        referenceKind = 'maximum';
    } else {
        const flown = allTracks.filter(t => t?.calculator_started && t.raw_quality != null).map(t => t!.raw_quality as number);
        reference = flown.length > 0 ? Math.max(...flown) : null;
        referenceKind = 'best';
    }
    let scaled: number;
    if (scoring?.qmax_policy === 'absolute') scaled = reference ? (taskValue * q) / reference : q;
    else scaled = reference && reference > 0 ? (taskValue * q) / reference : 0;
    const percentage = Math.min(100, Math.max(0, track.percentage_penalty ?? 0));
    const final = track.score ?? roundHalfUp(Math.max(0, scaled * (1 - percentage / 100)));
    const scaledWhole = roundHalfUp(scaled);
    let text = `Q ${trimmedNumber(q)}`;
    if (reference != null && referenceKind) {
        const word = referenceKind === 'best' ? 'best' : referenceKind === 'maximum' ? 'maximum' : 'scale';
        text += ` of ${word} ${trimmedNumber(reference)}`;
    }
    text += ` → ${scaledWhole}`;
    if (percentage > 0) text += `; ${MINUS}${trimmedNumber(percentage)}% → ${Math.round(final)}`;
    return { rawQuality: q, reference, referenceKind, scaled, percentagePenalty: percentage, final, text };
}

export type PenaltyMode = 'points' | 'percentage';

/** What an administrative penalty will do, in words, for the form that applies it. */
export function penaltyConsequence(scoring: TaskScoring | null | undefined, mode: PenaltyMode, value: number): string {
    if (!isQualityTask(scoring)) return '';
    if (!Number.isFinite(value) || value === 0) return '';
    if (mode === 'percentage') {
        return value >= 100
            ? 'Sets the task score to 0 (100% of the task score).'
            : `Reduces the task score by ${trimmedNumber(value)}% after it has been scaled.`;
    }
    return value > 0
        ? `Takes ${trimmedNumber(value)} raw points off the contestant's raw quality score Q; the task score follows from Q.`
        : `Gives ${trimmedNumber(-value)} raw points back to the contestant's raw quality score Q.`;
}

/** The task score from raw quality Q, the way the backend derives it (task_value x Q / reference, less percentages). */
function taskScoreFrom(scoring: TaskScoring, q: number, percentage: number, best: number, theoretical: number | null): number {
    const taskValue = scoring.task_value ?? 1000;
    let scaled: number;
    if (scoring.qmax_policy === 'absolute') {
        const reference = scoring.qmax_absolute_reference;
        scaled = reference ? (taskValue * q) / reference : q;
    } else {
        const reference = scoring.qmax_policy === 'theoretical' ? (theoretical ?? 0) : best;
        scaled = reference > 0 ? (taskValue * q) / reference : 0;
    }
    const penalty = Math.min(100, Math.max(0, percentage)) / 100;
    return Math.max(0, roundHalfUp(scaled * (1 - penalty)));
}

export interface ReplayContestant {
    id: number;
    /** Whether the contestant's flight was ever scored (a contestant who did not fly scores zero and sets no best). */
    started: boolean;
    start: number | null;
    theoretical: number | null;
    entries: { time: string; points: number; score_kind?: string | null }[];
}

/**
 * The task scores of every contestant at a moment of a replay, from the raw points in their logs up to then (the score
 * log holds raw quality points for a quality task, so adding them up would show Q, not the task score).
 */
export function replayTaskScores(scoring: TaskScoring, contestants: readonly ReplayContestant[], at: Date): Record<number, number> {
    const rows = contestants.map(c => {
        let q = c.start ?? 0;
        let percentage = 0;
        for (const entry of c.entries) {
            if (new Date(entry.time) > at) continue;
            if (entry.score_kind === 'percentage_penalty') percentage += entry.points;
            else q += entry.points;
        }
        return { c, q, percentage };
    });
    const best = Math.max(0, ...rows.filter(r => r.c.started).map(r => r.q));
    const scores: Record<number, number> = {};
    for (const { c, q, percentage } of rows) {
        scores[c.id] = c.started ? taskScoreFrom(scoring, q, percentage, best, c.theoretical) : 0;
    }
    return scores;
}
