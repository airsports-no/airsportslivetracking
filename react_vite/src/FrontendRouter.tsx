import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Loading } from "./features/route-editor/components/basicComponents";
import routes from "./routes.json";

const EditableRouteList = lazy(() => import("./features/route-editor/containers/EditableRouteList").then(module => ({ default: module.EditableRouteList })));
const RouteEditor = lazy(() => import("./features/route-editor/containers/RouteEditor"));
const MissionDashboard = lazy(() => import("./features/mission-dashboard/MissionDashboard"));
const ContestDashboard = lazy(() => import("./features/mission-dashboard/ContestDashboard"));
const CompetitionMapPage = lazy(() => import("./features/competition-map/CompetitionMapPage"));
const ScorecardEditorPage = lazy(() => import("./features/scorecard-editor/ScorecardEditorPage"));
const ContestResultsTable = lazy(() => import("./features/contest-results/ContestResultsTable").then(module => ({ default: module.ContestResultsTable })));
const ContestantScheduling = lazy(() => import("./features/scheduling/ContestantScheduling"));
const ContestantDeclarationPage = lazy(() => import("./features/scheduling/ContestantDeclarationPage"));
const PhotoManagementPage = lazy(() => import("./features/competition-map/PhotoManagementPage"));
const ScheduleFlightPage = lazy(() => import("./features/mission-dashboard/ScheduleFlightPage"));
const UpgradeOrganizer = lazy(() => import("./features/mission-dashboard/UpgradeOrganizer"));
const UpgradeSuccess = lazy(() => import("./features/mission-dashboard/UpgradeSuccess"));

export const FrontendRouter = () => {
    return (
        <BrowserRouter basename="/">
            <Suspense fallback={<Loading />}>
                <Routes>
                    <Route path={routes.ROUTE_EDITOR_LIST} element={<EditableRouteList />} />
                    <Route path={routes.ROUTE_EDITOR_EDIT} element={<RouteEditor />} />
                    <Route path={routes.ROUTE_EDITOR_CREATE} element={<RouteEditor />} />
                    <Route path={routes.MISSION_DASHBOARD_PHOTOS} element={<PhotoManagementPage />} />
                    <Route path={routes.MISSION_DASHBOARD_DETAIL} element={<ContestDashboard />} />
                    <Route path={routes.MISSION_DASHBOARD} element={<MissionDashboard />} />
                    <Route path={routes.COMPETITION_MAP} element={<CompetitionMapPage />} />
                    <Route path={routes.COMPETITION_MAP_DETAIL} element={<CompetitionMapPage />} />
                    <Route path={routes.SCORECARD_EDITOR} element={<ScorecardEditorPage />} />

                    <Route path={routes.CONTEST_RESULTS_TABLE} element={<ContestResultsTable />} />
                    <Route path={routes.SCHEDULE_FLIGHT} element={<ScheduleFlightPage />} />
                    <Route path={routes.CONTESTANT_SCHEDULING} element={<ContestantScheduling />} />
                    <Route path={routes.CONTESTANT_DECLARATION} element={<ContestantDeclarationPage />} />
                    <Route path={routes.UPGRADE_ORGANIZER} element={<UpgradeOrganizer />} />
                    <Route path={routes.UPGRADE_SUCCESS} element={<UpgradeSuccess />} />
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