import React from "react";
import {Route, withRouter} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";
import MyContestParticipationManagement from "../components/contests/myContestParticipationManagement";
import GlobalMapContainer from "../components/globalMapContainer";
import ParticipationRouter from "../components/contests/ParticipationRouter";


export default () => (
    <Switch>
        <Route exact path='/' component={GlobalMapContainer}/>
        <Route path='/resultsservice/' component={ResultsServiceRouter}/>
        <Route path='/participation/' component={ParticipationRouter}/>
    </Switch>
)
