import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";
import ParticipationRouter from "../components/contests/ParticipationRouter";
import RouteEditorRouter from "../components/routeEditor/RouteEditorRouter";
import GlobalMapRouter from "../components/GlobalMapRouter";


export default () => (
    <Switch>
        <Route exact path='/' component={GlobalMapRouter}/>
        <Route path='/global/' component={GlobalMapRouter}/>
        <Route path='/resultsservice/' component={ResultsServiceRouter}/>
        <Route path='/participation/' component={ParticipationRouter}/>
        <Route path='/routeeditor/' component={RouteEditorRouter}/>
    </Switch>
)
