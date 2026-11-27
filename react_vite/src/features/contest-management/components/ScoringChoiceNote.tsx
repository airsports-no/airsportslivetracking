import React, { useEffect, useState } from 'react';
import { Calculator } from 'lucide-react';
import { ScoringExplanation } from '../../../utils/taskScore';
import { fetchTaskTypeExplanation } from '../api';

interface ScoringChoiceViewProps {
    explanation: ScoringExplanation;
    /** The chosen way to determine the best score; blank for the task type's own default. */
    value: string;
    onChange: (policy: string) => void;
}

/**
 * What an organiser who starts a CIMA task must know before creating it: how the score is made, that it is scaled
 * against the best pilot and can change until everyone has flown, and the choice of how the best score is determined
 * (the rules' default preselected). The text is the backend's own (display/services/scoring_explanation.py).
 */
export const ScoringChoiceView: React.FC<ScoringChoiceViewProps> = ({ explanation, value, onChange }) => {
    const { qmax } = explanation;
    const chosen = value || qmax.default || '';
    return (
        <div className="alert alert-info flex-col items-start gap-2 text-sm" data-testid="scoring-choice-note">
            <div className="flex items-center gap-2 font-semibold">
                <Calculator size={16} aria-hidden="true" />
                How this task is scored
            </div>
            <p>{explanation.headline}</p>
            {explanation.creation_note && <p className="font-medium">{explanation.creation_note}</p>}
            {qmax.offered && (
                <fieldset className="w-full">
                    <legend className="font-medium mb-1">How is the best score determined?</legend>
                    <div className="flex flex-col gap-2">
                        {qmax.options.map(option => (
                            <label key={option.value} className="flex items-start gap-2 cursor-pointer">
                                <input
                                    type="radio"
                                    name="qmax_policy"
                                    className="radio radio-sm mt-0.5"
                                    value={option.value}
                                    checked={chosen === option.value}
                                    onChange={() => onChange(option.value)}
                                />
                                <span>
                                    <span className="font-medium">{option.label}</span>
                                    {option.is_default && <span className="badge badge-ghost badge-sm ml-2">The rules&rsquo; default</span>}
                                    <span className="block text-xs opacity-80">{option.description}</span>
                                </span>
                            </label>
                        ))}
                    </div>
                </fieldset>
            )}
            <p className="text-xs opacity-80">
                This is also written on the task&rsquo;s page, and you can change it later in the scorecard.
            </p>
        </div>
    );
};

interface ScoringChoiceNoteProps {
    taskSubtype: string;
    scorecard: string;
    value: string;
    onChange: (policy: string) => void;
}

/** Fetches the explanation of the chosen task type and scorecard and shows it; nothing for a task that is scored with penalty points. */
const ScoringChoiceNote: React.FC<ScoringChoiceNoteProps> = ({ taskSubtype, scorecard, value, onChange }) => {
    const [explanation, setExplanation] = useState<ScoringExplanation | null>(null);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        if (!taskSubtype) return;
        let cancelled = false;
        fetchTaskTypeExplanation(taskSubtype, scorecard || undefined, { qmax_policy: value || undefined })
            .then(result => {
                if (cancelled) return;
                setExplanation(result);
                setFailed(false);
            })
            .catch(() => {
                if (!cancelled) setFailed(true);
            });
        return () => {
            cancelled = true;
        };
    }, [taskSubtype, scorecard, value]);

    if (failed && !explanation) {
        // The explanation is advice, not a gate: the task can be created without it.
        return null;
    }
    if (!explanation || explanation.scoring_model !== 'quality') return null;
    return <ScoringChoiceView explanation={explanation} value={value} onChange={onChange} />;
};

export default ScoringChoiceNote;
