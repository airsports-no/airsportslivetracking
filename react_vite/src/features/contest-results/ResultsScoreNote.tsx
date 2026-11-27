import React from 'react';
import ProvisionalBadge from '../../components/common/ProvisionalBadge';
import { DNF_TITLE, isQualityTask, provisionalHelp, scoreHeading, scoresAreProvisional } from '../../utils/taskScore';
import { resultCellValue, TestScoring } from './resultsScoring';

/** Under the heading of a score column of a quality task: what the scores are out of, and that they can still change. */
export const ScoreColumnNote: React.FC<{ scoring: TestScoring | null | undefined; showScale?: boolean }> = ({ scoring, showScale = true }) => {
  if (!isQualityTask(scoring)) return null;
  const provisional = scoresAreProvisional(scoring);
  if (!showScale && !provisional) return null;
  return (
    <span className="flex items-center justify-center gap-1 text-xs font-normal opacity-90" data-testid="score-column-note">
      {showScale && <span>{scoreHeading(scoring)}</span>}
      {provisional && <ProvisionalBadge text={provisionalHelp(scoring)} />}
    </span>
  );
};

/** A result cell: a quality score as a whole number, DNF for a team that did not fly, anything else as it was. */
export const ResultCell: React.FC<{ value: unknown; scoring: TestScoring | null | undefined; teamId: number | undefined }> = ({ value, scoring, teamId }) => {
  const shown = resultCellValue(value, scoring, teamId);
  if (!shown) return <>{value as React.ReactNode}</>;
  return shown.dnf ? <span title={DNF_TITLE}>{shown.text}</span> : <>{shown.text}</>;
};
