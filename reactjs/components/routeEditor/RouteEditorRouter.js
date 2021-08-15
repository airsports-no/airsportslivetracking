import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../Switch";
import RouteEditorContainer from "./routeEditorContainer";


export default ({match: {path}}) => (
    <Switch>
        <Route exact path={path} component={RouteEditorContainer}/>
    </Switch>
)
