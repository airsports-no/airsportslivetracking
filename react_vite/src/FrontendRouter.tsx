import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Loading } from "./features/route-editor/components/basicComponents";

const EditableRouteList = lazy(() => import("./features/route-editor/containers/EditableRouteList").then(module => ({ default: module.EditableRouteList })));
const RouteEditor = lazy(() => import("./features/route-editor/containers/RouteEditor"));
const ScheduleFlightContainer = lazy(() => import("./features/schedule-flight/ScheduleFlightContainer"));
const PastFlightsPage = lazy(() => import("./features/schedule-flight/PastFlightsPage"));

export const FrontendRouter = () => {
    return (
        <BrowserRouter basename="/frontend/">
            <Suspense fallback={<Loading />}>
                <Routes>
                    <Route path="routeeditor/" element={<EditableRouteList />} />
                    <Route path="routeeditor/edit/:routeId" element={<RouteEditor />} />
                    <Route path="routeeditor/create" element={<RouteEditor />} />
                    <Route path="/schedule" element={<ScheduleFlightContainer />} />
                    <Route path="/past-flights" element={<PastFlightsPage />} />
                    <Route path="*" element={
                        <div className="hero min-h-screen bg-base-200">
                            <div className="hero-content text-center">
                                <div className="max-w-md">
                                    <h1 className="text-5xl font-bold">404</h1>
                                    <p className="py-6">Page Not Found</p>
                                    <Link to="/" className="btn btn-primary">Go Home</Link>
                                </div>
                            </div>
                        </div>
                    } />
                </Routes>
            </Suspense>
        </BrowserRouter>
    );
};
