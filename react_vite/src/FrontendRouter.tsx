import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Loading } from "./features/route-editor/components/basicComponents";
import routes from "./routes.json";

const EditableRouteList = lazy(() => import("./features/route-editor/containers/EditableRouteList").then(module => ({ default: module.EditableRouteList })));
const RouteEditor = lazy(() => import("./features/route-editor/containers/RouteEditor"));
const ScheduleFlightContainer = lazy(() => import("./features/schedule-flight/ScheduleFlightContainer"));
const PastFlightsPage = lazy(() => import("./features/schedule-flight/PastFlightsPage"));
const MissionDashboard = lazy(() => import("./features/mission-dashboard/MissionDashboard"));
const ContestDashboard = lazy(() => import("./features/mission-dashboard/ContestDashboard"));
const CompetitionMapPage = lazy(() => import("./features/competition-map/CompetitionMapPage"));

export const FrontendRouter = () => {
    return (
        <BrowserRouter basename="/frontend/">
            <Suspense fallback={<Loading />}>
                <Routes>
                    <Route path={routes.ROUTE_EDITOR_LIST} element={<EditableRouteList />} />
                    <Route path={routes.ROUTE_EDITOR_EDIT} element={<RouteEditor />} />
                    <Route path={routes.ROUTE_EDITOR_CREATE} element={<RouteEditor />} />
                    {/* Deep link for scheduling a flight: /schedule-flight?contestId=<CONTEST_ID>&navigationTaskId=<TASK_ID> */}
                    {/* Deep link for registering for a contest: /schedule-flight?registerContestId=<CONTEST_ID> */}
                    <Route path={routes.SCHEDULE_FLIGHT} element={<ScheduleFlightContainer />} />
                    <Route path={routes.PAST_FLIGHTS} element={<PastFlightsPage />} />
                    <Route path={routes.MISSION_DASHBOARD} element={<MissionDashboard />} />
                    <Route path={routes.MISSION_DASHBOARD_DETAIL} element={<ContestDashboard />} />
                    <Route path={routes.COMPETITION_MAP} element={<CompetitionMapPage />} />
                    <Route path={routes.COMPETITION_MAP_DETAIL} element={<CompetitionMapPage />} />
                    <Route path={routes.NOT_FOUND} element={
                        <div className="hero min-h-screen bg-base-200">
                            <div className="hero-content text-center">
                                <div className="max-w-md">
                                    <h1 className="text-5xl font-bold">404</h1>
                                    <p className="py-6">Page Not Found</p>
                                    <Link to={routes.HOME} className="btn btn-primary">Go Home</Link>
                                </div>
                            </div>
                        </div>
                    } />
                </Routes>
            </Suspense>
        </BrowserRouter>
    );
};