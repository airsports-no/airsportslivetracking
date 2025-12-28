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
                await fetch(document.configuration.EDITABLE_ROUTES_URL)
            ).json()
            setData(data)
        }
        dataFetch()
    }, [])

    const columns = useMemo(() => [
        {
            header: "Thumbnail",
            accessorKey: "thumbnail",
            id: "thumbnail",
            cell: ({ getValue }) => {
                const value = getValue();
                return value ? <img className="zoom" src={value}
                                            style={{
                                                width: "50px",
                                                marginBottom: "-20px",
                                                marginTop: "-20px",
                                                marginRight: "-20px"
                                            }}/> : null
            },
            enableSorting: false,
            enableColumnFilter: false,
            enableGlobalFilter: false,
        },
        {
            header: "Route",
            accessorKey: "name",
            id: "name",
            enableSorting: false,
            cell: info => <a href={document.configuration.editRouteViewUrl(info.row.original.id)}>{info.getValue()}</a>
        },
        {
            header: "Waypoints",
            accessorKey: "number_of_waypoints",
            id: "number_of_waypoints",
            enableColumnFilter: false,
        },
        {
            header: "Total length",
            accessorKey: "route_length",
            id: "route_length",
            enableColumnFilter: false,
            cell: ({ getValue }) => (getValue() / 1852).toFixed(2) + " NM"
        },
        {
            header: "Editors",
            accessorKey: "editors",
            id: "editors",
            cell: ({ getValue }) => {
                const value = getValue();
                if (!value) return null;
                return <ul>
                    {
                        value.map((editor) =>
                            <li key={editor.email}>{editor.first_name} {editor.last_name}</li>)
                    }
                </ul>
            },
            enableColumnFilter: false,
            enableSorting: false,
            enableGlobalFilter: false,
        },
        {
            header: "Actions",
            id: "actions",
            cell: ({ row }) => {
                return <span>
                    <a href={document.configuration.createTaskViewUrl(row.original.id)}>Create task</a> | <a
                    href={document.configuration.copyRouteViewUrl(row.original.id)}>Copy</a> | <a
                    href={document.configuration.permissionListViewUrl(row.original.id)}>Permissions</a> | <a
                    href={document.configuration.deleteRouteViewUrl(row.original.id)}>Delete</a>
                </span>
            },
            enableSorting: false,
            enableColumnFilter: false,
            enableGlobalFilter: false,
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
                    sorting: [
                        {
                            id: "name",
                            desc: false
                        }
                    ]
                }}

                         rowEvents={rowEvents}/></div>
            :
            <Loading/>
    )
}