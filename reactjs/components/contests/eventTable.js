import React from "react";
import {Form} from "react-bootstrap";
import {ASTable} from "../filteredSearchableTable";
import {useEffect, useMemo, useState} from "react";
import {Loading} from "../basicComponents";
import {DateTime} from "luxon";

export const EventTable = (contests) => {
    const columns = useMemo(() => [
        {
            Header: "Contest",
            accessor: "name",
            Cell: cellInfo => <a href={"/display/contest/" + cellInfo.row.original.id + "/"}>{cellInfo.value}</a>
        },
        {
            Header: "Sharing",
            accessor: "share_string",
            disableFilters: true,
            disableSortBy: true,
        },
        {
            Header: "Start",
            accessor: (row, index) => {
                return DateTime.fromISO(row.start_time).toISODate()
            },
            disableFilters: true,
            style: {width: "100px"}
        },
        {
            Header: "Finish",
            accessor: (row, index) => {
                return DateTime.fromISO(row.finish_time).toISODate()
            },
            disableFilters: true,
            style: {width: "100px"}
        },
        {
            Header: "Tasks",
            accessor: "number_of_tasks",
            disableFilters: true,
            style: {width: "80px"}
        },
        // {
        //     Header: "Editors",
        //     accessor: (row, index) => {
        //         return <ul>
        //             {
        //                 row.editors.map((editor) =>
        //                     <li key={editor.email}>{editor.first_name} {editor.last_name}</li>)
        //             }
        //         </ul>
        //     },
        //     disableFilters: true,
        //     disableSortBy: true,
        // }

    ], [])

    const rowEvents = {
        // onClick: (row) => {
        //     window.location.href = "/display/contest/" + row.id + "/"
        // }
    }
    return (
        <div>
            <ASTable columns={columns}
                     data={contests.contests}
                     className={"table table-striped table-hover"} initialState={{
                sortBy: [
                    {
                        id: "Start",
                        desc: true
                    }
                ]
            }}

                     rowEvents={rowEvents}/>
        </div>
    )
}
