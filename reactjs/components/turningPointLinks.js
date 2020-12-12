import React, {Component} from "react";
import {setDisplay} from "../actions";
import {TURNING_POINT_DISPLAY} from "../constants/display-types";
import {connect} from "react-redux";

const mapDispatchToProps = (dispatch, props) => ({
    displayTurningPointsStandings: turningPoint => dispatch(setDisplay({
        displayType: TURNING_POINT_DISPLAY,
        turningPoint: turningPoint
    }))
})

const mapStateToProps = (state, props) => ({
    turningPoints: state.navigationTask.route.waypoints.map((a) => {
        return a.name
    })
})

class ConnectedTurningPointLinks extends Component {
    constructor(props) {
        super(props);
        this.handleClick = this.handleClick.bind(this);
    }

    handleClick(turningPoint) {
        this.props.displayTurningPointsStandings(turningPoint)
    }

    render() {
        return <ul className={"commaList"}>
            {this.props.turningPoints.map((turningPoint) => {
                return <li key={"tplist" + turningPoint}><a href={"#"} onClick={() => {
                    this.handleClick(turningPoint)
                }} >{turningPoint}</a></li>
            })}
        </ul>
    }
}

const TurningPointLinks = connect(mapStateToProps, mapDispatchToProps)(ConnectedTurningPointLinks)

export default TurningPointLinks