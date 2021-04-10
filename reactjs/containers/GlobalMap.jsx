import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {render} from "react-dom";
import {Provider} from "react-redux";
import store from "../store/index";
import GlobalMapContainer from "../components/globalMapContainer";
import * as Sentry from "@sentry/react";
import {Integrations} from "@sentry/tracing";

Sentry.init({
    dsn: "https://dcf2a341a7b24d069425729a0c2aed9f@o568590.ingest.sentry.io/5713802",
    integrations: [new Integrations.BrowserTracing()],

    // Set tracesSampleRate to 1.0 to capture 100%
    // of transactions for performance monitoring.
    // We recommend adjusting this value in production
    tracesSampleRate: 1.0,
});
render(
    <Provider store={store}>
        <GlobalMapContainer/>
    </Provider>,
    document.getElementById("root")
);