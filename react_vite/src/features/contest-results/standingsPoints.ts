// The overall result of a contest made from standings points (FAI Annex 9, 6.7.7): each task gives points for the place
// in it and the points are added up. The server does the ranking (display/services/contest_standings_points.py); these
// helpers only show what it sends.

import type { ContestResults } from '../../store/contestResultsStore';

/** The place and the points of a team in a task, as the results carry them. */
export interface StandingsCell {
  place: number;
  points: number;
}

/** What the results carry for a contest with standings points; null or absent for one that sums the task scores. */
export interface StandingsPointsDetails {
  points_table: number[];
  /** The rank of each team (by id) with the countback of equal totals applied. */
  ranks: Record<string, number>;
  /** The cell of each team (by id) in each task (by id); a team without a result in the task has none. */
  tasks: Record<string, Record<string, StandingsCell>>;
}

/** Numbers separated by commas, spaces or semicolons: "25, 20 16" gives [25, 20, 16]. Anything else gives NaN. */
export const parsePointsTable = (text: string): number[] =>
  text
    .split(/[\s,;]+/)
    .filter(Boolean)
    .map(Number);

export const isValidPointsTable = (table: number[]): boolean => table.length > 0 && table.every((item) => Number.isFinite(item) && item >= 0);

/** 1st, 2nd, 3rd, 4th … 11th, 12th, 13th, 21st */
export const ordinal = (place: number): string => {
  const lastTwo = place % 100;
  if (lastTwo >= 11 && lastTwo <= 13) return `${place}th`;
  const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[place % 10 as 1 | 2 | 3] ?? 'th';
  return `${place}${suffix}`;
};

/** The standings points of the results, or null when the contest sums the task scores (and for older servers). */
export const standingsPointsOf = (results: Pick<ContestResults, 'overall_result_method' | 'standings_points'> | null | undefined): StandingsPointsDetails | null =>
  results?.overall_result_method === 'standings_points' ? ((results.standings_points as StandingsPointsDetails | null | undefined) ?? null) : null;

/** The first few points of the table, as shown in the explanation: "25, 20, 16, …" */
export const pointsTablePreview = (table: number[], shown = 3): string =>
  table.length > shown ? `${table.slice(0, shown).join(', ')}, …` : table.join(', ');

/** The line above the results table. */
export const standingsPointsExplanation = (table: number[]): string =>
  `Overall result by standings points: each task gives points by placing (${pointsTablePreview(table)}). Highest total wins.`;

export const cellOf = (details: StandingsPointsDetails, taskId: number, teamId: number): StandingsCell | undefined => details.tasks?.[String(taskId)]?.[String(teamId)];

/** The extra text of a task cell: "2nd · 20 p". Empty for a team with no place in the task. */
export const placeAndPoints = (cell: StandingsCell | undefined): string => (cell ? `${ordinal(cell.place)} · ${formatPoints(cell.points)} p` : '');

export const formatPoints = (points: number): string => points.toLocaleString('en-US', { maximumFractionDigits: 2 });
