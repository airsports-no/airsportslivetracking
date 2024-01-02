import React, {useEffect} from 'react'
import {useTable, useFilters, useGlobalFilter, useAsyncDebounce, useSortBy} from 'react-table'
import Icon from "@mdi/react";
import {mdiChevronDown, mdiChevronUp} from "@mdi/js";
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
export function ResultsServiceTable({columns, data, rowEvents, initialState, className, updateMyData, headerRowEvents}) {


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
            autoResetSortBy: false,
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
    const up = <Icon path={mdiChevronUp} title={"Ascending"} size={1}/>
    const down = <Icon path={mdiChevronDown} title={"Descending"} size={1}/>

    return (
        <>
            <table {...getTableProps()} className={className}>
                <thead>
                {headerGroups.map(headerGroup => (
                    <tr {...headerGroup.getHeaderGroupProps()}
                        onClick={() => (headerRowEvents && headerRowEvents.onClick) ? headerRowEvents.onClick() : null}
                        onMouseEnter={() => (headerRowEvents && headerRowEvents.onMouseEnter) ? headerRowEvents.onMouseEnter() : null}
                        onMouseLeave={() => (headerRowEvents && headerRowEvents.onMouseLeave) ? headerRowEvents.onMouseLeave() : null}
                    >
                        {headerGroup.headers.filter(column => !column.headerHidden).map(column => (
                            <th {...column.getHeaderProps({
                                style: {
                                    position: "relative",
                                    height: "100%"
                                },
                                colSpan: column.colSpan ? column.colSpan : 1,
                            })} onClick={() => {
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
                        <tr {...row.getRowProps({className: row.original.className})}
                            onClick={() => (rowEvents && rowEvents.onClick) ? rowEvents.onClick(row.original) : null}
                            onMouseEnter={() => (rowEvents && rowEvents.onMouseEnter) ? rowEvents.onMouseEnter(row.original) : null}
                            onMouseLeave={() => (rowEvents && rowEvents.onMouseLeave) ? rowEvents.onMouseLeave(row.original) : null}
                        >
                            {row.cells.map(cell => {
                                return <td {...cell.getCellProps({
                                    className: cell.column.classes,
                                    style: cell.column.style ? cell.column.style(row.original) : null
                                })}>{cell.render('Cell')}</td>
                            })}
                        </tr>
                    )
                })}
                </tbody>
            </table>
        </>
    )
}
