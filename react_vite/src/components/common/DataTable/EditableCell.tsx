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
    if (updateMyData) {
      updateMyData(index, id, value);
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