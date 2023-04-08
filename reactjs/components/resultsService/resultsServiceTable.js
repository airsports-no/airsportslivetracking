import React, {useEffect} from 'react'
import {useTable, useFilters, useGlobalFilter, useAsyncDebounce, useSortBy} from 'react-table'
// A great library for fuzzy filtering/sorting items

export const EditableCell = ({
                              value: initialValue,
                              row: row,
                              column: column,
                              updateMyData, // This is a custom function that we supplied to our table instance
                          }) => {
        // We need to keep and update the state of the cell normally
        const [value, setValue] = React.useState(initialValue)

        const onChange = e => {
            setValue(e.target.value)
        }

        // We'll only update the external data when the input is blurred
        const onBlur = () => {
            updateMyData(row, column, value)
        }

        // If the initialValue is changed external, sync it up with our state
        React.useEffect(() => {
            setValue(initialValue)
        }, [initialValue])

        return <input value={value} onChange={onChange} onBlur={onBlur}/>
    }
// Our table component
export function ResultsServiceTable({columns, data, rowEvents, initialState, className, updateMyData}) {



    const {
        getTableProps,
        getTableBodyProps,

        headerGroups,
        rows,
        prepareRow,
        visibleColumns,
        setHiddenColumns,
    } = useTable(
        {
            columns,
            data,
            initialState: initialState, manualSortBy: false,
            updateMyData
        },
        useSortBy
    )

    useEffect(
        () => {
            setHiddenColumns(
                columns.filter(column => column.hidden).map(column => column.id)
            );
        },
        [columns]
    );

    return (
        <>
            <table {...getTableProps()} className={className}>
                <thead>
                {headerGroups.map(headerGroup => (
                    <tr {...headerGroup.getHeaderGroupProps()}>
                        {headerGroup.headers.map(column => (
                            <th {...column.getHeaderProps({style:{
                            position: "relative",
                            height: "100%"
                        }})} onClick={() => {
                                !column.disableSortBy ? column.toggleSortBy(column.sortDirection === "desc") : null
                            }}>
                                <span>
                    {column.isSorted
                        ? column.isSortedDesc
                            ? '🔽'
                            : '🔼'
                        : ''}
                  </span>
                                {column.render('Header')}
                                {/* Add a sort direction indicator */}

                            </th>
                        ))}
                    </tr>
                ))}
                </thead>
                <tbody {...getTableBodyProps()}>
                {rows.map((row, i) => {
                    prepareRow(row)
                    return (
                        <tr {...row.getRowProps()}
                            onClick={() => (rowEvents && rowEvents.onClick) ? rowEvents.onClick(row.original) : null}>
                            {row.cells.map(cell => {
                                return <td {...cell.getCellProps({className: cell.column.classes})}>{cell.render('Cell')}</td>
                            })}
                        </tr>
                    )
                })}
                </tbody>
            </table>
        </>
    )
}
