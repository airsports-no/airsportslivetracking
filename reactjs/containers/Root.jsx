import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {render} from "react-dom";
import {Provider} from "react-redux";
import store from "../store/index";
import TrackingContainer from "../components/trackingContainer";
import * as Sentry from "@sentry/react";
import {Integrations} from "@sentry/tracing";

Sentry.init({
dsn: "https://fa1ab83945514f328a490f2cf96deb98@o568590.ingest.sentry.io/5713800",    integrations: [new Integrations.BrowserTracing()],

    // Set tracesSampleRate to 1.0 to capture 100%
    // of transactions for performance monitoring.
    // We recommend adjusting this value in production
    tracesSampleRate: 1.0,
});
render(
    <Provider store={store}>
        <TrackingContainer/>
    </Provider>,
    document.getElementById("root")
);