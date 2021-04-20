import React from "react";
import {render} from "react-dom";
import {BrowserRouter, Route, Redirect, withRouter} from 'react-router-dom'
import store from '../store/index'
import {Provider} from 'react-redux';
import Router from "../config/Router";


const Root = () => (
    <Provider store={store}>
        <BrowserRouter>
            <main>
                <Route path="/:url*" exact strict render={({location}) => <Redirect to={`${location.pathname}/`}/>}
                    // Redirect to trailing slash to avoid URL problems in children
                />
                <Route path="*" component={withRouter(Router)}/>
            </main>
        </BrowserRouter>
    </Provider>
);

render(<Root/>, document.getElementById('react-root'));
