import React from 'react';
import { CellContext } from '@tanstack/react-table';

export const EditableCell = <TData, TValue>({
  getValue,
  row: { index },
  column: { id },
  table,
}: CellContext<TData, TValue>) => {
  const initialValue = getValue() as TValue;
  const [value, setValue] = React.useState(initialValue);

  // Get the update function from the table meta
  const updateMyData = (table.options.meta as any)?.updateMyData;

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value as TValue);
  };

  const onBlur = () => {
    // Every column this is used for (contest/task/test scores) is numeric. Guard against
    // sending a value that isn't a complete, valid number - e.g. a lone "-" left behind when the
    // field loses focus mid-edit of a negative score - by reverting to the last saved value
    // instead. Without this, the raw string reached the backend and crashed its int()/FloatField
    // conversion into an unhandled 500 (Sentry PYTHON-DJANGO-19).
    const trimmed = typeof value === 'string' ? value.trim() : value;
    const numericValue = Number(trimmed);
    if (trimmed === '' || trimmed === null || trimmed === undefined || Number.isNaN(numericValue)) {
      setValue(initialValue);
      return;
    }
    if (updateMyData) {
      updateMyData(index, id, numericValue);
    }
  };

  React.useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  return (
    <input
      value={(value ?? '') as string}
      onChange={onChange}
      onBlur={onBlur}
      className="w-full p-1 border rounded" // Basic Tailwind styling
    />
  );
};