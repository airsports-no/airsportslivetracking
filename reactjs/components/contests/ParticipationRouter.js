import React from "react";
import {Route} from 'react-router-dom'
import MyContestParticipationManagement from "./myContestParticipationManagement";
import Switch from "../../config/Switch";


export default ({match: {path}}) => (
    <Switch>
        <Route exact path={path} component={MyContestParticipationManagement}/>
        <Route path={`${path}:id/register/`}
               render={props => <MyContestParticipationManagement {...props}
                                                                  registerContestId={parseInt(props.match.params.id)}/>}/>
        <Route path={`${path}myparticipation/:participation/`} exact
               render={props => <MyContestParticipationManagement {...props}
                                                                  currentParticipationId={parseInt(props.match.params.participation)}/>}/>
        <Route path={`${path}myparticipation/:participation/signup/:navigationtask/`}
               render={props => <MyContestParticipationManagement {...props}
                                                                  currentParticipationId={parseInt(props.match.params.participation)}
                                                                  navigationTaskId={parseInt(props.match.params.navigationtask)}/>}/>

    </Switch>
)
