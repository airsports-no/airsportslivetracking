import {Link} from "react-router-dom";
import React from "react";
import {Form} from "react-bootstrap";
import {ASTable, SelectColumnFilter} from "../filteredSearchableTable";
import {useEffect, useMemo, useState} from "react";
import {Loading} from "../basicComponents";
import {DateTime} from "luxon";

export const EventTable = (props) => {
    const columns = useMemo(() => [
        {
            Header: "Ctry",
            accessor: "country",
            Cell: cellInfo => <img src={cellInfo.row.original.country_flag_url} style={{height: "15px"}}
                                   alt={cellInfo.value}/>,
            Filter: SelectColumnFilter,
            style: {width: "30px"},
            disableSortBy: true,

        },
        {
            Header: "Contest",
            // accessor: "name",
            accessor: (row, index) => {
                return row.name + " (" + DateTime.fromISO(row.start_time).toISODate() + ")"
            },
            disableSortBy: true,
            Cell: cellInfo => <a href={"#"} onClick={() => props.handleContestClick(cellInfo.row.original)}><img
                className={"img-fluid"}
                src={cellInfo.row.original.logo && cellInfo.row.original.logo.length > 0 ? cellInfo.row.original.logo : document.configuration.STATIC_FILE_LOCATION+"img/airsportslogo.png"}
                alt={"Event logo"}
                style={{width: "100%", maxHeight: "40px", maxWidth: "40px", float: "left"}}/>{cellInfo.value}</a>,
        },
        // {
        //     Header: "Registration",
        //     disableFilters: true,
        //     accessor: (row, index) => {
        //     },
        //     Cell: cellInfo => <Link to={"/participation/" + cellInfo.row.original.id + "/register/"}>
        //         <button className={"btn btn-info"}>{cellInfo.row.original.registered?"Manage":"Register"}</button>
        //     </Link>
        // },
        {
            Header: "Start",
            id: "Start",
            accessor: "start_time",
            // (row, index) => {
            //     return DateTime.fromISO(row.start_time).toISODate()
            // },
            // disableSortBy: true,
            disableFilters: true,
            hidden:true
        },
        // {
        //     Header: "Finish",
        //     accessor: (row, index) => {
        //         return DateTime.fromISO(row.finish_time).toISODate()
        //     },
        //     disableFilters: true,
        //     style: {width: "100px"}
        // },
        {
            Header: "Tasks",
            accessor: "navigationtask_set",
            disableFilters: true,
            Cell: cellInfo => cellInfo.value.map((task, i) => [
                    i > 0 && ", ",
                    <a key={task.id + "_" + i} href={task.tracking_link}>{task.name}</a>
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
                     className={"table table-striped table-hover table-condensed"} initialState={{
                sortBy: [
                    {
                        id: "Start",
                        desc: true
                    }
                ],
                hiddenColumns: ["Start"]
            }}

                     rowEvents={rowEvents}/>
        </div>
    )
}
