import React  from "react";
import {Switch, Route} from 'react-router-dom'

/**
 * Extends react-router-dom's Switch component with a 404 page
 */
export default ({children, ...props}) => (
    <Switch {...props}>
        {children}
        <Route render={() => <h1>404 - Not found</h1>} />
    </Switch>
)