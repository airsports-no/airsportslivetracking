import React from "react";
import {Route, withRouter} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";
import MyContestParticipationManagement from "../components/contests/myContestParticipationManagement";
import GlobalMapContainer from "../components/globalMapContainer";


export default () => (
    <Switch>
        <Route exact path='/' component={GlobalMapContainer}/>
        <Route path='/resultsservice/' component={ResultsServiceRouter}/>
        <Route path='/participation/:id/register/'
               render={props => <MyContestParticipationManagement {...props}
                                                                  externalContestId={parseInt(props.match.params.id)}/>}/>
        <Route path='/participation/' component={MyContestParticipationManagement}/>
    </Switch>
)
