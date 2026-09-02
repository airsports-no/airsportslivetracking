import React, { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { FieldMeta } from '../fieldMetadata';

interface FieldRowProps {
    fieldName: string;
    meta: FieldMeta;
    value: number | boolean | string | null | undefined;
    overridden: boolean;
    onChange: (value: number | boolean | string) => void;
    onResetToStandard: () => void;
    disabled?: boolean;
}

// Numeric inputs keep their own local echo of the raw typed text, re-seeded whenever the
// effective value changes underneath them (a save, a reset, switching gates) - the same
// pattern EditPointView.tsx uses for unit-converted inputs. onChange only ever fires with an
// actually-parsed, valid number: a blank or unparsable input is never propagated into the
// editor state, so a field the user clears without retyping a value is simply left alone
// (never sent to the API as null - see scorecardEditorLogic.ts's buildSavePayload).
export const FieldRow: React.FC<FieldRowProps> = ({
    fieldName,
    meta,
    value,
    overridden,
    onChange,
    onResetToStandard,
    disabled,
}) => {
    const [text, setText] = useState(value === null || value === undefined ? '' : String(value));

    useEffect(() => {
        setText(value === null || value === undefined ? '' : String(value));
    }, [value]);

    const label = (
        <label className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase" htmlFor={fieldName}>
            {meta.label}
            {meta.unit ? <span className="normal-case text-gray-400">({meta.unit})</span> : null}
            {overridden ? <span className="badge badge-xs badge-warning" title="Differs from standard" /> : null}
        </label>
    );

    const resetButton = overridden ? (
        <button
            type="button"
            className="btn btn-ghost btn-xs btn-square"
            title="Reset to standard"
            onClick={onResetToStandard}
            disabled={disabled}
        >
            <RotateCcw size={12} />
        </button>
    ) : null;

    if (meta.kind === 'boolean') {
        return (
            <div className="flex items-center justify-between gap-2 py-1">
                <label className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase" htmlFor={fieldName}>
                    {meta.label}
                    {overridden ? <span className="badge badge-xs badge-warning" title="Differs from standard" /> : null}
                </label>
                <div className="flex items-center gap-1">
                    <input
                        id={fieldName}
                        type="checkbox"
                        className="checkbox checkbox-sm"
                        checked={Boolean(value)}
                        onChange={(e) => onChange(e.target.checked)}
                        disabled={disabled}
                    />
                    {resetButton}
                </div>
            </div>
        );
    }

    if (meta.kind === 'choice') {
        return (
            <div className="py-1">
                <div className="flex items-center justify-between">
                    {label}
                    {resetButton}
                </div>
                <select
                    id={fieldName}
                    className="select select-bordered select-sm w-full"
                    value={String(value ?? '')}
                    onChange={(e) => onChange(e.target.value)}
                    disabled={disabled}
                >
                    {meta.choices?.map((choice) => (
                        <option key={choice.value} value={choice.value}>
                            {choice.label}
                        </option>
                    ))}
                </select>
            </div>
        );
    }

    return (
        <div className="py-1">
            <div className="flex items-center justify-between">
                {label}
                {resetButton}
            </div>
            <input
                id={fieldName}
                type="number"
                className="input input-bordered input-sm w-full"
                value={text}
                min={meta.min}
                step={meta.step ?? (meta.kind === 'integer' ? 1 : 'any')}
                onChange={(e) => {
                    const raw = e.target.value;
                    setText(raw);
                    if (raw.trim() === '') return;
                    const parsed = Number(raw);
                    if (!Number.isNaN(parsed)) {
                        onChange(parsed);
                    }
                }}
                disabled={disabled}
            />
        </div>
    );
};
