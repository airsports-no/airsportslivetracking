import React from "react";
import {Route} from 'react-router-dom'
import GlobalMapContainer from "./globalMapContainer";
import Switch from "../../config/Switch";


export default ({match: {path}}) => (
    <Switch>
        <Route exact path={path} component={GlobalMapContainer}/>
        <Route path={`${path}contest_details/:id/`}
               render={props => <GlobalMapContainer {...props} contestDetailsId={parseInt(props.match.params.id)}/>}/>
    </Switch>
)
