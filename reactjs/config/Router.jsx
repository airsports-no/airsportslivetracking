import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";
import ContestRegistrationForm from "../components/contestRegistrationForm";
import UpcomingContestsSignupTable from "../components/upcomingContestsSignupTable";
import MyContestParticipationManagement from "../components/contests/myContestParticipationManagement";


export default () => (
    <Switch>
        <Route path='/web/resultsservice/' component={ResultsServiceRouter}/>
        <Route path='/web/participation/' component={MyContestParticipationManagement}/>
    </Switch>
)
