// How the contest results table shows the tasks that are scored with the quality model (the CIMA tasks): the same
// helpers as the live map (utils/taskScore.ts), applied to what the contest results carry for a test that is linked
// to a navigation task (`scoring`, display/serialisers.py TaskTestNestedSerialiser).

import type { Task, Test } from '../../store/contestResultsStore';
import { DNF_LABEL, formatTaskScore, isQualityTask, scoresAreProvisional, TaskScoring } from '../../utils/taskScore';

/** What the results carry for a test linked to a navigation task. */
export interface TestScoring extends TaskScoring {
  /** The teams whose flight never started: they score zero and are shown as DNF. */
  not_flown_team_ids?: number[] | null;
}

export const scoringOf = (test: Pick<Test, 'scoring'> | null | undefined): TestScoring | null => (test?.scoring as TestScoring | null | undefined) ?? null;

/**
 * The scoring of a task column that holds one test of the quality model counted once: then the column shows the same
 * numbers as the test, so it is shown the same way. A task with several tests adds them up, which is no longer a score
 * out of the task value.
 */
export function taskColumnScoring(task: Pick<Task, 'tasktest_set'>): TestScoring | null {
  const tests = task.tasktest_set || [];
  if (tests.length !== 1 || (tests[0].weight ?? 1) !== 1) return null;
  const scoring = scoringOf(tests[0]);
  return isQualityTask(scoring) ? scoring : null;
}

/** The quality tests of a task whose scores are still provisional. */
export const provisionalScorings = (task: Pick<Task, 'tasktest_set'>): TestScoring[] =>
  (task.tasktest_set || []).map(scoringOf).filter((scoring): scoring is TestScoring => isQualityTask(scoring) && scoresAreProvisional(scoring));

export const isDidNotFly = (scoring: TestScoring | null | undefined, teamId: number | undefined): boolean =>
  isQualityTask(scoring) && teamId !== undefined && !!scoring?.not_flown_team_ids?.includes(teamId);

/**
 * What a result cell shows. A quality score is a whole number, and a team that did not fly is DNF (Did Not Fly) where
 * the table has no score for it or a zero. Anything else, and every task of the other model, is shown as it was.
 */
export function resultCellValue(value: unknown, scoring: TestScoring | null | undefined, teamId: number | undefined): { text: string; dnf: boolean } | null {
  if (!isQualityTask(scoring)) return null;
  const missing = value === undefined || value === null || value === '-';
  if (isDidNotFly(scoring, teamId) && (missing || Number(value) === 0)) return { text: DNF_LABEL, dnf: true };
  if (typeof value === 'number') return { text: formatTaskScore(value, scoring), dnf: false };
  return null;
}
