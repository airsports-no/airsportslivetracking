import React, { useState } from 'react';
import { SCALAR_FIELD_META } from '../fieldMetadata';
import {
    getScalarValue,
    isScalarFieldOverridden,
    resetScalarFieldToOriginal,
    setScalarValue,
} from '../scorecardEditorLogic';
import { ScalarFieldName, ScorecardData, ScorecardEditorState } from '../types';
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

    return (
        <div className="card bg-base-100 shadow border border-base-300">
            <div className="card-body p-4">
                <h3 className="card-title text-sm">{title}</h3>
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
            </div>
        </div>
    );
};
