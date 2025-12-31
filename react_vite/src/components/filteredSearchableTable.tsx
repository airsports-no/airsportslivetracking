import React, { useEffect, useMemo, useState } from 'react';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    getFacetedUniqueValues,
    getFacetedMinMaxValues,
    flexRender,
    Column,
    Table,
    ColumnDef,
    FilterFn,
    Row
} from '@tanstack/react-table';
import { matchSorter } from "match-sorter";

// Define a default UI for filtering
function GlobalFilter({ globalFilter, setGlobalFilter, count }: { globalFilter: string, setGlobalFilter: (filter: string) => void, count: number }) {
    const [value, setValue] = useState(globalFilter || '');

    useEffect(() => {
        setValue(globalFilter || '');
    }, [globalFilter]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            setGlobalFilter(value || undefined);
        }, 200);
        return () => clearTimeout(timeout);
    }, [value, setGlobalFilter]);

    return (
        <div className="flex items-center space-x-2 mb-4">
            <span className="text-sm font-medium text-gray-700">Search:</span>
            <input
                value={value || ""}
                onChange={e => {
                    setValue(e.target.value);
                }}
                placeholder={`${count} records...`}
                className="input input-bordered input-sm w-full"
            />
        </div>
    );
}

// Define a default UI for filtering
function DefaultColumnFilter<T>({ column, table }: { column: Column<T, unknown>, table: Table<T> }) {
    const filterValue = column.getFilterValue();
    const count = table.getPreFilteredRowModel().rows.length;

    return (
        <input
            value={(filterValue || '') as string}
            onChange={e => {
                column.setFilterValue(e.target.value || undefined); // Set undefined to remove the filter entirely
            }}
            placeholder={`Search ${count} records...`}
            className="input input-bordered input-xs w-full mt-1 font-normal"
            onClick={e => e.stopPropagation()}
        />
    );
}

// This is a custom filter UI for selecting
// a unique option from a list
export function SelectColumnFilter<T>({ column }: { column: Column<T, unknown> }) {
    const filterValue = column.getFilterValue();
    // Calculate the options for filtering
    // using the getFacetedUniqueValues
    const options = useMemo(() => {
        const uniqueValues = column.getFacetedUniqueValues();
        return Array.from(uniqueValues.keys()).sort();
    }, [column]);

    // Render a multi-select box
    return (
        <select
            value={filterValue as string}
            onChange={e => {
                column.setFilterValue(e.target.value || undefined);
            }}
            className="select select-bordered select-xs w-full mt-1 font-normal"
            onClick={e => e.stopPropagation()}
        >
            <option value="">All</option>
            {options.map((option, i) => (
                <option key={i} value={option}>
                    {option}
                </option>
            ))}
        </select>
    );
}

// This is a custom filter UI that uses a
// slider to set the filter value between a column's
// min and max values
function SliderColumnFilter<T>({ column }: { column: Column<T, unknown> }) {
    const filterValue = column.getFilterValue();
    // Calculate the min and max
    // using the getFacetedMinMaxValues
    const [min, max] = useMemo(() => {
        return column.getFacetedMinMaxValues() || [0, 0];
    }, [column]);

    return (
        <div className="flex items-center space-x-2" onClick={e => e.stopPropagation()}>
            <input
                type="range"
                min={min}
                max={max}
                value={(filterValue || min) as number}
                onChange={e => {
                    column.setFilterValue(parseInt(e.target.value, 10));
                }}
                className="range range-xs range-primary"
            />
            <button
                onClick={() => column.setFilterValue(undefined)}
                className="btn btn-xs btn-ghost"
            >
                Off
            </button>
        </div>
    );
}

// This is a custom UI for our 'between' or number range
// filter. It uses two number boxes and filters rows to
// ones that have values between the two
function NumberRangeColumnFilter<T>({ column }: { column: Column<T, unknown> }) {
    const filterValue = (column.getFilterValue() || []) as [number, number];
    const [min, max] = useMemo(() => {
        return column.getFacetedMinMaxValues() || [0, 0];
    }, [column]);

    return (
        <div className="flex space-x-2" onClick={e => e.stopPropagation()}>
            <input
                value={filterValue[0] || ''}
                type="number"
                onChange={e => {
                    const val = e.target.value;
                    column.setFilterValue((old: [number, number] = [undefined, undefined]) => [val ? parseInt(val, 10) : undefined, old[1]]);
                }}
                placeholder={`Min (${min})`}
                className="input input-bordered input-xs w-20"
            />
            <span className="text-gray-500 self-center">to</span>
            <input
                value={filterValue[1] || ''}
                type="number"
                onChange={e => {
                    const val = e.target.value;
                    column.setFilterValue((old: [number, number] = [undefined, undefined]) => [old[0], val ? parseInt(val, 10) : undefined]);
                }}
                placeholder={`Max (${max})`}
                className="input input-bordered input-xs w-20"
            />
        </div>
    );
}

const fuzzyTextFilterFn: FilterFn<any> = (row, columnId, filterValue) => {
    // matchSorter expects an array of items, so we pass the single cell value in an array
    const itemValue = row.getValue(columnId);
    const res = matchSorter([itemValue], filterValue);
    return res.length > 0;
}

// Let the table remove the filter if the string is empty
fuzzyTextFilterFn.autoRemove = (val: any) => !val;

interface ASTableProps<T> {
    columns: ColumnDef<T, any>[];
    data: T[];
    rowEvents?: {
        onClick?: (row: T) => void;
    };
    initialState?: any;
    className?: string;
}

// Our table component
export function ASTable<T>({ columns = [], data = [], rowEvents, initialState, className }: ASTableProps<T>) {
    const [globalFilter, setGlobalFilter] = useState(initialState?.globalFilter || '');
    const [columnVisibility, setColumnVisibility] = useState({});

    const defaultColumn = useMemo(() => ({
        // Let's pass the Filter component in the column definition meta or directly
        // In v8, we usually define this in the column defs, but for backward compat:
        filterComponent: DefaultColumnFilter,
    }), []);

    // Initialize column visibility from columns prop
    useEffect(() => {
        const visibility: { [key: string]: boolean } = {};
        (columns || []).forEach(col => {
            if (col && (col as any).hidden) {
                visibility[(col as any).id || col.accessorKey] = false;
            }
        });
        setColumnVisibility(prev => {
            if (JSON.stringify(prev) === JSON.stringify(visibility)) return prev;
            return visibility;
        });
    }, [columns]);

    const table = useReactTable({
        data,
        columns: columns || [],
        defaultColumn,
        initialState,
        state: {
            globalFilter,
            columnVisibility,
        },
        onGlobalFilterChange: setGlobalFilter,
        onColumnVisibilityChange: setColumnVisibility,
        globalFilterFn: fuzzyTextFilterFn,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFacetedUniqueValues: getFacetedUniqueValues(),
        getFacetedMinMaxValues: getFacetedMinMaxValues(),
    });

    return (
        <div className="flex flex-col">
            <GlobalFilter
                globalFilter={globalFilter}
                setGlobalFilter={setGlobalFilter}
                count={table.getPreFilteredRowModel().rows.length}
            />
            <table className={`table table-zebra w-full ${className || ''}`}>
                <thead>
                    {table.getHeaderGroups().map(headerGroup => (
                        <tr key={headerGroup.id}>
                            {headerGroup.headers.map(column => (
                                <th
                                    key={column.id}
                                    colSpan={column.colSpan}
                                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider align-top"
                                >
                                    <div className="flex flex-col gap-2">
                                        <div className="flex items-center justify-between">
                                            <span
                                                className={column.column.getCanSort() ? "cursor-pointer select-none" : ""}
                                                onClick={column.column.getToggleSortingHandler()}
                                            >
                                                {flexRender(column.column.columnDef.header, column.getContext())}
                                                {{
                                                    asc: ' 🔼',
                                                    desc: ' 🔽',
                                                }[(column.column.getIsSorted() as "asc" | "desc")] ?? null}
                                            </span>
                                        </div>
                                        <div onClick={e => e.stopPropagation()} className="font-normal normal-case">
                                            {column.column.getCanFilter() ? (
                                                // Render the Filter component passed in column def or default
                                                React.createElement(
                                                    (column.column.columnDef as any).Filter || defaultColumn.filterComponent,
                                                    { column: column.column, table }
                                                )
                                            ) : null}
                                        </div>
                                    </div>
                                </th>
                            ))}
                        </tr>
                    ))}
                </thead>
                <tbody>
                    {table.getRowModel().rows.map(row => {
                        return (
                            <tr
                                key={row.id}
                                onClick={() => (rowEvents && rowEvents.onClick) ? rowEvents.onClick(row.original) : null}
                                className={rowEvents && rowEvents.onClick ? "cursor-pointer hover" : ""}
                            >
                                {row.getVisibleCells().map(cell => {
                                    return (
                                        <td key={cell.id} className="whitespace-nowrap text-sm">
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </td>
                                    );
                                })}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

// Define a custom filter filter function!
function filterGreaterThan<T>(row: Row<T>, columnId: string, filterValue: any): boolean {
    const rowValue = row.getValue(columnId);
    return rowValue >= filterValue;
}

// This is an autoRemove method on the filter function that
// when given the new filter value and returns true, the filter
// will be automatically removed. Normally this is just an undefined
// check, but here, we want to remove the filter if it's not a number
filterGreaterThan.autoRemove = (val: any) => typeof val !== 'number';
