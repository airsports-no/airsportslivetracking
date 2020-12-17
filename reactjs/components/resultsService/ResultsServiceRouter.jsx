import Switch from "../Switch";
import {Route} from "react-router-dom";
import React from "react";
import TaskSummaryResultsTable from "./TaskSummaryResultsTable";
import ContestSummaryResultsTable from "./ContestSummaryResultsTable";

export default ({match: {path}}) => (
    <Switch>
        <Route exact path={path} component={ContestSummaryResultsTable}/>
        <Route path={`${path}:id/taskresults/`}
               render={props => <TaskSummaryResultsTable {...props} contestId={parseInt(props.match.params.id)}/>}/>
    </Switch>
)
