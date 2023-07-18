import React from "react";
import {Form} from "react-bootstrap";
import {ASTable} from "../filteredSearchableTable";
import {useEffect, useMemo, useState} from "react";
import {Loading} from "../basicComponents";
import {DateTime} from "luxon";

export const EditableRouteList = () => {
    const [data, setData] = useState()
    const [showAll, setShowAll] = useState()
    useEffect(() => {
        setShowAll(false)
        const dataFetch = async () => {
            const data = await (
                await fetch("/api/v1/editableroutes/")
            ).json()
            setData(data)
        }
        dataFetch()
    }, [])

    const columns = useMemo(() => [
        {
            Header: "Thumbnail",
            accessor: "thumbnail",
            Cell: ({value}) => value ? <img className="zoom" src={value}
                                            style={{
                                                width: "50px",
                                                marginBottom: "-20px",
                                                marginTop: "-20px",
                                                marginRight: "-20px"
                                            }}/> : null,
            disableSortBy: true,
            disableFilters: true,
        },
        {
            Header: "Route",
            accessor: "name",
            id: "Route",
            disableSortBy: true,
            Cell: cellInfo=><a href={document.configuration.editRoute(cellInfo.row.original.id)}>{cellInfo.value}</a>
        },
        {
            Header: "Waypoints",
            accessor: "number_of_waypoints",
            disableFilters: true,
        },
        {
            Header: "Total length",
            accessor: "route_length",
            disableFilters: true,
            Cell: ({value}) => (value/1852).toFixed(2) + " NM"
        },
        {
            Header: "Editors",
            accessor: "editors",
            Cell: ({value}) => {
                return <ul>
                    {
                        value.map((editor) =>
                            <li key={editor.email}>{editor.first_name} {editor.last_name}</li>)
                    }
                </ul>
            },
            disableFilters: true,
            disableSortBy: true,
        },
        {
            Header: "Actions",
            accessor: (row, index) => {
                return <span>
                    <a href={document.configuration.createTask(row.id)}>Create task</a> | <a
                    href={document.configuration.copyRoute(row.id)}>Copy</a> | <a
                    href={document.configuration.permissionList(row.id)}>Permissions</a> | <a
                    href={document.configuration.deleteRoute(row.id)}>Delete</a>
                </span>
            },
            disableSortBy: true,
            disableFilters: true,
        }

    ], [])

    const rowEvents = {
        // onClick: (row) => {
        //     window.location.href = document.configuration.editRoute(row.id)
        // }
    }

    return (
        data ? <div>{document.configuration.is_superuser ?
                <Form.Check type={"checkbox"} onChange={(e) => {
                    setShowAll(e.target.checked)
                }} label={"Show all"}/> : null}
                <ASTable columns={columns}
                         data={data.filter((item) => showAll || item.is_editor)}
                         className={"table table-striped table-hover"} initialState={{
                    sortBy: [
                        {
                            id: "Route",
                            desc: false
                        }
                    ]
                }}

                         rowEvents={rowEvents}/></div>
            :
            <Loading/>
    )
}