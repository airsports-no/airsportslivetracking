import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from "react-router-dom";
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
                    <Route path="*" element={<div>404 Not Found</div>} />
                </Routes>
            </Suspense>
        </BrowserRouter>
    );
};
