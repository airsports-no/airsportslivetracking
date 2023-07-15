import {Link} from "react-router-dom";
import React from "react";
import {Form} from "react-bootstrap";
import {ASTable} from "../filteredSearchableTable";
import {useEffect, useMemo, useState} from "react";
import {Loading} from "../basicComponents";
import {DateTime} from "luxon";

export const EventTable = (props) => {
    const columns = useMemo(() => [
        {
            Header: "Contest",
            accessor: "name",
            Cell: cellInfo => <a onClick={() => props.handleContestClick(cellInfo.row.original)}>{cellInfo.value}</a>
        },
        {
            Header: "Registration",
            disableFilters: true,
            accessor: (row, index) => {
            },
            Cell: cellInfo => <Link to={"/participation/" + cellInfo.row.original.id + "/register/"}>
                <button className={"btn btn-info"}>Manage</button>
            </Link>
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
            accessor: "navigationtask_set",
            disableFilters: true,
            Cell: cellInfo => cellInfo.value.map((task, i) => [
                    i > 0 && ", ",
                    <a href={task.tracking_link}>{task.name}</a>
                ]
            )
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
        //     props.handleContestClick(row)
        // }
        // onClick: (row) => {
        //     window.location.href = "/display/contest/" + row.id + "/"
        // }
    }
    return (
        <div>
            <ASTable columns={columns}
                     data={props.contests}
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
