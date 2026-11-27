import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { applyScoreUpdate, mergeStandingsPoints } from '../../store/contestResultsStore';
import type { ContestResults } from '../../store/contestResultsStore';
import StandingsTaskCell from './StandingsTaskCell';
import { cellOf, isValidPointsTable, ordinal, parsePointsTable, placeAndPoints, standingsPointsExplanation, standingsPointsOf } from './standingsPoints';

const details = {
  points_table: [25, 20, 16, 13],
  ranks: { '1': 1, '2': 2 },
  tasks: { '10': { '1': { place: 2, points: 20 } } },
};

describe('points table helpers', () => {
  it('parses commas, spaces and semicolons and checks the numbers', () => {
    expect(parsePointsTable('25, 20 16;13')).toEqual([25, 20, 16, 13]);
    expect(isValidPointsTable([25, 0])).toBe(true);
    expect(isValidPointsTable([])).toBe(false);
    expect(isValidPointsTable(parsePointsTable('25, x'))).toBe(false);
    expect(isValidPointsTable([25, -1])).toBe(false);
  });

  it('writes places as ordinals', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 103].map(ordinal)).toEqual(['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '103rd']);
  });

  it('explains the method with the start of the table', () => {
    expect(standingsPointsExplanation([25, 20, 16, 13])).toBe(
      'Overall result by standings points: each task gives points by placing (25, 20, 16, …). Highest total wins.',
    );
    expect(standingsPointsExplanation([5, 3])).toContain('(5, 3)');
  });

  it('shows the place and the points of a cell', () => {
    expect(placeAndPoints(cellOf(details, 10, 1))).toBe('2nd · 20 p');
    expect(placeAndPoints(cellOf(details, 10, 2))).toBe('');
  });

  it('only uses standings points for a contest that has them', () => {
    expect(standingsPointsOf({ overall_result_method: 'standings_points', standings_points: details })).toBe(details);
    expect(standingsPointsOf({ overall_result_method: 'sum_of_scores', standings_points: null })).toBeNull();
    expect(standingsPointsOf({} as any)).toBeNull();
    expect(standingsPointsOf(null)).toBeNull();
  });
});

describe('StandingsTaskCell', () => {
  it('shows the score with the place and the points', () => {
    const html = renderToStaticMarkup(<StandingsTaskCell value={1120} scoring={null} teamId={1} cell={{ place: 2, points: 20 }} />);
    expect(html).toContain('1,120');
    expect(html).toContain('2nd · 20 p');
  });

  it('shows only the score, as before, for a team without a place', () => {
    expect(renderToStaticMarkup(<StandingsTaskCell value="-" scoring={null} teamId={2} cell={undefined} />)).toBe('-');
  });
});

describe('results of a contest with standings points', () => {
  const results = { id: 1, summary_score_sorting_direction: 'desc', contestsummary_set: [], task_set: [], overall_result_method: 'standings_points', standings_points: details } as unknown as ContestResults;

  it('takes the new places from a fresh copy of the results', () => {
    const fresh = { ...results, standings_points: { ...details, ranks: { '1': 2, '2': 1 } }, contestsummary_set: [{ id: 5, points: 40 }] } as unknown as ContestResults;
    const merged = mergeStandingsPoints(results, fresh);
    expect(merged.standings_points?.ranks).toEqual({ '1': 2, '2': 1 });
    expect(merged.contestsummary_set).toEqual([{ id: 5, points: 40 }]);
  });

  it('keeps a score update working', () => {
    const next = applyScoreUpdate(results, { type: 'score.update', test_score: null, task_summary: null, contest_summary: { id: 5, points: 41 } as any });
    expect(next.contestsummary_set).toHaveLength(1);
  });
});
