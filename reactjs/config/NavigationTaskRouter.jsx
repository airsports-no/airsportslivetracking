import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../components/Switch";
import TrackingContainer from "../components/trackingContainer";


export default () => (
    <Switch>
        <Route path='/' component={TrackingContainer}/>
    </Switch>
)
