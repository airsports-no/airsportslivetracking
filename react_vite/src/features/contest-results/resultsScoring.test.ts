import { describe, expect, it } from 'vitest';
import { isDidNotFly, provisionalScorings, resultCellValue, scoringOf, taskColumnScoring } from './resultsScoring';

const quality = { scoring_model: 'quality', task_value: 1000, scores_provisional: true, not_flown_team_ids: [7] };
const finished = { ...quality, scores_provisional: false, not_flown_team_ids: [] };
const penalties = { scoring_model: 'penalties' };
const test = (scoring: unknown, weight = 1) => ({ id: 1, weight, scoring }) as any;

describe('resultCellValue', () => {
  it('shows a quality score as a whole number', () => {
    expect(resultCellValue(874.4, quality, 1)).toEqual({ text: '874', dnf: false });
    expect(resultCellValue(874.5, quality, 1)).toEqual({ text: '875', dnf: false });
  });

  it('shows a team that did not fly as DNF, whether the table has a zero or nothing for it', () => {
    expect(resultCellValue(0, quality, 7)).toEqual({ text: 'DNF', dnf: true });
    expect(resultCellValue('-', quality, 7)).toEqual({ text: 'DNF', dnf: true });
    expect(resultCellValue(undefined, quality, 7)).toEqual({ text: 'DNF', dnf: true });
  });

  it('does not hide a score that a team has, and shows a missing score of a team that flew as before', () => {
    expect(resultCellValue(310, quality, 7)).toEqual({ text: '310', dnf: false });
    expect(resultCellValue('-', quality, 1)).toBeNull();
  });

  it('leaves a task of the penalty model, and a test that is not linked to a task, exactly as it was', () => {
    expect(resultCellValue(12.5, penalties, 7)).toBeNull();
    expect(resultCellValue(0, null, 7)).toBeNull();
    expect(resultCellValue(0, undefined, 7)).toBeNull();
  });
});

describe('isDidNotFly', () => {
  it('is only for a team on the list of a quality task', () => {
    expect(isDidNotFly(quality, 7)).toBe(true);
    expect(isDidNotFly(quality, 1)).toBe(false);
    expect(isDidNotFly(penalties as any, 7)).toBe(false);
    expect(isDidNotFly(quality, undefined)).toBe(false);
  });
});

describe('taskColumnScoring', () => {
  it('is the scoring of the one quality test a task consists of', () => {
    expect(taskColumnScoring({ tasktest_set: [test(quality)] })).toBe(quality);
  });

  it('is nothing for a task that adds up several tests, a weighted test or a task of the other model', () => {
    expect(taskColumnScoring({ tasktest_set: [test(quality), test(quality)] })).toBeNull();
    expect(taskColumnScoring({ tasktest_set: [test(quality, 2)] })).toBeNull();
    expect(taskColumnScoring({ tasktest_set: [test(penalties)] })).toBeNull();
    expect(taskColumnScoring({ tasktest_set: [test(null)] })).toBeNull();
    expect(taskColumnScoring({ tasktest_set: [] })).toBeNull();
  });
});

describe('provisionalScorings', () => {
  it('lists the quality tests whose scores can still change', () => {
    expect(provisionalScorings({ tasktest_set: [test(quality), test(finished), test(penalties), test(null)] })).toEqual([quality]);
    expect(provisionalScorings({ tasktest_set: [test(finished)] })).toEqual([]);
  });
});

describe('scoringOf', () => {
  it('is null for a test without scoring', () => {
    expect(scoringOf(test(undefined))).toBeNull();
    expect(scoringOf(null)).toBeNull();
  });
});
