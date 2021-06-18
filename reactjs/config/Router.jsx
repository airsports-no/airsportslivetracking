import React from "react";
import {Route, withRouter} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";
import ParticipationRouter from "../components/contests/ParticipationRouter";
import GlobalMapRouter from "../components/GlobalMapRouter";


export default () => (
    <Switch>
        <Route exact path='/' component={GlobalMapRouter}/>
        <Route path='/global/' component={GlobalMapRouter}/>
        <Route path='/resultsservice/' component={ResultsServiceRouter}/>
        <Route path='/participation/' component={ParticipationRouter}/>
    </Switch>
)
