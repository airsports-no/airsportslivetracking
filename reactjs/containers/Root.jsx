import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {render} from "react-dom";
import {Provider} from "react-redux";
import store from "../store/index";
import TrackingContainer from "../components/trackingContainer";

render(
    <Provider store={store}>
        <TrackingContainer/>
    </Provider>,
    document.getElementById("root")
);