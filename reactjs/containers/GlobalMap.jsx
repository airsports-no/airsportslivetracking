import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {render} from "react-dom";
import {Provider} from "react-redux";
import store from "../store/index";
// import * as Sentry from "@sentry/react";
import {Integrations} from "@sentry/tracing";
import {BrowserRouter, Redirect, Route, withRouter} from "react-router-dom";
import Router from "../config/Router";

// Sentry.init({
//     dsn: "https://dcf2a341a7b24d069425729a0c2aed9f@o568590.ingest.sentry.io/5713802",
//     integrations: [new Integrations.BrowserTracing()],
//
//     // Set tracesSampleRate to 1.0 to capture 100%
//     // of transactions for performance monitoring.
//     // We recommend adjusting this value in production
//     tracesSampleRate: 1.0,
// });
render(
    <Provider store={store}>
        <BrowserRouter>
            <main>
                <Route path="/:url*" exact strict render={({location}) => <Redirect to={`${location.pathname}/`}/>}
                    // Redirect to trailing slash to avoid URL problems in children
                />
                <Route path="*" component={withRouter(Router)}/>
            </main>
        </BrowserRouter>
    </Provider>,
    document.getElementById("root")
);