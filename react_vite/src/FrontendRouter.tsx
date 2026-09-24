import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { Loading } from "./features/route-editor/components/basicComponents";
import RouteErrorBoundary from "./components/common/RouteErrorBoundary";
import routes from "./routes.json";

const EditableRouteList = lazy(() => import("./features/route-editor/containers/EditableRouteList").then(module => ({ default: module.EditableRouteList })));
const RouteEditor = lazy(() => import("./features/route-editor/containers/RouteEditor"));
const MissionDashboard = lazy(() => import("./features/mission-dashboard/MissionDashboard"));
const ContestDashboard = lazy(() => import("./features/mission-dashboard/ContestDashboard"));
const NavigationTaskDetailPage = lazy(() => import("./features/navigation-task-detail/NavigationTaskDetailPage"));
const CompetitionMapPage = lazy(() => import("./features/competition-map/CompetitionMapPage"));
const ScorecardEditorPage = lazy(() => import("./features/scorecard-editor/ScorecardEditorPage"));
const ContestResultsTable = lazy(() => import("./features/contest-results/ContestResultsTable").then(module => ({ default: module.ContestResultsTable })));
const ContestantScheduling = lazy(() => import("./features/scheduling/ContestantScheduling"));
const ContestantDeclarationPage = lazy(() => import("./features/scheduling/ContestantDeclarationPage"));
const PhotoManagementPage = lazy(() => import("./features/competition-map/PhotoManagementPage"));
const ScheduleFlightPage = lazy(() => import("./features/mission-dashboard/ScheduleFlightPage"));
const UpgradeOrganizer = lazy(() => import("./features/mission-dashboard/UpgradeOrganizer"));
const UpgradeSuccess = lazy(() => import("./features/mission-dashboard/UpgradeSuccess"));
const AdminFlightActivityPage = lazy(() => import("./features/admin-dashboard/AdminFlightActivityPage"));

const AppRoutes = () => {
    // Keying each boundary by pathname forces a remount (clearing any prior error state) when
    // navigating to a different page - including a different param on the same route, e.g.
    // moving from a broken /mission-dashboard/1004 to a working /mission-dashboard/1005 -
    // instead of getting stuck showing a stale fallback for the rest of the session.
    const location = useLocation();
    const wrap = (element: React.ReactNode) => (
        <RouteErrorBoundary key={location.pathname}>{element}</RouteErrorBoundary>
    );

    return (
        <Routes>
            <Route path={routes.ROUTE_EDITOR_LIST} element={wrap(<EditableRouteList />)} />
            <Route path={routes.ROUTE_EDITOR_EDIT} element={wrap(<RouteEditor />)} />
            <Route path={routes.ROUTE_EDITOR_CREATE} element={wrap(<RouteEditor />)} />
            <Route path={routes.MISSION_DASHBOARD_PHOTOS} element={wrap(<PhotoManagementPage />)} />
            <Route path={routes.MISSION_DASHBOARD_DETAIL} element={wrap(<ContestDashboard />)} />
            <Route path={routes.NAVIGATION_TASK_DETAIL} element={wrap(<NavigationTaskDetailPage />)} />
            <Route path={routes.MISSION_DASHBOARD} element={wrap(<MissionDashboard />)} />
            <Route path={routes.COMPETITION_MAP} element={wrap(<CompetitionMapPage />)} />
            <Route path={routes.COMPETITION_MAP_DETAIL} element={wrap(<CompetitionMapPage />)} />
            <Route path={routes.SCORECARD_EDITOR} element={wrap(<ScorecardEditorPage />)} />

            <Route path={routes.CONTEST_RESULTS_TABLE} element={wrap(<ContestResultsTable />)} />
            <Route path={routes.SCHEDULE_FLIGHT} element={wrap(<ScheduleFlightPage />)} />
            <Route path={routes.CONTESTANT_SCHEDULING} element={wrap(<ContestantScheduling />)} />
            <Route path={routes.CONTESTANT_DECLARATION} element={wrap(<ContestantDeclarationPage />)} />
            <Route path={routes.UPGRADE_ORGANIZER} element={wrap(<UpgradeOrganizer />)} />
            <Route path={routes.UPGRADE_SUCCESS} element={wrap(<UpgradeSuccess />)} />
            <Route path={routes.ADMIN_FLIGHT_ACTIVITY} element={wrap(<AdminFlightActivityPage />)} />
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
    );
};

export const FrontendRouter = () => {
    return (
        <BrowserRouter basename="/">
            <Suspense fallback={<Loading />}>
                <AppRoutes />
            </Suspense>
        </BrowserRouter>
    );
};