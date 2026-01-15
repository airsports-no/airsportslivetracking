import React from 'react';
import { CellContext } from '@tanstack/react-table';

interface EditableCellProps<TData, TValue> extends CellContext<TData, TValue> {
  updateMyData: (rowIndex: number, columnId: string, value: TValue) => void;
}

export const EditableCell = <TData, TValue>({
  getValue,
  row: { index },
  column: { id },
  table,
  updateMyData, // Custom function from the table instance
}: EditableCellProps<TData, TValue>) => {
  const initialValue = getValue() as TValue;
  const [value, setValue] = React.useState(initialValue);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value as TValue);
  };

  const onBlur = () => {
    updateMyData(index, id, value);
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
