import React, { useState } from 'react';
import { SCALAR_FIELD_META } from '../fieldMetadata';
import {
    formatCardSummary,
    getScalarValue,
    isScalarFieldOverridden,
    resetScalarFieldToOriginal,
    setScalarValue,
} from '../scorecardEditorLogic';
import { ScalarFieldName, ScorecardData, ScorecardEditorState } from '../types';
import { CollapsibleCard } from './CollapsibleCard';
import { FieldRow } from './FieldRow';

interface ScalarFieldGroupProps {
    title: string;
    fields: ScalarFieldName[];
    scorecard: ScorecardData;
    state: ScorecardEditorState;
    onChange: (state: ScorecardEditorState) => void;
    disabled?: boolean;
}

export const ScalarFieldGroup: React.FC<ScalarFieldGroupProps> = ({
    title,
    fields,
    scorecard,
    state,
    onChange,
    disabled,
}) => {
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const primaryFields = fields.filter((f) => scorecard.visible_fields.includes(f));
    const advancedFields = fields.filter((f) => !scorecard.visible_fields.includes(f));

    const renderField = (field: ScalarFieldName) => (
        <FieldRow
            key={field}
            fieldName={field}
            meta={SCALAR_FIELD_META[field]}
            value={getScalarValue(scorecard, state, field)}
            overridden={isScalarFieldOverridden(scorecard, state, field)}
            onChange={(value) => onChange(setScalarValue(state, field, value))}
            onResetToStandard={() => onChange(resetScalarFieldToOriginal(scorecard, state, field))}
            disabled={disabled}
        />
    );

    if (primaryFields.length === 0 && advancedFields.length === 0) return null;

    // "Current value of the common fields" for the collapsed summary - the primary
    // (non-advanced) fields if there are any, otherwise the first few fields overall so a
    // card with everything behind "Advanced" (e.g. an uncurated scorecard) still shows
    // something useful at a glance.
    const summaryFields = primaryFields.length > 0 ? primaryFields : fields.slice(0, 3);
    const summary = formatCardSummary(
        summaryFields.map((field) => ({
            label: SCALAR_FIELD_META[field].label,
            value: getScalarValue(scorecard, state, field),
            unit: SCALAR_FIELD_META[field].unit,
        })),
    );

    return (
        <CollapsibleCard title={title} summary={summary}>
            {primaryFields.map(renderField)}
            {advancedFields.length > 0 && (
                <div className="collapse collapse-arrow bg-base-200 mt-2">
                    <input
                        type="checkbox"
                        checked={advancedOpen}
                        onChange={(e) => setAdvancedOpen(e.target.checked)}
                    />
                    <div className="collapse-title text-xs font-semibold py-2 min-h-0">
                        Advanced ({advancedFields.length})
                    </div>
                    <div className="collapse-content">{advancedFields.map(renderField)}</div>
                </div>
            )}
        </CollapsibleCard>
    );
};
