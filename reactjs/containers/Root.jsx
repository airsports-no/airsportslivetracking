import 'react-app-polyfill/ie9';
import 'react-app-polyfill/stable'
import React from "react";
import {render} from "react-dom";
import {Provider} from "react-redux";
import store from "../store/index";
import {BrowserRouter, Redirect, Route, withRouter} from "react-router-dom";
import Router from "../config/NavigationTaskRouter";
// import * as Sentry from "@sentry/react";

// Sentry.init({
// dsn: "https://fa1ab83945514f328a490f2cf96deb98@o568590.ingest.sentry.io/5713800",    integrations: [new Integrations.BrowserTracing()],
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