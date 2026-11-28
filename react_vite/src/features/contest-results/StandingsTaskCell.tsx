import React from 'react';
import { isQualityTask } from '../../utils/taskScore';
import { ResultCell } from './ResultsScoreNote';
import type { TestScoring } from './resultsScoring';
import { formatPoints, placeAndPoints, StandingsCell } from './standingsPoints';

/** A task cell of a contest with standings points: the task score, then the place and the points it gave. "1,120 · 2nd · 20 p" */
const StandingsTaskCell: React.FC<{ value: unknown; scoring: TestScoring | null | undefined; teamId: number | undefined; cell: StandingsCell | undefined }> = ({
  value,
  scoring,
  teamId,
  cell,
}) => {
  const extra = placeAndPoints(cell);
  // A quality score is shown as ResultCell shows it; any other number gets thousands separators
  const plain = typeof value === 'number' && !isQualityTask(scoring) ? formatPoints(value) : null;
  return (
    <>
      {plain ?? <ResultCell value={value} scoring={scoring} teamId={teamId} />}
      {extra && <span className="opacity-70" data-testid="standings-place"> · {extra}</span>}
    </>
  );
};

export default StandingsTaskCell;
