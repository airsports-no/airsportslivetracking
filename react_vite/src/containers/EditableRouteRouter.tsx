import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Loading } from "../components/basicComponents";

const EditableRouteList = lazy(() => import("./EditableRouteList").then(module => ({ default: module.EditableRouteList })));
const RouteEditor = lazy(() => import("./RouteEditor"));

export const EditableRouteRouter = () => {
    return (
        <BrowserRouter basename="/display/editableroutereact/">
            <Suspense fallback={<Loading />}>
                <Routes>
                    <Route path="/" element={<EditableRouteList />} />
                    <Route path="/edit/:routeId" element={<RouteEditor />} />
                    <Route path="/create" element={<RouteEditor />} />
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
