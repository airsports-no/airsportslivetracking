import {Link, withRouter} from "react-router-dom";
import React, {Component} from "react";
import {connect} from "react-redux";
import RouteEditor from "./routeEditor";

class ConnectedRouteEditorOuter extends Component {
    render() {
        return <div>
            <div id="routeEditor"/>
            <RouteEditor routeId={this.props.routeId}/>
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

const RouteEditorContainer = connect(mapStateToProps, mapDispatchToProps)(withRouter(ConnectedRouteEditorOuter));
export default RouteEditorContainer;