import React from "react";
import {Route} from 'react-router-dom'
import Switch from "./Switch";
import TrackingContainer from "../components/navigationTasks/trackingContainer";


export default () => (
    <Switch>
        <Route path='/' component={TrackingContainer}/>
    </Switch>
)
