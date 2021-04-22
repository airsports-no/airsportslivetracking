import React from "react";
import {Route} from 'react-router-dom'
import Switch from "../components/Switch";
import ResultsServiceRouter from "../components/resultsService/ResultsServiceRouter";
import ContestRegistrationForm from "../components/contestRegistrationForm";
import UpcomingContestsSignupTable from "../components/upcomingContestsSignupTable";
import MyContestParticipationManagement from "../components/contests/myContestParticipationManagement";
import TaskSummaryResultsTable from "../components/resultsService/TaskSummaryResultsTable";


export default () => (
    <Switch>
        <Route path='/web/resultsservice/' component={ResultsServiceRouter}/>
        <Route path='/web/participation/:id/register/'
               render={props => <MyContestParticipationManagement {...props}
                                                                  externalContestId={parseInt(props.match.params.id)}/>}/>
        <Route path='/web/participation/' component={MyContestParticipationManagement}/>
    </Switch>
)
