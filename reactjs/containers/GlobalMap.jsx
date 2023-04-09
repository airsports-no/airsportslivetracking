import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {Provider} from "react-redux";
import store from "../store/index";
import {BrowserRouter, Route, Routes} from "react-router-dom";
import {createRoot} from "react-dom/client";
import GlobalMapContainer from "../components/globalMap/globalMapContainer";
import ContestSummaryResultsTable from "../components/resultsService/ContestSummaryResultsTable";
import TaskSummaryResultsTable from "../components/resultsService/TaskSummaryResultsTable";
import MyContestParticipationManagement from "../components/contests/myContestParticipationManagement";
import RouteEditorContainer from "../components/routeEditor/routeEditorContainer";
import NotFound from "../components/notFound";

const root = createRoot(document.getElementById("root"))
root.render(
    <Provider store={store}>
        <BrowserRouter>
            <Routes>
                {/*<Route path="/:url*" exact strict render={({location}) => <Redirect to={`${location.pathname}/`}/>}*/}
                {/*    // Redirect to trailing slash to avoid URL problems in children*/}
                {/*/>*/}
                <Route index element={<GlobalMapContainer/>}/>
                <Route path='global'>
                    <Route index element={<GlobalMapContainer/>}/>
                    <Route path="contest_details/:contestDetailsId" element={<GlobalMapContainer/>}/>
                </Route>
                <Route path='resultsservice'>
                    <Route index element={<ContestSummaryResultsTable/>}/>
                    <Route path=":contestId/taskresults/:task/" element={<TaskSummaryResultsTable/>}/>
                    <Route path=":contestId/taskresults/" element={<TaskSummaryResultsTable/>}/>
                </Route>
                <Route path='/participation/'>
                    <Route index element={<MyContestParticipationManagement/>}/>
                    <Route path=":registerContestId/register/" element={<MyContestParticipationManagement/>}/>
                    <Route path="myparticipation/:currentParticipationId/"
                           element={<MyContestParticipationManagement/>}/>
                    <Route path="myparticipation/:currentParticipationId/signup/:navigationTaskId/"
                           element={<MyContestParticipationManagement/>}/>
                </Route>
                <Route path='/routeeditor/'>
                    <Route index element={<RouteEditorContainer routeType={"precision"}/>}/>
                    <Route path=":routeId/" element={<RouteEditorContainer routeType={"precision"}/>}/>
                </Route>
                <Route path='*' element={<NotFound />}/>
            </Routes>
        </BrowserRouter>
    </Provider>,
);