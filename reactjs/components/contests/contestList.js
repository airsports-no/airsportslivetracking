import React from "react";
import {Form} from "react-bootstrap";
import {ASTable} from "../filteredSearchableTable";
import {useEffect, useMemo, useState} from "react";
import {Loading} from "../basicComponents";
import {DateTime} from "luxon";

export const ContestList = () => {
    const [data, setData] = useState({contests:[],nextContestsUrl:null})
    const [showAll, setShowAll] = useState()
    const dataFetch = async () => {
        if (!data.nextContestsUrl&&data.contests.length>0){
            // If there is no next hurl but we have data, we have fetched everything
            return
        }
        const results = await (
            await fetch(data.nextContestsUrl||document.configuration.CONTEST_FRONT_END)
        ).json()
        setData({contests:data.contests.concat(results.results),nextContestsUrl:results.next})
        // if (data.contests.length<300){
        //     dataFetch()
        // }
    }
    useEffect(() => {
        setShowAll(false)
        
        dataFetch()
    }, [data])

    const columns = useMemo(() => [
        {
            Header: "Contest",
            accessor: "name",
            Cell: cellInfo=><a href={document.configuration.contestDetailsViewUrl(cellInfo.row.original.id)}>{cellInfo.value}</a>,
            disableSortBy: true,
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
        {
            Header: "Editors",
            accessor: (row, index) => {
                return <ul>
                    {
                        row.editors.map((editor) =>
                            <li key={editor.email}>{editor.first_name} {editor.last_name}</li>)
                    }
                </ul>
            },
            disableFilters: true,
            disableSortBy: true,
        }

    ], [])

    const rowEvents = {
        // onClick: (row) => {
        //     window.location.href = "/display/contest/" + row.id + "/"
        // }
    }

    return (
        data ? <div>{document.configuration.is_superuser ?
                <Form.Check type={"checkbox"} onChange={(e) => {
                    setShowAll(e.target.checked)
                }} label={"Show all"}/> : null}
                {data.nextContestsUrl?<a href="#" onClick={dataFetch}>Fetch more</a>:null}
                <ASTable columns={columns}
                         data={data.contests.filter((item) => showAll || item.is_editor)}
                         className={"table table-striped table-hover"} initialState={{
                    sortBy: [
                        {
                            id: "Start",
                            desc: true
                        }
                    ]
                }}

                         rowEvents={rowEvents}/></div>
            :
            <Loading/>
    )
}