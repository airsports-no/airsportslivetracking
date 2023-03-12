import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../../config/Switch";
import RouteEditorContainer from "./routeEditorContainer";

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
