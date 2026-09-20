import React from 'react';
import { CellContext } from '@tanstack/react-table';

// ContestResultsTable seeds every task/test column with the literal string '-' for a team with
// no score yet (no TaskSummary/TeamTestScore row) - not an empty value with a placeholder. That
// meant merely clicking into and back out of an ungraded cell, without typing anything, put '-'
// into the input and sent it as the "edit" on blur (Sentry PYTHON-DJANGO-19/JAVASCRIPT-REACT-H).
// Treat it as what it actually means - no value - so it renders as an empty, placeholder-only
// field instead of literal editable text.
const UNSCORED_PLACEHOLDER = '-';

function toEditableValue<TValue>(raw: TValue): TValue {
  return (raw === UNSCORED_PLACEHOLDER ? '' : raw) as TValue;
}

export const EditableCell = <TData, TValue>({
  getValue,
  row: { index },
  column: { id },
  table,
}: CellContext<TData, TValue>) => {
  const initialValue = getValue() as TValue;
  const [value, setValue] = React.useState<TValue>(toEditableValue(initialValue));

  // Get the update function from the table meta
  const updateMyData = (table.options.meta as any)?.updateMyData;

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value as TValue);
  };

  const onBlur = () => {
    // Every column this is used for (contest/task/test scores) is numeric. Guard against
    // sending a value that isn't a complete, valid number - an empty field (the common case,
    // per the placeholder handling above) or otherwise malformed input (e.g. pasted text) -
    // by reverting to the last saved value instead of sending it. Without this, the raw string
    // reached the backend and crashed its int()/FloatField conversion into an unhandled 500.
    const trimmed = typeof value === 'string' ? value.trim() : value;
    const numericValue = Number(trimmed);
    if (trimmed === '' || trimmed === null || trimmed === undefined || Number.isNaN(numericValue)) {
      setValue(toEditableValue(initialValue));
      return;
    }
    if (updateMyData) {
      updateMyData(index, id, numericValue);
    }
  };

  React.useEffect(() => {
    setValue(toEditableValue(initialValue));
  }, [initialValue]);

  return (
    <input
      value={(value ?? '') as string}
      onChange={onChange}
      onBlur={onBlur}
      placeholder={UNSCORED_PLACEHOLDER}
      className="w-full p-1 border rounded" // Basic Tailwind styling
    />
  );
};