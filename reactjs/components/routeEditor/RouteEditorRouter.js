import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../Switch";
import RouteEditorContainer from "./routeEditorContainer";
import TaskSummaryResultsTable from "../resultsService/TaskSummaryResultsTable";


export default ({match: {path}}) => (
    <Switch>
        <Route exact path={path} render={(props) => {
            return <RouteEditorContainer {...props} routeType={"precision"}/>
        }}/>
        <Route path={`${path}:id/`} render={(props) => {
            return <RouteEditorContainer {...props} routeId={parseInt(props.match.params.id)}
                                         routeType={"precision"}/>
        }}/>
    </Switch>
)
