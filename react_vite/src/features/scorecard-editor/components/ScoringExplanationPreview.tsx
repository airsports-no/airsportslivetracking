import React, { useEffect, useRef, useState } from 'react';
import ScoringExplanationCard from '../../../components/common/ScoringExplanationCard';
import { ScoringExplanation } from '../../../utils/taskScore';
import { fetchScoringExplanation } from '../api';

interface ScoringExplanationPreviewProps {
    contestId: number;
    navigationTaskId: number;
    /** The explanation of the saved scorecard, as the task's payload carries it. */
    initial: ScoringExplanation | null | undefined;
    /** The unsaved scoring values of the editor, as query parameters (scoringPreview.previewOverrides). */
    overrides: Record<string, string>;
    /** Changes when the scorecard is loaded again (reset to standard), which makes the text be fetched again. */
    scorecardVersion: unknown;
}

const DEBOUNCE_MS = 350;

/**
 * "How this task is scored" at the top of the scorecard editor. It starts with the explanation of the saved scorecard and
 * asks the server for a new one while the scoring model, the way the best score is determined, the task value or the
 * other values that change the wording are edited, so it never shows more than a moment old text.
 */
const ScoringExplanationPreview: React.FC<ScoringExplanationPreviewProps> = ({ contestId, navigationTaskId, initial, overrides, scorecardVersion }) => {
    const [explanation, setExplanation] = useState<ScoringExplanation | null>(initial ?? null);
    const [failed, setFailed] = useState(false);
    const key = JSON.stringify(overrides);
    const firstRun = useRef(true);

    useEffect(() => {
        // The saved scorecard's explanation came with the task: nothing to ask until something is edited or reset
        if (firstRun.current) {
            firstRun.current = false;
            if (Object.keys(overrides).length === 0) return;
        }
        let cancelled = false;
        const timer = setTimeout(() => {
            fetchScoringExplanation(contestId, navigationTaskId, overrides)
                .then(result => {
                    if (cancelled) return;
                    setExplanation(result);
                    setFailed(false);
                })
                .catch(() => {
                    if (!cancelled) setFailed(true);
                });
        }, DEBOUNCE_MS);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [contestId, navigationTaskId, key, scorecardVersion]);

    if (!explanation) return null;
    return (
        <div className="mb-6" data-testid="scoring-explanation-preview">
            <ScoringExplanationCard explanation={explanation} />
            {Object.keys(overrides).length > 0 && (
                <p className="text-xs text-base-content/70 mt-1">
                    {failed ? 'Could not refresh this text for your changes. ' : ''}
                    This text follows the changes you have made below; they take effect when you save.
                </p>
            )}
        </div>
    );
};

export default ScoringExplanationPreview;
