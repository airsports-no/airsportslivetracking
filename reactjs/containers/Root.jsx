import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {Provider} from "react-redux";
import store from "../store/index";
import {BrowserRouter, Route, Routes} from "react-router-dom";
import {createRoot} from "react-dom/client";
import TrackingContainer from "../components/navigationTasks/trackingContainer";

const root = createRoot(document.getElementById("root"))

root.render(
    <Provider store={store}>
        <BrowserRouter>
            <Routes>
                {/*<Route path="/:url*" exact strict render={({location}) => <Redirect to={`${location.pathname}/`}/>}*/}
                {/*    // Redirect to trailing slash to avoid URL problems in children*/}
                {/*/>*/}
                <Route path={"*"} element={<TrackingContainer/>}/>
            </Routes>
        </BrowserRouter>
    </Provider>,
);