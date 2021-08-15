import React, {Component} from "react";
import {connect} from "react-redux";
import RouteEditor from "./routeEditor";

class ConnectedRouteEditorOuter extends Component {
    render() {
        return <div>
            <div id="routeEditor"/>
            <RouteEditor/>
        </div>
    }
}

const mapStateToProps = (state, props) => (
{
}
)
const mapDispatchToProps =
{
}

const RouteEditorContainer = connect(mapStateToProps, mapDispatchToProps)(ConnectedRouteEditorOuter);
export default RouteEditorContainer;