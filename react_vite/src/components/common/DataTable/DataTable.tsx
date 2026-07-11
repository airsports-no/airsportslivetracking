import React, { useEffect, useState } from 'react';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  Table as ReactTableType,
} from '@tanstack/react-table';
import { ChevronDown, ChevronUp } from 'lucide-react';

// Define the props for the DataTable component
interface DataTableProps<TData extends object> {
  data: TData[];
  columns: ColumnDef<TData>[];
  rowEvents?: {
    onClick?: (row: TData) => void;
    onMouseEnter?: (row: TData) => void;
    onMouseLeave?: (row: TData) => void;
  };
  headerRowEvents?: {
    onClick?: () => void;
    onMouseEnter?: () => void;
    onMouseLeave?: () => void;
  };
  className?: string;
  updateMyData?: (rowIndex: number, columnId: string, value: any) => void;
  initialState?: {
    hiddenColumns?: string[];
  };
  initialSorting?: SortingState;
}

export function DataTable<TData extends object>({
  data,
  columns,
  rowEvents,
  headerRowEvents,
  className,
  updateMyData,
  initialState,
  initialSorting = [],
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting);
  const [columnVisibility, setColumnVisibility] = useState({});

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnVisibility,
    },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    // Pass the custom updateMyData function to the table context if provided
    meta: {
      updateMyData: updateMyData,
    },
  });

  // Handle hidden columns from initialState
  useEffect(() => {
    if (initialState?.hiddenColumns) {
      const newVisibility = initialState.hiddenColumns.reduce((acc, columnId) => {
        acc[columnId] = false;
        return acc;
      }, {} as Record<string, boolean>);
      setColumnVisibility((prev) => ({ ...prev, ...newVisibility }));
    }
  }, [initialState?.hiddenColumns]);

  return (
    <div className="w-full overflow-x-auto">
      <table className={className}>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr
              key={headerGroup.id}
              onClick={() => (headerRowEvents && headerRowEvents.onClick) ? headerRowEvents.onClick() : null}
              onMouseEnter={() => (headerRowEvents && headerRowEvents.onMouseEnter) ? headerRowEvents.onMouseEnter() : null}
              onMouseLeave={() => (headerRowEvents && headerRowEvents.onMouseLeave) ? headerRowEvents.onMouseLeave() : null}
            >
              {headerGroup.headers.map((header) => {
                // Cast header.column.columnDef as any to access custom properties like headerHidden
                const customHeaderDef = header.column.columnDef as any;
                if (customHeaderDef.headerHidden) return null;

                return (
                  <th
                    key={header.id}
                    colSpan={header.colSpan}
                    style={{ position: 'relative', height: '100%' }}
                    onClick={(e) => {
                      const meta = header.column.columnDef.meta as any;
                      if (meta?.fixedSortDirection) {
                        const isDesc = meta.fixedSortDirection.toUpperCase() === 'DESC';
                        const currentSort = header.column.getIsSorted();
                        if (currentSort === (isDesc ? 'desc' : 'asc')) {
                          return; // Already sorted in the correct direction, do nothing
                        }
                        header.column.toggleSorting(isDesc, e.shiftKey);
                      } else {
                        header.column.getToggleSortingHandler()?.(e);
                      }
                    }}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {{
                      asc: <ChevronUp size={16} />,
                      desc: <ChevronDown size={16} />,
                    }[header.column.getIsSorted() as string] ?? null}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={(row.original as any).className} // Assuming className can be on original data
              onClick={() => (rowEvents && rowEvents.onClick) ? rowEvents.onClick(row.original) : null}
              onMouseEnter={() => (rowEvents && rowEvents.onMouseEnter) ? rowEvents.onMouseEnter(row.original) : null}
              onMouseLeave={() => (rowEvents && rowEvents.onMouseLeave) ? rowEvents.onMouseLeave(row.original) : null}
            >
              {row.getVisibleCells().map((cell) => {
                // Cast cell.column.columnDef as any to access custom properties like classes and style
                const customCellDef = cell.column.columnDef as any;
                return (
                  <td
                    key={cell.id}
                    className={customCellDef.classes}
                    style={customCellDef.style ? customCellDef.style(row.original) : undefined}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Helper to get the updateMyData function from the table instance
export function getTableUpdateMyData<TData extends object>(table: ReactTableType<TData>) {
  return (table.options.meta as { updateMyData?: (rowIndex: number, columnId: string, value: any) => void })?.updateMyData;
}
