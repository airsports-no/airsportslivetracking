import React, { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { GATE_FIELD_META, GATE_FIELD_ORDER, getGateTypeDisplayName } from '../fieldMetadata';
import {
    findGate,
    formatCardSummary,
    getGateFieldValue,
    isGateFieldOverridden,
    resetGateFieldToOriginal,
    resetGateToOriginal,
    setGateFieldValue,
} from '../scorecardEditorLogic';
import { ScorecardData, ScorecardEditorState } from '../types';
import { CollapsibleCard } from './CollapsibleCard';
import { FieldRow } from './FieldRow';

interface GateSectionProps {
    gateType: string;
    scorecard: ScorecardData;
    state: ScorecardEditorState;
    onChange: (state: ScorecardEditorState) => void;
    disabled?: boolean;
}

export const GateSection: React.FC<GateSectionProps> = ({ gateType, scorecard, state, onChange, disabled }) => {
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const gate = findGate(scorecard, gateType);
    if (!gate) return null;

    const primaryFields = GATE_FIELD_ORDER.filter((f) => gate.visible_fields.includes(f));
    const advancedFields = GATE_FIELD_ORDER.filter((f) => !gate.visible_fields.includes(f));

    const renderField = (field: (typeof GATE_FIELD_ORDER)[number]) => (
        <FieldRow
            key={field}
            fieldName={`${gateType}-${field}`}
            meta={GATE_FIELD_META[field]}
            value={getGateFieldValue(scorecard, state, gateType, field)}
            overridden={isGateFieldOverridden(scorecard, state, gateType, field)}
            onChange={(value) => onChange(setGateFieldValue(state, gateType, field, value as number))}
            onResetToStandard={() => onChange(resetGateFieldToOriginal(scorecard, state, gateType, field))}
            disabled={disabled}
        />
    );

    const summaryFields = primaryFields.length > 0 ? primaryFields : GATE_FIELD_ORDER.slice(0, 3);
    const summary = formatCardSummary(
        summaryFields.map((field) => ({
            label: GATE_FIELD_META[field].label,
            value: getGateFieldValue(scorecard, state, gateType, field),
            unit: GATE_FIELD_META[field].unit,
        })),
    );

    return (
        <CollapsibleCard
            title={getGateTypeDisplayName(gateType)}
            summary={summary}
            headerExtra={
                <button
                    type="button"
                    className="btn btn-ghost btn-xs gap-1"
                    title="Reset this gate to standard"
                    onClick={() => onChange(resetGateToOriginal(scorecard, state, gateType))}
                    disabled={disabled || !scorecard.original_scorecard}
                >
                    <RotateCcw size={12} /> Reset gate
                </button>
            }
        >
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
