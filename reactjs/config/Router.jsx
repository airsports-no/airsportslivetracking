import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";


export default () => (
    <Switch>
        <Route path='/resultsservice/' component={ResultsServiceRouter}/>
    </Switch>
)
