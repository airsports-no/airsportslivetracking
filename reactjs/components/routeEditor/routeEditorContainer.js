import React, {Component} from "react";
import {connect} from "react-redux";
import RouteEditor from "./routeEditor";
import {withParams} from "../../utilities";

class ConnectedRouteEditorOuter extends Component {
    render() {
        return <div>
            <div id="routeEditor"/>
            <RouteEditor routeId={this.props.params.routeId} routeType={this.props.routeType}/>
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
export default withParams(RouteEditorContainer);